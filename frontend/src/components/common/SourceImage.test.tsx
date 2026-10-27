import { invoke } from "@tauri-apps/api/core";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { SourceImage } from "./SourceImage";

afterEach(() => { cleanup(); vi.mocked(invoke).mockReset(); });

test("loads bounded native pixels and reports original dimensions", async () => {
  vi.mocked(invoke).mockResolvedValue({ png_base64: "pixels", width: 800, height: 600, error: "" });
  const dimensions = vi.fn();
  render(<SourceImage path="/photos/source.png" alt="source" onDimensions={dimensions} />);
  expect(await screen.findByAltText("source")).toHaveAttribute("src", "data:image/png;base64,pixels");
  expect(invoke).toHaveBeenCalledWith("media_subtab", { action: "preview", params: { path: "/photos/source.png" } });
  expect(dimensions).toHaveBeenCalledWith(800, 600);
});

test("ignores a stale preview after the source changes", async () => {
  let resolveOld!: (frame: unknown) => void;
  vi.mocked(invoke).mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve; }))
    .mockResolvedValueOnce({ png_base64: "new", width: 10, height: 10, error: "" });
  const dimensions = vi.fn();
  const view = render(<SourceImage path="/old.png" alt="source" onDimensions={dimensions} />);
  view.rerender(<SourceImage path="/new.png" alt="source" onDimensions={dimensions} />);
  expect(await screen.findByAltText("source")).toHaveAttribute("src", "data:image/png;base64,new");
  resolveOld({ png_base64: "old", width: 800, height: 600, error: "" });
  await waitFor(() => expect(dimensions).toHaveBeenCalledTimes(1));
  expect(screen.getByAltText("source")).toHaveAttribute("src", "data:image/png;base64,new");
});
