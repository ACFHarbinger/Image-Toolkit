# Cloud Jobs Service — OpenCode proposal

— OpenCode, 2026-10-19. Proposal only; builds on Harbinger's recorded answers
and the proposals from Claude, Codex, and Gemini. No implementation.

## Summary

I agree with the emerging consensus: the core is an asynchronous,
provider-neutral job lifecycle with durable state, a reconciler, and teardown
tracked separately from computation. Provider adapters and the manager UI sit
on top of that. I am not restating that architecture here.

This proposal adds the pieces the current proposals still leave thin:

1. a concrete **supervisor contract** for the out-of-app daemon — single
   instance, local IPC, version handshake, crash-only recovery, cross-platform;
2. a **unified admission/placement planner** that includes the local GPU
   arbiter, so cloud is the escalation path rather than a separate world;
3. a **worker trust model** for user-supplied images, because
   "user-supplied container" (recorded Q5 answer) is the largest new security
   boundary in this feature. Harbinger chose the digest-pinned + warning path,
   so the non-negotiable credential/output boundaries stay and the full
   sandbox becomes an optional "strict isolation" profile;
4. an **adapter certification kit** so eight providers cannot drift into eight
   half-contracts;
5. a per-job **flight recorder** and a manager UI focused on "needs attention",
   cost forecast, and a kill switch;
6. a **crash-point test matrix** that proves teardown and no duplicate spend
   before any paid provider is wired.

Persistence follows the recorded PostgreSQL + daemon-WAL answer; I am not
reopening the SQLite question.

## 1. Supervisor contract (the part the daemon answer still needs)

The recorded lifetime answer is "jobs keep running after the app closes; a
local daemon watches them and guarantees teardown." A daemon with no lifecycle
contract becomes a second source of truth and a new leak path. Concrete
shape:

- **One detached supervisor**, `backend/src/cloud/supervisor.py`, started by
  the GUI on demand (and by `python backend/main.py cloud-daemon
  --foreground` for debugging). It exits after an idle grace period only when
  there are no active jobs and no outstanding teardown obligations.
- **Single instance.** Take an OS-level lock (POSIX `flock`, Windows named
  mutex) plus a heartbeat row/file. A stale lock is not proof of death; a new
  process may take over only after the existing leader lease expires (the
  fencing Codex described). Never let two supervisors call providers for the
  same job.
- **Local IPC only.** Unix domain socket on Linux/macOS, named pipe on
  Windows, under the app config root, mode `0600`, with a random per-install
  token in a separate `0600` file. No TCP listener, no remote unlock. The GUI
  is a client; provider calls, retries, and transfers never run on the Qt
  thread.
- **Versioned protocol.** JSON-lines requests with request id, protocol
  version, and auth token. On an app/daemon version mismatch, drain then
  restart the supervisor; refuse unknown commands instead of guessing.
- **Crash-only design.** Any process may die at any instruction. Submission
  intent and teardown obligations are durable before the provider call; the
  reconciler is idempotent. A supervisor crash must not change what the cloud
  is doing; the next start reconciles it.
- **Cross-platform autostart** is deliberately *not* v1. Offer "start with
  the app" and tray status first; an OS service/launchd/Task Scheduler install
  can follow once the contract is stable.
- **Tradeoff:** more moving parts than a GUI-owned reconciler. It is the only
  way to make the recorded lifetime answer true while the app is closed, and
  the IPC boundary also keeps provider SDKs out of the GUI process.

## 2. Unified admission and placement (local → cloud)

Cloud offload should appear exactly where local work fails, not only in a
separate cloud window. Add a Qt-free `PlacementPlan` (for example
`backend/src/cloud/placement.py`) as the single decision surface used by both
the Extractor/ComfyUI/LoRA paths and the Cloud Jobs window.

- **Inputs:** `JobSpec`, a snapshot from `gpu_lease_arbiter` (owner, estimated
  VRAM, device total, profile, external Comfy session), capability catalogue,
  budget state, privacy policy, provider health, and the user's provider/GPU
  ranking.
- **Outputs:** `LOCAL`, `CLOUD(provider, mode, shape)`, `QUEUE_LOCAL`,
  `ASK_USER`, or `BLOCKED`. Each cloud candidate carries estimated total cost,
  estimated wall time, confidence, blocking rules, and a short `why` list.
