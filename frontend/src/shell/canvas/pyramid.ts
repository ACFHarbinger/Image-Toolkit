/**
 * Dynamic Level-of-Detail (LoD) tile pyramid math, viewport frustum culling,
 * and fake document factory for the shared canvas host spike (S-02 / #888).
 */

export interface CanvasPoint {
  x: number;
  y: number;
}

export interface CanvasRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export type CanvasBlendMode = "normal" | "difference" | "split-wipe";

export interface CanvasLayerSpec {
  id: string;
  label: string;
  width: number;
  height: number;
  offsetX: number;
  offsetY: number;
  opacity: number;
  visible: boolean;
  /**
   * Directory inside `~/.image-toolkit/cache/render/` holding pre-sliced
   * `{level}_{col}_{row}.jpg` pyramid tiles for this layer.
   */
  tileCacheRoot: string;
}

export interface FakeCanvasDocument {
  id: string;
  title: string;
  width: number;
  height: number;
  tileSize: number;
  layers: CanvasLayerSpec[];
  seamPolygon: CanvasPoint[];
  roiBox: CanvasRect | null;
}

export interface ViewportTransform {
  /** Pan offset in screen pixels (top-left of document relative to viewport). */
  panX: number;
  panY: number;
  /** Zoom scale (screen pixels per document pixel). */
  zoom: number;
  viewportWidth: number;
  viewportHeight: number;
}

export interface PyramidLevelSpec {
  level: number;
  scale: number;
  width: number;
  height: number;
  cols: number;
  rows: number;
  totalTiles: number;
}

export interface VisibleTileDescriptor {
  key: string;
  layerId: string;
  level: number;
  col: number;
  row: number;
  /** Document-space bounding box of this tile (in full-resolution document pixels). */
  docRect: CanvasRect;
  /** Candidate cache file path for this tile. */
  cachePath: string;
}

export interface FrustumCullResult {
  level: number;
  scale: number;
  totalPyramidTilesAtLevel: number;
  visibleBoundsDoc: CanvasRect;
  tiles: VisibleTileDescriptor[];
}

const MIN_ZOOM = 1 / 1024;
const MAX_ZOOM = 64;

export function clampZoom(zoom: number): number {
  if (!Number.isFinite(zoom) || zoom <= 0) {
    return 1;
  }
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));
}

/**
 * Computes the LoD tile pyramid from level 0 (full resolution, scale = 1)
 * up to the coarsest level where the whole document fits within a single tile.
 */
export function buildPyramidLevels(
  docWidth: number,
  docHeight: number,
  tileSize = 512,
): PyramidLevelSpec[] {
  const safeWidth = Math.max(1, Math.floor(docWidth));
  const safeHeight = Math.max(1, Math.floor(docHeight));
  const safeTile = Math.max(64, Math.floor(tileSize));
  const maxDim = Math.max(safeWidth, safeHeight);
  const maxLevel = Math.max(0, Math.ceil(Math.log2(maxDim / safeTile)));

  const levels: PyramidLevelSpec[] = [];
  for (let level = 0; level <= maxLevel; level += 1) {
    const divisor = 2 ** level;
    const scale = 1 / divisor;
    const width = Math.max(1, Math.ceil(safeWidth / divisor));
    const height = Math.max(1, Math.ceil(safeHeight / divisor));
    const cols = Math.max(1, Math.ceil(width / safeTile));
    const rows = Math.max(1, Math.ceil(height / safeTile));
    levels.push({
      level,
      scale,
      width,
      height,
      cols,
      rows,
      totalTiles: cols * rows,
    });
  }
  return levels;
}

/**
 * Selects the pyramid level whose resolution is closest to (and at least as
 * detailed as) the current zoom factor.
 * - zoom >= 1 => level 0 (full resolution)
 * - zoom = 0.5 => level 1
 * - zoom = 0.125 => level 3
 */
export function selectPyramidLevel(zoom: number, maxLevel: number): number {
  const safeMax = Math.max(0, Math.floor(maxLevel));
  const z = clampZoom(zoom);
  if (z >= 1) {
    return 0;
  }
  const rawLevel = Math.floor(Math.log2(1 / z));
  return Math.min(safeMax, Math.max(0, rawLevel));
}

