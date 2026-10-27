import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { LibraryPreviewWindow, type PreviewClient } from "./LibraryPreviewWindow";

const LEFT = "/tmp/left.png";
const RIGHT = "/tmp/right.png";

function client(): PreviewClient {
  return {
    libraryPreviewDescribe: vi.fn().mockResolvedValue({
      items: [
        { path: LEFT, exists: true, width: 2, height: 1, animated: false, error: "" },
        { path: RIGHT, exists: false, width: 0, height: 0, animated: false, error: "not a file" },
      ],
    }),
    libraryPreviewFrame: vi.fn().mockImplementation(async ({ path }: { path: string }) => ({
      path,
      width: 2,
      height: 1,
      png_base64: "aaaa",
      error: path === RIGHT ? "not a file" : "",
    })),
    libraryPreviewDifference: vi.fn().mockResolvedValue({
      available: false,
      mean_abs: 0,
      reason: "size mismatch",
      png_base64: "",
    }),
  };
}

async function inspect(view: PreviewClient) {
  cleanup();
  render(<LibraryPreviewWindow client={view} />);
  fireEvent.change(screen.getByTestId("preview-paths"), { target: { value: `${LEFT}\n${RIGHT}` } });
  fireEvent.click(screen.getByTestId("preview-inspect"));
  expect(await screen.findByTestId("preview-path")).toHaveTextContent(LEFT);
}

test("preview steps through described paths and rotates", async () => {
  const view = client();
  await inspect(view);
  expect(view.libraryPreviewFrame).toHaveBeenCalledWith({ path: LEFT });
  expect(screen.getByTestId("preview-zoom")).toHaveTextContent("100%");
  fireEvent.click(screen.getByTestId("preview-zoom-out"));
  expect(screen.getByTestId("preview-zoom")).toHaveTextContent("90%");
  fireEvent.click(screen.getByTestId("preview-fit"));
  expect(screen.getByTestId("preview-zoom")).toHaveTextContent("100%");
  fireEvent.click(screen.getByTestId("preview-zoom-in"));
  expect(screen.getByTestId("preview-zoom")).toHaveTextContent("110%");
  fireEvent.click(screen.getByTestId("preview-rotate"));
  expect(screen.getByTestId("preview-frame")).toHaveStyle({ transform: "scale(1.1) rotate(90deg)" });
  fireEvent.click(screen.getByTestId("preview-next"));
  expect(screen.getByTestId("preview-path")).toHaveTextContent(RIGHT);
  expect(screen.getByRole("alert")).toHaveTextContent("not a file");
});

test("preview actual size, counter-clockwise rotate, and fit-to-width at zero pane width", async () => {
  const view = client();
  await inspect(view);
  fireEvent.click(screen.getByTestId("preview-zoom-in"));
  expect(screen.getByTestId("preview-zoom")).toHaveTextContent("110%");
  fireEvent.click(screen.getByTestId("preview-actual-size"));
  expect(screen.getByTestId("preview-zoom")).toHaveTextContent("100%");
  fireEvent.click(screen.getByTestId("preview-rotate-ccw"));
  expect(screen.getByTestId("preview-frame")).toHaveStyle({ transform: "scale(1) rotate(270deg)" });
  fireEvent.click(screen.getByTestId("preview-zoom-in"));
  fireEvent.click(screen.getByTestId("preview-fit-width"));
  expect(screen.getByTestId("preview-zoom")).toHaveTextContent("100%");
});

