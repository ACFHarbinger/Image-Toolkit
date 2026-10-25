import { open, save } from "@tauri-apps/plugin-dialog";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { HieEditorTab } from "./HieEditorTab";

afterEach(() => {
  cleanup();
  vi.mocked(open).mockReset();
  vi.mocked(open).mockImplementation(() => Promise.resolve(null));
  vi.mocked(save).mockReset();
  vi.mocked(save).mockImplementation(() => Promise.resolve(null));
});

function hostClient() {
  return {
    hieOpenDocument: vi.fn().mockResolvedValue({
      success: true,
      document_id: "doc-test-123",
      frame_count: 5,
      width: 1920,
      height: 1080,
      elapsed_seconds: 0.05,
    }),
    hieExecuteEdit: vi.fn().mockResolvedValue({
      success: true,
      document_id: "doc-test-123",
      output_document_id: "doc-test-123-out",
      modified_layers: [],
      elapsed_seconds: 0.02,
    }),
    hieExportDocument: vi.fn().mockResolvedValue({
      success: true,
      output_path: "/chosen/hie-export.png",
      size_bytes: 1234,
      elapsed_seconds: 0.1,
    }),
    hieListCapabilities: vi.fn().mockResolvedValue({
      capabilities: ["brush_assistant", "global_tone"],
      models_available: ["birefnet"],
    }),
  };
}

test("HieEditorTab uses hostClient for document open, edit, and export", async () => {
  const showModal = vi.fn();
  const client = hostClient();
  vi.mocked(open).mockResolvedValueOnce("/chosen/photo.png");
  vi.mocked(save).mockResolvedValueOnce("/chosen/hie-export.png");

  render(<HieEditorTab showModal={showModal} hostClient={client as any} />);

  await waitFor(() => {
    expect(client.hieListCapabilities).toHaveBeenCalled();
  });

  fireEvent.click(screen.getByRole("button", { name: /Open Media/i }));
  await waitFor(() => {
    expect(client.hieOpenDocument).toHaveBeenCalledWith(
      expect.objectContaining({ source: "/chosen/photo.png" })
    );
  });
  expect(client.hieOpenDocument).not.toHaveBeenCalledWith(
    expect.objectContaining({ source: "/sample-editor.png" })
  );
  expect(await screen.findByText(/5 frame/i)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /Preview Assistance/i }));
  await waitFor(() => {
    expect(client.hieExecuteEdit).toHaveBeenCalledWith(
      expect.objectContaining({
        document_id: "doc-test-123",
        operation: "brush-assistant",
      })
    );
  });
  expect(await screen.findByText(/Proposal Ready/i)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /Accept into History/i }));
  await waitFor(() => {
    expect(client.hieExecuteEdit).toHaveBeenCalledWith(
      expect.objectContaining({
        document_id: "doc-test-123",
        operation: "accept",
      })
    );
  });
  expect(client.hieExecuteEdit).not.toHaveBeenCalledWith(
    expect.objectContaining({ operation: "brush-assistant_accept" })
  );

  fireEvent.click(screen.getByRole("button", { name: /Export Document/i }));
  await waitFor(() => {
    expect(client.hieExportDocument).toHaveBeenCalledWith(
      expect.objectContaining({
        document_id: "doc-test-123",
        output_path: "/chosen/hie-export.png",
        format: "png",
        quality: 95,
      })
    );
  });
  expect(client.hieExportDocument).not.toHaveBeenCalledWith(
    expect.objectContaining({ output_path: "/tmp/hie-export.png" })
  );
  expect(await screen.findByText(/Export complete/i)).toBeInTheDocument();
});

test("cancelled Open Media leaves the previous status unchanged", async () => {
  const showModal = vi.fn();
  const client = hostClient();
  vi.mocked(open).mockResolvedValueOnce(null);

  render(<HieEditorTab showModal={showModal} hostClient={client as any} />);
  expect(await screen.findByText(/Ready for media sequence/i)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /Open Media/i }));
  await waitFor(() => {
    expect(vi.mocked(open)).toHaveBeenCalled();
  });
  await waitFor(() => {
    expect(client.hieOpenDocument).not.toHaveBeenCalled();
    expect(screen.getByText(/Ready for media sequence/i)).toBeInTheDocument();
  });
});

test("Open Media uses the first string when the dialog returns a list", async () => {
  const client = hostClient();
  vi.mocked(open).mockResolvedValueOnce(["/from/list.png", "/other.png"] as unknown as string);

  render(<HieEditorTab showModal={vi.fn()} hostClient={client as any} />);
  fireEvent.click(screen.getByRole("button", { name: /Open Media/i }));
  await waitFor(() => {
    expect(client.hieOpenDocument).toHaveBeenCalledWith(
      expect.objectContaining({ source: "/from/list.png" })
    );
  });
});

test("cancelled Export does not call hieExportDocument or change status", async () => {
  const client = hostClient();
  vi.mocked(save).mockResolvedValueOnce(null);

  render(<HieEditorTab showModal={vi.fn()} hostClient={client as any} />);
  expect(await screen.findByText(/Ready for media sequence/i)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /Export Document/i }));
  await waitFor(() => {
    expect(vi.mocked(save)).toHaveBeenCalled();
  });
  await waitFor(() => {
    expect(client.hieExportDocument).not.toHaveBeenCalled();
    expect(screen.getByText(/Ready for media sequence/i)).toBeInTheDocument();
    expect(screen.queryByText(/Export complete/i)).not.toBeInTheDocument();
  });
});
