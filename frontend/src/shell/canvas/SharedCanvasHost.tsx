import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  CullWorkerClient,
  CullWorkerResponse,
  processCullRequest,
  WorkerMessagePortLike,
} from "./cullWorker";
import {
  CanvasBlendMode,
  CanvasPoint,
  clampZoom,
  documentToScreenPoint,
  FakeCanvasDocument,
  screenToDocumentPoint,
  ViewportTransform,
  zoomAroundScreenPoint,
} from "./pyramid";
import { RenderFrameStats, SharedCanvasRenderer } from "./webglRenderer";
import { TileTextureCache, TileTextureLoader } from "./tileTextureCache";

export interface SharedCanvasHostProps {
  document: FakeCanvasDocument;
  viewportWidth?: number;
  viewportHeight?: number;
  initialPanX?: number;
  initialPanY?: number;
  initialZoom?: number;
  blendMode?: CanvasBlendMode;
  splitWipeRatio?: number;
  overscanTiles?: number;
  workerPort?: WorkerMessagePortLike;
  /** Source factory for tile textures; defaults to an HTMLImageElement decode. */
  textureLoader?: TileTextureLoader;
  /** LRU budget of decoded tile sources (default 256). */
  textureCacheBudget?: number;
  onViewportChange?: (viewport: ViewportTransform) => void;
  onSeamVertexMove?: (vertexIndex: number, nextDocPoint: CanvasPoint) => void;
}

/**
 * Shared Canvas Host (S-02 / #888) for stitch, merge, and frame-slice.
 *
 * - Off-screen worker performs frustum culling and level-of-detail (LoD) tile
 *   selection, validating that every tile URL stays confined inside
 *   `~/.image-toolkit/cache/render/`.
 * - WebGL2 / WebGPU viewport surface draws visible tile quads and vector
 *   seam/ROI overlays without allocating a full-document 2D `<canvas>`.
 */
