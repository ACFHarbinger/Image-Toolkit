import React, { useRef, useState } from "react";

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
type DiffBoost = 1 | 2 | 4 | 8;

const ZOOM_STEP = 0.1;
const ZOOM_MIN = 0.1;
const ZOOM_MAX = 5;
const DIFF_BOOSTS: readonly DiffBoost[] = [1, 2, 4, 8];

function clampZoom(value: number): number {
  if (value < ZOOM_MIN) return ZOOM_MIN;
  if (value > ZOOM_MAX) return ZOOM_MAX;
  return value;
}

function adjustZoom(current: number, delta: number): number {
  return clampZoom(current + delta);
}

/** One axis of the pane, clamped to 0.1–5. A non-positive measure stays at 1×. */
function fitAxis(usable: number, imageSize: number): number {
  if (usable <= 0 || imageSize <= 0) return 1;
  return clampZoom(usable / imageSize);
}

function wrapDegrees(degrees: number): number {
  return ((degrees % 360) + 360) % 360;
}

/** Classic fit: pane size minus control margins, never above 1×. */
function fitScale(
  pane: Pick<HTMLElement, "clientWidth" | "clientHeight"> | null,
  imageWidth: number,
  imageHeight: number,
): number {
  const usableWidth = (pane?.clientWidth ?? 0) - 100;
  const usableHeight = (pane?.clientHeight ?? 0) - 50;
  if (usableWidth <= 0 || usableHeight <= 0 || imageWidth === 0 || imageHeight === 0) {
    return 1;
  }
  return Math.min(usableWidth / imageWidth, usableHeight / imageHeight, 1);
}

function diffBoost(value: string): DiffBoost {
  const parsed = Number(value);
  if (parsed === 2 || parsed === 4 || parsed === 8) {
    return parsed;
  }
  return 1;
}

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
  const [overlayFlipped, setOverlayFlipped] = useState(false);
  const [dragAt, setDragAt] = useState<{ x: number; y: number } | null>(null);
  const [difference, setDifference] = useState<PreviewDifference | null>(null);
  const [boost, setBoost] = useState<DiffBoost>(1);
  const [notice, setNotice] = useState("");
  const paneRef = useRef<HTMLElement>(null);

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
      boost,
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
        <section ref={paneRef} data-testid="preview-pane">
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
            <button type="button" data-testid="preview-zoom-in" onClick={() => setZoom((value) => adjustZoom(value, ZOOM_STEP))}>
              Zoom in
            </button>
            <button type="button" data-testid="preview-zoom-out" onClick={() => setZoom((value) => adjustZoom(value, -ZOOM_STEP))}>
              Zoom out
            </button>
            <button
              type="button"
              data-testid="preview-fit"
              onClick={() => {
                const frame = frameFor(current.path);
                setZoom(fitScale(paneRef.current, frame?.width ?? 0, frame?.height ?? 0));
              }}
            >
              Fit
            </button>
            <button
              type="button"
              data-testid="preview-fit-width"
              onClick={() => {
                const frame = frameFor(current.path);
                setZoom(fitAxis((paneRef.current?.clientWidth ?? 0) - 100, frame?.width ?? 0));
              }}
            >
              Fit to width
            </button>
            <button
              type="button"
              data-testid="preview-fit-height"
              onClick={() => {
                const frame = frameFor(current.path);
                setZoom(fitAxis((paneRef.current?.clientHeight ?? 0) - 50, frame?.height ?? 0));
              }}
            >
              Fit to height
            </button>
            <button type="button" data-testid="preview-actual-size" onClick={() => setZoom(1)}>
              Actual size
            </button>
            <button type="button" data-testid="preview-rotate" onClick={() => setRotation((value) => (value + 90) % 360)}>
              Rotate
            </button>
            <button
              type="button"
              data-testid="preview-rotate-ccw"
              onClick={() => setRotation((value) => wrapDegrees(value - 90))}
            >
              Rotate counter-clockwise
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
          <button type="button" data-testid="compare-flip" onClick={() => setOverlayFlipped((value) => !value)}>
            Flip overlay
          </button>
          <div className="relative h-40" data-testid="compare-overlay">
            <div className="absolute inset-0">
              <FrameImage frame={frameFor((overlayFlipped ? items[0] : items[1]).path)} zoom={1} rotation={0} />
            </div>
            <div className="absolute inset-0" style={{ opacity: opacity / 100 }}>
              <FrameImage frame={frameFor((overlayFlipped ? items[1] : items[0]).path)} zoom={1} rotation={0} />
            </div>
          </div>
          <label>
            Diff amplification
            <select value={boost} onChange={(event) => setBoost(diffBoost(event.target.value))}>
              {DIFF_BOOSTS.map((level) => (
                <option key={level} value={level}>
                  {level}×
                </option>
              ))}
            </select>
          </label>
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
