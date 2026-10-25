import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import {
  buildOverlayBatch,
  buildPyramidLevels,
  buildTileQuadBatch,
  createFakeCanvasDocument,
  cullVisibleTiles,
  CullWorkerClient,
  CullWorkerResponse,
  processCullRequest,
  renderCacheTileUrl,
  selectPyramidLevel,
  SharedCanvasHost,
  SharedCanvasRenderer,
  WorkerMessagePortLike,
  zoomAroundScreenPoint,
} from "./index";

afterEach(() => {
  cleanup();
});

test("50,000x30,000 fake document builds an 8-level pyramid and culls >99.7% of level-0 tiles", () => {
  const doc = createFakeCanvasDocument({ width: 50_000, height: 30_000, tileSize: 512 });
  const levels = buildPyramidLevels(doc.width, doc.height, doc.tileSize);

  expect(levels).toHaveLength(8);
  expect(levels[0]).toMatchObject({
    level: 0,
    scale: 1,
    width: 50_000,
    height: 30_000,
    cols: 98,
    rows: 59,
    totalTiles: 5782,
  });
  expect(levels[7]).toMatchObject({
    level: 7,
    scale: 1 / 128,
    cols: 1,
    rows: 1,
    totalTiles: 1,
  });

  // At full resolution (zoom = 1) in a 1280x720 viewport positioned near the seam overlap
  const culled = cullVisibleTiles(doc, {
    panX: -10_000,
    panY: -14_000,
    zoom: 1,
    viewportWidth: 1280,
    viewportHeight: 720,
  });
  expect(culled.level).toBe(0);
  expect(culled.totalPyramidTilesAtLevel).toBe(5782);
  expect(culled.tiles.length).toBeGreaterThan(0);
  expect(culled.tiles.length).toBeLessThanOrEqual(24);
});

test("zooming out selects coarser pyramid levels and keeps focal document point fixed", () => {
  expect(selectPyramidLevel(2.0, 7)).toBe(0);
  expect(selectPyramidLevel(1.0, 7)).toBe(0);
  expect(selectPyramidLevel(0.5, 7)).toBe(1);
  expect(selectPyramidLevel(0.125, 7)).toBe(3);
  expect(selectPyramidLevel(0.001, 7)).toBe(7);

  const initial = {
    panX: -2000,
    panY: -1000,
    zoom: 1.0,
    viewportWidth: 1280,
    viewportHeight: 720,
  };
  const zoomed = zoomAroundScreenPoint(initial, 0.5, 640, 360);
  // Document point under (640, 360) before zoom: (2640, 1360)
  // After zoom to 0.5: 2640 * 0.5 + panX = 640 => panX = -680
  expect(zoomed.zoom).toBe(0.5);
  expect(zoomed.panX).toBeCloseTo(-680, 5);
  expect(zoomed.panY).toBeCloseTo(-320, 5);
});

test("render-cache tile URL confinement refuses originals and path traversal", () => {
  const validTile = "/home/user/.image-toolkit/cache/render/frame_a_L0_4_2.jpg";
  const windowsTile = "C:\\Users\\user\\.image-toolkit\\cache\\render\\frame_a_L0_4_2.jpg";
  const original = "/home/user/Pictures/manga_page_01.png";
  const traversal = "/home/user/.image-toolkit/cache/render/../secrets.jpg";

  expect(renderCacheTileUrl(validTile)).toBe(validTile);
  expect(renderCacheTileUrl(windowsTile)).toBe(
    "C:/Users/user/.image-toolkit/cache/render/frame_a_L0_4_2.jpg",
  );
  expect(renderCacheTileUrl(original)).toBeNull();
  expect(renderCacheTileUrl(traversal)).toBeNull();
  expect(
    renderCacheTileUrl("/home/user/.image-toolkit/cache/render/%2e%2e/secrets.jpg"),
  ).toBeNull();
  expect(
    renderCacheTileUrl("/home/user/.image-toolkit/cache/render/my..tile.jpg"),
  ).toBe("/home/user/.image-toolkit/cache/render/my..tile.jpg");

  const docWithOriginal = createFakeCanvasDocument({
    cacheRoot: "/home/user/Pictures/raw_originals",
  });
  const response = processCullRequest({
    requestId: 1,
    document: docWithOriginal,
    viewport: { panX: 0, panY: 0, zoom: 1, viewportWidth: 1280, viewportHeight: 720 },
  });
  expect(response.tiles).toHaveLength(0);
  expect(response.rejectedCount).toBeGreaterThan(0);
});

