import React, { useState } from "react";
import { deskButtonClass, deskControlClass, DeskField, DeskForm } from "../../components/common/DeskForm";

export interface MediaPlanResult {
  readonly accepted: boolean;
  readonly downloaded: false;
  readonly url: string;
  readonly destination: string;
  readonly reason: string;
}

export interface MediaLoaderClient {
  mediaLoaderPlan(params: { url: string; destination: string }): Promise<MediaPlanResult>;
}

/** Check a download plan (#909). The URL is not fetched. */
export function MediaLoaderView({ hostClient }: { readonly hostClient: MediaLoaderClient }): React.ReactElement {
  const [url, setUrl] = useState("");
  const [destination, setDestination] = useState("");
  const [result, setResult] = useState<MediaPlanResult | null>(null);
  const [error, setError] = useState("");

  async function onSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setError("");
    try {
      const next = await hostClient.mediaLoaderPlan({ url, destination });
      setResult(next);
      if (!next.accepted) {
        setError(next.reason);
      }
    } catch (exc) {
      setResult(null);
      setError(exc instanceof Error ? exc.message : "plan failed");
    }
  }

  return (
    <DeskForm testId="media-loader-view" title="Media Loader" description="Check a download plan. The URL is not fetched." onSubmit={onSubmit}>
      <DeskField label="URL">
        <input className={deskControlClass} value={url} onChange={(event) => setUrl(event.target.value)} />
      </DeskField>
      <DeskField label="Destination">
        <input className={deskControlClass} value={destination} onChange={(event) => setDestination(event.target.value)} />
      </DeskField>
      <button type="submit" className={deskButtonClass}>Plan</button>
      {error ? <p role="alert" className="text-sm text-red-600">{error}</p> : null}
      {result?.accepted ? <p className="text-sm">{result.reason}</p> : null}
    </DeskForm>
  );
}