- **Escalation:** when the local arbiter refuses a job for VRAM, offer
  "Run in cloud instead", prefilled with the same spec and an estimate. When
  the cloud budget is exhausted, offer local/queue instead. Neither direction
  silently spends money.
- **No paid surprise:** automatic fallback only within the user's approved
  provider/region/GPU list and retry budget (recorded Codex Q3 answer). The
  planner explains why it placed a job where it did and what the next-cheapest
  alternative would cost.
- **Deterministic and testable:** pure function, injected clock and fake
  capabilities. Same rule IDs and thresholds as the risk evaluator and the
  Settings cost safeguards.
- **Tradeoff:** one more layer between the job kinds and the provider adapters.
  In exchange, local and cloud admission stop being two unrelated policies.

## 3. Trust tiers for workers and user images

Recorded Q5 allows version-pinned packs plus user-supplied container images.
Harbinger then chose **option (c)** for how to constrain them: digest-pinned
images run under normal provider isolation with a prominent warning. The full
Tier B sandbox is therefore not a v1 gate. Keep these boundaries, because they
do not depend on trusting the image:

- **First-party images** are built from this repo, digest-pinned, and
  published to our registry. They still get only job-scoped presigned URLs,
  never VaultManager or database credentials.
- **User-supplied images and arbitrary ComfyUI custom nodes** are third-party
  code even when a node pack looks "supported". Reject mutable tags such as
  `:latest`; pass only short-lived presigned URLs; never inject provider
  identity, VaultManager, or database credentials.
- **Outputs are untrusted input.** Never execute them; cap archive sizes;
  validate manifests and hashes before import; route mismatches to review
  (consistent with the recorded import answer).
- **Redact** prompts, filenames, URLs, and tokens from logs by default. The
  submit warning and the job detail should state plainly that a malicious
  image can exfiltrate its own inputs or presigned URLs.
- **Optional strict-isolation profile** (future hardening, not a blocker): no
  provider instance role or metadata credentials; no host mounts, Docker
  socket, or local network; read-only root filesystem; non-root user; hard
  CPU/GPU/disk/wall-clock caps; egress allowlist limited to the staging
  endpoint; quarantined outputs; enforcement verified with a test that tries
  to reach a non-allowlisted host.
- **Tradeoff:** option (c) is faster for users but pushes risk onto the warning
  and on the provider's default isolation. Do not describe it as sandboxed.

## 4. Adapter certification kit

Eight providers, several of them young APIs, will not stay consistent without
a shared contract. Add `backend/src/cloud/testing/adapter_contract.py` (or
equivalent) that every adapter must pass before it is listed as usable:

- submit with idempotency key; **unknown submit outcome** reconciles owned
  resources before any retry;
- poll, cancel, logs, `list_owned_resources`, teardown, expiry/deadline;
- pagination, rate-limit/backoff, timeouts, clock skew;
- resource tags/name prefixes and ownership verification;
- capability manifest with evidence URL/date and explicit
  supported/unavailable/unverified states.

Certification levels: `declared` (manifest only), `recorded` (HTTP fixtures),
`live-smoke` (smallest real job, gated by Harbinger like benchmarks). The
manager UI should show the level, so "we wrote an adapter" is never mistaken
for "this provider is certified."

If a provider cannot list owned resources, the adapter must declare that
limitation and fall back to tags/name prefixes plus provider inventory, with a
visible warning. Leak protection cannot be stronger than the provider's
inventory API, and the UI should say so.

## 5. Flight recorder and support bundle

Every job gets a portable local bundle, for example under
`~/.image-toolkit/cloud/jobs/<job-id>/`:

- `job.json` — redacted spec and effective settings;
- `events.jsonl` — lifecycle and telemetry, same shape as `training_runs.py`;
- `attempts.jsonl` — durable attempt and idempotency records;
- `resources.jsonl` — owned resources and teardown evidence;
- `manifest.json` — output hashes, model/schema versions, checksums;
- `provider/` — redacted request/response evidence: method, URL with query
  secrets stripped, status, timing, provider request id.

"Export diagnostics" produces a zip with redaction applied. This is the
artifact that resolves provider billing disputes, API-churn bugs, and "the job
said it failed but the pod is still running" reports. Retention is
user-configurable, matching the recorded Q4 answer.

## 6. Manager UI additions

Beyond Claude's jobs/detail/resources/spend views:

