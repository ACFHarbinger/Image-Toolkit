import { invoke } from "@tauri-apps/api/core";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { MergeView } from "./MergeView";

afterEach(() => {
  cleanup();
});

test("concatenate sends the caller paths and output", async () => {
  const hostClient = {
    mergeConcatenate: vi.fn().mockResolvedValue({
      written: true,
      width: 4,
      height: 2,
      preview_png_base64: "",
      error: "",
    }),
  };
  render(<MergeView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Images"), { target: { value: "/a.png\n/b.png" } });
  fireEvent.change(screen.getByPlaceholderText(/Output Filename/i), { target: { value: "/out.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Concatenate" }));
  expect(await screen.findByRole("img", { name: "Merged preview" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "canvas" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "grid" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "panorama" })).toBeInTheDocument();
  expect(hostClient.mergeConcatenate).toHaveBeenCalledWith({
    paths: ["/a.png", "/b.png"],
    output_path: "/out.png",
    direction: "horizontal",
    spacing: 0,
    align: "start",
  });
});

test("move down reorders the images sent to concatenate", async () => {
  const hostClient = {
    mergeConcatenate: vi.fn().mockResolvedValue({
      written: true,
      width: 4,
      height: 2,
      preview_png_base64: "",
      error: "",
    }),
  };
  render(<MergeView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Images"), {
    target: { value: "/pics/a.png\n/pics/b.png\n/pics/c.png" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Move down a.png" }));
  fireEvent.change(screen.getByPlaceholderText(/Output Filename/i), { target: { value: "/out.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Concatenate" }));
  expect(await screen.findByRole("img", { name: "Merged preview" })).toBeInTheDocument();
  expect(hostClient.mergeConcatenate).toHaveBeenCalledWith({
    paths: ["/pics/b.png", "/pics/a.png", "/pics/c.png"],
    output_path: "/out.png",
    direction: "horizontal",
    spacing: 0,
    align: "start",
  });
});

test("a canvas directory becomes tiles the user can drag", async () => {
  vi.mocked(invoke).mockImplementation(async (command: string) => {
    if (command === "scan_files") {
      return ["/pics/a.png", "/pics/b.png"];
    }
    return {
      written: true,
      width: 1920,
      height: 1080,
      preview_png_base64: "",
      success: true,
      error: "",
    };
  });
  const rect = {
    width: 1920,
    height: 1080,
    x: 0,
    y: 0,
    top: 0,
    left: 0,
    bottom: 1080,
    right: 1920,
    toJSON() {
      return {};
    },
  };
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(rect as DOMRect);
  const hostClient = { mergeConcatenate: vi.fn() };
  render(<MergeView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Direction"), { target: { value: "canvas" } });
  fireEvent.change(screen.getByLabelText("Image directory"), { target: { value: "/pics" } });
  fireEvent.click(screen.getByRole("button", { name: "Scan" }));
  expect(await screen.findByRole("option", { name: "a.png" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("option", { name: "b.png" })).toHaveAttribute("aria-selected", "true");
  const tile = screen.getByRole("button", { name: "a.png" });
  fireEvent.pointerDown(tile, { clientX: 0, clientY: 0, button: 0 });
  fireEvent.pointerMove(window, { clientX: 40, clientY: 15 });
  fireEvent.pointerUp(window);
  fireEvent.change(screen.getByPlaceholderText(/Output Filename/i), { target: { value: "/out.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Concatenate" }));
  await waitFor(() => {
    expect(vi.mocked(invoke).mock.calls.some((call) => call[0] === "media_subtab" && (call[1] as { action?: string })?.action === "merge")).toBe(true);
  });
  const call = vi.mocked(invoke).mock.calls.find((entry) => entry[0] === "media_subtab" && (entry[1] as { action?: string })?.action === "merge");
  const params = (call?.[1] as { params: { canvas_layout: { path: string; x: number; y: number }[] } }).params;
  const placed = params.canvas_layout.find((item) => item.path === "/pics/a.png");
  expect(placed).toMatchObject({ x: 40, y: 15 });
  expect(hostClient.mergeConcatenate).not.toHaveBeenCalled();
  vi.restoreAllMocks();
});