export function SharedCanvasHost({
  document,
  viewportWidth = 1280,
  viewportHeight = 720,
  initialPanX = 0,
  initialPanY = 0,
  initialZoom = 1,
  blendMode = "normal",
  splitWipeRatio = 0.5,
  overscanTiles = 0,
  workerPort,
  textureLoader,
  textureCacheBudget,
  onViewportChange,
  onSeamVertexMove,
}: SharedCanvasHostProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<SharedCanvasRenderer | null>(null);
  const workerClientRef = useRef<CullWorkerClient | null>(null);

  const [viewport, setViewport] = useState<ViewportTransform>(() => ({
    panX: initialPanX,
    panY: initialPanY,
    zoom: clampZoom(initialZoom),
    viewportWidth,
    viewportHeight,
  }));

  useEffect(() => {
    setViewport((prev) => ({
      ...prev,
      panX: initialPanX,
      panY: initialPanY,
      zoom: clampZoom(initialZoom),
      viewportWidth,
      viewportHeight,
    }));
  }, [initialPanX, initialPanY, initialZoom, viewportWidth, viewportHeight]);

  // Production texture pipeline (Y-00 / #902): visible tiles upload into the
  // renderer's GL texture set through an LRU-bounded cache; eviction frees
  // the GL texture with the JS entry. textureVersion bumps re-render a frame
  // once loads complete so tiles pop in without waiting for the next pan.
  const textureCacheRef = useRef<TileTextureCache | null>(null);
  const [textureVersion, setTextureVersion] = useState(0);
  if (textureCacheRef.current === null) {
    textureCacheRef.current = new TileTextureCache({
      maxEntries: textureCacheBudget,
      loader: textureLoader,
      onEvict: (url) => rendererRef.current?.evictTileTexture(url),
    });
  }
  const textureCache = textureCacheRef.current;

  const [seamPolygon, setSeamPolygon] = useState<CanvasPoint[]>(() => document.seamPolygon);
  useEffect(() => {
    setSeamPolygon(document.seamPolygon);
  }, [document.seamPolygon]);

  // Synchronous initial cull so first paint has immediate deterministic tiles,
  // while subsequent viewport/document updates flow through the off-screen worker.
  const initialCull = useMemo(
    () =>
      processCullRequest({
        requestId: 0,
        document,
        viewport: {
          panX: initialPanX,
          panY: initialPanY,
          zoom: clampZoom(initialZoom),
          viewportWidth,
          viewportHeight,
        },
        overscanTiles,
      }),
    [document, initialPanX, initialPanY, initialZoom, viewportWidth, viewportHeight, overscanTiles],
  );

  const [cullState, setCullState] = useState<CullWorkerResponse>(initialCull);
  const [frameStats, setFrameStats] = useState<RenderFrameStats>({
    backend: "headless",
    drawnTileCount: initialCull.tiles.length,
    texturedTileCount: 0,
    seamVertexCount: document.seamPolygon.length,
    roiVertexCount: document.roiBox ? 5 : 0,
    blendMode,
    splitWipeRatio,
  });

  const dragStateRef = useRef<
    | { mode: "idle" }
    | { mode: "pan"; startX: number; startY: number; startPanX: number; startPanY: number }
    | { mode: "seam"; vertexIndex: number }
  >({ mode: "idle" });

  useEffect(() => {
    const client = new CullWorkerClient(workerPort);
    workerClientRef.current = client;
    const unsubscribe = client.subscribe((response) => {
      setCullState(response);
    });
    client.requestCull(document, viewport, overscanTiles);
    return () => {
      unsubscribe();
      client.dispose();
      workerClientRef.current = null;
    };
  }, [workerPort]);

  useEffect(() => {
    workerClientRef.current?.requestCull(document, viewport, overscanTiles);
  }, [document, viewport, overscanTiles]);

  useEffect(() => {
    for (const url of textureCache.pendingFor(cullState.tiles)) {
      void textureCache.load(url).then((source) => {
        if (!source) {
          return; // failed load: the placeholder stays for this tile
        }
        // A later load can evict this URL before the callback runs. Uploading
        // then would create a GL texture with no cache entry left to free it.
        if (textureCache.get(url) !== source) {
          return;
        }
        rendererRef.current?.uploadTileTexture(url, source);
        setTextureVersion((version) => version + 1);
      });
    }
  }, [cullState, textureCache]);

  useEffect(() => () => textureCache.clear(), [textureCache]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const renderer = new SharedCanvasRenderer(canvas);
    rendererRef.current = renderer;
    return () => {
      renderer.dispose();
      rendererRef.current = null;
    };
  }, []);

  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer) {
      return;
    }
    const opacities: Record<string, number> = {};
    for (const layer of document.layers) {
      opacities[layer.id] = layer.opacity;
    }
    const stats = renderer.renderFrame({
      viewport,
      tiles: cullState.tiles,
      layerOpacities: opacities,
      blendMode,
      splitWipeRatio,
      seamPolygon,
      roiBox: document.roiBox,
    });
    setFrameStats(stats);
  }, [cullState, viewport, document.layers, document.roiBox, blendMode, splitWipeRatio, seamPolygon, textureVersion]);

  const applyViewport = (next: ViewportTransform) => {
    setViewport(next);
    onViewportChange?.(next);
  };

  const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    const factor = event.deltaY < 0 ? 1.25 : 0.8;
    const rect = event.currentTarget.getBoundingClientRect();
    const anchorX = event.clientX - rect.left;
    const anchorY = event.clientY - rect.top;
    const next = zoomAroundScreenPoint(viewport, viewport.zoom * factor, anchorX, anchorY);
    applyViewport(next);
  };

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement | null;
    const seamIndexAttr = target?.getAttribute?.("data-seam-index");
    if (seamIndexAttr !== null && seamIndexAttr !== undefined) {
      const idx = Number(seamIndexAttr);
      if (Number.isInteger(idx) && idx >= 0 && idx < seamPolygon.length) {
        dragStateRef.current = { mode: "seam", vertexIndex: idx };
        return;
      }
    }
    dragStateRef.current = {
      mode: "pan",
      startX: event.clientX,
      startY: event.clientY,
      startPanX: viewport.panX,
      startPanY: viewport.panY,
    };
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const state = dragStateRef.current;
    if (state.mode === "pan") {
      const dx = event.clientX - state.startX;
      const dy = event.clientY - state.startY;
      applyViewport({
        ...viewport,
        panX: state.startPanX + dx,
        panY: state.startPanY + dy,
      });
    } else if (state.mode === "seam") {
      const rect = event.currentTarget.getBoundingClientRect();
      const screenX = event.clientX - rect.left;
      const screenY = event.clientY - rect.top;
      const docPt = screenToDocumentPoint(screenX, screenY, viewport);
      const clampedPt: CanvasPoint = {
        x: Math.max(0, Math.min(document.width, Math.round(docPt.x))),
        y: Math.max(0, Math.min(document.height, Math.round(docPt.y))),
      };
      setSeamPolygon((prev) =>
        prev.map((pt, idx) => (idx === state.vertexIndex ? clampedPt : pt)),
      );
      onSeamVertexMove?.(state.vertexIndex, clampedPt);
    }
  };

  const handlePointerUp = () => {
    dragStateRef.current = { mode: "idle" };
  };

  return (
    <div
      data-testid="shared-canvas-host"
      data-doc-id={document.id}
      data-doc-width={document.width}
      data-doc-height={document.height}
      data-lod-level={cullState.level}
      data-lod-scale={cullState.scale}
      data-mounted-tiles={cullState.tiles.length}
      data-rejected-tiles={cullState.rejectedCount}
      data-total-level-tiles={cullState.totalPyramidTilesAtLevel}
      data-renderer-backend={frameStats.backend}
      data-textured-tile-count={frameStats.texturedTileCount}
      data-texture-cache-entries={textureCache.stats().entries}
      data-texture-cache-evictions={textureCache.stats().evictions}
      data-blend-mode={frameStats.blendMode}
      data-split-wipe={frameStats.splitWipeRatio}
      data-zoom={viewport.zoom}
      data-pan-x={viewport.panX}
      data-pan-y={viewport.panY}
      style={{
        width: viewportWidth,
        height: viewportHeight,
        position: "relative",
        overflow: "hidden",
        userSelect: "none",
      }}
      onWheel={handleWheel}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
    >
      <canvas
        ref={canvasRef}
        data-testid="shared-canvas-surface"
        width={viewportWidth}
        height={viewportHeight}
        style={{ width: viewportWidth, height: viewportHeight, display: "block" }}
      />
      <div
        data-testid="shared-canvas-tile-layer"
        style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
      >
        {cullState.tiles.map((tile) => {
          const topLeft = documentToScreenPoint(tile.docRect.x, tile.docRect.y, viewport);
          return (
            <div
              key={tile.key}
              data-testid="canvas-tile-quad"
              data-tile-key={tile.key}
              data-layer-id={tile.layerId}
              data-lod-level={tile.level}
              data-tile-src={tile.assetUrl}
              style={{
                position: "absolute",
                left: topLeft.x,
                top: topLeft.y,
                width: tile.docRect.width * viewport.zoom,
                height: tile.docRect.height * viewport.zoom,
              }}
            />
          );
        })}
      </div>
      <svg
        data-testid="shared-canvas-overlay"
        width={viewportWidth}
        height={viewportHeight}
        style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
      >
        {seamPolygon.length >= 2 && (
          <polyline
            data-testid="canvas-seam-polyline"
            fill="none"
            stroke="#38bdf8"
            strokeWidth={2}
            points={seamPolygon
              .map((pt) => {
                const screen = documentToScreenPoint(pt.x, pt.y, viewport);
                return `${screen.x},${screen.y}`;
              })
              .join(" ")}
          />
        )}
      </svg>
      {seamPolygon.map((pt, index) => {
        const screen = documentToScreenPoint(pt.x, pt.y, viewport);
        return (
          <button
            key={`seam-vertex-${index}`}
            type="button"
            data-testid="canvas-seam-handle"
            data-seam-index={index}
            data-doc-x={pt.x}
            data-doc-y={pt.y}
            aria-label={`Seam vertex ${index}`}
            style={{
              position: "absolute",
              left: screen.x - 5,
              top: screen.y - 5,
              width: 10,
              height: 10,
              padding: 0,
              borderRadius: "50%",
            }}
          />
        );
      })}
    </div>
  );
}