- **Needs attention** inbox: blocked submissions, failed jobs, orphaned
  resources, credentials expiring, budget approaching/exceeded. Each row has a
  one-click remedy (retry, terminate, open settings).
- **Kill switch** with three explicit actions: *stop new submissions*, *drain
  current work*, and *stop all jobs and tear down* (typed confirmation).
  Partial outputs are retained; the UI states what will be lost.
- **Cost forecast:** projected month-end from current burn, estimate vs
  provider-reported actual, and "what changed" when the user edits a job.
- **Explainable placement:** why this provider/mode/shape was chosen, plus the
  next-best alternative and its cost/time delta.
- **Accessibility:** risk is not communicated by colour alone; include icon,
  text, and screen-reader labels. The job table must stay responsive while
  providers are slow or offline (render from the local store and IPC only).

## 7. Crash-point test matrix

Before a paid provider is wired, prove the lifecycle with fakes:

- enumerate every state transition and, for each, kill the supervisor before
  and after the side effect (persist intent, submit, provision, collect,
  teardown, delete); assert: no resource can bill without an obligation, no
  duplicate job, no lost collected output, no double budget reservation;
- fake provider with a virtual clock and fault injection: lost response, 500,
  slow provisioning, preemption, quota/rate limit, partial upload, torn
  `events.jsonl`, expired presigned URL;
- concurrent budget reservations and duplicate event delivery;
- property-based checks for idempotency keys and retention/TTL.

These run with no network and no spend, so they stay inside the normal
targeted-test rule. Live smoke tests remain opt-in and gated.

## 8. Rollout

- **Stage 0:** contracts, supervisor, placement planner, fake providers,
  crash matrix, PoC migration with shims. No paid calls.
- **Stage 1:** GCP (the existing Cloud Run worker) + RunPod Pods, end to end:
  extraction and ComfyUI.
- **Stage 2:** embedding/indexing and LoRA/LyCORIS, with checkpoint/resume and
  spot rules; add a second CPU provider behind the same contract.
- **Stage 3:** remaining providers, certified before exposure.

All four workloads remain v1; this is an implementation order, consistent with
the recorded sequencing answer.

## Provider assumptions to verify

I have not certified any provider API. Treat these as assumptions for the
rollout recommendation, not facts: GCP has the only worker this repo already
runs; RunPod exposes Pods and Serverless; Hyperstack and Thunder Compute look
instance-only and have younger APIs; Cloudflare Containers are CPU-oriented,
with R2 attractive for staging and Workers AI a separate inference capability;
Oracle has CPU and GPU compute shapes but stopped-instance billing needs
verification. Each adapter must land with a dated capability manifest and
evidence links.

## Risks

1. **Supervisor complexity** — a daemon, IPC, and fencing are more code than a
   GUI loop; crash-point tests and single-instance enforcement are mandatory.
2. **User-image escape/exfiltration** — mitigate with Tier B controls and an
   explicit "unverified isolation" state where a provider cannot enforce them.
3. **Provider API churn** — keep adapters thin, pin versions, certify with
   fixtures, and never let a manifest claim more than was tested.
4. **Stale prices** — version the catalogue, show `last_verified`, and
   reconcile against provider billing where possible.
5. **False confidence in cleanup** — if a provider cannot list resources, say
   so in the UI rather than presenting a sweep as complete.

## Q. Questions for Harbinger

Recommended option first. These are new questions; the answered ones in the
brief are not repeated.

### [OpenCode Q1] Which providers ship first?

- **(a) Recommended: GCP + RunPod.** Reuse the existing Cloud Run worker as the
  first managed-batch backend, and use RunPod Pods for the first GPU path. This
  is the shortest route to one real CPU job and one real GPU job end to end;
  RunPod can add Serverless later.
- **(b) AWS Batch + RunPod.** Broadest enterprise reach and S3; more IAM,
  queue, and registry setup to validate before the first job.
- **(c) Oracle + Thunder Compute.** Lowest hourly prices, but the youngest
  APIs and thinnest documentation, so slower to certify and debug.
- **(d) Cloudflare Containers + Hyperstack.** R2 is attractive for staging,
  but Cloudflare is CPU-oriented and Hyperstack is instance-only; neither
  reduces first-job risk.

### [OpenCode Q2] Should the UI suggest a default execution mode per workload?

