import React, { useState } from "react";

export interface ProbeResult {
  readonly available: boolean;
  readonly width: number;
  readonly height: number;
  readonly duration_seconds: number;
  readonly codec: string;
  readonly error: string;
}

export interface FileResult {
  readonly written: boolean;
  readonly output_path: string;
  readonly error: string;
}

export interface CutResult {
  readonly written: boolean;
  readonly output_dir: string;
  readonly width: number;
  readonly height: number;
  readonly paths: readonly string[];
  readonly error: string;
}

export interface ExtractorJobStatus {
  readonly state: string;
  readonly result?: Partial<FileResult & CutResult>;
  readonly error?: { readonly message_key?: string; readonly code?: string; readonly message?: string } | string;
}

export interface ExtractorClient {
  extractorProbe(params: { path: string }): Promise<ProbeResult>;
  extractorSnapshot(params: { path: string; time_seconds: number; output_path: string }): Promise<{ job_id: string }>;
  extractorExtractRange(params: {
    path: string;
    start_seconds: number;
    end_seconds: number;
    output_path: string;
  }): Promise<{ job_id: string }>;
  cancelJob(jobId: string): Promise<unknown>;
  jobStatus(jobId: string): Promise<ExtractorJobStatus>;
  extractorCutSheet(params: {
    path: string;
    output_dir: string;
    arrangement: "grid" | "vertical" | "horizontal";
    frame_width: number;
    frame_height: number;
    offset_x: number;
    offset_y: number;
    spacing: number;
    include_partial: boolean;
  }): Promise<{ job_id: string }>;
}

