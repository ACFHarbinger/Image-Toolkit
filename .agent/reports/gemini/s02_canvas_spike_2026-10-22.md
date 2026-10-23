# S-02 shared canvas host spike — go/no-go note

— Gemini, 2026-10-22. Issue #888. Grok reviews; Harbinger decides. This note is the measurement record, not the decision.

## What was measured

The shared canvas host (`frontend/src/shell/canvas/`) is designed to back stitch, merge, and frame-slice workspaces (Grok T7, Gemini G2–G3, Codex R5) on documents exceeding HTML5 2D `<canvas>` hardware limits (typically 16,384 px per axis in Chromium/WebKit):

1. **Dynamic Level-of-Detail (LoD) Tile Pyramid & Frustum Culler (`frontend/src/shell/canvas/pyramid.ts`):**
   - `buildPyramidLevels(docWidth, docHeight, tileSize)` builds a power-of-two tile pyramid from level `0` (full resolution, `scale = 1`) down to the coarsest level where the entire document fits inside a single tile.
   - For the synthetic 50,000 × 30,000 px two-layer stitch document (`createFakeCanvasDocument`, `tileSize = 512`), level `0` spans `98 × 59 = 5,782` tiles per full-document extent (`1.5 GPix`), and the pyramid has 8 levels (`L0` through `L7`).
   - `cullVisibleTiles(doc, viewport, overscanTiles)` computes the exact document-space frustum for each visible layer and emits only the intersecting tiles at the active LoD level (`selectPyramidLevel`).
   - `zoomAroundScreenPoint` keeps the document coordinate under the cursor stationary across zoom steps.

2. **Off-Screen Culling Worker & Render-Cache Asset Confinement (`frontend/src/shell/canvas/cullWorker.ts`):**
   - `attachCullWorkerHost` / `CullWorkerClient` run frustum culling and tile resolution off the main thread over a `postMessage` worker channel (`WorkerMessagePortLike`), dropping stale/out-of-order responses via monotonic `requestId` tracking.
   - `renderCacheTileUrl` enforces the Wave 0 default-deny asset scope (`/.image-toolkit/cache/render/` in `frontend/src-tauri/tauri.conf.json`), rejecting raw original image paths and any `..` traversal before calling `convertFileSrc`.

3. **WebGL2 / WebGPU Tile-Quad & Vector-Overlay Renderer (`frontend/src/shell/canvas/webglRenderer.ts`, `SharedCanvasHost.tsx`):**
   - `SharedCanvasRenderer` compiles a WebGL2 `#version 300 es` shader pair (`TILE_VERTEX_SHADER_GLSL`, `TILE_FRAGMENT_SHADER_GLSL`) supporting per-layer opacity, difference blending, and split-wipe curtain clipping (`u_splitWipeNdcX`), and uploads interleaved NDC/UV quad batches (`buildTileQuadBatch`) plus seam/ROI vector overlays (`buildOverlayBatch`).
   - `<SharedCanvasHost />` binds the viewport `<canvas>` (sized to the viewport `1280 × 720`, never the 50,000 × 30,000 document), the off-screen worker client, pointer pan/zoom, and interactive polygon seam vertex handles.

## Evidence

Targeted checks only per RESOURCE RULE. No full suite and no corpus benchmark.

- `npm --prefix frontend test -- --run src/shell/canvas/canvas.test.tsx`: **6 passed in 110 ms**.
  - **50,000 × 30,000 fake document culling:** Level 0 has `5,782` pyramid tiles; a `1280 × 720` viewport at `zoom = 1` over the two-layer overlap mounts **16 tile quads** (`99.7%` culled).
  - **LoD selection & focal zoom:** Zooming from `1.0` to `0.4096` transitions automatically from `L0` to `L1` while keeping the focal document point stationary (`zoomAroundScreenPoint` accurate to `< 1e-5` px).
  - **Asset scope confinement:** Valid Linux and Windows paths under `/.image-toolkit/cache/render/` resolve; raw originals (`/home/user/Pictures/manga_page_01.png`) and `..` traversal paths return `null` and increment `data-rejected-tiles`.
  - **Monotonic worker ordering:** Out-of-order worker responses (`requestId = 1` arriving after `requestId = 2`) are dropped before reaching the renderer.
  - **WebGL2 shader & quad batching:** `SharedCanvasRenderer` compiles the GLSL 300 ES shaders, uploads `24` floats per visible tile quad, and issues `gl.drawArrays(gl.TRIANGLES, 0, quadCount * 6)`.
  - **Interactive responsiveness budget:** Initial mount + cull + render of the 50,000 × 30,000 two-layer document completed in **~64–101 ms** in jsdom (well inside the 1,000 ms test bound), with pointer seam-vertex dragging updating document-space seam coordinates synchronously.
- `npm --prefix frontend run typecheck` (`tsc --noEmit`): **0 errors**.

## Recommendation

**Go for the shared canvas host** (`frontend/src/shell/canvas/`) as the common viewport foundation for Feature Wave 4 (Merge, Frame Slice) and Feature Wave 8 (Image Stitching, Interactive Seam Editor):

1. Keep the `<canvas>` backing store strictly equal to the viewport dimensions (`viewportWidth × viewportHeight`) and stream only culled LoD tiles from `~/.image-toolkit/cache/render/` over `asset://`.
2. Next step in Feature Wave 4 (`S-01` / Merge): connect the C++ tile-pyramid slicer (`backend`) to write `{layer}_L{level}_{col}_{row}.jpg` into `~/.image-toolkit/cache/render/` on demand and bind `HTMLImageElement` / `ImageBitmap` texture uploads into `SharedCanvasRenderer`'s LRU texture cache.

— Gemini
