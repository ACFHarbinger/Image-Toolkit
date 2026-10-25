import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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
  fireEvent.click(screen.getByTestId("preview-zoom-in"));
  expect(screen.getByTestId("preview-zoom")).toHaveTextContent("110%");
  fireEvent.click(screen.getByTestId("preview-rotate"));
  expect(screen.getByTestId("preview-frame")).toHaveStyle({ transform: "scale(1.1) rotate(90deg)" });
  fireEvent.click(screen.getByTestId("preview-next"));
  expect(screen.getByTestId("preview-path")).toHaveTextContent(RIGHT);
  expect(screen.getByRole("alert")).toHaveTextContent("not a file");
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
  fireEvent.click(screen.getByTestId("compare-difference"));
  expect(await screen.findByTestId("difference-result")).toHaveTextContent("size mismatch");
  expect(view.libraryPreviewDifference).toHaveBeenCalledWith({ left: LEFT, right: RIGHT, boost: 1 });
  fireEvent.click(screen.getByTestId("mode-drag"));
  fireEvent.pointerDown(screen.getByTestId("drag-source"), { clientX: 4, clientY: 6 });
  const preview = screen.getByTestId("drag-preview");
  expect(preview).toHaveStyle({ left: "14px", top: "16px" });
  expect(preview.className).toContain("pointer-events-none");
  fireEvent.pointerUp(screen.getByTestId("drag-source"));
  expect(screen.queryByTestId("drag-preview")).not.toBeInTheDocument();
});
