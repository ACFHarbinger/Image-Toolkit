import { act, cleanup, fireEvent, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import {
  createInboundDrop,
  extractDomPaths,
  positionHitsTarget,
  subscribeTauriDrop,
  useFileDropTarget,
  type TauriDropEvent,
} from "../inbound";
import type { DropFs, DropFsStat } from "../paths";

function fileStat(bytes: number): DropFsStat {
  return {
    bytes,
    isFile: true,
    isDirectory: false,
    isSymlink: false,
    isSocket: false,
    isFifo: false,
  };
}

function makeFs(stats: Record<string, DropFsStat>): DropFs {
  return {
    stat: vi.fn(async (path: string) => {
      const entry = stats[path];
      if (!entry) throw new Error(`ENOENT: ${path}`);
      return entry;
    }),
    realpath: vi.fn(async (path: string) => {
      throw new Error(`EINVAL: not a symlink: ${path}`);
    }),
  };
}

/** Minimal DataTransfer stand-in (jsdom's implementation is a stub). */
function fakeDataTransfer(init: { files?: File[]; uriList?: string } = {}): DataTransfer {
  const store = new Map<string, string>();
  if (init.uriList !== undefined) store.set("text/uri-list", init.uriList);
  return {
    files: init.files ?? [],
    effectAllowed: "",
    types: Array.from(store.keys()),
    setData: (type: string, value: string) => {
      store.set(type, value);
    },
    getData: (type: string) => store.get(type) ?? "",
  } as unknown as DataTransfer;
}

const FS = makeFs({ "/pics/a.png": fileStat(10), "/pics/b.png": fileStat(20) });

// Mock the Tauri webview module: default behaviour mimics "no runtime"
// (getCurrentWebview throws, as it does under jsdom); tests flip
// `webviewState.mode` to "ok" to capture the subscribed handler(s).
const webviewState = vi.hoisted(() => ({
  mode: "throw" as "throw" | "ok",
  handler: null as null | ((event: { payload: unknown }) => void),
  handlers: [] as Array<(event: { payload: unknown }) => void>,
  unlistenCount: 0,
}));

vi.mock("@tauri-apps/api/webview", () => ({
  getCurrentWebview: () => {
    if (webviewState.mode === "throw") {
      throw new Error("no webview available (jsdom has no Tauri globals)");
    }
    return {
      onDragDropEvent: (handler: (event: { payload: unknown }) => void) => {
        webviewState.handler = handler;
        webviewState.handlers.push(handler);
        return Promise.resolve(() => {
          webviewState.unlistenCount += 1;
        });
      },
    };
  },
}));

/** Deliver a native event to every subscribed handler (multiple mounted targets). */
function emitTauriToAll(payload: unknown) {
  for (const handler of webviewState.handlers) {
    handler({ payload });
  }
}

const flushMicrotasks = () => act(() => new Promise<void>((resolve) => setTimeout(resolve, 0)));

afterEach(() => {
  cleanup();
  webviewState.mode = "throw";
  webviewState.handler = null;
  webviewState.handlers = [];
  webviewState.unlistenCount = 0;
});

describe("positionHitsTarget", () => {
  const rect = { left: 10, right: 20, top: 30, bottom: 40 };

  test("converts physical pixels to CSS pixels via the device pixel ratio", () => {
    expect(positionHitsTarget({ x: 30, y: 70 }, rect, 2)).toBe(true); // CSS (15, 35)
    expect(positionHitsTarget({ x: 42, y: 70 }, rect, 2)).toBe(false); // CSS (21, 35)
  });

  test("boundaries are inclusive and a bogus ratio falls back to 1", () => {
    expect(positionHitsTarget({ x: 10, y: 40 }, rect, 1)).toBe(true);
    expect(positionHitsTarget({ x: 9, y: 40 }, rect, 1)).toBe(false);
    expect(positionHitsTarget({ x: 10, y: 41 }, rect, 1)).toBe(false);
    expect(positionHitsTarget({ x: 10, y: 40 }, rect, 0)).toBe(true);
  });
});

describe("createInboundDrop", () => {
  test("ignores over/enter/leave without planning or calling onBatch", async () => {
    const onBatch = vi.fn();
    const handler = createInboundDrop(onBatch, { fs: FS });
    for (const type of ["over", "enter", "leave"] as const) {
      const summary = await handler.handleTauriEvent({ type, position: { x: 1, y: 2 }, paths: [] });
      expect(summary).toEqual({ ignored: true, accepted: 0, rejected: 0 });
    }
    expect(onBatch).not.toHaveBeenCalled();
  });

  test("drop events are planned and forwarded to onBatch", async () => {
    const onBatch = vi.fn();
    const handler = createInboundDrop(onBatch, { fs: FS });
    const summary = await handler.handleTauriEvent({
      type: "drop",
      position: { x: 3, y: 4 },
      paths: ["/pics/a.png", "/pics/b.png"],
    });
    expect(summary).toEqual({ ignored: false, accepted: 2, rejected: 0 });
    expect(onBatch).toHaveBeenCalledTimes(1);
    expect(onBatch.mock.calls[0][0]).toEqual([
      { path: "/pics/a.png", bytes: 10 },
      { path: "/pics/b.png", bytes: 20 },
    ]);
  });

  test("a drop where everything is rejected does not call onBatch", async () => {
    const onBatch = vi.fn();
    const handler = createInboundDrop(onBatch, { fs: FS });
    const summary = await handler.handleTauriEvent({
      type: "drop",
      position: { x: 0, y: 0 },
      paths: ["relative.png"],
    });
    expect(summary).toEqual({ ignored: false, accepted: 0, rejected: 1 });
    expect(onBatch).not.toHaveBeenCalled();
  });

  test("handleDomDrop accepts a string[] directly", async () => {
    const onBatch = vi.fn();
    const handler = createInboundDrop(onBatch, { fs: FS });
    const summary = await handler.handleDomDrop(["/pics/a.png"]);
    expect(summary).toEqual({ ignored: false, accepted: 1, rejected: 0 });
    expect(onBatch).toHaveBeenCalledWith([{ path: "/pics/a.png", bytes: 10 }]);
  });

  test("batch budgets flow through", async () => {
    const onBatch = vi.fn();
    const handler = createInboundDrop(onBatch, { fs: FS, maxItems: 1 });
    const summary = await handler.handleDomDrop(["/pics/a.png", "/pics/b.png"]);
    expect(summary).toEqual({ ignored: false, accepted: 1, rejected: 1 });
  });
});

describe("extractDomPaths", () => {
  test("prefers Chromium File.path when present", () => {
    const fileWithPath = Object.assign(new File(["x"], "a.png"), { path: "/native/a.png" });
    const dt = fakeDataTransfer({ files: [fileWithPath], uriList: "file:///ignored/b.png" });
    expect(extractDomPaths(dt)).toEqual(["/native/a.png"]);
  });

  test("falls back to file:// entries in text/uri-list", () => {
    const dt = fakeDataTransfer({
      uriList: "file:///pics/a.png\r\n# a comment\r\n\r\nfile://host/pics/b.png\r\nhttps://example.com/c.png\r\n",
    });
    expect(extractDomPaths(dt)).toEqual(["/pics/a.png", "/pics/b.png"]);
  });

  test("decodes URI-escaped path segments", () => {
    const dt = fakeDataTransfer({ uriList: "file:///pics/a%20b.png" });
    expect(extractDomPaths(dt)).toEqual(["/pics/a b.png"]);
  });

  test("returns [] for transfers without paths", () => {
    expect(extractDomPaths(fakeDataTransfer())).toEqual([]);
    const dt = fakeDataTransfer({ uriList: "https://example.com/x.png" });
    expect(extractDomPaths(dt)).toEqual([]);
  });
});

describe("subscribeTauriDrop", () => {
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
  });

  test("no-ops with a warning when no Tauri runtime exists", async () => {
    webviewState.mode = "throw";
    const received: TauriDropEvent[] = [];
    const unsubscribe = subscribeTauriDrop((evt) => received.push(evt));
    await flushMicrotasks();
    expect(warnSpy).toHaveBeenCalledTimes(1);
    expect(warnSpy.mock.calls[0][0]).toContain("DOM fallback remains active");
    unsubscribe();
    await flushMicrotasks();
    expect(received).toEqual([]);
  });

  test("normalizes payloads: drop keeps paths, over gets none", async () => {
    webviewState.mode = "ok";
    const received: TauriDropEvent[] = [];
    subscribeTauriDrop((evt) => received.push(evt));
    await flushMicrotasks();
    expect(webviewState.handler).not.toBeNull();
    act(() => {
      webviewState.handler?.({ payload: { type: "drop", paths: ["/pics/a.png"], position: { x: 5, y: 6 } } });
      webviewState.handler?.({ payload: { type: "over", position: { x: 7, y: 8 } } });
    });
    expect(received).toEqual([
      { type: "drop", position: { x: 5, y: 6 }, paths: ["/pics/a.png"] },
      { type: "over", position: { x: 7, y: 8 }, paths: [] },
    ]);
  });

  test("unsubscribe silences late events and unlistens", async () => {
    webviewState.mode = "ok";
    const received: TauriDropEvent[] = [];
    const unsubscribe = subscribeTauriDrop((evt) => received.push(evt));
    await flushMicrotasks();
    unsubscribe();
    expect(webviewState.unlistenCount).toBe(1);
    act(() => {
      webviewState.handler?.({ payload: { type: "drop", paths: ["/pics/a.png"], position: { x: 0, y: 0 } } });
    });
    expect(received).toEqual([]);
  });

  test("unsubscribing before the subscription settles does not leak listeners", async () => {
    webviewState.mode = "ok";
    const unsubscribe = subscribeTauriDrop(() => {});
    unsubscribe();
    await flushMicrotasks();
    expect(webviewState.unlistenCount).toBe(1);
  });
});

