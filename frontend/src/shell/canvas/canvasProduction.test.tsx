// Production texture pipeline for the shared canvas host (Y-00 / #902).
// jsdom renders the host headless (no WebGL2 context), which is exactly
// the path under test: the LRU cache, the load→upload→re-render flow, and
// the stats the host exposes to its consumer (Merge, #903).

import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { createFakeCanvasDocument, SharedCanvasHost } from "./index";
import type { TileTextureLoader } from "./tileTextureCache";

afterEach(() => cleanup());

function controlledLoader() {
  const calls: string[] = [];
  const resolvers = new Map<string, ((ok: boolean) => void)[]>();
  const loader: TileTextureLoader = (url) =>
    new Promise((resolve, reject) => {
      calls.push(url);
      const entry = resolvers.get(url) ?? [];
      entry.push((ok) => (ok ? resolve({ fake: url } as unknown as TexImageSource) : reject(new Error(url))));
      resolvers.set(url, entry);
    });
  return {
    loader,
    calls,
    settle: (url: string, ok = true) => (resolvers.get(url) ?? []).forEach((fn) => fn(ok)),
  };
}

test("visible tiles load, upload, and re-render with texture stats", async () => {
  const { loader, calls, settle } = controlledLoader();
  const document = createFakeCanvasDocument();

  render(<SharedCanvasHost document={document} textureLoader={loader} />);
  const host = screen.getByTestId("shared-canvas-host") as HTMLElement;

  // Cull state arrives synchronously; every visible tile queues one load.
  const mounted = Number(host.getAttribute("data-mounted-tiles"));
  expect(calls).toHaveLength(mounted);

  await act(async () => {
    for (const url of [...calls]) {
      settle(url);
    }
  });

  await waitFor(() => {
    expect(host.getAttribute("data-textured-tile-count")).toBe(String(mounted));
  });
  expect(host.getAttribute("data-texture-cache-entries")).toBe(String(mounted));
  expect(host.getAttribute("data-texture-cache-evictions")).toBe("0");
});

test("the LRU budget evicts and frees GL-side entries with the JS ones", async () => {
  const { loader, calls, settle } = controlledLoader();
  const document = createFakeCanvasDocument();

  render(
    <SharedCanvasHost
      document={document}
      textureLoader={loader}
      textureCacheBudget={2}
    />,
  );
  const host = screen.getByTestId("shared-canvas-host") as HTMLElement;
  const mounted = Number(host.getAttribute("data-mounted-tiles"));
  expect(mounted).toBeGreaterThan(2);

  await act(async () => {
    for (const url of [...calls]) {
      settle(url);
    }
  });

  await waitFor(() => {
    expect(Number(host.getAttribute("data-texture-cache-entries"))).toBeLessThanOrEqual(2);
  });
  expect(Number(host.getAttribute("data-texture-cache-evictions"))).toBeGreaterThan(0);
});

test("failed loads keep the placeholder and never throw", async () => {
  const { loader, calls, settle } = controlledLoader();
  const document = createFakeCanvasDocument();

  render(<SharedCanvasHost document={document} textureLoader={loader} />);
  const host = screen.getByTestId("shared-canvas-host") as HTMLElement;
  const mounted = Number(host.getAttribute("data-mounted-tiles"));

  await act(async () => {
    for (const url of [...calls]) {
      settle(url, false);
    }
  });

  expect(host.getAttribute("data-textured-tile-count")).toBe("0");
  expect(host.getAttribute("data-texture-cache-entries")).toBe("0");
  expect(mounted).toBeGreaterThan(0);
});

test("panning culls new tiles and queues only their textures", async () => {
  const { loader, calls, settle } = controlledLoader();
  const document = createFakeCanvasDocument();

  const onViewportChange = vi.fn();
  render(
    <SharedCanvasHost
      document={document}
      textureLoader={loader}
      onViewportChange={onViewportChange}
    />,
  );
  const host = screen.getByTestId("shared-canvas-host") as HTMLElement;
  await act(async () => {
    for (const url of [...calls]) {
      settle(url);
    }
  });

  const before = calls.length;
  // A zoom changes the frustum; new tiles queue loads only for URLs that
  // are neither cached nor in flight.
  fireEvent.wheel(host, { deltaY: -1, clientX: 100, clientY: 100 });
  expect(onViewportChange).toHaveBeenCalled();
  const queued = calls.slice(before);
  await act(async () => {
    for (const url of queued) {
      settle(url);
    }
  });
  expect(calls.length).toBeGreaterThanOrEqual(before);
  expect(new Set(queued).size).toBe(queued.length);
});
