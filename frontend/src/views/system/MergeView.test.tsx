import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { MergeView } from "./MergeView";

afterEach(() => {
  cleanup();
});

const written = {
  written: true,
  output_path: "/out.png",
  width: 4,
  height: 2,
  preview_png_base64: "",
  error: "",
};

async function addImage(path: string) {
  fireEvent.change(screen.getByLabelText("Add image"), { target: { value: path } });
  fireEvent.click(screen.getByRole("button", { name: "Add" }));
}

test("concatenate sends the queue in order", async () => {
  const hostClient = {
    mergeConcatenate: vi.fn().mockResolvedValue(written),
    mergePlace: vi.fn(),
  };
  render(<MergeView hostClient={hostClient} />);
  await addImage("/a.png");
  await addImage("/b.png");
  fireEvent.change(screen.getByPlaceholderText(/Output Filename/i), { target: { value: "/out.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Concatenate" }));
  expect(await screen.findByRole("img", { name: "Merged preview" })).toBeInTheDocument();
  expect(await screen.findByText("4x2 /out.png")).toBeInTheDocument();
  expect(hostClient.mergeConcatenate).toHaveBeenCalledWith({
    paths: ["/a.png", "/b.png"],
    output_path: "/out.png",
    direction: "horizontal",
    spacing: 0,
    align: "start",
  });
  expect(hostClient.mergePlace).not.toHaveBeenCalled();
});

test("empty output folder keeps the filename and a browsed folder joins its last segment", async () => {
  const hostClient = {
    mergeConcatenate: vi.fn().mockResolvedValue(written),
    mergePlace: vi.fn(),
  };
  render(<MergeView hostClient={hostClient} />);
  fireEvent.change(screen.getByPlaceholderText(/Output Filename/i), { target: { value: "/out.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Concatenate" }));
  expect(await screen.findByText("4x2 /out.png")).toBeInTheDocument();
  expect(hostClient.mergeConcatenate).toHaveBeenCalledWith({
    paths: [],
    output_path: "/out.png",
    direction: "horizontal",
    spacing: 0,
    align: "start",
  });
  expect(hostClient.mergePlace).not.toHaveBeenCalled();

  vi.mocked(open).mockResolvedValueOnce("/exports");
  fireEvent.click(screen.getByRole("button", { name: "Browse output folder" }));
  await waitFor(() => expect(screen.getByLabelText("Output folder")).toHaveValue("/exports"));
  expect(open).toHaveBeenCalledWith({ directory: true, multiple: false });
  expect(hostClient.mergeConcatenate).toHaveBeenCalledTimes(1);
  expect(hostClient.mergePlace).not.toHaveBeenCalled();

  fireEvent.change(screen.getByPlaceholderText(/Output Filename/i), { target: { value: "merged.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Concatenate" }));
  expect(hostClient.mergeConcatenate).toHaveBeenLastCalledWith({
    paths: [],
    output_path: "/exports/merged.png",
    direction: "horizontal",
    spacing: 0,
    align: "start",
  });
  vi.mocked(open).mockReset();
});

test("placement sends stored rectangles", async () => {
  const hostClient = {
    mergeConcatenate: vi.fn(),
    mergePlace: vi.fn().mockResolvedValue({ ...written, width: 5, height: 3 }),
  };
  render(<MergeView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Mode"), { target: { value: "placement" } });
  await addImage("/a.png");
  fireEvent.change(screen.getByLabelText("x 0"), { target: { value: "1" } });
  fireEvent.change(screen.getByLabelText("y 0"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("width 0"), { target: { value: "8" } });
  fireEvent.change(screen.getByLabelText("height 0"), { target: { value: "9" } });
  fireEvent.change(screen.getByPlaceholderText(/Output Filename/i), { target: { value: "/out.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Place" }));
  expect(await screen.findByText("5x3 /out.png")).toBeInTheDocument();
  expect(hostClient.mergePlace).toHaveBeenCalledWith({
    placements: [{ path: "/a.png", x: 1, y: 2, width: 8, height: 9 }],
    output_path: "/out.png",
  });
});

test("a scanned thumbnail fills the add-image field without merging", async () => {
  vi.mocked(invoke).mockImplementation(async (command: string) => {
    if (command === "scan_files") {
      return ["/pics/tile.png"];
    }
    return {};
  });
  const hostClient = {
    mergeConcatenate: vi.fn(),
    mergePlace: vi.fn(),
  };
  render(<MergeView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Image directory"), { target: { value: "/pics" } });
  fireEvent.click(screen.getByRole("button", { name: "Scan" }));
  fireEvent.click(await screen.findByRole("option", { name: "tile.png" }));
  expect(screen.getByLabelText("Add image")).toHaveValue("/pics/tile.png");
  expect(hostClient.mergeConcatenate).not.toHaveBeenCalled();
  expect(hostClient.mergePlace).not.toHaveBeenCalled();
  vi.mocked(invoke).mockReset();
});

test("selecting both scanned thumbnails queues them and pages without merging", async () => {
  vi.mocked(invoke).mockImplementation(async (command: string) => {
    if (command === "scan_files") {
      return ["/pics/a.png", "/pics/b.png"];
    }
    return {};
  });
  const hostClient = {
    mergeConcatenate: vi.fn(),
    mergePlace: vi.fn(),
  };
  render(<MergeView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Image directory"), { target: { value: "/pics" } });
  fireEvent.click(screen.getByRole("button", { name: "Scan" }));
  fireEvent.click(await screen.findByRole("option", { name: "a.png" }));
  fireEvent.click(screen.getByRole("option", { name: "b.png" }));
  expect(screen.getByRole("option", { name: "a.png" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("option", { name: "b.png" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByText("/pics/a.png")).toBeInTheDocument();
  expect(screen.getByText("/pics/b.png")).toBeInTheDocument();
  expect(hostClient.mergeConcatenate).not.toHaveBeenCalled();
  expect(hostClient.mergePlace).not.toHaveBeenCalled();

  fireEvent.change(screen.getByLabelText("Queue page size"), { target: { value: "1" } });
  expect(screen.getByText("/pics/a.png")).toBeInTheDocument();
  expect(screen.queryByText("/pics/b.png")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  expect(screen.getByText("Items 2\u20132 of 2")).toBeInTheDocument();
  expect(screen.getByText("/pics/b.png")).toBeInTheDocument();
  expect(screen.queryByText("/pics/a.png")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Remove" }));
  expect(screen.getByText("/pics/a.png")).toBeInTheDocument();
  expect(screen.queryByText("/pics/b.png")).not.toBeInTheDocument();
  vi.mocked(invoke).mockReset();
});