export function screenToDocumentPoint(
  screenX: number,
  screenY: number,
  viewport: ViewportTransform,
): CanvasPoint {
  const z = clampZoom(viewport.zoom);
  return {
    x: (screenX - viewport.panX) / z,
    y: (screenY - viewport.panY) / z,
  };
}

export function documentToScreenPoint(
  docX: number,
  docY: number,
  viewport: ViewportTransform,
): CanvasPoint {
  const z = clampZoom(viewport.zoom);
  return {
    x: docX * z + viewport.panX,
    y: docY * z + viewport.panY,
  };
}

/**
 * Zooms around a focal screen point `(anchorScreenX, anchorScreenY)` so the
 * document point underneath the cursor remains stationary.
 */
export function zoomAroundScreenPoint(
  viewport: ViewportTransform,
  nextZoom: number,
  anchorScreenX: number,
  anchorScreenY: number,
): ViewportTransform {
  const clampedNext = clampZoom(nextZoom);
  const docFocus = screenToDocumentPoint(anchorScreenX, anchorScreenY, viewport);
  return {
    ...viewport,
    zoom: clampedNext,
    panX: anchorScreenX - docFocus.x * clampedNext,
    panY: anchorScreenY - docFocus.y * clampedNext,
  };
}

/**
 * Computes the visible tiles for all visible layers of a document given the
 * current viewport transform. Only tiles intersecting the viewport frustum
 * (plus `overscanTiles`) are emitted.
 */
export function cullVisibleTiles(
  doc: FakeCanvasDocument,
  viewport: ViewportTransform,
  overscanTiles = 0,
): FrustumCullResult {
  const tileSize = Math.max(64, Math.floor(doc.tileSize));
  const levels = buildPyramidLevels(doc.width, doc.height, tileSize);
  const maxLevel = levels.length - 1;
  const level = selectPyramidLevel(viewport.zoom, maxLevel);
  const levelSpec = levels[level];
  const z = clampZoom(viewport.zoom);
  const overscan = Math.max(0, Math.floor(overscanTiles));

  const topLeftDoc = screenToDocumentPoint(0, 0, { ...viewport, zoom: z });
  const bottomRightDoc = screenToDocumentPoint(
    Math.max(1, viewport.viewportWidth),
    Math.max(1, viewport.viewportHeight),
    { ...viewport, zoom: z },
  );

  const visibleMinX = Math.max(0, Math.min(doc.width, topLeftDoc.x));
  const visibleMinY = Math.max(0, Math.min(doc.height, topLeftDoc.y));
  const visibleMaxX = Math.max(0, Math.min(doc.width, bottomRightDoc.x));
  const visibleMaxY = Math.max(0, Math.min(doc.height, bottomRightDoc.y));

  const visibleBoundsDoc: CanvasRect = {
    x: visibleMinX,
    y: visibleMinY,
    width: Math.max(0, visibleMaxX - visibleMinX),
    height: Math.max(0, visibleMaxY - visibleMinY),
  };

  if (visibleBoundsDoc.width <= 0 || visibleBoundsDoc.height <= 0) {
    return {
      level,
      scale: levelSpec.scale,
      totalPyramidTilesAtLevel: levelSpec.totalTiles,
      visibleBoundsDoc,
      tiles: [],
    };
  }

  // Span of a single tile at `level` in full-resolution document pixels
  const docSpanPerTile = tileSize * 2 ** level;
  const tiles: VisibleTileDescriptor[] = [];

  for (const layer of doc.layers) {
    if (!layer.visible || layer.opacity <= 0) {
      continue;
    }
    const layerMinX = Math.max(layer.offsetX, visibleMinX);
    const layerMinY = Math.max(layer.offsetY, visibleMinY);
    const layerMaxX = Math.min(layer.offsetX + layer.width, visibleMaxX);
    const layerMaxY = Math.min(layer.offsetY + layer.height, visibleMaxY);

    if (layerMaxX <= layerMinX || layerMaxY <= layerMinY) {
      continue;
    }

    const localMinX = layerMinX - layer.offsetX;
    const localMinY = layerMinY - layer.offsetY;
    const localMaxX = layerMaxX - layer.offsetX;
    const localMaxY = layerMaxY - layer.offsetY;

    const maxLayerCol = Math.max(0, Math.ceil(layer.width / docSpanPerTile) - 1);
    const maxLayerRow = Math.max(0, Math.ceil(layer.height / docSpanPerTile) - 1);

    const startCol = Math.max(0, Math.floor(localMinX / docSpanPerTile) - overscan);
    const endCol = Math.min(maxLayerCol, Math.floor((localMaxX - 1e-6) / docSpanPerTile) + overscan);
    const startRow = Math.max(0, Math.floor(localMinY / docSpanPerTile) - overscan);
    const endRow = Math.min(maxLayerRow, Math.floor((localMaxY - 1e-6) / docSpanPerTile) + overscan);

    const normalizedRoot = layer.tileCacheRoot.replace(/\/+$/, "");
    for (let row = startRow; row <= endRow; row += 1) {
      for (let col = startCol; col <= endCol; col += 1) {
        const docX = layer.offsetX + col * docSpanPerTile;
        const docY = layer.offsetY + row * docSpanPerTile;
        const docW = Math.min(docSpanPerTile, layer.offsetX + layer.width - docX);
        const docH = Math.min(docSpanPerTile, layer.offsetY + layer.height - docY);
        const key = `${layer.id}:${level}:${col}:${row}`;
        const cachePath = `${normalizedRoot}/${layer.id}_L${level}_${col}_${row}.jpg`;
        tiles.push({
          key,
          layerId: layer.id,
          level,
          col,
          row,
          docRect: { x: docX, y: docY, width: docW, height: docH },
          cachePath,
        });
      }
    }
  }

  return {
    level,
    scale: levelSpec.scale,
    totalPyramidTilesAtLevel: levelSpec.totalTiles,
    visibleBoundsDoc,
    tiles,
  };
}

