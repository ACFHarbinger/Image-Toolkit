import React, { useState } from "react";

export interface MergeResult {
  readonly written: boolean;
  readonly width: number;
  readonly height: number;
  readonly preview_png_base64: string;
  readonly error: string;
}

export interface MergeClient {
  mergeConcatenate(params: {
    paths: string[];
    output_path: string;
    direction: "horizontal" | "vertical";
    spacing: number;
    align: "start" | "center" | "end";
  }): Promise<MergeResult>;
}

function splitPaths(raw: string): string[] {
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

/** Horizontal or vertical concatenation (#903). Pixels come from the sidecar. */
export function MergeView({ hostClient }: { readonly hostClient: MergeClient }): React.ReactElement {
  const [rawPaths, setRawPaths] = useState("");
  const [outputPath, setOutputPath] = useState("");
  const [direction, setDirection] = useState<"horizontal" | "vertical">("horizontal");
  const [spacing, setSpacing] = useState(0);
  const [align, setAlign] = useState<"start" | "center" | "end">("start");
  const [result, setResult] = useState<MergeResult | null>(null);
  const [error, setError] = useState("");

  async function onSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setError("");
    try {
      const next = await hostClient.mergeConcatenate({
        paths: splitPaths(rawPaths),
        output_path: outputPath,
        direction,
        spacing,
        align,
      });
      setResult(next);
      if (!next.written) {
        setError(next.error);
      }
    } catch (exc) {
      setResult(null);
      setError(exc instanceof Error ? exc.message : "concatenate failed");
    }
  }

  return (
    <form data-testid="merge-view" onSubmit={onSubmit}>
      <label>
        Images
        <textarea value={rawPaths} onChange={(event) => setRawPaths(event.target.value)} />
      </label>
      <label>
        Output
        <input
          value={outputPath}
          placeholder="Output Filename (e.g. merged.png)"
          onChange={(event) => setOutputPath(event.target.value)}
        />
      </label>
      <label>
        Direction
        <select value={direction} onChange={(event) => setDirection(event.target.value as "horizontal" | "vertical")}>
          <option value="horizontal">horizontal</option>
          <option value="vertical">vertical</option>
        </select>
      </label>
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
      <button type="submit">Concatenate</button>
      {error ? <p role="alert">{error}</p> : null}
      {result?.written ? (
        <img alt="Merged preview" src={`data:image/png;base64,${result.preview_png_base64}`} />
      ) : null}
    </form>
  );
}
