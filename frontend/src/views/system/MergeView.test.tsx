import { invoke } from "@tauri-apps/api/core";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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
