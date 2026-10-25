import React, { useState } from "react";

export interface PreviewItem {
  readonly path: string;
  readonly exists: boolean;
  readonly width: number;
  readonly height: number;
  readonly animated: boolean;
  readonly error: string;
}

export interface PreviewFrame {
  readonly path: string;
  readonly width: number;
  readonly height: number;
  readonly png_base64: string;
  readonly error: string;
}

export interface PreviewDifference {
  readonly available: boolean;
  readonly mean_abs: number;
  readonly reason: string;
  readonly png_base64: string;
}

export interface PreviewClient {
  libraryPreviewDescribe(params: { paths: string[] }): Promise<{ items: PreviewItem[] }>;
  libraryPreviewFrame(params: { path: string }): Promise<PreviewFrame>;
  libraryPreviewDifference(params: {
    left: string;
    right: string;
    boost: 1 | 2 | 4 | 8;
  }): Promise<PreviewDifference>;
}

type Mode = "preview" | "compare" | "drag";

const ZOOM_STEP = 0.1;

function splitPaths(raw: string): string[] {
  return raw.split("\n").map((line) => line.trim()).filter((line) => line.length > 0);
}

/** Preview, compare, and drag-preview pop-out (#895). Pixels come from the sidecar. */
export function LibraryPreviewWindow({ client }: { readonly client: PreviewClient }): React.ReactElement {
  const [rawPaths, setRawPaths] = useState("");
  const [items, setItems] = useState<PreviewItem[]>([]);
  const [frames, setFrames] = useState<Record<string, PreviewFrame>>({});
  const [index, setIndex] = useState(0);
  const [mode, setMode] = useState<Mode>("preview");
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [opacity, setOpacity] = useState(50);
  const [dragAt, setDragAt] = useState<{ x: number; y: number } | null>(null);
  const [difference, setDifference] = useState<PreviewDifference | null>(null);
  const [notice, setNotice] = useState("");

  const current = items[index];

  const inspect = async () => {
    const paths = splitPaths(rawPaths);
    if (paths.length === 0) {
      setItems([]);
      setNotice("Add one path per line.");
      return;
    }
    const described = await client.libraryPreviewDescribe({ paths });
    const nextFrames: Record<string, PreviewFrame> = {};
    for (const item of described.items) {
      if (item.exists && item.error === "") {
        nextFrames[item.path] = await client.libraryPreviewFrame({ path: item.path });
      }
    }
    setItems(described.items);
    setFrames(nextFrames);
    setIndex(0);
    setDifference(null);
    setNotice("");
  };

  const showDifference = async () => {
    if (items.length < 2) {
      setNotice("Compare needs two paths.");
      return;
    }
    const result = await client.libraryPreviewDifference({
      left: items[0].path,
      right: items[1].path,
      boost: 1,
    });
    setDifference(result);
    setMode("compare");
  };

  const frameFor = (path: string | undefined) => (path ? frames[path] : undefined);

  return (
    <main data-testid="library-preview-window" className="flex min-h-screen flex-col gap-4 p-4">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold">Image preview</h1>
        {(["preview", "compare", "drag"] as const).map((next) => (
          <button key={next} type="button" data-testid={`mode-${next}`} onClick={() => setMode(next)}>
            {next}
          </button>
        ))}
      </header>
      <textarea
        data-testid="preview-paths"
        value={rawPaths}
        onChange={(event) => setRawPaths(event.target.value)}
        rows={3}
        className="w-full rounded border p-2 font-mono text-sm"
        aria-label="Image paths"
      />
      <button type="button" data-testid="preview-inspect" onClick={() => void inspect()}>
        Inspect
      </button>
      {notice ? <p role="status">{notice}</p> : null}
      {mode === "preview" && current ? (
        <section data-testid="preview-pane">
          <p data-testid="preview-path">{current.path}</p>
          {current.error ? <p role="alert">{current.error}</p> : null}
          {current.animated ? <p>Animation plays the first frame.</p> : null}
          <FrameImage frame={frameFor(current.path)} zoom={zoom} rotation={rotation} />
          <div className="flex gap-2">
            <button type="button" data-testid="preview-prev" onClick={() => setIndex((value) => Math.max(0, value - 1))}>
              Previous
            </button>
            <button
              type="button"
              data-testid="preview-next"
              onClick={() => setIndex((value) => Math.min(items.length - 1, value + 1))}
            >
              Next
            </button>
            <button type="button" data-testid="preview-zoom-in" onClick={() => setZoom((value) => value + ZOOM_STEP)}>
              Zoom in
            </button>
            <button type="button" data-testid="preview-rotate" onClick={() => setRotation((value) => (value + 90) % 360)}>
              Rotate
            </button>
          </div>
          <p data-testid="preview-zoom">{Math.round(zoom * 100)}%</p>
        </section>
      ) : null}
      {mode === "compare" && items.length >= 2 ? (
        <section data-testid="compare-pane" className="flex flex-col gap-2">
          <div className="flex gap-4">
            <FrameImage frame={frameFor(items[0].path)} zoom={zoom} rotation={0} />
            <FrameImage frame={frameFor(items[1].path)} zoom={zoom} rotation={0} />
          </div>
          <label>
            Overlay
            <input
              data-testid="compare-opacity"
              type="range"
              min={0}
              max={100}
              value={opacity}
              onChange={(event) => setOpacity(Number(event.target.value))}
            />
          </label>
          <div className="relative h-40">
            <FrameImage frame={frameFor(items[1].path)} zoom={1} rotation={0} />
            <div style={{ opacity: opacity / 100 }}>
              <FrameImage frame={frameFor(items[0].path)} zoom={1} rotation={0} />
            </div>
          </div>
          <button type="button" data-testid="compare-difference" onClick={() => void showDifference()}>
            Difference
          </button>
          {difference ? (
            <div data-testid="difference-result">
              {difference.available ? (
                <>
                  <p>Mean absolute difference {difference.mean_abs.toFixed(2)}</p>
                  <img alt="Difference map" src={`data:image/png;base64,${difference.png_base64}`} />
                </>
              ) : (
                <p role="alert">{difference.reason}</p>
              )}
            </div>
          ) : null}
        </section>
      ) : null}
      {mode === "drag" && current ? (
        <section
          data-testid="drag-source"
          className="inline-flex w-fit"
          onPointerDown={(event) => setDragAt({ x: event.clientX + 10, y: event.clientY + 10 })}
          onPointerMove={(event) => {
            if (dragAt) setDragAt({ x: event.clientX + 10, y: event.clientY + 10 });
          }}
          onPointerUp={() => setDragAt(null)}
        >
          <FrameImage frame={frameFor(current.path)} zoom={0.5} rotation={0} />
          {dragAt ? (
            <div
              data-testid="drag-preview"
              className="pointer-events-none fixed"
              style={{ left: dragAt.x, top: dragAt.y }}
            >
              <FrameImage frame={frameFor(current.path)} zoom={0.25} rotation={0} />
            </div>
          ) : null}
        </section>
      ) : null}
    </main>
  );
}

function FrameImage({
  frame,
  zoom,
  rotation,
}: {
  readonly frame: PreviewFrame | undefined;
  readonly zoom: number;
  readonly rotation: number;
}): React.ReactElement | null {
  if (!frame || frame.error || !frame.png_base64) return null;
  return (
    <img
      alt={frame.path}
      data-testid="preview-frame"
      src={`data:image/png;base64,${frame.png_base64}`}
      style={{ transform: `scale(${zoom}) rotate(${rotation}deg)` }}
    />
  );
}
