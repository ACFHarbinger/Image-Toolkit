import React, { useState } from "react";

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
    <form data-testid="media-loader-view" onSubmit={onSubmit}>
      <label>
        URL
        <input value={url} onChange={(event) => setUrl(event.target.value)} />
      </label>
      <label>
        Destination
        <input value={destination} onChange={(event) => setDestination(event.target.value)} />
      </label>
      <button type="submit">Plan</button>
      {error ? <p role="alert">{error}</p> : null}
      {result?.accepted ? <p>{result.reason}</p> : null}
    </form>
  );
}
