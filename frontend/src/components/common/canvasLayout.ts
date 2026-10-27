/** One placed image on the merge canvas. Coordinates are canvas pixels. */
export interface CanvasTile {
  path: string;
  x: number;
  y: number;
  w: number;
  h: number;
  /** True after the file's pixel size, or a manual edit, has set w and h. */
  fitted?: boolean;
}

export const DEFAULT_CANVAS_WIDTH = 1920;
export const DEFAULT_CANVAS_HEIGHT = 1080;

/** Classic MergeCanvas offsets: each new tile steps 30px right and 20px down, then wraps. */
export function placeOnCanvas(
  paths: string[],
  canvasWidth: number,
  canvasHeight: number,
  startIndex = 0,
): CanvasTile[] {
  const canvasW = Math.max(1, canvasWidth);
  const canvasH = Math.max(1, canvasHeight);
  return paths.map((path, index) => {
    const w = Math.min(400, canvasW);
    const h = Math.min(300, canvasH);
    const n = startIndex + index;
    return {
      path,
      x: (n * 30) % Math.max(1, canvasW - w),
      y: (n * 20) % Math.max(1, canvasH - h),
      w,
      h,
    };
  });
}

/** Keep tiles the user already moved. New paths are placed; dropped paths leave. */
export function reconcileTiles(
  previous: readonly CanvasTile[],
  paths: readonly string[],
  canvasWidth: number,
  canvasHeight: number,
): CanvasTile[] {
  const wanted = new Set(paths);
  const kept = previous.filter((tile) => wanted.has(tile.path));
  const known = new Set(kept.map((tile) => tile.path));
  const added = placeOnCanvas(
    paths.filter((path) => !known.has(path)),
    canvasWidth,
    canvasHeight,
    kept.length,
  );
  const order = new Map(paths.map((path, index) => [path, index]));
  return [...kept, ...added].sort((left, right) => (order.get(left.path) ?? 0) - (order.get(right.path) ?? 0));
}

/** Scale a tile down to the canvas the first time its real pixel size is known. */
export function fitTile(
  tile: CanvasTile,
  naturalWidth: number,
  naturalHeight: number,
  canvasWidth: number,
  canvasHeight: number,
): CanvasTile {
  if (tile.fitted || naturalWidth < 1 || naturalHeight < 1) {
    return tile;
  }
  let w = naturalWidth;
  let h = naturalHeight;
  if (w > canvasWidth || h > canvasHeight) {
    const scale = Math.min(canvasWidth / w, canvasHeight / h);
    w = Math.max(1, Math.floor(w * scale));
    h = Math.max(1, Math.floor(h * scale));
  }
  return { ...tile, w, h, fitted: true };
}

export function dragPosition(
  origin: { x: number; y: number },
  deltaX: number,
  deltaY: number,
  boardWidth: number,
  boardHeight: number,
  canvasWidth: number,
  canvasHeight: number,
): { x: number; y: number } {
  if (boardWidth <= 0 || boardHeight <= 0) {
    return origin;
  }
  return {
    x: Math.round(origin.x + (deltaX / boardWidth) * canvasWidth),
    y: Math.round(origin.y + (deltaY / boardHeight) * canvasHeight),
  };
}
