import React, { useState } from "react";

export interface DrivePlanResult {
  readonly submitted: false;
  readonly provider: string;
  readonly count: number;
  readonly reason: string;
}

export interface DriveSyncClient {
  driveSyncPlan(params: { provider: string; paths: string[] }): Promise<DrivePlanResult>;
}

/** Record a sync plan (#908). Nothing is uploaded. */
export function DriveSyncView({ hostClient }: { readonly hostClient: DriveSyncClient }): React.ReactElement {
  const [provider, setProvider] = useState("google_drive");
  const [paths, setPaths] = useState("");
  const [result, setResult] = useState<DrivePlanResult | null>(null);
  const [error, setError] = useState("");

  async function onSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setError("");
    const listed = paths.split("\n").map((line) => line.trim()).filter(Boolean);
    try {
      setResult(await hostClient.driveSyncPlan({ provider, paths: listed }));
    } catch (exc) {
      setResult(null);
      setError(exc instanceof Error ? exc.message : "plan failed");
    }
  }

  return (
    <form data-testid="drive-sync-view" onSubmit={onSubmit}>
      <label>
        Provider
        <select value={provider} onChange={(event) => setProvider(event.target.value)}>
          <option value="google_drive">Google Drive</option>
          <option value="dropbox">Dropbox</option>
          <option value="onedrive">OneDrive</option>
        </select>
      </label>
      <label>
        Paths
        <textarea value={paths} onChange={(event) => setPaths(event.target.value)} />
      </label>
      <button type="submit">Plan</button>
      {error ? <p role="alert">{error}</p> : null}
      {result ? (
        <p>
          {result.provider} {result.count} {result.reason}
        </p>
      ) : null}
    </form>
  );
}