test("off-screen worker client drops stale out-of-order responses", () => {
  type Listener = (event: { data: unknown }) => void;
  const clientListeners = new Set<Listener>();
  const pendingRequests: Array<{ requestId: number }> = [];

  const manualPort: WorkerMessagePortLike = {
    postMessage(message: unknown) {
      pendingRequests.push(message as { requestId: number });
    },
    addEventListener(_type: "message", listener: Listener) {
      clientListeners.add(listener);
    },
    removeEventListener(_type: "message", listener: Listener) {
      clientListeners.delete(listener);
    },
  };

  const client = new CullWorkerClient(manualPort);
  const received: number[] = [];
  client.subscribe((res) => {
    received.push(res.requestId);
  });

  const doc = createFakeCanvasDocument();
  const vp = { panX: 0, panY: 0, zoom: 1, viewportWidth: 1280, viewportHeight: 720 };
  const id1 = client.requestCull(doc, vp);
  const id2 = client.requestCull(doc, { ...vp, panX: -500 });
  expect(id1).toBe(1);
  expect(id2).toBe(2);
  expect(pendingRequests).toHaveLength(2);

  // Emit response 2 first, then stale response 1
  const emitResponse = (requestId: number) => {
    const fakeResponse: CullWorkerResponse = {
      requestId,
      level: 0,
      scale: 1,
      totalPyramidTilesAtLevel: 5782,
      visibleBoundsDoc: { x: 0, y: 0, width: 1280, height: 720 },
      tiles: [],
      rejectedCount: 0,
    };
    for (const listener of Array.from(clientListeners)) {
      listener({ data: fakeResponse });
    }
  };

  emitResponse(2);
  emitResponse(1);
  expect(received).toEqual([2]);
  client.dispose();
});

test("WebGL2 renderer compiles shaders and draws tile quads when WebGL2 context is available", () => {
  const doc = createFakeCanvasDocument();
  const vp = { panX: 0, panY: 0, zoom: 1, viewportWidth: 1280, viewportHeight: 720 };
  const culled = processCullRequest({ requestId: 1, document: doc, viewport: vp });

  const quadBatch = buildTileQuadBatch(culled.tiles, vp);
  expect(quadBatch.quadCount).toBe(culled.tiles.length);
  expect(quadBatch.vertices).toHaveLength(culled.tiles.length * 24);

  const overlayBatch = buildOverlayBatch(doc.seamPolygon, doc.roiBox, vp);
  expect(overlayBatch.seamVertices).toHaveLength(doc.seamPolygon.length * 2);
  expect(overlayBatch.roiVertices).toHaveLength(10);

  const canvas = document.createElement("canvas");
  const drawArrays = vi.fn();
  const mockGl = {
    VERTEX_SHADER: 0x8b31,
    FRAGMENT_SHADER: 0x8b30,
    COLOR_BUFFER_BIT: 0x4000,
    ARRAY_BUFFER: 0x8892,
    DYNAMIC_DRAW: 0x88e8,
    FLOAT: 0x1406,
    TRIANGLES: 0x0004,
    createShader: vi.fn(() => ({})),
    shaderSource: vi.fn(),
    compileShader: vi.fn(),
    createProgram: vi.fn(() => ({})),
    attachShader: vi.fn(),
    linkProgram: vi.fn(),
    createBuffer: vi.fn(() => ({})),
    viewport: vi.fn(),
    clearColor: vi.fn(),
    clear: vi.fn(),
    useProgram: vi.fn(),
    bindBuffer: vi.fn(),
    bufferData: vi.fn(),
    enableVertexAttribArray: vi.fn(),
    vertexAttribPointer: vi.fn(),
    drawArrays,
    deleteBuffer: vi.fn(),
    deleteProgram: vi.fn(),
    // Tile texture pipeline (Y-00 / #902)
    createTexture: vi.fn(() => ({})),
    bindTexture: vi.fn(),
    texImage2D: vi.fn(),
    texParameteri: vi.fn(),
    pixelStorei: vi.fn(),
    deleteTexture: vi.fn(),
    activeTexture: vi.fn(),
    getUniformLocation: vi.fn(() => ({})),
    uniform1i: vi.fn(),
    uniform1f: vi.fn(),
  };
  vi.spyOn(canvas, "getContext").mockImplementation(
    ((contextId: string) => (contextId === "webgl2" ? mockGl : null)) as unknown as typeof canvas.getContext,
  );

  const renderer = new SharedCanvasRenderer(canvas);
  expect(renderer.backend).toBe("webgl2");
  const stats = renderer.renderFrame({
    viewport: vp,
    tiles: culled.tiles,
    layerOpacities: { frame_a: 1, frame_b: 0.85 },
    blendMode: "split-wipe",
    splitWipeRatio: 0.4,
    seamPolygon: doc.seamPolygon,
    roiBox: doc.roiBox,
  });
  expect(stats.backend).toBe("webgl2");
  expect(stats.drawnTileCount).toBe(culled.tiles.length);
  // Per-tile draws since Y-00: each visible tile binds its own texture.
  expect(drawArrays).toHaveBeenCalledTimes(culled.tiles.length);
  for (let i = 0; i < culled.tiles.length; i += 1) {
    expect(drawArrays).toHaveBeenNthCalledWith(i + 1, mockGl.TRIANGLES, i * 6, 6);
  }
  renderer.dispose();
});

