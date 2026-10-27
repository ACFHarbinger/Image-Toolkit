import React, { useState } from "react";
import { deskButtonClass, deskControlClass, DeskField, DeskForm } from "../../components/common/DeskForm";
import { ThumbnailGallery } from "../../components/common/ThumbnailGallery";

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

  function onCopyAll(): void {
    if (!result) {
      return;
    }
    const clipboard = navigator.clipboard;
    if (typeof clipboard?.writeText !== "function") {
      return;
    }
    try {
      // A failed copy leaves the lines on screen and does not reread.
      void Promise.resolve(clipboard.writeText(result.lines.join("\n"))).catch(() => undefined);
    } catch {
      // writeText threw synchronously.
    }
  }

  function onClear(): void {
    if (!result) {
      return;
    }
    setResult({ ...result, lines: [] });
  }

  return (
    <DeskForm testId="log-desk" title="Logs" description="Last lines of a log file. The file is not followed." onSubmit={onSubmit}>
      <ThumbnailGallery
        extensions={["log", "txt"]}
        multiple={false}
        directoryLabel="Log directory"
        selected={path ? [path] : []}
        onSelectedChange={(paths) => setPath(paths[0] ?? "")}
      />
      <DeskField label="Path">
        <input className={deskControlClass} value={path} onChange={(event) => setPath(event.target.value)} />
      </DeskField>
      <DeskField label="Limit">
        <input
          className={deskControlClass}
          type="number"
          min={1}
          max={200}
          value={limit}
          onChange={(event) => setLimit(Number(event.target.value))}
        />
      </DeskField>
      <button type="submit" className={deskButtonClass}>Read</button>
      <button type="button" className={deskButtonClass} onClick={onCopyAll}>Copy all</button>
      <button type="button" className={deskButtonClass} onClick={onClear}>Clear</button>
      {error ? <p role="alert" className="text-sm text-red-600">{error}</p> : null}
      {result ? <p className="text-sm">{result.reason}</p> : null}
      {result ? (
        <ul className="space-y-1 font-mono text-xs">
          {result.lines.map((line, index) => (
            <li key={`${index}:${line}`}>{line}</li>
          ))}
        </ul>
      ) : null}
    </DeskForm>
  );
}