- **(a) Recommended: yes.** Extraction/embedding/phash default to managed
  batch; ComfyUI and LoRA default to an instance because they need a
  persistent GPU/volume and run longer. Always overridable.
- **(b) No default.** The user chooses every time; more friction, but no stale
  assumptions.
- **(c) Learn from history.** Default from the user's completed jobs; needs
  history before the first use.

### [OpenCode Q3] How should user-supplied images be constrained?

- **(a) Recommended: untrusted tier.** Digest-pinned only; no provider
  identity; job-scoped presigned URLs; egress allowlist; read-only root;
  non-root; no host mounts/metadata; hard caps; quarantined outputs. If the
  provider cannot enforce this, disable the combination or require explicit
  acknowledgement.
- **(b) Signed base image required.** User images must be built `FROM` a
  first-party base with a declared dependency manifest; still run untrusted,
  but reuse more layers.
- **(c) Warning only.** Any digest-pinned image runs under normal provider
  isolation with a prominent warning. Fastest, weakest.

### [OpenCode Q4] Provider accounts and credentials?

- **(a) Recommended: bring-your-own accounts.** Keys stored in VaultManager,
  least-privilege IAM templates per provider, and Toolkit-side estimates/caps.
- **(b) Project-managed accounts.** Simplest onboarding, but you own abuse,
  billing, and liability.
- **(c) Hybrid.** Managed cheap CPU/staging, BYO for GPU compute.

### [OpenCode Q5] What should a hard spend cap do to a running job?

- **(a) Recommended: predict forward, then stop.** When projected cost reaches
  the cap, checkpoint if the workload supports it, cancel, and tear down. Keep
  partial outputs; show actual vs cap.
- **(b) Stop immediately at the cap.** Simplest; loses uncheckpointed work.
- **(c) Warn only.** Caps stop being hard caps.
- **(d) Pause and ask.** Safer for attended jobs, but the user may be away.

### [OpenCode Q6] Where do pricing and actual spend come from?

- **(a) Recommended: curated catalogue + billing reconciliation.** A versioned
  in-repo price catalogue (provider/region/shape/GPU, `last_verified`, user
  overrides) drives estimates; reconcile against provider billing APIs daily
  where available and show estimate vs actual.
- **(b) Live price APIs only.** Fresher, but incomplete across GPU
  marketplaces and adds a runtime dependency.
- **(c) User-entered prices only.** No shipped data; poor first-run.

### [OpenCode Q7] How should private data be classified for cloud dispatch?

- **(a) Recommended: per-job data classes + provider allowlist.** Public/model,
  private library, and sensitive; private needs a warning; sensitive is
  blocked from Cloud Sync remotes and third-party GPU hosts unless explicitly
  allowed per job. Redact prompts/filenames from logs by default.
- **(b) One global "allow cloud processing" switch.** One first-run warning.
- **(c) No classification.** Warn on every dispatch.

### [OpenCode Q8] Where should collected outputs land?

- **(a) Recommended: a per-job collection/group.** e.g.
  `Cloud Jobs/<job-id>` with its manifest; the user promotes results into the
  library when satisfied. Keeps unvalidated cloud output out of normal albums.
- **(b) The currently selected collection.** Convenient, but mixes unreviewed
  output into the user's working set.
- **(c) A configured output folder only.** No library import; the user manages
  it outside the app.

## Recorded answers (2026-10-19)

Harbinger answered all eight; these supersede the recommendations where they
differ.

- **Q1 → (a)** GCP + RunPod first.
- **Q2 → (a)** Suggest a default mode per workload, always overridable.
- **Q3 → (c)** Digest-pinned user images run under normal provider isolation
  with a prominent warning. The non-negotiable credential/output boundaries in
  §3 still apply; strict isolation becomes optional hardening.
- **Q4 → (a)** Bring-your-own provider accounts through VaultManager.
- **Q5 → (a)** Predict forward; checkpoint if possible, cancel and tear down
  at the cap, keep partial outputs.
- **Q6 → (a) plus (b) where available.** Curated versioned catalogue for
  estimates, live provider price APIs where they exist, and billing
  reconciliation for actuals.
- **Q7 → (a)** Per-job data classes plus provider allowlist and log redaction.
- **Q8 → (a)** Per-job `Cloud Jobs/<job-id>` collection with manifest; user
  promotes results.

— OpenCode, 2026-10-19
