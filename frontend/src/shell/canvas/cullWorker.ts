/**
 * Off-screen worker protocol, render-cache asset URL confinement check, and
 * scheduler for the shared canvas host spike (S-02 / #888).
 */

import { convertFileSrc } from "@tauri-apps/api/core";
import {
  CanvasRect,
  cullVisibleTiles,
  FakeCanvasDocument,
  FrustumCullResult,
  ViewportTransform,
} from "./pyramid";

/** Matches the default-deny scope in `tauri.conf.json`. Originals never match. */
export const RENDER_CACHE_SEGMENT = "/.image-toolkit/cache/render/";

/**
 * Validates that a candidate tile path resides inside `/.image-toolkit/cache/render/`
 * with no parent-traversal (`..`) segments, and converts it via `convertFileSrc`.
 * Originals or paths outside the render cache return `null`.
 */
function canonicalCachePath(cachePath: string): string | null {
  const normalized = cachePath.replaceAll("\\", "/");
  if (!normalized || normalized.includes("\0")) {
    return null;
  }
  const parts: string[] = [];
  const rawParts = normalized.split("/");
  for (let index = 0; index < rawParts.length; index += 1) {
    let part = rawParts[index];
    try {
      part = decodeURIComponent(part);
    } catch {
      return null;
    }
    if (part.includes("/") || part.includes("\\") || part === "." || part === "..") {
      return null;
    }
    if (part === "") {
      // Keep the leading slash of an absolute POSIX path. Any other empty
      // segment is a trailing slash or a double slash.
      if (index === 0) {
        parts.push("");
        continue;
      }
      return null;
    }
    parts.push(part);
  }
  const canonical = parts.join("/");
  const marker = canonical.indexOf(RENDER_CACHE_SEGMENT);
  if (marker < 0) {
    return null;
  }
  const rest = canonical.slice(marker + RENDER_CACHE_SEGMENT.length);
  if (!rest || rest.endsWith("/")) {
    return null;
  }
  return canonical;
}

export function renderCacheTileUrl(cachePath: string): string | null {
  const canonical = canonicalCachePath(cachePath);
  if (canonical === null) {
    return null;
  }
  return convertFileSrc(canonical);
}

export interface ResolvedTile {
  key: string;
  layerId: string;
  level: number;
  col: number;
  row: number;
  docRect: CanvasRect;
  cachePath: string;
  assetUrl: string;
}

export interface CullWorkerRequest {
  requestId: number;
  document: FakeCanvasDocument;
  viewport: ViewportTransform;
  overscanTiles?: number;
}

export interface CullWorkerResponse {
  requestId: number;
  level: number;
  scale: number;
  totalPyramidTilesAtLevel: number;
  visibleBoundsDoc: CanvasRect;
  tiles: ResolvedTile[];
  rejectedCount: number;
}

/**
 * Pure worker request handler: executes frustum culling and resolves each
 * visible tile's `asset://` URL while rejecting any path outside the
 * `~/.image-toolkit/cache/render/` scope.
 */
export function processCullRequest(request: CullWorkerRequest): CullWorkerResponse {
  const culled: FrustumCullResult = cullVisibleTiles(
    request.document,
    request.viewport,
    request.overscanTiles ?? 0,
  );
  const resolved: ResolvedTile[] = [];
  let rejectedCount = 0;

  for (const tile of culled.tiles) {
    const assetUrl = renderCacheTileUrl(tile.cachePath);
    if (assetUrl === null) {
      rejectedCount += 1;
      continue;
    }
    resolved.push({
      key: tile.key,
      layerId: tile.layerId,
      level: tile.level,
      col: tile.col,
      row: tile.row,
      docRect: tile.docRect,
      cachePath: tile.cachePath,
      assetUrl,
    });
  }

  return {
    requestId: request.requestId,
    level: culled.level,
    scale: culled.scale,
    totalPyramidTilesAtLevel: culled.totalPyramidTilesAtLevel,
    visibleBoundsDoc: culled.visibleBoundsDoc,
    tiles: resolved,
    rejectedCount,
  };
}

export interface WorkerMessagePortLike {
  postMessage(message: unknown): void;
  addEventListener(type: "message", listener: (event: { data: unknown }) => void): void;
  removeEventListener(type: "message", listener: (event: { data: unknown }) => void): void;
  terminate?(): void;
}

