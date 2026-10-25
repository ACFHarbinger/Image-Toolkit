import React, { useState } from "react";

export interface ProbeResult {
  readonly available: boolean;
  readonly width: number;
  readonly height: number;
  readonly duration_seconds: number;
  readonly codec: string;
  readonly error: string;
}

export interface ExtractorClient {
  extractorProbe(params: { path: string }): Promise<ProbeResult>;
}

/** One-path video probe (#905). Frame extraction stays on PySide6. */
export function ExtractorView({ hostClient }: { readonly hostClient: ExtractorClient }): React.ReactElement {
  const [path, setPath] = useState("");
  const [result, setResult] = useState<ProbeResult | null>(null);
  const [error, setError] = useState("");

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

  return (
    <form data-testid="extractor-view" onSubmit={onSubmit}>
      <label>
        Video
        <input value={path} onChange={(event) => setPath(event.target.value)} />
      </label>
      <button type="submit">Probe</button>
      {error ? <p role="alert">{error}</p> : null}
      {result?.available ? (
        <p>
          {result.width}x{result.height} {result.codec} {result.duration_seconds}s
        </p>
      ) : null}
    </form>
  );
}
