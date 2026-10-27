import { open } from "@tauri-apps/plugin-dialog";
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

/** One step back when a removal leaves the current page with no rows. */
function pageAfterRemoval(page: number, pageSize: number, nextLength: number): number {
  if (nextLength === 0) {
    return 0;
  }
  if (page * pageSize >= nextLength && page > 0) {
    return page - 1;
  }
  return page;
}

/** Empty folder keeps the filename verbatim. Otherwise join the folder to the filename's last segment. */
function outputPathForMerge(folder: string, filename: string): string {
  if (folder.length === 0) {
    return filename;
  }
  let end = folder.length;
  while (end > 0 && folder[end - 1] === "/") {
    end -= 1;
  }
  const directory = folder.slice(0, end);
  const slash = filename.lastIndexOf("/");
  const name = slash < 0 ? filename : filename.slice(slash + 1);
  return `${directory}/${name}`;
}

/** Ordered queue. Placement stores a rectangle per image; other modes concatenate. */
export function MergeView({ hostClient }: { readonly hostClient: MergeClient }): React.ReactElement {
  const [draft, setDraft] = useState("");
  const [gallerySelected, setGallerySelected] = useState<string[]>([]);
  const [items, setItems] = useState<QueueItem[]>([]);
  const [queuePage, setQueuePage] = useState(0);
  const [queuePageSize, setQueuePageSize] = useState(10);
  const [outputFolder, setOutputFolder] = useState("");
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

  /** Append gallery picks that are not already queued. Deselect leaves the queue. */
  function onGallerySelected(paths: string[]): void {
    const already = new Set(gallerySelected);
    setGallerySelected(paths);
    setDraft(paths[0] ?? "");
    const added = paths.filter((path) => path.length > 0 && !already.has(path));
    if (added.length === 0) {
      return;
    }
    setItems((current) => {
      const queued = new Set(current.map((item) => item.path));
      let next = current;
      for (const path of added) {
        if (queued.has(path)) {
          continue;
        }
        if (next === current) {
          next = [...current];
        }
        next.push({ path, x: 0, y: next.length * 32, width: 32, height: 32 });
        queued.add(path);
      }
      return next;
    });
  }

  function changeQueuePageSize(raw: string): void {
    const parsed = Number(raw);
    const size = Number.isFinite(parsed) && parsed >= 1 ? Math.floor(parsed) : 1;
    setQueuePageSize(size);
    setQueuePage(0);
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
    if (index < 0 || index >= items.length) {
      return;
    }
    const nextLength = items.length - 1;
    setItems((current) => current.filter((_, itemIndex) => itemIndex !== index));
    setQueuePage((currentPage) => pageAfterRemoval(currentPage, queuePageSize, nextLength));
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
    removeItem(items.findIndex((item) => item.path === path));
  }

  async function browseOutputFolder(): Promise<void> {
    try {
      const picked = await open({ directory: true, multiple: false });
      if (typeof picked === "string" && picked.length > 0) {
        setOutputFolder(picked);
      }
    } catch {
      // A thrown dialog leaves the folder unchanged and does not submit.
    }
  }

  async function onSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setError("");
    const destination = outputPathForMerge(outputFolder, outputPath);
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
              output_path: destination,
            })
          : await hostClient.mergeConcatenate({
              paths: items.map((item) => item.path),
              output_path: destination,
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

  const lastPage = items.length === 0 ? 0 : Math.ceil(items.length / queuePageSize) - 1;
  const page = Math.min(queuePage, lastPage);
  const pageStart = page * queuePageSize;
  const visibleItems = items.slice(pageStart, pageStart + queuePageSize);
  const rangeStart = items.length === 0 ? 0 : pageStart + 1;
  const rangeEnd = items.length === 0 ? 0 : Math.min(pageStart + queuePageSize, items.length);

  return (
    <form data-testid="merge-view" onSubmit={onSubmit}>
      <ThumbnailGallery
        multiple
        directoryLabel="Image directory"
        selected={gallerySelected}
        onSelectedChange={onGallerySelected}
      />
      <label>
        Add image
        <input value={draft} onChange={(event) => setDraft(event.target.value)} />
      </label>
      <button type="button" onClick={addItem}>
        Add
      </button>
      <ol>
        {visibleItems.map((item, offset) => {
          const index = pageStart + offset;
          return (
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
          );
        })}
      </ol>
      <label>
        Queue page size
        <input type="number" min={1} value={queuePageSize} onChange={(event) => changeQueuePageSize(event.target.value)} />
      </label>
      <button type="button" onClick={() => setQueuePage(page - 1)} disabled={page === 0}>
        Previous
      </button>
      <button type="button" onClick={() => setQueuePage(page + 1)} disabled={page >= lastPage}>
        Next
      </button>
      <p>{`Items ${rangeStart}\u2013${rangeEnd} of ${items.length}`}</p>
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
          onClear={() => {
            setItems([]);
            setQueuePage(0);
          }}
        />
      ) : null}
      <label>
        Output folder
        <input value={outputFolder} onChange={(event) => setOutputFolder(event.target.value)} />
      </label>
      <button type="button" onClick={() => void browseOutputFolder()}>
        Browse output folder
      </button>
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