/**
 * Attaches the off-screen culling handler to a Worker global scope or
 * MessagePort-compatible channel.
 */
export function attachCullWorkerHost(scope: WorkerMessagePortLike): () => void {
  const onMessage = (event: { data: unknown }) => {
    const payload = event.data as CullWorkerRequest | null;
    if (!payload || typeof payload.requestId !== "number" || !payload.document || !payload.viewport) {
      return;
    }
    const response = processCullRequest(payload);
    scope.postMessage(response);
  };
  scope.addEventListener("message", onMessage);
  return () => {
    scope.removeEventListener("message", onMessage);
  };
}

/**
 * Creates an in-memory paired worker port (`clientPort` for the UI host and
 * `workerPort` with `attachCullWorkerHost` pre-installed) so tests and
 * fallback environments without a bundled Worker URL still exercise the exact
 * asynchronous message-passing contract.
 */
export function createLoopbackCullWorkerPort(): WorkerMessagePortLike {
  type Listener = (event: { data: unknown }) => void;
  const clientListeners = new Set<Listener>();
  const workerListeners = new Set<Listener>();
  let terminated = false;

  const workerPort: WorkerMessagePortLike = {
    postMessage(message: unknown) {
      if (terminated) {
        return;
      }
      queueMicrotask(() => {
        if (terminated) {
          return;
        }
        for (const listener of Array.from(clientListeners)) {
          listener({ data: message });
        }
      });
    },
    addEventListener(_type: "message", listener: Listener) {
      workerListeners.add(listener);
    },
    removeEventListener(_type: "message", listener: Listener) {
      workerListeners.delete(listener);
    },
  };

  const detachWorker = attachCullWorkerHost(workerPort);

  const clientPort: WorkerMessagePortLike = {
    postMessage(message: unknown) {
      if (terminated) {
        return;
      }
      queueMicrotask(() => {
        if (terminated) {
          return;
        }
        for (const listener of Array.from(workerListeners)) {
          listener({ data: message });
        }
      });
    },
    addEventListener(_type: "message", listener: Listener) {
      clientListeners.add(listener);
    },
    removeEventListener(_type: "message", listener: Listener) {
      clientListeners.delete(listener);
    },
    terminate() {
      terminated = true;
      detachWorker();
      clientListeners.clear();
      workerListeners.clear();
    },
  };

  return clientPort;
}

/**
 * Client wrapper around the off-screen culling worker that enforces monotonic
 * `requestId` ordering so stale responses from superseded pan/zoom frames are
 * dropped before reaching the renderer.
 */
export class CullWorkerClient {
  private readonly port: WorkerMessagePortLike;
  private latestRequestId = 0;
  private latestAppliedId = 0;
  private readonly subscribers = new Set<(response: CullWorkerResponse) => void>();
  private readonly handleMessage: (event: { data: unknown }) => void;

  constructor(port?: WorkerMessagePortLike) {
    this.port = port ?? createLoopbackCullWorkerPort();
    this.handleMessage = (event: { data: unknown }) => {
      const response = event.data as CullWorkerResponse | null;
      if (!response || typeof response.requestId !== "number") {
        return;
      }
      // Drop out-of-order / stale worker frames
      if (response.requestId < this.latestRequestId || response.requestId <= this.latestAppliedId) {
        return;
      }
      this.latestAppliedId = response.requestId;
      for (const subscriber of Array.from(this.subscribers)) {
        subscriber(response);
      }
    };
    this.port.addEventListener("message", this.handleMessage);
  }

  subscribe(listener: (response: CullWorkerResponse) => void): () => void {
    this.subscribers.add(listener);
    return () => {
      this.subscribers.delete(listener);
    };
  }

  requestCull(
    document: FakeCanvasDocument,
    viewport: ViewportTransform,
    overscanTiles = 0,
  ): number {
    this.latestRequestId += 1;
    const requestId = this.latestRequestId;
    const payload: CullWorkerRequest = {
      requestId,
      document,
      viewport,
      overscanTiles,
    };
    this.port.postMessage(payload);
    return requestId;
  }

  dispose(): void {
    this.port.removeEventListener("message", this.handleMessage);
    this.subscribers.clear();
    this.port.terminate?.();
  }
}