test("SharedCanvasHost mounts a 50kx30k fake document within budget and supports pan, zoom, and seam editing", async () => {
  const doc = createFakeCanvasDocument({ width: 50_000, height: 30_000, tileSize: 512 });
  const started = performance.now();

  let latestSeamMove: { index: number; x: number; y: number } | null = null;
  render(
    <SharedCanvasHost
      document={doc}
      viewportWidth={1280}
      viewportHeight={720}
      initialPanX={-5_000}
      initialPanY={-14_500}
      initialZoom={1}
      blendMode="split-wipe"
      splitWipeRatio={0.6}
      onSeamVertexMove={(index, pt) => {
        latestSeamMove = { index, x: pt.x, y: pt.y };
      }}
    />,
  );
  const elapsedMs = performance.now() - started;
  expect(elapsedMs).toBeLessThan(1000);

  const host = screen.getByTestId("shared-canvas-host");
  expect(host).toHaveAttribute("data-doc-width", "50000");
  expect(host).toHaveAttribute("data-doc-height", "30000");
  expect(host).toHaveAttribute("data-lod-level", "0");
  expect(host).toHaveAttribute("data-rejected-tiles", "0");

  const mountedTiles = Number(host.getAttribute("data-mounted-tiles"));
  expect(mountedTiles).toBeGreaterThan(0);
  expect(mountedTiles).toBeLessThanOrEqual(24);

  const tileQuads = screen.getAllByTestId("canvas-tile-quad");
  expect(tileQuads).toHaveLength(mountedTiles);
  expect(
    tileQuads.every((node) =>
      (node.getAttribute("data-tile-src") ?? "").includes("/.image-toolkit/cache/render/"),
    ),
  ).toBe(true);

  // Wheel zoom out four steps (1.0 -> 0.8 -> 0.64 -> 0.512 -> 0.4096 => LoD level 1)
  for (let i = 0; i < 4; i += 1) {
    await act(async () => {
      fireEvent.wheel(host, { deltaY: 120, clientX: 640, clientY: 360 });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
  expect(Number(host.getAttribute("data-lod-level"))).toBeGreaterThanOrEqual(1);

  // Drag seam handle 1 and verify document coordinate update
  const handles = screen.getAllByTestId("canvas-seam-handle");
  expect(handles).toHaveLength(doc.seamPolygon.length);
  await act(async () => {
    fireEvent.pointerDown(handles[1], { clientX: 400, clientY: 300 });
    fireEvent.pointerMove(host, { clientX: 520, clientY: 340 });
    fireEvent.pointerUp(host);
  });
  expect(latestSeamMove).not.toBeNull();
  expect(latestSeamMove!.index).toBe(1);
});
