import React, { useState } from "react";
import { deskButtonClass, deskControlClass, DeskField, DeskForm } from "../../components/common/DeskForm";
import { ThumbnailGallery } from "../../components/common/ThumbnailGallery";

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
    <DeskForm testId="drive-sync-view" title="Cloud Synchronization" description="Record a sync plan. Nothing is uploaded." onSubmit={onSubmit}>
      <DeskField label="Provider">
        <select className={deskControlClass} value={provider} onChange={(event) => setProvider(event.target.value)}>
          <option value="google_drive">Google Drive</option>
          <option value="dropbox">Dropbox</option>
          <option value="onedrive">OneDrive</option>
        </select>
      </DeskField>
      <ThumbnailGallery
        multiple
        selected={paths.split("\n").map((line) => line.trim()).filter(Boolean)}
        onSelectedChange={(next) => setPaths(next.join("\n"))}
      />
      <DeskField label="Paths">
        <textarea className={deskControlClass} rows={4} value={paths} onChange={(event) => setPaths(event.target.value)} />
      </DeskField>
      <button type="submit" className={deskButtonClass}>Plan</button>
      {error ? <p role="alert" className="text-sm text-red-600">{error}</p> : null}
      {result ? (
        <p className="text-sm">
          {result.provider} {result.count} {result.reason}
        </p>
      ) : null}
    </DeskForm>
  );
}
