import React, { useState } from "react";
import { deskButtonClass, deskControlClass, DeskField, DeskForm } from "../../components/common/DeskForm";

export type DlRoute = "train" | "generate" | "review" | "runs";

export interface DlInspectResult {
  readonly found: boolean;
  readonly run_dir: string;
  readonly run_id: string;
  readonly status: string;
  readonly engine: string;
  readonly model_id: string;
  readonly event_count: number;
  readonly started: boolean;
  readonly reason: string;
}

export interface DlClient {
  dlInspect(params: { run_dir: string }): Promise<DlInspectResult>;
}

/** Read a run directory (#912). This view never starts a job. */
export function DlWorkspace({
  hostClient,
  route,
}: {
  readonly hostClient: DlClient;
  readonly route: DlRoute;
}): React.ReactElement {
  const [runDir, setRunDir] = useState("");
  const [result, setResult] = useState<DlInspectResult | null>(null);
  const [error, setError] = useState("");

  async function onSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setError("");
    try {
      setResult(await hostClient.dlInspect({ run_dir: runDir }));
    } catch (exc) {
      setResult(null);
      setError(exc instanceof Error ? exc.message : "inspect failed");
    }
  }

  return (
    <section data-testid="dl-workspace" data-route={route}>
      <DeskForm testId="dl-inspect" title={route} description="Read a run directory. This page never starts a job." onSubmit={onSubmit}>
        <DeskField label="Run directory">
          <input className={deskControlClass} value={runDir} onChange={(event) => setRunDir(event.target.value)} />
        </DeskField>
        <button type="submit" className={deskButtonClass}>Inspect</button>
        {error ? <p role="alert" className="text-sm text-red-600">{error}</p> : null}
        {result ? (
          <p className="text-sm">
            {result.run_id} {result.status} {result.engine} {result.event_count} {result.reason}
          </p>
        ) : null}
      </DeskForm>
    </section>
  );
}
