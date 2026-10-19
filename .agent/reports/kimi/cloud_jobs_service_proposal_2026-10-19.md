# Cloud Jobs Service — Kimi proposal

— Kimi, 2026-10-19. Proposal only; no code until the scope is locked.
Builds on every recorded answer (Claude Q1–Q10, Codex Q1–Q7, Gemini Q1–Q5,
OpenCode Q1–Q8, Grok Q1–Q8, Cursor Q1–Q8) and on Mistral's proposal.
Where my recommendation differs from an earlier one, I say so.

## 0. Consensus I build on, not re-argue

- Asynchronous state machine + reconciler (Claude, Mistral §1);
  PostgreSQL system of record + daemon WAL (Gemini Q4).
- Local daemon + cloud watchdog + verified provider deadlines (Codex Q1);
  job-scoped credential lease (Cursor Q3); presigned-URL staging (Gemini Q1).
- User picks per job with total-cost suggestion card (Claude Q6, Codex Q2,
  Mistral §3); GCP + RunPod first (OpenCode Q1); extraction → ComfyUI →
  indexing → training (Codex Q7).
- Risk-reactive form from data-driven rules (Claude Q8, Mistral §2);
  versioned curated price catalogue + live APIs + billing reconciliation
  (OpenCode Q6); per-job output collections (OpenCode Q8).

My additions: the shard model (§1), a minimal adapter contract (§2), the
ordered preflight pipeline (§3), a deterministic cost model with a
calibration loop (§4), a global emergency stop (§5), worker credential
hardening for gated models (§6), and an estimate replay harness (§7).
Questions in §8.

## 0.5 Recorded answers (2026-10-19) and design deltas

Harbinger answered all eight questions the same day; full record in the
[team report](../team/cloud_jobs_service_2026-10-19.md) §5 (Kimi).

- **Q1 A — shards confirmed.** §1 is the unit-of-work model.
- **Q2 — A, B, or C as a Settings choice.** All three instance-packing
  modes (1:1, sequential chaining, parallel packing) are in scope and
  user-selectable; no default was recorded. The lease/spend ledger and
  reconciler must handle whichever mode is active, so §1's "instance
  backends run shards sequentially" becomes "run shards under the
  configured packing mode".
- **Q3 A — no worker credentials, ever.** §6 confirmed as designed.
- **Q4 A — global emergency stop in.** §5 confirmed.
- **Q5 C — full remote manage in v1.** This reverses my desktop-only
  recommendation: the `api/` Django layer grows authenticated
  cloud-jobs endpoints (status, logs, cancel, retry) for mobile/web,
  extending Cursor Q3's credential lease and Cursor Q6's
  leader/observer to remote clients. Public-internet exposure is now a
  v1 design constraint: scoped short-lived tokens, TLS, and an audit
  log of remote actions.
- **Q6 B — wall-clock scheduling in v1.** The state machine gains
  clock-triggered transitions out of `queued`; at fire time the normal
  preflight (including the Q7 quota probe) runs, and an out-of-stock
  choice still fails fast per Grok Q2. No `waiting_for_capacity`.
- **Q7 A — quota/capacity probe in preflight**, right before costing.
- **Q8 A — submit ends in a Plan & cost confirmation sheet.**

## 1. The shard model — one unit for progress, retry, and collection

**Problem.** "A job" is a different size in each of the four workloads:
an extraction run can cover 10,000 files, a ComfyUI batch 800 prompts,
an indexing backfill a million images, a LoRA run one long process.
Retry granularity, progress %, partial collection and cost attribution
all need a shared unit smaller than "the job".

**Proposal.** Every job decomposes into shards at submit time:

- Extraction: shard = a fixed file slice of the staging manifest.
- ComfyUI batch: shard = a prompt-list slice; fixed seeds make shards
  reproducible and re-runnable independently.
- Embedding/phash: shard = an image-ID range; each shard emits its own
  vector Parquet + manifest, and Gemini Q5's staging-table merge consumes
  shard manifests.
- LoRA: a single-shard job; the shard is the resumable unit and
  checkpoint cadence lives inside it.

**Properties:**

- Each shard carries its own state (`pending/running/done/failed`), its
  own `events.jsonl` tail, its own retry count.
- Collection and re-drive are shard-granular: a 10,000-file extraction
  that failed 40 files retries those 40, not the job.
- Spend is attributed per shard and rolled up; the hard cap (OpenCode Q5)
  checkpoints at shard boundaries.
