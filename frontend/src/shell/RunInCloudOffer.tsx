import { useEffect, useState, type FormEvent, type ReactElement } from "react";

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
  spec: Record<string, unknown>;
}

interface OfferDraft {
  title: string;
  kind: string;
  provider: string;
  region: string;
  vramGbMin: string;
  runtimeS: string;
  jobId: string;
}

function readRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function draftFromOffer(offer: CloudOffer): OfferDraft {
  const spec = readRecord(offer.spec);
  const placement = readRecord(spec.placement);
  const resources = readRecord(spec.resources);
  const params = readRecord(spec.params);
  return {
    title: String(spec.title ?? offer.kind),
    kind: String(spec.kind ?? offer.kind),
    provider: String(placement.provider ?? offer.provider),
    region: String(placement.region ?? offer.region),
    vramGbMin: String(resources.vram_gb_min ?? offer.vram_gb_min),
    runtimeS: String(params.expected_runtime_s ?? offer.runtime_s),
    jobId: String(spec.job_id ?? offer.job_id),
  };
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
  const [draft, setDraft] = useState<OfferDraft | null>(null);

  useEffect(() => {
    setDraft(offer?.offered ? draftFromOffer(offer) : null);
  }, [offer]);

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
      {offer?.offered && draft ? (
        <div data-testid="run-in-cloud-prefill" className="flex flex-col gap-2">
          <p>
            {offer.kind} · {offer.provider}/{offer.region} · {offer.vram_gb_min} GB ·{" "}
            {offer.estimate_known ? `$${offer.estimate_usd.toFixed(2)}` : "estimate unknown"} · {offer.job_id}
          </p>
          <p>Edit the prefilled request. This does not save or submit it.</p>
          <label>
            Title
            <input
              data-testid="offer-title"
              value={draft.title}
              onChange={(event) => setDraft({ ...draft, title: event.target.value })}
            />
          </label>
          <label>
            Kind
            <input
              data-testid="offer-kind"
              value={draft.kind}
              onChange={(event) => setDraft({ ...draft, kind: event.target.value })}
            />
          </label>
          <label>
            Provider
            <input
              data-testid="offer-provider"
              value={draft.provider}
              onChange={(event) => setDraft({ ...draft, provider: event.target.value })}
            />
          </label>
          <label>
            Region
            <input
              data-testid="offer-region"
              value={draft.region}
              onChange={(event) => setDraft({ ...draft, region: event.target.value })}
            />
          </label>
          <label>
            VRAM GB minimum
            <input
              data-testid="offer-vram"
              value={draft.vramGbMin}
              onChange={(event) => setDraft({ ...draft, vramGbMin: event.target.value })}
            />
          </label>
          <label>
            Runtime seconds
            <input
              data-testid="offer-runtime"
              value={draft.runtimeS}
              onChange={(event) => setDraft({ ...draft, runtimeS: event.target.value })}
            />
          </label>
          <label>
            Job id
            <input
              data-testid="offer-job-id"
              value={draft.jobId}
              onChange={(event) => setDraft({ ...draft, jobId: event.target.value })}
            />
          </label>
        </div>
      ) : null}
    </section>
  );
}