test("compare asks for a difference and drag preview ignores pointer events", async () => {
  const view = client();
  view.libraryPreviewDescribe = vi.fn().mockResolvedValue({
    items: [
      { path: LEFT, exists: true, width: 2, height: 1, animated: false, error: "" },
      { path: RIGHT, exists: true, width: 2, height: 1, animated: false, error: "" },
    ],
  });
  view.libraryPreviewFrame = vi.fn().mockImplementation(async ({ path }: { path: string }) => ({
    path,
    width: 2,
    height: 1,
    png_base64: "aaaa",
    error: "",
  }));
  await inspect(view);
  fireEvent.click(screen.getByTestId("mode-compare"));
  const overlay = screen.getByTestId("compare-overlay");
  const frames = overlay.querySelectorAll("[data-testid=preview-frame]");
  expect(frames).toHaveLength(2);
  for (const frame of frames) {
    expect(frame.parentElement?.className).toContain("absolute");
    expect(frame.parentElement?.className).toContain("inset-0");
  }
  expect(frames[0]).toHaveAttribute("alt", RIGHT);
  expect(frames[1]).toHaveAttribute("alt", LEFT);
  fireEvent.click(screen.getByRole("button", { name: "Flip overlay" }));
  const flipped = overlay.querySelectorAll("[data-testid=preview-frame]");
  expect(flipped[0]).toHaveAttribute("alt", LEFT);
  expect(flipped[1]).toHaveAttribute("alt", RIGHT);
  fireEvent.click(screen.getByRole("button", { name: "Flip overlay" }));
  const restored = overlay.querySelectorAll("[data-testid=preview-frame]");
  expect(restored[0]).toHaveAttribute("alt", RIGHT);
  expect(restored[1]).toHaveAttribute("alt", LEFT);
  const rowFrames = screen.getByTestId("compare-pane").firstElementChild?.querySelectorAll("[data-testid=preview-frame]");
  expect(rowFrames?.[0]).toHaveAttribute("alt", LEFT);
  expect(rowFrames?.[1]).toHaveAttribute("alt", RIGHT);
  fireEvent.click(screen.getByTestId("compare-difference"));
  expect(await screen.findByTestId("difference-result")).toHaveTextContent("size mismatch");
  expect(view.libraryPreviewDifference).toHaveBeenCalledWith({ left: LEFT, right: RIGHT, boost: 1 });
  fireEvent.change(screen.getByRole("combobox", { name: "Diff amplification" }), { target: { value: "4" } });
  fireEvent.click(screen.getByTestId("compare-difference"));
  expect(view.libraryPreviewDifference).toHaveBeenLastCalledWith({ left: LEFT, right: RIGHT, boost: 4 });
  fireEvent.click(screen.getByTestId("mode-drag"));
  fireEvent.pointerDown(screen.getByTestId("drag-source"), { clientX: 4, clientY: 6 });
  const preview = screen.getByTestId("drag-preview");
  expect(preview).toHaveStyle({ left: "14px", top: "16px" });
  expect(preview.className).toContain("pointer-events-none");
  fireEvent.pointerUp(screen.getByTestId("drag-source"));
  expect(screen.queryByTestId("drag-preview")).not.toBeInTheDocument();
});

test("preview copies the current frame png without refetching", async () => {
  const view = client();
  await inspect(view);
  const frameCalls = vi.mocked(view.libraryPreviewFrame).mock.calls.length;
  class ClipboardItem {
    readonly items: object;
    constructor(items: object) {
      this.items = items;
    }
  }
  const write = vi.fn().mockResolvedValue(undefined);
  const nav = navigator as unknown as { clipboard?: { write: typeof write } };
  const previousClipboard = nav.clipboard;
  const previousClipboardItem = globalThis.ClipboardItem;
  try {
    globalThis.ClipboardItem = ClipboardItem as unknown as typeof globalThis.ClipboardItem;
    nav.clipboard = { write };
    fireEvent.click(screen.getByTestId("preview-copy"));
    await waitFor(() => expect(write).toHaveBeenCalledTimes(1));
    const written = write.mock.calls[0][0] as unknown[];
    expect(written[0]).toBeInstanceOf(ClipboardItem);
    expect(await screen.findByTestId("preview-copied")).toHaveTextContent("Copied left.png");
    expect(vi.mocked(view.libraryPreviewFrame).mock.calls.length).toBe(frameCalls);
  } finally {
    nav.clipboard = previousClipboard;
    globalThis.ClipboardItem = previousClipboardItem;
  }
});