/** Mount useFileDropTarget against a real element (no JSX: this file stays .ts). */
function mountTarget(options: {
  fs: DropFs;
  onBatch: (batch: readonly { path: string; bytes: number }[]) => void;
  enabled?: boolean;
  rect?: { left: number; right: number; top: number; bottom: number };
}) {
  const el = document.createElement("div");
  document.body.appendChild(el);
  if (options.rect) {
    // jsdom reports an all-zero rect; give the target a real hit area.
    const rect = options.rect;
    el.getBoundingClientRect = () =>
      ({
        left: rect.left,
        right: rect.right,
        top: rect.top,
        bottom: rect.bottom,
        x: rect.left,
        y: rect.top,
        width: rect.right - rect.left,
        height: rect.bottom - rect.top,
        toJSON: () => ({}),
      }) as DOMRect;
  }
  const ref = { current: el };
  const view = renderHook(() =>
    useFileDropTarget(ref, { fs: options.fs, onBatch: options.onBatch, enabled: options.enabled }),
  );
  return {
    el,
    unmount: () => {
      view.unmount();
      el.remove();
    },
  };
}

describe("useFileDropTarget", () => {
  beforeEach(() => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
  });

  test("preventDefaults dragover so the browser allows the drop", () => {
    webviewState.mode = "ok";
    const onBatch = vi.fn();
    const { el, unmount } = mountTarget({ fs: FS, onBatch });
    const event = new Event("dragover", { bubbles: true, cancelable: true });
    expect(el.dispatchEvent(event)).toBe(false); // false => default was prevented
    unmount();
  });

  test("DOM drop on the element is planned through to onBatch", async () => {
    webviewState.mode = "ok";
    const onBatch = vi.fn();
    const { el, unmount } = mountTarget({ fs: FS, onBatch });
    fireEvent.drop(el, { dataTransfer: fakeDataTransfer({ uriList: "file:///pics/a.png" }) });
    await vi.waitFor(() => {
      expect(onBatch).toHaveBeenCalledWith([{ path: "/pics/a.png", bytes: 10 }]);
    });
    unmount();
  });

  test("Tauri events flow through the hook to onBatch", async () => {
    webviewState.mode = "ok";
    const onBatch = vi.fn();
    const target = mountTarget({ fs: FS, onBatch, rect: { left: 0, right: 100, top: 0, bottom: 100 } });
    await flushMicrotasks();
    expect(webviewState.handler).not.toBeNull();
    act(() => {
      webviewState.handler?.({ payload: { type: "drop", paths: ["/pics/b.png"], position: { x: 1, y: 1 } } });
    });
    await vi.waitFor(() => {
      expect(onBatch).toHaveBeenCalledWith([{ path: "/pics/b.png", bytes: 20 }]);
    });
    target.unmount();
  });

  test("native drops outside the target rect are ignored", async () => {
    webviewState.mode = "ok";
    const onBatch = vi.fn();
    const target = mountTarget({ fs: FS, onBatch, rect: { left: 0, right: 100, top: 0, bottom: 100 } });
    await flushMicrotasks();
    act(() => {
      webviewState.handler?.({ payload: { type: "drop", paths: ["/pics/a.png"], position: { x: 150, y: 1 } } });
    });
    await flushMicrotasks();
    expect(onBatch).not.toHaveBeenCalled();
    target.unmount();
  });

  test("native drop position is physical pixels, rect is CSS pixels", async () => {
    webviewState.mode = "ok";
    const onBatch = vi.fn();
    const dpr = Object.getOwnPropertyDescriptor(window, "devicePixelRatio");
    Object.defineProperty(window, "devicePixelRatio", { value: 2, configurable: true });
    try {
      const target = mountTarget({ fs: FS, onBatch, rect: { left: 40, right: 60, top: 0, bottom: 100 } });
      await flushMicrotasks();
      // Physical (100, 50) -> CSS (50, 50): inside the 40..60 rect only after /DPR.
      act(() => {
        webviewState.handler?.({ payload: { type: "drop", paths: ["/pics/a.png"], position: { x: 100, y: 50 } } });
      });
      await vi.waitFor(() => {
        expect(onBatch).toHaveBeenCalledWith([{ path: "/pics/a.png", bytes: 10 }]);
      });
      onBatch.mockClear();
      // Physical (200, 50) -> CSS (100, 50): outside.
      act(() => {
        webviewState.handler?.({ payload: { type: "drop", paths: ["/pics/a.png"], position: { x: 200, y: 50 } } });
      });
      await flushMicrotasks();
      expect(onBatch).not.toHaveBeenCalled();
      target.unmount();
    } finally {
      if (dpr) Object.defineProperty(window, "devicePixelRatio", dpr);
    }
  });

  test("multiple mounted targets: only the hit target receives the batch", async () => {
    webviewState.mode = "ok";
    const onBatchA = vi.fn();
    const onBatchB = vi.fn();
    const a = mountTarget({ fs: FS, onBatch: onBatchA, rect: { left: 0, right: 100, top: 0, bottom: 100 } });
    // Mount sequentially: vitest's mocked dynamic import mishandles two
    // concurrent importers in one test (real ESM caches in-flight imports).
    await flushMicrotasks();
    const b = mountTarget({ fs: FS, onBatch: onBatchB, rect: { left: 200, right: 300, top: 0, bottom: 100 } });
    await flushMicrotasks();
    expect(webviewState.handlers).toHaveLength(2);
    act(() => {
      emitTauriToAll({ type: "drop", paths: ["/pics/a.png"], position: { x: 250, y: 50 } });
    });
    await vi.waitFor(() => {
      expect(onBatchB).toHaveBeenCalledWith([{ path: "/pics/a.png", bytes: 10 }]);
    });
    await flushMicrotasks();
    expect(onBatchA).not.toHaveBeenCalled();
    a.unmount();
    b.unmount();
  });

  test("enabled:false skips both subscriptions", async () => {
    webviewState.mode = "ok";
    const onBatch = vi.fn();
    const { el, unmount } = mountTarget({ fs: FS, onBatch, enabled: false });
    await flushMicrotasks();
    expect(webviewState.handler).toBeNull();
    fireEvent.drop(el, { dataTransfer: fakeDataTransfer({ uriList: "file:///pics/a.png" }) });
    expect(onBatch).not.toHaveBeenCalled();
    unmount();
  });

  test("unmount removes DOM listeners and unsubscribes Tauri events", async () => {
    webviewState.mode = "ok";
    const onBatch = vi.fn();
    const { el, unmount } = mountTarget({ fs: FS, onBatch });
    await flushMicrotasks();
    unmount();
    expect(webviewState.unlistenCount).toBe(1);
    // Late Tauri events after unmount are swallowed.
    act(() => {
      webviewState.handler?.({ payload: { type: "drop", paths: ["/pics/a.png"], position: { x: 0, y: 0 } } });
    });
    // DOM events on the detached node no longer reach the pipeline either.
    fireEvent.drop(el, { dataTransfer: fakeDataTransfer({ uriList: "file:///pics/a.png" }) });
    expect(onBatch).not.toHaveBeenCalled();
  });

  test("falls back to DOM-only wiring without a Tauri runtime", async () => {
    webviewState.mode = "throw";
    const onBatch = vi.fn();
    const { el, unmount } = mountTarget({ fs: FS, onBatch });
    await flushMicrotasks();
    expect(webviewState.handler).toBeNull();
    fireEvent.drop(el, { dataTransfer: fakeDataTransfer({ uriList: "file:///pics/a.png" }) });
    await vi.waitFor(() => {
      expect(onBatch).toHaveBeenCalledTimes(1);
    });
    unmount();
  });
});
