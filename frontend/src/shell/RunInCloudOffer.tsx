import { useState, type FormEvent, type ReactElement } from "react";

export interface CloudOffer {
  offered: boolean;
  submitted: false;
  reason: string;
  estimate_usd: number;
  estimate_known: boolean;
  kind: string;
  vram_gb_min: number;
  provider: string;
  region: string;
  runtime_s: number;
  job_id: string;
}

/** Prefill only. Submit stays on Gate D4. */
export function RunInCloudOffer({
  offer,
  notice,
  onPrefill,
}: {
  offer: CloudOffer | null;
  notice: string;
  onPrefill: (owner: string, estimatedGb: number, deviceGb: number) => void;
}): ReactElement {
  const [owner, setOwner] = useState("train-lora");
  const [estimated, setEstimated] = useState("9.1");
  const [device, setDevice] = useState("10");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    onPrefill(owner, Number(estimated), Number(device));
  };

  return (
    <section data-testid="run-in-cloud-offer" className="flex flex-col gap-2">
      <h2>Run in cloud instead</h2>
      <p>This does not submit a job.</p>
      <form className="flex flex-col gap-2" onSubmit={submit}>
        <label>
          Owner
          <input value={owner} onChange={(event) => setOwner(event.target.value)} />
        </label>
        <label>
          Estimated GB
          <input value={estimated} onChange={(event) => setEstimated(event.target.value)} />
        </label>
        <label>
          Device GB
          <input value={device} onChange={(event) => setDevice(event.target.value)} />
        </label>
        <button type="submit">Run in cloud instead</button>
      </form>
      {notice ? <p data-testid="run-in-cloud-notice">{notice}</p> : null}
      {offer?.offered ? (
        <p data-testid="run-in-cloud-prefill">
          {offer.kind} · {offer.provider}/{offer.region} · {offer.vram_gb_min} GB ·{" "}
          {offer.estimate_known ? `$${offer.estimate_usd.toFixed(2)}` : "estimate unknown"} · {offer.job_id}
        </p>
      ) : null}
    </section>
  );
}
