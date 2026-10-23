import { createElement } from "react";
import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import {
  applyDragSource,
  buildDownloadUrlPayload,
  getNativeDragOut,
  registerNativeDragOut,
  useDragSource,
  type OutboundDragItem,
} from "../outbound";

afterEach(() => {
  cleanup();
  registerNativeDragOut(null);
});

/** Minimal DataTransfer recording setData writes. */
function recordingDataTransfer(): DataTransfer & { dump: () => Record<string, string> } {
  const store = new Map<string, string>();
  const dt = {
    effectAllowed: "",
    setData: (type: string, value: string) => {
      store.set(type, value);
    },
    getData: (type: string) => store.get(type) ?? "",
    dump: () => Object.fromEntries(store),
  };
  return dt as unknown as DataTransfer & { dump: () => Record<string, string> };
}

const ITEMS: readonly OutboundDragItem[] = [
  { mime: "image/png", filename: "a.png", blobUrl: "blob:http://localhost/uuid-a" },
  { mime: "image/jpeg", filename: "b.jpg", blobUrl: "blob:http://localhost/uuid-b" },
];

describe("buildDownloadUrlPayload", () => {
  test("builds a mime:filename:url entry", () => {
    expect(buildDownloadUrlPayload("image/png", "a.png", "blob:x")).toBe("image/png:a.png:blob:x");
  });

  test("blob URLs keep their colons (only the filename is sanitized)", () => {
    const payload = buildDownloadUrlPayload("image/png", "a.png", "blob:http://localhost/1");
    expect(payload).toBe("image/png:a.png:blob:http://localhost/1");
  });

  test("sanitizes colons, slashes and newlines in the filename", () => {
    expect(buildDownloadUrlPayload("image/png", "a:b/c\r\n.png", "blob:x")).toBe("image/png:a_b_c_.png:blob:x");
  });

  test("falls back to octet-stream for an empty mime", () => {
    expect(buildDownloadUrlPayload("", "a.bin", "blob:x")).toBe("application/octet-stream:a.bin:blob:x");
  });
});

describe("applyDragSource", () => {
  test("sets a single DownloadURL tuple plus the full uri-list, and allows copy", () => {
    const dt = recordingDataTransfer();
    applyDragSource(dt, ITEMS);
    // Chromium accepts exactly one mime:filename:url tuple; extra items would
    // be swallowed into the first URL, so only the first rides DownloadURL.
    expect(dt.dump()).toEqual({
      DownloadURL: "image/png:a.png:blob:http://localhost/uuid-a",
      "text/uri-list": "blob:http://localhost/uuid-a\r\nblob:http://localhost/uuid-b",
    });
    expect(dt.effectAllowed).toBe("copy");
  });

  test("single item sets both payload types for that item", () => {
    const dt = recordingDataTransfer();
    applyDragSource(dt, [ITEMS[1]]);
    expect(dt.dump()).toEqual({
      DownloadURL: "image/jpeg:b.jpg:blob:http://localhost/uuid-b",
      "text/uri-list": "blob:http://localhost/uuid-b",
    });
  });

  test("no-ops on an empty item list", () => {
    const dt = recordingDataTransfer();
    applyDragSource(dt, []);
    expect(dt.dump()).toEqual({});
    expect(dt.effectAllowed).toBe("");
  });
});

describe("useDragSource", () => {
  // createElement instead of JSX keeps this file .ts per the module layout.
  function Source(props: { items: readonly OutboundDragItem[]; onStart?: () => void; onEnd?: () => void }) {
    const binding = useDragSource(props.items, { onDragStart: props.onStart, onDragEnd: props.onEnd });
    return createElement(
      "div",
      { "data-testid": "source", ...binding },
      String(binding.dragging),
    );
  }

  test("spreads draggable and applies the drag source on dragstart", () => {
    const dt = recordingDataTransfer();
    const onStart = vi.fn();
    const { container } = render(createElement(Source, { items: ITEMS, onStart }));
    const source = container.querySelector("[data-testid='source']") as HTMLElement;
    expect(source.draggable).toBe(true);
    expect(source.textContent).toBe("false");
    fireEvent.dragStart(source, { dataTransfer: dt });
    expect(dt.getData("DownloadURL")).toContain("image/png:a.png:blob:http://localhost/uuid-a");
    expect(dt.getData("text/uri-list")).toContain("blob:http://localhost/uuid-b");
    expect(onStart).toHaveBeenCalledTimes(1);
    expect(source.textContent).toBe("true");
  });

  test("dragend clears dragging and invokes the callback", () => {
    const dt = recordingDataTransfer();
    const onEnd = vi.fn();
    const { container } = render(createElement(Source, { items: ITEMS, onEnd }));
    const source = container.querySelector("[data-testid='source']") as HTMLElement;
    fireEvent.dragStart(source, { dataTransfer: dt });
    expect(source.textContent).toBe("true");
    fireEvent.dragEnd(source, { dataTransfer: dt });
    expect(source.textContent).toBe("false");
    expect(onEnd).toHaveBeenCalledTimes(1);
  });

  test("reads the freshest item list at drag time", () => {
    const dt = recordingDataTransfer();
    const view = render(createElement(Source, { items: ITEMS }));
    view.rerender(createElement(Source, { items: [{ mime: "image/gif", filename: "c.gif", blobUrl: "blob:z" }] }));
    const source = view.container.querySelector("[data-testid='source']") as HTMLElement;
    fireEvent.dragStart(source, { dataTransfer: dt });
    expect(dt.getData("DownloadURL")).toBe("image/gif:c.gif:blob:z");
  });
});

describe("NativeDragOut seam", () => {
  test("no handle is registered by default", () => {
    expect(getNativeDragOut()).toBeNull();
  });

  test("register/get round-trips a handle", async () => {
    const calls: string[][] = [];
    registerNativeDragOut({ startDrag: async (paths) => void calls.push(paths) });
    const handle = getNativeDragOut();
    expect(handle).not.toBeNull();
    await handle?.startDrag(["/out/a.png"]);
    expect(calls).toEqual([["/out/a.png"]]);
  });

  test("re-registering replaces the handle; null clears it", async () => {
    const first = vi.fn();
    const second = vi.fn();
    registerNativeDragOut({ startDrag: first });
    registerNativeDragOut({ startDrag: second });
    await getNativeDragOut()?.startDrag(["/x.png"]);
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
    registerNativeDragOut(null);
    expect(getNativeDragOut()).toBeNull();
  });
});
