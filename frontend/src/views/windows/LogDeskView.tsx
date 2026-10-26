import React, { useState } from "react";

export interface LogsReadResult {
  readonly found: boolean;
  readonly path: string;
  readonly lines: readonly string[];
  readonly error_count: number;
  readonly reason: string;
}

export interface LogsClient {
  logsRead(params: { path: string; limit: number }): Promise<LogsReadResult>;
}

/** Last lines of a caller log (#919). The file is not followed. */
export function LogDeskView({ hostClient }: { readonly hostClient: LogsClient }): React.ReactElement {
  const [path, setPath] = useState("");
  const [limit, setLimit] = useState(50);
  const [result, setResult] = useState<LogsReadResult | null>(null);
  const [error, setError] = useState("");

  async function onSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setError("");
    try {
      setResult(await hostClient.logsRead({ path, limit }));
    } catch (exc) {
      setResult(null);
      setError(exc instanceof Error ? exc.message : "log read failed");
    }
  }

  return (
    <form data-testid="log-desk" onSubmit={onSubmit}>
      <label>
        Path
        <input value={path} onChange={(event) => setPath(event.target.value)} />
      </label>
      <label>
        Limit
        <input
          type="number"
          min={1}
          max={200}
          value={limit}
          onChange={(event) => setLimit(Number(event.target.value))}
        />
      </label>
      <button type="submit">Read</button>
      {error ? <p role="alert">{error}</p> : null}
      {result ? <p>{result.reason}</p> : null}
      {result ? (
        <ul>
          {result.lines.map((line, index) => (
            <li key={`${index}:${line}`}>{line}</li>
          ))}
        </ul>
      ) : null}
    </form>
  );
}
