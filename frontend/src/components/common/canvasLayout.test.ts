import { expect, test } from "vitest";
import { dragPosition, placeOnCanvas, reconcileTiles } from "./canvasLayout";

test("new canvas tiles step across the board", () => {
  const tiles = placeOnCanvas(["/a.png", "/b.png"], 1920, 1080);
  expect(tiles[0]).toMatchObject({ path: "/a.png", x: 0, y: 0, w: 400, h: 300 });
  expect(tiles[1]).toMatchObject({ path: "/b.png", x: 30, y: 20 });
});

test("reconcile keeps a tile the user already moved", () => {
  const kept = reconcileTiles(
    [{ path: "/a.png", x: 80, y: 12, w: 400, h: 300, fitted: true }],
    ["/a.png", "/b.png"],
    1920,
    1080,
  );
  expect(kept[0]).toMatchObject({ path: "/a.png", x: 80, y: 12, fitted: true });
  expect(kept[1].path).toBe("/b.png");
});

test("drag maps pointer delta through the board scale", () => {
  expect(dragPosition({ x: 10, y: 4 }, 40, 15, 1920, 1080, 1920, 1080)).toEqual({ x: 50, y: 19 });
});
