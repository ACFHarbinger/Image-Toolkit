import React, { useState } from "react";
import { MergeCanvasBoard } from "../../components/common/MergeCanvasBoard";
import { ThumbnailGallery } from "../../components/common/ThumbnailGallery";

export interface MergeResult {
  readonly written: boolean;
  readonly output_path: string;
  readonly width: number;
  readonly height: number;
  readonly preview_png_base64: string;
  readonly error: string;
}

export interface MergePlacement {
  readonly path: string;
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

export interface MergeClient {
  mergeConcatenate(params: {
    paths: string[];
    output_path: string;
    direction: "horizontal" | "vertical";
    spacing: number;
    align: "start" | "center" | "end";
  }): Promise<MergeResult>;
  mergePlace(params: { placements: MergePlacement[]; output_path: string }): Promise<MergeResult>;
}

type QueueItem = MergePlacement;

/** Ordered queue. Placement stores a rectangle per image; other modes concatenate. */
export function MergeView({ hostClient }: { readonly hostClient: MergeClient }): React.ReactElement {
  const [draft, setDraft] = useState("");
  const [items, setItems] = useState<QueueItem[]>([]);
  const [outputPath, setOutputPath] = useState("");
  const [mode, setMode] = useState<"horizontal" | "vertical" | "placement">("horizontal");
  const [spacing, setSpacing] = useState(0);
  const [align, setAlign] = useState<"start" | "center" | "end">("start");
  const [result, setResult] = useState<MergeResult | null>(null);
  const [error, setError] = useState("");
  const [selectedPath, setSelectedPath] = useState("");

  function addItem() {
    const path = draft.trim();
    if (!path) {
      return;
    }
    setItems((current) => [
      ...current,
      { path, x: 0, y: current.length * 32, width: 32, height: 32 },
    ]);
    setDraft("");
  }

  function updateItem(index: number, patch: Partial<QueueItem>) {
    setItems((current) => current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)));
  }

  function moveItem(index: number, direction: -1 | 1) {
    setItems((current) => {
      const target = index + direction;
      if (target < 0 || target >= current.length) {
        return current;
      }
      const next = [...current];
      const [item] = next.splice(index, 1);
      next.splice(target, 0, item);
      return next;
    });
  }

  function removeItem(index: number) {
    setItems((current) => current.filter((_, itemIndex) => itemIndex !== index));
  }

  function moveTile(path: string, x: number, y: number) {
    setItems((current) => current.map((item) => (item.path === path ? { ...item, x, y } : item)));
  }

  function resizeTile(path: string, width: number, height: number) {
    const nextWidth = Math.max(1, width);
    const nextHeight = Math.max(1, height);
    setItems((current) =>
      current.map((item) => (item.path === path ? { ...item, width: nextWidth, height: nextHeight } : item)),
    );
  }

  function removeTile(path: string) {
    setItems((current) => {
      const index = current.findIndex((item) => item.path === path);
      if (index < 0) {
        return current;
      }
      return current.filter((_, itemIndex) => itemIndex !== index);
    });
  }

  async function onSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setError("");
    try {
      const next =
        mode === "placement"
          ? await hostClient.mergePlace({
              placements: items.map((item) => ({
                path: item.path,
                x: item.x,
                y: item.y,
                width: item.width,
                height: item.height,
              })),
              output_path: outputPath,
            })
          : await hostClient.mergeConcatenate({
              paths: items.map((item) => item.path),
              output_path: outputPath,
              direction: mode,
              spacing,
              align,
            });
      setResult(next);
      if (!next.written) {
        setError(next.error);
      }
    } catch (exc) {
      setResult(null);
      setError(exc instanceof Error ? exc.message : "merge failed");
    }
  }

  return (
    <form data-testid="merge-view" onSubmit={onSubmit}>
      <ThumbnailGallery
        multiple={false}
        directoryLabel="Image directory"
        selected={draft ? [draft] : []}
        onSelectedChange={(paths) => setDraft(paths[0] ?? "")}
      />
      <label>
        Add image
        <input value={draft} onChange={(event) => setDraft(event.target.value)} />
      </label>
      <button type="button" onClick={addItem}>
        Add
      </button>
      <ol>
        {items.map((item, index) => (
          <li key={`${item.path}:${index}`}>
            <span>{item.path}</span>
            <button type="button" onClick={() => moveItem(index, -1)} disabled={index === 0}>
              Up
            </button>
            <button type="button" onClick={() => moveItem(index, 1)} disabled={index === items.length - 1}>
              Down
            </button>
            <button type="button" onClick={() => removeItem(index)}>
              Remove
            </button>
            {mode === "placement" ? (
              <>
                <label>
                  x {index}
                  <input
                    aria-label={`x ${index}`}
                    type="number"
                    value={item.x}
                    onChange={(event) => updateItem(index, { x: Number(event.target.value) })}
                  />
                </label>
                <label>
                  y {index}
                  <input
                    aria-label={`y ${index}`}
                    type="number"
                    value={item.y}
                    onChange={(event) => updateItem(index, { y: Number(event.target.value) })}
                  />
                </label>
                <label>
                  width {index}
                  <input
                    aria-label={`width ${index}`}
                    type="number"
                    min={1}
                    value={item.width}
                    onChange={(event) => updateItem(index, { width: Number(event.target.value) })}
                  />
                </label>
                <label>
                  height {index}
                  <input
                    aria-label={`height ${index}`}
                    type="number"
                    min={1}
                    value={item.height}
                    onChange={(event) => updateItem(index, { height: Number(event.target.value) })}
                  />
                </label>
              </>
            ) : null}
          </li>
        ))}
      </ol>
      {mode === "placement" ? (
        <MergeCanvasBoard
          tiles={items.map((item) => ({
            path: item.path,
            x: item.x,
            y: item.y,
            w: item.width,
            h: item.height,
          }))}
          canvasWidth={1920}
          canvasHeight={1080}
          background="transparent"
          selectedPath={selectedPath}
          onSelect={setSelectedPath}
          onMove={moveTile}
          onResize={resizeTile}
          onFit={() => undefined}
          onRemove={removeTile}
          onClear={() => setItems([])}
        />
      ) : null}
      <label>
        Output
        <input
          value={outputPath}
          placeholder="Output Filename (e.g. merged.png)"
          onChange={(event) => setOutputPath(event.target.value)}
        />
      </label>
      <label>
        Mode
        <select
          value={mode}
          onChange={(event) => setMode(event.target.value as "horizontal" | "vertical" | "placement")}
        >
          <option value="horizontal">horizontal</option>
          <option value="vertical">vertical</option>
          <option value="placement">placement</option>
        </select>
      </label>
      {mode === "placement" ? null : (
        <>
          <label>
            Spacing
            <input
              type="number"
              min={0}
              max={64}
              value={spacing}
              onChange={(event) => setSpacing(Number(event.target.value))}
            />
          </label>
          <label>
            Align
            <select value={align} onChange={(event) => setAlign(event.target.value as "start" | "center" | "end")}>
              <option value="start">start</option>
              <option value="center">center</option>
              <option value="end">end</option>
            </select>
          </label>
        </>
      )}
      <button type="submit">{mode === "placement" ? "Place" : "Concatenate"}</button>
      {error ? <p role="alert">{error}</p> : null}
      {result?.written ? (
        <>
          <p>
            {result.width}x{result.height} {result.output_path}
          </p>
          <img alt="Merged preview" src={`data:image/png;base64,${result.preview_png_base64}`} />
        </>
      ) : null}
    </form>
  );
}