- Managed-batch backends map one shard to one container task; instance
  backends run shards sequentially on the leased instance.

**Tradeoffs.** One extra manifest table in PostgreSQL and more
reconciler bookkeeping. Shards must be sized so per-shard overhead
(staging round-trips, task startup) stays a small fraction of shard work —
a shard-sizing hint per workload kind belongs in the capability manifest.

## 2. Adapter contract: three verbs plus a capability manifest

Thin per-provider modules behind one interface in `backend/src/cloud/`:

- `plan(spec, catalogue, quotas) -> Plan` — pure, no network; powers
  estimates, the suggestion card, and preflight.
- `submit(plan, lease, idempotency_key) -> Attempt` — the only writer of
  provider resources; ambiguous submits resolve by listing tagged
  resources before any retry (Mistral §1, Codex Q3).
- `observe(attempt) -> Observation` — status, tagged resources, spend
  signals; the reconciler's only window on the provider.
- `teardown(attempt)` and `collect(attempt, shard)` round it out.

Every adapter ships a **capability manifest**: execution modes, GPU
classes, storage methods it can use (Claude Q5), verified timeouts
(Cursor Q8), quota introspection where the API offers it. The risk
engine and the grey-out rules read the manifest — no Qt imports, no SDK
imports — so capability data stays testable. Provider SDKs (boto3,
google-cloud-*, azure-*, runpod) are pinned per release and isolated
inside the adapters; the rest of `backend/src/cloud/` stays SDK-free so
test doubles and the pure preflight pipeline pull no provider deps.

## 3. Preflight pipeline: ordered, pure, one home per check

The individual checks are already decided: secret scan (Grok Q4), weight
cloud-classes (Grok Q3), risk rules (Claude Q8), quota (my Q7). Proposal:
run them as **one fixed-order pipeline of pure functions** over
`(JobSpec, Settings, catalogue, manifests)`, each emitting findings. The
UI and the backend submit path call the same pipeline; the backend
re-checks at submit so a stale form can't bypass a block (Mistral §2).

Order: schema validate → data class (OpenCode Q7) → secret scan → weight
classes → quota/capacity probe (fails fast, Grok Q2) → plan + total-cost
estimate (Codex Q2) → risk rules → confirmation sheet (my Q8).
Fail-fast checks run before costing, so a blocked job never presents
prices.

## 4. Cost model: estimates as a deterministic, snapshot function

The curated catalogue (OpenCode Q6) needs billing-granularity fields to
produce Codex-Q2 total-job estimates: per-second vs per-hour rounding,
minimum billable duration, per-task vs per-instance pricing, public IPv4
surcharges (AWS charges ~$0.005/h per public IPv4), egress tables per
provider pair, storage/volume rates.

`estimate = f(spec, plan, catalogue)` is deterministic and **snapshotted**:
the catalogue rows and prices used are stored with the job. Spend-so-far
in the UI then compares like for like, and billing reconciliation writes
actuals into the same ledger.

**Calibration loop.** For every completed job, keep (estimate inputs,
billed actuals). A periodic report flags catalogue rows whose error
drifts past a threshold — prices rot, and the suggestion card's
price-age band (Mistral §3) should be backed by measured accuracy, not
just timestamps.

## 5. Emergency stop: a first-class control

Every safety mechanism so far is per-job or predictive. Add one global
action — "Stop all cloud activity" (my Q4): checkpoint-cancel all active
jobs (Cursor Q7 semantics), revoke daemon credential leases, trigger
watchdog teardown immediately, and block new submits until re-enabled.
It must work with the GUI closed (daemon IPC plus a watchdog-reachable
trigger) and be visible: the header badge shows the blocked state.

## 6. Worker credential hardening and gated models

The boundary "workers hold no credentials" (Gemini Q1, OpenCode Q3) has
one gap: gated model repos (HuggingFace tokens). Proposal: **never**.
Gated weights are resolved at staging time by the daemon — pulled from
the local library/mirror into the staging manifest under the weight
cloud-class rules (Grok Q3), then placed on cache volumes (Grok Q6).
Workers only ever see presigned URLs. Users who need custom gated pulls
bake them into their own digest-pinned image (untrusted tier, OpenCode
Q3). My Q3 asks Harbinger to confirm this reading.

## 7. Testing: estimate replay harness

Complements Mistral's zero-spend harness: recorded `events.jsonl` and
billed actuals from real completed jobs are replayed against the
estimator (catalogue version pinned) in plain pytest, so estimate
accuracy is regression-tested without spend. Live smoke tests stay
behind the same gate as benchmarks (AGENTS.md RESOURCE RULE; Mistral Q1).