/** One-path video probe (#905). Frame extraction stays on PySide6. */
export function ExtractorView({ hostClient }: { readonly hostClient: ExtractorClient }): React.ReactElement {
  const [cutJob, setCutJob] = useState<string | null>(null);
  const [cutting, setCutting] = useState(false);
  const [path, setPath] = useState("");
  const [result, setResult] = useState<ProbeResult | null>(null);
  const [error, setError] = useState("");
  const [snapshotAt, setSnapshotAt] = useState(0);
  const [snapshotOut, setSnapshotOut] = useState("");
  const [rangeStart, setRangeStart] = useState(0);
  const [rangeEnd, setRangeEnd] = useState(1);
  const [rangeOut, setRangeOut] = useState("");
  const [sheetPath, setSheetPath] = useState("");
  const [sheetDir, setSheetDir] = useState("");
  const [arrangement, setArrangement] = useState<"grid" | "vertical" | "horizontal">("grid");
  const [frameWidth, setFrameWidth] = useState(32);
  const [frameHeight, setFrameHeight] = useState(32);
  const [offsetX, setOffsetX] = useState(0);
  const [offsetY, setOffsetY] = useState(0);
  const [spacing, setSpacing] = useState(0);
  const [includePartial, setIncludePartial] = useState(false);
  const [actionNote, setActionNote] = useState("");

  async function onSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setError("");
    try {
      const next = await hostClient.extractorProbe({ path });
      setResult(next);
      if (!next.available) {
        setError(next.error);
      }
    } catch (exc) {
      setResult(null);
      setError(exc instanceof Error ? exc.message : "probe failed");
    }
  }

  async function onSnapshot(): Promise<void> {
    setError("");
    try {
      const started = await hostClient.extractorSnapshot({
        path,
        time_seconds: snapshotAt,
        output_path: snapshotOut,
      });
      await showFileJob(started.job_id);
    } catch (exc) {
      setActionNote("");
      setError(exc instanceof Error ? exc.message : "snapshot failed");
    }
  }

  async function onRange(): Promise<void> {
    setError("");
    try {
      const started = await hostClient.extractorExtractRange({
        path,
        start_seconds: rangeStart,
        end_seconds: rangeEnd,
        output_path: rangeOut,
      });
      await showFileJob(started.job_id);
    } catch (exc) {
      setActionNote("");
      setError(exc instanceof Error ? exc.message : "extract failed");
    }
  }

  async function showFileJob(jobId: string): Promise<void> {
    const finished = await pollJob(hostClient, jobId);
    if (finished.state === "cancelled") {
      setActionNote("cancelled");
      setError("");
      return;
    }
    if (finished.state === "failed") {
      setActionNote("");
      setError(jobErrorText(finished.error));
      return;
    }
    const file = finished.result;
    const written = file?.written === true;
    const outputPath = typeof file?.output_path === "string" ? file.output_path : "";
    setActionNote(written ? outputPath : "");
    setError(typeof file?.error === "string" ? file.error : "");
  }

  async function onCut(): Promise<void> {
    setCutting(true);
    setActionNote("");
    setError("");
    try {
      const started = await hostClient.extractorCutSheet({
        path: sheetPath,
        output_dir: sheetDir,
        arrangement,
        frame_width: frameWidth,
        frame_height: frameHeight,
        offset_x: offsetX,
        offset_y: offsetY,
        spacing,
        include_partial: includePartial,
      });
      setCutJob(started.job_id);
      const finished = await pollJob(hostClient, started.job_id);
      if (finished.state === "cancelled") {
        setActionNote("cancelled");
      } else if (finished.state === "failed") {
        setError(jobErrorText(finished.error));
      } else {
        const next = finished.result;
        setActionNote(next?.written ? `${next.width}x${next.height} ${next.paths?.length ?? 0}` : "");
        setError(next?.error ?? "");
      }
    } catch (exc) {
      setActionNote("");
      setError(exc instanceof Error ? exc.message : "cut failed");
    } finally {
      setCutJob(null);
      setCutting(false);
    }
  }

  return (
    <form data-testid="extractor-view" onSubmit={onSubmit}>
      <label>
        Video
        <input value={path} onChange={(event) => setPath(event.target.value)} />
      </label>
      <button type="submit">Probe</button>
      {cutJob ? <button type="button" onClick={() => {
        void hostClient.cancelJob(cutJob).catch((exc: unknown) => setError(String(exc)));
      }}>Cancel sheet cut</button> : null}
      {error ? <p role="alert">{error}</p> : null}
      {result?.available ? (
        <p>
          {result.width}x{result.height} {result.codec} {result.duration_seconds}s
        </p>
      ) : null}
      <label>
        Snapshot at
        <input
          type="number"
          min={0}
          value={snapshotAt}
          onChange={(event) => setSnapshotAt(Number(event.target.value))}
        />
      </label>
      <label>
        Snapshot output
        <input value={snapshotOut} onChange={(event) => setSnapshotOut(event.target.value)} />
      </label>
      <button type="button" onClick={onSnapshot}>
        Snapshot
      </button>
      <label>
        Range start
        <input type="number" min={0} value={rangeStart} onChange={(event) => setRangeStart(Number(event.target.value))} />
      </label>
      <label>
        Range end
        <input type="number" min={0} value={rangeEnd} onChange={(event) => setRangeEnd(Number(event.target.value))} />
      </label>
      <label>
        Range output
        <input value={rangeOut} onChange={(event) => setRangeOut(event.target.value)} />
      </label>
      <button type="button" onClick={onRange}>
        Extract range
      </button>
      <label>
        Sheet image
        <input value={sheetPath} onChange={(event) => setSheetPath(event.target.value)} />
      </label>
      <label>
        Sheet output
        <input value={sheetDir} onChange={(event) => setSheetDir(event.target.value)} />
      </label>
      <label>
        Arrangement
        <select
          value={arrangement}
          onChange={(event) => setArrangement(event.target.value as "grid" | "vertical" | "horizontal")}
        >
          <option value="grid">grid</option>
          <option value="vertical">vertical</option>
          <option value="horizontal">horizontal</option>
        </select>
      </label>
      <label>
        Frame width
        <input type="number" min={1} value={frameWidth} onChange={(event) => setFrameWidth(Number(event.target.value))} />
      </label>
      <label>
        Frame height
        <input
          type="number"
          min={1}
          value={frameHeight}
          onChange={(event) => setFrameHeight(Number(event.target.value))}
        />
      </label>
      <label>
        Offset x
        <input type="number" min={0} value={offsetX} onChange={(event) => setOffsetX(Number(event.target.value))} />
      </label>
      <label>
        Offset y
        <input type="number" min={0} value={offsetY} onChange={(event) => setOffsetY(Number(event.target.value))} />
      </label>
      <label>
        Spacing
        <input type="number" min={0} value={spacing} onChange={(event) => setSpacing(Number(event.target.value))} />
      </label>
      <label>
        Include partial last frame
        <input
          type="checkbox"
          checked={includePartial}
          onChange={(event) => setIncludePartial(event.target.checked)}
        />
      </label>
      <button type="button" onClick={onCut} disabled={cutting}>
        Cut sheet
      </button>
      {actionNote ? <p>{actionNote}</p> : null}
    </form>
  );
}

async function pollJob(hostClient: ExtractorClient, jobId: string): Promise<ExtractorJobStatus> {
  let status = await hostClient.jobStatus(jobId);
  for (;;) {
    if (status.state !== "queued" && status.state !== "running") {
      return status;
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
    status = await hostClient.jobStatus(jobId);
  }
}

function jobErrorText(error: ExtractorJobStatus["error"]): string {
  if (typeof error === "string" && error) {
    return error;
  }
  if (error && typeof error === "object") {
    return error.message || error.message_key || error.code || "extract failed";
  }
  return "extract failed";
}