/**
 * Creates a deterministic fake multi-layer stitching/merge document whose
 * dimensions (default 50,000 x 30,000 px) exceed HTML5 2D canvas hardware
 * limits (16,384 px) to exercise pyramid culling, worker tile scheduling,
 * and WebGL2/WebGPU quad + seam overlay rendering.
 */
export function createFakeCanvasDocument(
  options: {
    width?: number;
    height?: number;
    tileSize?: number;
    cacheRoot?: string;
  } = {},
): FakeCanvasDocument {
  const width = options.width ?? 50_000;
  const height = options.height ?? 30_000;
  const tileSize = options.tileSize ?? 512;
  const cacheRoot = options.cacheRoot ?? "/home/user/.image-toolkit/cache/render";

  return {
    id: "fake-stitch-doc-50kx30k",
    title: "Synthetic 50k×30k Panorama Stitch Document",
    width,
    height,
    tileSize,
    layers: [
      {
        id: "frame_a",
        label: "Frame 01 (Reference Anchor)",
        width,
        height: Math.floor(height * 0.6),
        offsetX: 0,
        offsetY: 0,
        opacity: 1.0,
        visible: true,
        tileCacheRoot: cacheRoot,
      },
      {
        id: "frame_b",
        label: "Frame 02 (Warped Overlap)",
        width,
        height: Math.floor(height * 0.6),
        offsetX: 0,
        offsetY: Math.floor(height * 0.4),
        opacity: 0.85,
        visible: true,
        tileCacheRoot: cacheRoot,
      },
    ],
    seamPolygon: [
      { x: 0, y: Math.floor(height * 0.48) },
      { x: Math.floor(width * 0.35), y: Math.floor(height * 0.51) },
      { x: Math.floor(width * 0.7), y: Math.floor(height * 0.49) },
      { x: width, y: Math.floor(height * 0.52) },
    ],
    roiBox: {
      x: Math.floor(width * 0.1),
      y: Math.floor(height * 0.38),
      width: Math.floor(width * 0.8),
      height: Math.floor(height * 0.24),
    },
  };
}