## 8. Questions for Harbinger

Recommendation first in each list. None of these re-ask a recorded answer.

### Q1 — What is the unit of work for multi-item jobs?

- **(a) Recommended: shards.** Job = a manifest of shards; retry,
  collection, progress, and cost attribution all happen at shard
  granularity. LoRA is a one-shard job; a 10,000-file extraction retries
  only its failed slices.
- **(b):** One job per item (file/prompt/image), visually grouped by a
  batch id. Simplest ledger; floods the jobs table with 10,000 rows and
  10,000 estimate rows per real job.
- **(c):** Job-level only; partial failure means retry the whole job or
  collect it partial. Least bookkeeping, most re-spend.

### Q2 — May multiple jobs share one provisioned instance?

- **(a) Recommended: strict 1:1 job:instance in v1.** Simplest
  accounting, teardown, and cap logic; refcounted cache volumes
  (Grok Q6) already amortize boot and weight downloads across jobs.
- **(b):** Sequential chaining — the daemon queues same-account jobs onto
  one warm instance. Saves idle boot minutes; complicates the lease and
  spend ledger and delays teardown of a billing instance.
- **(c):** Parallel packing with per-job quotas. Best utilization, worst
  blast radius: one misbehaving job can take down the instance and its
  neighbors.

### Q3 — How are gated model repos (HuggingFace tokens) handled?

- **(a) Recommended: no worker credentials, ever.** The daemon resolves
  gated weights into the staging manifest from the local library,
  subject to the weight cloud-classes (Grok Q3); custom gated pulls exist
  only inside user-supplied images.
- **(b):** A short-lived HF token is injected per job via the provider's
  secret mechanism. Convenient; punches the no-credential boundary the
  other answers keep drawing.
- **(c):** v1 supports only publicly downloadable models; even
  first-party workers require user-baked images for gated weights.

### Q4 — Is there a global emergency stop?

- **(a) Recommended: yes.** One "Stop all cloud activity" action in the
  Cloud Jobs header: checkpoint-cancel everything (Cursor Q7 semantics),
  revoke leases, trigger watchdog teardown, block new submits until
  re-enabled; usable with the GUI closed via daemon IPC.
- **(b):** Per-provider stop toggles in Settings only.
- **(c):** No global control; per-job Cancel/Force stop is enough.

### Q5 — Any remote or mobile monitoring in v1?

- **(a) Recommended: desktop-only in v1.** Daemon IPC stays local; the
  `api/` Django project is not extended for cloud jobs yet. Revisit once
  v1 ships and real usage says what remote view matters.
- **(b):** Read-only remote monitor — extend `api/` with token-auth'd
  cloud-jobs read endpoints (status, spend, logs) for mobile/web.
- **(c):** Full remote manage (cancel/retry from a phone). Stretches the
  credential-lease design onto the public internet; out of proportion
  for v1.

### Q6 — Scheduled or delayed submission?

- **(a) Recommended: submit-now only in v1.** No clock transitions in
  the state machine; scheduled starts become a later feature on the same
  JobSpec.
- **(b):** Run-at-wall-clock-time scheduling in the daemon.
- **(c):** Spot-window scheduling (start when price/capacity conditions
  are met). Tempting for GPU cost, but it needs the
  `waiting_for_capacity` machinery declined in Grok Q2.

### Q7 — Should quota/capacity be a preflight probe?

- **(a) Recommended: yes** — a quota probe runs right before costing;
  failure hard-blocks with the provider's quota-request link (Azure ACI
  GPU quotas default to 0, per Mistral §5). Consistent with fail-fast on
  out-of-stock (Grok Q2) and costs nothing.
- **(b):** Skip the probe; surface provider quota errors at submit time.
  Fewer API calls, worse UX.
- **(c):** Hold the job in `queued` until quota appears — waits forever
  if the user never files the request.

### Q8 — Should submit end in a confirmation sheet?

- **(a) Recommended: yes — a Plan & cost sheet.** Providers, execution
  mode, storage method, staging-manifest size, estimated total with the
  Mistral §3 breakdown, risk findings with ⚠; "Submit" is an explicit
  final click.
- **(b):** Inline estimates only, one-click submit. Frictionless, but a
  misclick is a real invoice.
- **(c):** No confirmation; submit fires immediately with a toast. Only
  sane for free tiers this service does not have.
