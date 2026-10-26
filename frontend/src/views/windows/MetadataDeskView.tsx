import React, { useState } from "react";

export interface MetadataDescribeResult {
  readonly found: boolean;
  readonly path: string;
  readonly name: string;
  readonly size: number;
  readonly suffix: string;
  readonly reason: string;
}

export interface MetadataClient {
  metadataDescribe(params: { path: string }): Promise<MetadataDescribeResult>;
}

/** Name and size of a caller file (#919). library.db is not opened. */
export function MetadataDeskView({ hostClient }: { readonly hostClient: MetadataClient }): React.ReactElement {
  const [path, setPath] = useState("");
  const [result, setResult] = useState<MetadataDescribeResult | null>(null);
  const [error, setError] = useState("");

  async function onSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setError("");
    try {
      setResult(await hostClient.metadataDescribe({ path }));
    } catch (exc) {
      setResult(null);
      setError(exc instanceof Error ? exc.message : "metadata failed");
    }
  }

  return (
    <form data-testid="metadata-desk" onSubmit={onSubmit}>
      <label>
        Path
        <input value={path} onChange={(event) => setPath(event.target.value)} />
      </label>
      <button type="submit">Describe</button>
      {error ? <p role="alert">{error}</p> : null}
      {result ? <p>{result.reason}</p> : null}
      {result?.found ? (
        <p>
          {result.name} {result.size} {result.suffix}
        </p>
      ) : null}
    </form>
  );
}
