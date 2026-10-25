import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { HieEditorTab } from "./HieEditorTab";

afterEach(() => {
  cleanup();
});

test("HieEditorTab uses hostClient for document open, edit, and export", async () => {
  const showModal = vi.fn();
  const hostClient = {
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
      modified_layers: ["layer-0"],
      elapsed_seconds: 0.02,
    }),
    hieExportDocument: vi.fn().mockResolvedValue({
      success: true,
      output_path: "/tmp/hie-export.png",
      size_bytes: 1234,
      elapsed_seconds: 0.1,
    }),
    hieListCapabilities: vi.fn().mockResolvedValue({
      capabilities: ["brush_assistant", "global_tone"],
      models_available: ["birefnet"],
    }),
  };

  render(<HieEditorTab showModal={showModal} hostClient={hostClient as any} />);

  // Initial capabilities query
  await waitFor(() => {
    expect(hostClient.hieListCapabilities).toHaveBeenCalled();
  });

  // Open Media
  fireEvent.click(screen.getByRole("button", { name: /Open Media/i }));
  await waitFor(() => {
    expect(hostClient.hieOpenDocument).toHaveBeenCalled();
  });
  expect(await screen.findByText(/5 frame/i)).toBeInTheDocument();

  // Preview Assistance
  fireEvent.click(screen.getByRole("button", { name: /Preview Assistance/i }));
  await waitFor(() => {
    expect(hostClient.hieExecuteEdit).toHaveBeenCalledWith(
      expect.objectContaining({
        document_id: "doc-test-123",
        operation: "brush-assistant",
      })
    );
  });
  expect(await screen.findByText(/Proposal Ready/i)).toBeInTheDocument();

  // Accept into History
  fireEvent.click(screen.getByRole("button", { name: /Accept into History/i }));
  await waitFor(() => {
    expect(hostClient.hieExecuteEdit).toHaveBeenCalledWith(
      expect.objectContaining({
        document_id: "doc-test-123",
        operation: "brush-assistant_accept",
      })
    );
  });

  // Export Document
  fireEvent.click(screen.getByRole("button", { name: /Export Document/i }));
  await waitFor(() => {
    expect(hostClient.hieExportDocument).toHaveBeenCalledWith(
      expect.objectContaining({
        document_id: "doc-test-123",
      })
    );
  });
  expect(await screen.findByText(/Export complete/i)).toBeInTheDocument();
});
