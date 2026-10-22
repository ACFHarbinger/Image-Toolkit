import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { renderCacheAssetUrl } from "./assetUrl";
import { requestAnimatedPreview } from "./preview";
import { VirtualGallery } from "./VirtualGallery";
import { visibleWindow } from "./window";

afterEach(() => {
  cleanup();
});

const VIEW = { viewportHeight: 600, rowHeight: 120, columns: 5 };

test("a 100k grid mounts a window, including after a long scroll", () => {
  const top = visibleWindow(100_000, { ...VIEW, scrollTop: 0 });
  const scrolled = visibleWindow(100_000, { ...VIEW, scrollTop: 48_000 });
  expect(top.mounted).toBeGreaterThan(0);
  expect(top.mounted).toBeLessThanOrEqual(40);
  expect(scrolled.mounted).toBeLessThanOrEqual(40);
  expect(scrolled.start).toBeGreaterThan(1_000);
  expect(scrolled.end).toBeLessThan(100_000);
});

test("the grid renders that window and refuses originals", () => {
  const cache = "/home/user/.image-toolkit/cache/render/abc_256.jpg";
  const original = "/home/user/Pictures/original.png";
  expect(renderCacheAssetUrl(cache)).toBe(cache);
  expect(renderCacheAssetUrl(original)).toBeNull();
  expect(renderCacheAssetUrl("/home/user/.image-toolkit/cache/render/../secret.jpg")).toBeNull();

  const items = Array.from({ length: 100_000 }, (_, index) => ({
    id: String(index),
    cachePath: index === 3 ? original : cache,
  }));
  const started = performance.now();
  render(
    <VirtualGallery
      items={items}
      scrollTop={0}
      viewportHeight={600}
      rowHeight={120}
      columns={5}
    />,
  );
  const elapsedMs = performance.now() - started;
  const cells = screen.getAllByTestId("gallery-cell");
  const gallery = screen.getByTestId("virtual-gallery");
  expect(gallery).toHaveAttribute("data-count", "100000");
  expect(Number(gallery.getAttribute("data-mounted"))).toBe(cells.length);
  expect(cells.length).toBeLessThanOrEqual(40);
  const images = gallery.querySelectorAll("img");
  expect(images).toHaveLength(cells.length - 1);
  expect(Array.from(images).every((image) => image.getAttribute("src") === cache)).toBe(true);
  expect(elapsedMs).toBeLessThan(1000);
});

test("animated preview rejects when already aborted and does not resolve a still", async () => {
  const aborted = new AbortController();
  aborted.abort();
  await expect(requestAnimatedPreview(aborted.signal)).rejects.toMatchObject({
    name: "AbortError",
  });

  const pending = new AbortController();
  const request = requestAnimatedPreview(pending.signal);
  pending.abort();
  await expect(request).rejects.toMatchObject({ name: "AbortError" });
});
