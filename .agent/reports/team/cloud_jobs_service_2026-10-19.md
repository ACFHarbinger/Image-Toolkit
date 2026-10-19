# Cloud Jobs Service — Team Brainstorm

**Participants:** Harbinger, Claude, and (invited) Codex, Gemini, Grok,
Cursor, Mistral, Kimi, OpenCode.

**Origin:** Harbinger wants a new backend service under `backend/src/cloud/`
that runs CPU- and GPU-intensive jobs in the cloud, plus a new manager UI
(window or tab) to monitor and manage those jobs. This is a
**brainstorming round**: agents ask Harbinger questions and propose
options. Nothing here is approved for implementation yet. The rule from
`.agent/bus/onboarding/README.md` §4.2 applies: claim on the bus, wait for
the phase gate, then code. Don't start building from your own proposal.

This is a **living document**. Add your proposal summary under §4 and your
questions under §5. Don't rewrite other people's sections. Sign and date
what you add.

---

## 1. Goal

1. **A cloud jobs service** in `backend/src/cloud/` (the directory exists
   and is empty) that submits, tracks, and collects heavy jobs on:
   - **CPU:** AWS, GCP, Azure.
   - **GPU:** RunPod, Hyperstack, Thunder Compute.
   - **Also in scope (added 2026-10-19):** Cloudflare and Oracle. How to
     classify them is still open; see §5 Q10.
2. **A manager UI** (a new window or tab) to monitor and manage cloud jobs:
   status, logs, progress, cost, cancel and retry, outputs, and the live
   cloud resources the jobs created.

## 2. Current state (build on this; don't assume)

- **§4.21 Cloud Compute Offload** (`docs/moon/roadmaps/new_features.md`,
  issues #486–#491, all closed). This was a proof of concept: Extractor-tab
  extractions run on Google Cloud Run.
  - **Backend:** `backend/src/web/cloud/compute/`, about 1,050 lines.
    - `CloudJob` holds the extraction-only wire schema.
    - `CloudProviderAdapter.run(job)` is **synchronous and blocking**.
    - `GCDCloudRunAdapter` is the only real adapter. Cloudflare and Oracle
      are `NotImplementedError` stubs.
    - `CloudExtractionDispatcher` uploads to GCS, runs the job, downloads
      the outputs, and writes a usage row.
    - `UsageStore` holds those usage rows as JSONL.
  - **Worker:** `infra/cloud/gcd/worker/`, an FFmpeg-only Cloud Run
    container exposing `POST /jobs`.
  - **Other infra stubs:** `infra/cloud/aws/cfn-template.yaml`, `cloudflare/`
    and `oracle/`. `azure-pipelines/` is CI, not compute.
  - **GUI:** `gui/src/windows/cloud/` holds the Cloud Compute window. Its
    panes are Providers, Request Builder (which has a small "Cloud Job
    Queue & Activity" table), Dashboards (with usage charts) and Settings.
  - **None of the six target providers has an adapter.** AWS only has a
    descriptor card.
- **Pieces a cloud service could reuse or integrate with:**
  - `backend/src/core/vault_manager.py`: credentials. Never put secrets in
    configs.
  - `backend/src/core/gpu_lease_arbiter.py` and `gpu_vram_estimate.py`:
    local GPU admission and VRAM estimates. A natural "this won't fit
    locally → run it in the cloud" hook.
  - `backend/src/core/training_runs.py`: training run records with a
    `record.json` and an `events.jsonl` sink. The Deep Learning Runs view
    reads these.
  - `backend/src/web/cloud/` sync clients (Google Drive, OneDrive, Dropbox):
    an existing pattern for data movement and auth.
  - The wallpaper slideshow daemons: a precedent for a background process
    that outlives the GUI and is controlled through a JSON config with
    tokens.

**Provider facts:** verify these against each provider's *current* API
docs before relying on them in a proposal. Several of these products
change quickly.

## 3. Process

1. **Proposals only.** Don't build anything yet.
2. **Write your proposal** to
   `.agent/reports/<your-name>/cloud_jobs_service_proposal_2026-10-19.md`.
   Each proposal should cover:
   - **Ideas.** For each idea: what it is, the user problem it solves, a
     rough implementation shape, and its tradeoffs and risks. Cost and
     billing leaks, credential handling, data egress, cold starts, and
     provider API stability all count as risks here.
   - **Questions for Harbinger.** For each question, give 2–4 concrete
     options and your recommendation. Harbinger asked for questions with
     options, not open-ended "what do you want?".
   - **Coverage.** Depth beats forced coverage. Pick the axes in §6 where
     you have real ideas.
3. **Report back.**
   - Post a one-line pointer on `.agent/bus/2026-10-19.md`.
   - Add a short summary and link under §4.
   - Copy your questions into §5 and tag each one with your name.
4. **Harbinger answers** inline in §5.
5. **Final brainstorming round.** Harbinger and Claude review everything
   together, clear up any remaining ambiguity, and follow up on any
   interesting ideas that came up. The outcome is recorded in §7.
6. **Decision.** Harbinger and Claude lock the scope. Then they:
   - write a roadmap update (a new `docs/moon/roadmaps/cloud_jobs.md`, or
     §4.21 if the scope stays small);
   - create a GitHub milestone and issues.

## 4. Proposals (add yours here)

- **Claude** (2026-10-19):
  [Full proposal](../claude/cloud_jobs_service_proposal_2026-10-19.md).
  Recommends:
  - **Job model:** one provider-neutral job spec and an **asynchronous**
    job state machine. Today's blocking `run()` can't handle GPU instance
    lifecycles.
  - **Backend families:** two of them. *Instance* backends provision a
    VM or pod, run it, then tear it down; RunPod pods, Hyperstack, Thunder
    Compute and the VMs on the CPU clouds would be this kind. *Managed
    batch* backends are AWS Batch, GCP Batch or Cloud Run Jobs, Azure
    Container Apps Jobs, and RunPod Serverless.
  - **Job store:** a SQLite store that survives restarts, with a
    reconciler.
  - **Leak protection** as a first-class feature: tag every resource,
    sweep orphans at startup, and give each instance a self-terminate
    timer.
  - **Data and workers:**
    - presigned-URL staging, so workers hold no long-lived credentials;
    - one versioned worker image;
    - pre-flight cost estimates and budget caps.
  - **Manager UI:** a dedicated Cloud Jobs window, with a jobs table, a
    detail view (timeline, live log, spend so far), and a Resources view.

- **Codex** (2026-10-19):
  [Full proposal](../codex/cloud_jobs_service_proposal_2026-10-19.md).
  Recommends PostgreSQL (SQLite conflicts with AGENTS.md), durable attempts
  and submission reconciliation, independent remote cleanup protection,
  shared capability/risk rules, total-job cost estimates with budget
  reservations, bounded retries, version-pinned workload images, and
  validated local result imports. Flags that the current HTTP Cloud Run
  worker needs a durable lifecycle, not just a threaded wrapper. Includes
  sourced Cloudflare/Oracle checks; other provider combinations still need
  verification. All four workloads and all eight providers stay in scope.

- **Gemini** (2026-10-19):
  [Full proposal](../gemini/cloud_jobs_service_proposal_2026-10-19.md).
  Recommends PostgreSQL system of record coupled with a daemon-resident
  Write-Ahead Log (WAL) to ensure uninterrupted teardown and reconcile
  operations even during local database restarts or machine sleep;
  zero-trust ephemeral staging for Cloud Sync remotes (Drive/Dropbox/OneDrive)
  so workers never hold user OAuth refresh tokens; a push-telemetry event sink
  (`events.jsonl` matching `training_runs.py`) polled by the daemon to power live
  loss curves in the standalone Cloud Jobs window with zero inbound open ports;
  a pure-Python declarative risk evaluator (`RiskDiagnosis`) driving Qt control
  recolouring, warning banners (⚠), and hard greying-out; classification of
  Cloudflare for R2 zero-egress staging and CPU container tasks (excluding custom
  GPU/LoRA in v1); and a 2-stage staging table + SHA-256 hash validation protocol
  for safely merging cloud CLIP/phash vector indices into `pgvector`.

- **OpenCode** (2026-10-19):
  [Full proposal](../opencode/cloud_jobs_service_proposal_2026-10-19.md).
  Adds to the consensus:
  - a **supervisor contract** for the out-of-app daemon: single instance,
    local-only authenticated IPC, protocol version handshake, crash-only
    recovery, and cross-platform lock/pipe details;
  - a **unified placement planner** that includes the local
    `gpu_lease_arbiter`, so "run in cloud" is the explicit escalation path
    when local admission refuses a job;
  - a **two-tier worker trust model** for user-supplied images and arbitrary
    ComfyUI custom nodes, with egress allowlists, no provider identity,
    quarantined outputs, and an honest "unverified isolation" state;
  - an **adapter certification kit** with a shared contract, capability
    manifests, and declared/recorded/live-smoke levels;
  - a per-job **flight recorder** / redacted support bundle;
  - a **crash-point test matrix** covering every lifecycle transition and
    fault-injection case before paid adapters are wired;
  - a staged rollout starting with GCP + RunPod, all four workloads still in
    v1. Asks about first providers, default mode per workload, user-image
    sandboxing, account model, hard-cap behavior, pricing/billing source,
    privacy classes, and output placement.

- **Grok** (2026-10-19):
  [Full proposal](../grok/cloud_jobs_service_proposal_2026-10-19.md).
  Adds, on top of the recorded answers:
  - a **cloud admission snapshot** (max concurrent jobs, max GPU
    instances, max reserved spend) so queued work does not provision;
  - **one daemon per OS user**, shared across checkouts, with jobs
    tagged by profile;
  - **preflight scans** for weight cloud-class (`allow` / `warn` /
    `block`) and ComfyUI widget secrets, before any upload;
  - **instance boot via cloud-init** pulling a digest-pinned worker.
    Hyperstack and Thunder are instance APIs, not batch. Hyperstack has
    a stock endpoint, CPU flavors, and spot-as-a-separate-model-name.
    Thunder templates (`comfy-ui`) are an unverified override. Never
    omit Thunder `public_key` (the API may return a generated private
    key);
  - a local **`waiting_for_capacity`** state that polls stock and bills
    nothing until the chosen flavor exists;
  - **one refcounted cache volume per account and region**, plus a
    per-attempt scratch disk;
  - cloud training writes the existing `record.json` / `events.jsonl`
    layout so Deep Learning Runs keeps working;
  - **headless v1** (no floating IP, no forwarded port) and incremental
    shard collection. Asks about concurrency caps, stock waits, weight
    class, workflow secrets, boot strategy, cache topology, training
    visibility, and attended ComfyUI.
  - **Harbinger answered 2026-10-19:** Q1 A, Q2 B, Q3 A, Q4 A, Q5 A,
    Q6 A, Q7 A, Q8 C. Out-of-stock fails immediately (no
    `waiting_for_capacity` hold). An attended ComfyUI desktop is a
    separate product, not part of this jobs service.

- **Cursor** (2026-10-19):
  [Full proposal](../cursor/cloud_jobs_service_proposal_2026-10-19.md).
  Adds, on top of the recorded answers:
  - a **window map**: submit from the origin tab *and* Request Builder
    (Q1 C) via one `JobSpec` / `SubmitCloudJobIntent`; Cloud Jobs
    (`cloud.jobs`) is monitor/kill; Cloud Compute (`cloud.compute`)
    stays setup; header ☁️ badge opens Jobs, not a third builder;
  - a **job-scoped credential lease** so the daemon can poll/teardown
    after the GUI closes without holding the vault passphrase;
  - a concrete **watchdog home** for Codex Q1: tiny GCP function first,
    Cloudflare Worker also valid, watchdog-only IAM;
  - **user-owned Artifact Registry** for digest-pinned worker images,
    copied into `registry.cloudflare.com` when CF is selected;
  - sourced matrix: Cloud Run GPU task timeout ≤ 1h; RunPod adapter is
    **API v2 only** (v1 retires 2026-11-15); Thunder `mode` is
    deprecated; Hyperstack labels are a follow-up PUT and
    `assign_floating_ip` stays false; Oracle Container Instances are
    CPU-only (the existing Terraform comment is wrong); Azure
    serverless GPU is documented for apps, not Jobs.
  - Asks about submit surface, watchdog hosting, credential lease,
    image registry, header button, multi-machine, Cancel vs Force
    stop, and the GCP GPU path.
  - **Harbinger answered 2026-10-19:** Q1 C, Q2 A, Q3 A, Q4 A, Q5 A,
    Q6 A, Q7 A, Q8 A. Both Request Builder and origin-tab submit stay.
    Watchdog, credential lease, user Artifact Registry, one header
    control, shared-Postgres leader/observer, Cancel-then-Force-stop,
    and GCE for long GCP GPU jobs.

- **Mistral** (2026-10-19):
  [Full proposal](../mistral/cloud_jobs_service_proposal_2026-10-19.md).
  Builds on the recorded consensus and adds:
  - a **concrete state machine and reconciler**: `queued → submitting →
    provisioning → running → collecting → settling → terminal`, with
    intent + idempotency key persisted before the first provider call,
    ambiguous submits resolved by listing tagged provider resources,
    and the reconciler as a pure `(state, observation, settings) →
    actions` function replayed after crashes; the UI reads events only;
  - the **risk rule set Claude Q8 asked for**: shipped versioned YAML
    evaluated by a pure-Python engine, `block`/`warn`/`info`
    severities, generic field-path targets the form binds to,
    thresholds sourced from Settings (shared with the Q7 cost caps),
    and the same rules re-checked by the backend at submit;
  - a **placement suggestion card**: ranked candidates with a cost
    breakdown including egress, retained storage and expected retries,
    a price-age confidence band, one-click apply, capacity re-checked
    at submit;
  - a **zero-spend test harness**: scripted FakeProvider fault
    timelines, recorded HTTP fixtures per provider, and reconciler
    replay-table tests under normal pytest; live smoke tests as a
    separate opt-in marker;
  - sourced classifications: **AWS Batch supports GPU jobs** (EC2 GPU
    instance types, multi-node parallel training), so AWS managed batch
    is not CPU-only; **Azure** is CPU managed batch in v1 with GPU via
    the instance family until ACI GPU quotas (default 0) are verified
    per account;
  - **daemon UX**: a daemon status row (lease owner, WAL depth, last
    poll), attempt timeline from the event log, spend-so-far vs
    reserved.
  Asks about live-smoke gating, unattended notifications, region
  defaults, daemon platforms, rule editability, local history
  retention, and the UsageStore/Dashboards migration.

- **Kimi** (2026-10-19):
  [Full proposal](../kimi/cloud_jobs_service_proposal_2026-10-19.md).
  Adds, on top of the recorded answers:
  - a **shard model**: every job decomposes into shards (extraction =
    file slices, ComfyUI = prompt slices with fixed seeds, indexing =
    image-ID ranges, LoRA = one shard) so retry, collection, progress,
    spend attribution, and cap checkpoints all happen at shard
    granularity;
  - a minimal **adapter contract** — `plan` (pure) / `submit` /
    `observe` / `teardown` / `collect(attempt, shard)` — with a
    SDK-free capability manifest the risk engine reads, and provider
    SDKs pinned and isolated inside adapters;
  - one **fixed-order pure preflight pipeline** (validate → data class →
    secret scan → weight classes → quota probe → cost → risk rules →
    confirmation) shared by the UI and the backend submit path;
  - a **deterministic, snapshotted cost model** — estimates are a pure
    function of (spec, plan, catalogue) with catalogue rows stored per
    job, billing-granularity catalogue fields (rounding, minimums,
    public-IPv4 surcharges, per-pair egress), plus a **calibration
    loop** that flags catalogue rows whose estimate-vs-actual error
    drifts;
  - a global **emergency stop** ("Stop all cloud activity": checkpoint-
    cancel all, revoke leases, watchdog teardown, block new submits,
    usable GUI-closed);
  - **worker credential hardening for gated models**: no worker ever
    holds a HuggingFace token — the daemon resolves gated weights into
    the staging manifest under the weight cloud-classes;
  - an **estimate replay harness**: recorded events + billed actuals
    replayed against the pinned estimator in plain pytest.
  Asks about shard semantics, instance packing, gated models, the
  emergency stop, remote/mobile monitoring, scheduled submission, quota
  preflight, and a submit confirmation sheet.
  **Harbinger answered 2026-10-19:** Q1 A (shards); Q2 A/B/C as a
  Settings choice (all packing modes in scope, none default);
  Q3 A (no worker credentials); Q4 A (global emergency stop);
  Q5 C (full remote manage in v1 — `api/` grows authenticated endpoints);
  Q6 B (wall-clock scheduling in v1); Q7 A (quota preflight probe);
  Q8 A (Plan & cost confirmation sheet).

## 5. Questions for Harbinger (tag with your name; Harbinger answers inline)

Claude's questions are in its proposal (§Q). The first four were asked
directly in chat on 2026-10-19, and their answers are recorded here:

- **[Claude Q1] First workloads → ALL FOUR:**
  - ComfyUI batch generation (GPU);
  - LoRA/LyCORIS training (GPU);
  - extraction, ported from the PoC (CPU);
  - embedding and indexing: CLIP backfill and phash/dedup (CPU or GPU).

  Proposals should say how to sequence these, since all four are in v1.
- **[Claude Q2] Execution model → the USER CHOOSES how each job runs.**
  Harbinger picked none of the fixed options (batch on CPU clouds with
  instances on GPU clouds, instances everywhere, or managed only).
  - Both backend families (instance and managed batch/serverless) are in
    scope, and the user picks per job.
  - Open point for proposals: which provider supports which mode.
    Hyperstack and Thunder look instance-only; RunPod has Pods and
    Serverless; the CPU clouds have VMs and managed batch.
  - Also open: should the UI suggest a default mode per job kind?
- **[Claude Q3] Lifetime → jobs KEEP RUNNING after the app closes.**
  A local daemon keeps watching them, collects outputs and guarantees
  teardown. The wallpaper slideshow daemons are the precedent.
- **[Claude Q4] Manager UI → a STANDALONE "Cloud Jobs" window.**
  - It opens from the header and shows a badge with running jobs and
    spend.
  - The Cloud Compute window stays the setup surface: providers,
    credentials and the request builder.

- **[Claude Q5] Data staging → the USER SELECTS the storage method.**
  - All three options are in scope:
    - one user-chosen bucket (S3, GCS or Azure Blob) with presigned URLs;
    - each provider's native storage or volumes;
    - the existing Cloud Sync remotes (Google Drive, OneDrive, Dropbox).
  - Proposals should define a storage interface these plug into.
  - Also needed: which storage methods each provider and execution mode
    can actually use.
- **[Claude Q6] Provider placement → the user picks and the service
  suggests.**
  - The suggestion is the cheapest option that has capacity.
  - The user can rank fallback GPU classes.
- **[Claude Q7] Cost safeguards → ALL of them, each set in Settings.**
  - The safeguards: pre-flight estimates, warnings at thresholds, and hard
    caps (per-job max runtime, per-job max spend, monthly cap).
  - The user decides in Settings which are on and what their values are.
- **[Claude Q9] Existing PoC code → migrate it into `backend/src/cloud/`.**
  - Leave re-export shims at `backend/src/web/cloud/compute/` for one
    release.
  - The Cloud Run adapter becomes the first managed-batch backend.

- **[Claude Q8] Spot/preemptible → handled through risk feedback in the
  UI, not a fixed policy.** The job configuration UI reacts to the
  parameters set for a job in three ways:
  - It **recolours the background and text** of the affected controls or
    sections according to the risk level.
  - It shows a **textual warning** in bright colours with a ⚠ sign. This
    warns the user about using certain resources for that job, for
    example spot instances for a job that can't resume, an expensive GPU
    class, a long max runtime, or a large egress.
  - It **greys out options entirely** where the combination is invalid or
    unsupported, for example spot for a kind that can't resume from a
    checkpoint, or a storage method the selected provider and mode can't
    use.

  This applies to every job option, not only spot. Proposals should
  define the rule set for warnings and disabled options (which job
  parameters trigger which level) and where the rules live. The rules
  should be data-driven and testable without Qt. They should share their
  thresholds with the Q7 cost safeguards in Settings.
- **[Claude Q10] Cloudflare and Oracle → IN SCOPE as providers too.**
  - The provider list is now AWS, GCP, Azure, Cloudflare, Oracle, RunPod,
    Hyperstack and Thunder Compute.
  - Proposals should classify each provider:
    - **Oracle** has CPU and GPU shapes.
    - **Cloudflare:** check what it can actually run today. Workers,
      Queues and R2 are the obvious pieces. Check current docs for its
      container and GPU offerings.
  - The existing stubs, `infra/cloud/cloudflare/` and
    `infra/cloud/oracle/`, are the starting point.

All ten of Claude's questions are now answered.

### Codex — 2026-10-19 (all seven answered)

- **[Codex Q1] What protects running jobs when the computer is asleep or offline?**
  - **Harbinger answer (2026-10-19; recorded by Codex):** A + B; C is optional future work. Use the local daemon and cloud-side cleanup watchdog together with verified provider-native deadlines. Where protection is reduced, disclose it and require acknowledgement. An always-on remote controller is deferred.
  - **A (recommended):** local daemon plus a small cloud-side cleanup watchdog; require a verified remote deadline for unattended jobs.
  - **B:** use provider-native deadlines where verified; other modes show reduced protection and require explicit acknowledgement.
  - **C:** deploy an always-on remote controller as well as the local daemon; more setup and operating cost.
- **[Codex Q2] What should “cheapest” mean in suggestions?**
  - **Harbinger answer (2026-10-19; recorded by Codex):** A, with C when the user sets a completion deadline. Rank by estimated total job cost; if a deadline is supplied, rank compatible candidates expected to meet it.
  - **A (recommended):** estimated total job cost, including startup, transfers, storage and retries; show uncertainty and price age.
  - **B:** lowest hourly compute price; simpler, but may cost more for the completed job.
  - **C:** lowest estimated total cost among options meeting a user-set completion deadline.
- **[Codex Q3] How much recovery may happen automatically?**
  - **Harbinger answer (2026-10-19; recorded by Codex):** A by default; B as an optional setting. Use bounded retries on the selected provider, asking before placement/storage changes unless the user enables automatic fallback within an approved list and retry budget.
  - **A (recommended):** bounded retries on the selected provider; ask before changing provider, region or storage.
  - **B:** automatic fallback within a user-approved provider/region/GPU list and retry budget.
  - **C:** manual retry after every failed attempt.
  Unknown submission outcomes must be reconciled before any option retries.
- **[Codex Q4] What should happen to paid caches and staged data after completion?**
  - **Harbinger answer (2026-10-19; recorded by Codex):** User-configurable in Settings. Offer retention/cleanup policies for staged inputs, model caches and outputs, including expiry and storage-budget controls. No single retention policy or default was selected in this answer.
  - **A (recommended):** delete temporary inputs after verified collection; retain reusable models with an editable TTL and storage budget; retain uncollected outputs until their explicit retention deadline.
  - **B:** delete all temporary data and caches after verified collection; cold starts repeat.
  - **C:** retain everything until manual deletion; show ongoing storage cost.
- **[Codex Q5] Which ComfyUI workflows should cloud v1 accept?**
  - **Harbinger answer (2026-10-19; recorded by Codex):** B. Support version-pinned node packs plus user-supplied container images in v1.
  - **A (recommended):** supported, version-pinned node packs first; incompatible workflows get an actionable preflight error.
  - **B:** supported packs plus a user-supplied container image; broader support and more troubleshooting.
  - **C:** build a custom image automatically from each workflow's dependencies; most flexible, largest security and maintenance burden.
- **[Codex Q6] When may cloud results update the local library?**
  - **Harbinger answer (2026-10-19; recorded by Codex):** A. Auto-import validated results only when source hashes and model/schema versions match; route mismatches to review.
  - **A (recommended):** auto-import validated results only when source hashes and model/schema versions still match; send mismatches to review.
  - **B:** review every result before importing.
  - **C:** download only; importing remains a separate manual action.
  Workers receive no direct credentials for the local image database in any option.
- **[Codex Q7] How should the four required workloads be sequenced within v1?**
  - **Harbinger answer (2026-10-19; recorded by Codex):** A. Extraction → ComfyUI → embedding/indexing → LoRA/LyCORIS, with restart and cleanup checks at each step. All four remain in v1.
  - **A (recommended):** extraction → ComfyUI → embedding/indexing → LoRA/LyCORIS, with restart and cleanup checks at each step.
  - **B:** extraction → training → ComfyUI → indexing, validating checkpoints earlier.
  - **C:** build the four workload integrations concurrently after the lifecycle contract is agreed; faster breadth, higher integration risk.
  All four remain in v1; this chooses implementation order, not reduced scope.

### Gemini — 2026-10-19 (all five answered)

- **[Gemini Q1] Cloud Sync Remote (Drive/Dropbox/OneDrive) Staging Protocol:**
  - **Harbinger answer (2026-10-19; recorded by Gemini):** A. Local daemon ephemeral staging: the local daemon stages needed inputs from the Cloud Sync remote (or local mirror) to an ephemeral presigned bucket/storage endpoint, and uploads final outputs back to the remote upon collection. Remote workers only touch short-lived presigned URLs and never hold Cloud Sync credentials.
  - **A (recommended):** Local daemon ephemeral staging. The local daemon downloads needed inputs from the Cloud Sync remote (or reads local sync mirror), stages them to an ephemeral presigned bucket/storage endpoint, and uploads final outputs back to the remote upon collection. Remote workers only touch short-lived presigned URLs and never hold Cloud Sync credentials.
  - **B:** Direct in-worker Cloud Sync with ephemeral OAuth tokens. The daemon issues short-lived, downscoped access tokens to the worker container, which runs headless rclone/SDK to fetch directly from Google Drive/OneDrive.
  - **C:** Restrict Cloud Sync remotes to staging targets only. Cloud Sync remotes can be selected as final archival destinations, but the intermediate job execution must use native provider storage or S3/GCS.
- **[Gemini Q2] Telemetry & Live Training Logs Protocol:**
  - **Harbinger answer (2026-10-19; recorded by Gemini):** A. Presigned append-only event sink (`events.jsonl` matching `training_runs.py` format) with daemon byte-range polling every 2–5 seconds, streaming over local IPC to GUI. Zero inbound open ports.
  - **A (recommended):** Presigned append-only event sink (`events.jsonl`) with daemon polling. The remote worker appends telemetry lines to an `events.jsonl` on staging storage (matching `training_runs.py` format). The local daemon polls byte ranges every 2–5 seconds and relays updates over local IPC to the GUI.
  - **B:** Outbound serverless WebSocket relay. A lightweight serverless relay (e.g. Cloudflare Worker) bridges events pushed by the worker to a persistent outbound WebSocket held by the local daemon.
  - **C:** Terminal batch retrieval only. No live metric streaming during execution; console logs and checkpoint reports are downloaded as a batch artifact only upon job completion or termination.
- **[Gemini Q3] Cloudflare Provider Workload Scope in v1:**
  - **Harbinger answer (2026-10-19; recorded by Gemini):** B. Full compute + Workers AI proxying: use Cloudflare Containers for eligible CPU tasks and map compatible prompt-based inference to Cloudflare Workers AI fixed endpoints, while using R2 for zero-egress staging.
  - **A (recommended):** R2 zero-egress staging + Cloudflare Containers for CPU tasks only. Utilize R2 as an inexpensive staging tier across all clouds, and Cloudflare Containers for CPU extraction and phash/CLIP indexing. Exclude custom GPU training and arbitrary ComfyUI graphs on Cloudflare in v1.
  - **B:** Full compute + Workers AI proxying. Use Containers for CPU workloads and map compatible prompt inference requests to Cloudflare Workers AI fixed endpoints.
  - **C:** Edge storage & webhook tier only. Restrict Cloudflare strictly to R2 storage and edge coordination; run all compute on the other 7 providers.
- **[Gemini Q4] Database Resiliency & Headless Daemon Operations:**
  - **Harbinger answer (2026-10-19; recorded by Gemini):** A. PostgreSQL system of record with daemon in-memory/WAL fallback for teardown obligations and reconciliation during transient DB disconnects or shutdown.
  - **A (recommended):** PostgreSQL system of record with daemon in-memory/WAL fallback. PostgreSQL stores all persistent job history, attempts, and budget ledgers. The local daemon keeps an append-only JSONL Write-Ahead Log of teardown obligations so that if PostgreSQL is temporarily unreachable during desktop shutdown, teardown enforcement continues unimpeded and syncs back on recovery.
  - **B:** Strict PostgreSQL dependency. The daemon operates strictly via active PostgreSQL connections. If PostgreSQL is offline, the daemon halts and relies entirely on cloud-side dead-man timers for instance termination.
  - **C:** Separate daemon state file. Maintain active orchestration state exclusively in a daemon JSON state file (`.cloud_daemon_state.json`, similar to `slideshow_daemon.py`), writing to PostgreSQL only upon job completion.
- **[Gemini Q5] Workload 4 (CLIP/phash) Vector Indexing Safety Gate:**
  - **Harbinger answer (2026-10-19; recorded by Gemini):** A with optional C as an on/off setting. Validated results stage through a hash verification table into an atomic transactional upsert by default; a Settings toggle allows requiring manual user review before importing.
  - **A (recommended):** Staging table + content hash verification + atomic chunked upsert. Worker outputs a Parquet vector archive. The local importer verifies image SHA-256 and modification timestamps against the local database, stages validated rows into a temporary table, and executes an atomic transaction with conflict resolution. Mismatches route to a Review list.
  - **B:** Direct bulk upsert. Ingest vectors directly via PostgreSQL `COPY` or bulk `INSERT ... ON CONFLICT DO UPDATE`, trusting the cloud batch output manifest without pre-flight hash re-verification.
  - **C:** Mandatory manual import review. Ingested vector batches are never auto-committed; they must be visually inspected and manually approved by the user in the Manager UI.

### OpenCode — 2026-10-19 (all eight answered)

Recommendation first in each list.

- **[OpenCode Q1] Which providers ship first?**
  - **Harbinger answer (2026-10-19; recorded by OpenCode):** (a) GCP + RunPod.
  - **(a) Recommended:** GCP + RunPod. Reuse the existing Cloud Run worker as the first managed-batch backend and RunPod Pods for the first GPU path; shortest route to one real CPU and one real GPU job end to end.
  - **(b):** AWS Batch + RunPod. Broadest enterprise reach and S3; more IAM/queue/registry setup before the first job.
  - **(c):** Oracle + Thunder Compute. Lowest hourly prices, but the youngest APIs and thinnest documentation.
  - **(d):** Cloudflare Containers + Hyperstack. R2 is attractive for staging, but Cloudflare is CPU-oriented and Hyperstack is instance-only.
- **[OpenCode Q2] Should the UI suggest a default execution mode per workload?**
  - **Harbinger answer (2026-10-19; recorded by OpenCode):** (a) Yes: extraction/embedding/phash default to managed batch; ComfyUI and LoRA default to an instance; always overridable.
  - **(a) Recommended:** Yes. Extraction/embedding/phash default to managed batch; ComfyUI and LoRA default to an instance because they need a persistent GPU/volume. Always overridable.
  - **(b):** No default; the user chooses every time.
  - **(c):** Learn defaults from the user's completed jobs; needs history before first use.
- **[OpenCode Q3] How should user-supplied images be constrained?** (The recorded Q5 answer already allows them.)
  - **Harbinger answer (2026-10-19; recorded by OpenCode):** (c) Any digest-pinned image runs under normal provider isolation with a prominent warning. The non-negotiable boundaries still apply: no VaultManager/database credentials in workers, job-scoped presigned URLs only, untrusted/quarantined outputs, redacted logs. The stricter sandbox remains an optional "strict isolation" profile and future hardening.
  - **(a) Recommended:** Untrusted tier: digest-pinned only, no provider identity, job-scoped presigned URLs, egress allowlist, read-only root, non-root, no host mounts/metadata, hard caps, quarantined outputs. If the provider cannot enforce this, disable the combination or require explicit acknowledgement.
  - **(b):** Require images to be built `FROM` a signed first-party base with a declared dependency manifest; still run untrusted.
  - **(c):** Any digest-pinned image with a prominent warning and normal provider isolation only.
- **[OpenCode Q4] Provider accounts and credentials?**
  - **Harbinger answer (2026-10-19; recorded by OpenCode):** (a) Bring-your-own accounts; keys in VaultManager, least-privilege IAM templates, Toolkit-side estimates/caps.
  - **(a) Recommended:** Bring-your-own accounts; keys in VaultManager, least-privilege IAM templates, Toolkit-side estimates/caps.
  - **(b):** Project-managed accounts; simplest onboarding, but the project owns abuse, billing, and liability.
  - **(c):** Hybrid: managed cheap CPU/staging, BYO for GPU compute.
- **[OpenCode Q5] What should a hard spend cap do to a running job?**
  - **Harbinger answer (2026-10-19; recorded by OpenCode):** (a) Predict forward; when projected cost reaches the cap, checkpoint if supported, cancel, and tear down. Keep partial outputs.
  - **(a) Recommended:** Predict forward; when projected cost reaches the cap, checkpoint if supported, cancel, and tear down. Keep partial outputs.
  - **(b):** Stop immediately at the cap; simplest, loses uncheckpointed work.
  - **(c):** Warn only; caps stop being hard caps.
  - **(d):** Pause and ask; safer for attended jobs, but the user may be away.
- **[OpenCode Q6] Where do pricing and actual spend come from?**
  - **Harbinger answer (2026-10-19; recorded by OpenCode):** (a) plus (b) for providers that expose a usable live price API: curated versioned catalogue for estimates, live APIs where available, and provider billing reconciliation for actuals.
  - **(a) Recommended:** Versioned curated price catalogue (`last_verified`, user overrides) for estimates, plus daily provider billing-API reconciliation where available; show estimate vs actual.
  - **(b):** Live price APIs only; fresher but incomplete across GPU marketplaces.
  - **(c):** User-entered prices only; no shipped data.
- **[OpenCode Q7] How should private data be classified for cloud dispatch?**
  - **Harbinger answer (2026-10-19; recorded by OpenCode):** (a) Per-job data classes plus a provider allowlist; private gets a warning; sensitive is blocked from Cloud Sync remotes and third-party GPU hosts unless explicitly allowed; redact prompts/filenames from logs by default.
  - **(a) Recommended:** Per-job data classes (public/model, private library, sensitive) plus a provider allowlist; private gets a warning; sensitive is blocked from Cloud Sync remotes and third-party GPU hosts unless explicitly allowed. Redact prompts/filenames from logs by default.
  - **(b):** One global "allow cloud processing" switch with a first-run warning.
  - **(c):** No classification; warn on every dispatch.
- **[OpenCode Q8] Where should collected outputs land?**
  - **Harbinger answer (2026-10-19; recorded by OpenCode):** (a) A per-job collection/group, e.g. `Cloud Jobs/<job-id>` with its manifest; the user promotes results when satisfied.
  - **(a) Recommended:** A per-job collection/group, e.g. `Cloud Jobs/<job-id>` with its manifest; the user promotes results when satisfied.
  - **(b):** The currently selected collection; convenient, but mixes unreviewed output into the working set.
  - **(c):** A configured output folder only; no library import.

### Grok — 2026-10-19 (all eight answered)

Harbinger's answers below supersede the original recommendations where they differ. Recorded by Grok, 2026-10-19. Scope still awaits the team final round.

- **[Grok Q1] How many cloud jobs may run at once?**
  - **Harbinger answer (2026-10-19; recorded by Grok):** A. Settings caps for max concurrent jobs, max concurrent GPU instances, and max reserved spend. Extra jobs wait locally in `queued` and do not provision.
  - **A (recommended):** Settings caps for max concurrent jobs, max concurrent GPU instances, and max reserved spend. Extra jobs wait locally in `queued` and do not provision.
  - **B:** No concurrency cap. The monthly spend cap is the only brake.
  - **C:** One GPU job at a time, always. CPU batch jobs are unlimited aside from the spend cap.
- **[Grok Q2] What happens when the chosen GPU is out of stock?**
  - **Harbinger answer (2026-10-19; recorded by Grok):** B. Fail the job immediately and leave retry to the user. No `waiting_for_capacity` hold in v1.
  - **A (recommended):** Hold the job locally in `waiting_for_capacity` until a user deadline, polling provider stock. Do not change GPU or provider unless automatic fallback is already enabled.
  - **B:** Fail the job immediately and leave retry to the user.
  - **C:** Automatically move to the next GPU class that fits the cap and the data-class allowlist.
- **[Grok Q3] May a job upload local model weights?**
  - **Harbinger answer (2026-10-19; recorded by Grok):** A. Each weight has a cloud class: `allow`, `warn`, or `block`. Unknown hashes warn and require acknowledgement. `block` never enters the staging manifest.
  - **A (recommended):** Each weight has a cloud class: `allow`, `warn`, or `block`. Unknown hashes warn and require acknowledgement. `block` never enters the staging manifest.
  - **B:** One global switch: the user accepts uploading weights to configured providers.
  - **C:** Never upload weights. Jobs may use only weights already on a provider cache volume.
- **[Grok Q4] What should preflight do with secrets inside a ComfyUI graph?**
  - **Harbinger answer (2026-10-19; recorded by Grok):** A. Scan widget values. Block submit until the user strips the flagged fields or explicitly keeps them. Logs store the redacted graph. The finding names the node id.
  - **A (recommended):** Scan widget values. Block submit until the user strips the flagged fields or explicitly keeps them. Logs store the redacted graph. The finding names the node id.
  - **B:** Reject any graph that is not in the pinned pack's known node set. No user override.
  - **C:** Upload the graph as-is and show a single warning.
- **[Grok Q5] What boots a Hyperstack or Thunder job?**
  - **Harbinger answer (2026-10-19; recorded by Grok):** A. Cloud-init always pulls our digest-pinned worker image. A provider template such as Thunder's `comfy-ui` is an explicit override, marked unverified, and still gets the secret scan, the no-credential rule, and hard caps.
  - **A (recommended):** Cloud-init always pulls our digest-pinned worker image. A provider template such as Thunder's `comfy-ui` is an explicit override, marked unverified, and still gets the secret scan, the no-credential rule, and hard caps.
  - **B:** Prefer the provider template when one exists. Our image is the fallback.
  - **C:** Provider templates only on Thunder. Our image everywhere else, with no template override.
- **[Grok Q6] Where do reusable model files live between jobs?**
  - **Harbinger answer (2026-10-19; recorded by Grok):** A. One cache volume per provider account and region, content-addressed and reference-counted by running jobs. Each attempt also has a scratch disk that is deleted with the attempt. Sharing can be turned off in Settings.
  - **A (recommended):** One cache volume per provider account and region, content-addressed and reference-counted by running jobs. Each attempt also has a scratch disk that is deleted with the attempt. Sharing can be turned off in Settings.
  - **B:** Per-job disk only. Every job re-downloads what it needs.
  - **C:** The user attaches an existing volume by hand on each job.
- **[Grok Q7] How should a cloud training run appear in the app?**
  - **Harbinger answer (2026-10-19; recorded by Grok):** A. The daemon writes the same `record.json` and `events.jsonl` layout as a local run. Deep Learning Runs, the report card, and the checkpoint tournament read it. Cloud Jobs shows spend and instances and links to that run.
  - **A (recommended):** The daemon writes the same `record.json` and `events.jsonl` layout as a local run. Deep Learning Runs, the report card, and the checkpoint tournament read it. Cloud Jobs shows spend and instances and links to that run.
  - **B:** Cloud training appears only in the Cloud Jobs window. Deep Learning Runs stays local-only.
  - **C:** Cloud Jobs grows its own copy of the training panels.
- **[Grok Q8] Does v1 open a ComfyUI web UI on the instance?**
  - **Harbinger answer (2026-10-19; recorded by Grok):** C. A separate "cloud ComfyUI desktop" product, not part of the jobs service. The jobs service does not open a web UI, floating IP, or forwarded port.
  - **A (recommended):** No. v1 jobs are headless. No floating public IP and no forwarded port. An attended UI can be a later session type that is time-boxed and torn down with the job.
  - **B:** Every ComfyUI job opens the web UI through an SSH tunnel or the provider port API until the job ends.
  - **C:** A separate "cloud ComfyUI desktop" product, not part of the jobs service.

### Cursor — 2026-10-19 (all eight answered)

Harbinger's answers below supersede the original recommendations where they differ. Recorded by Cursor, 2026-10-19. Scope still awaits the team final round.

- **[Cursor Q1] Where does the user submit a cloud job from?**
  - **Harbinger answer (2026-10-19; recorded by Cursor):** C. Keep both Request Builder and origin-tab submit. They must share one `JobSpec` so the two surfaces cannot drift.
  - **A (recommended):** From the origin tab (Extractor, ComfyUI, Train, Index) via `SubmitCloudJobIntent`. Cloud Jobs is monitor, kill, retry, clone. Cloud Compute Request Builder loses submit.
  - **B:** Cloud Jobs window is the only submit surface. Origin tabs offer "Open in Cloud Jobs with this spec".
  - **C:** Keep both Request Builder and origin-tab submit.
  - **D:** Fold monitor into Cloud Compute; no separate Cloud Jobs window after all. (Would reopen Claude Q4.)
- **[Cursor Q2] Where does the cloud-side cleanup watchdog run?**
  - **Harbinger answer (2026-10-19; recorded by Cursor):** A. Tiny job-scoped function in an account we already use: GCP Cloud Function/Run first, Cloudflare Worker also valid. Watchdog-only IAM. Heartbeat + deadline ⇒ teardown.
  - **A (recommended):** A tiny job-scoped function in an account we already use: GCP Cloud Function/Run first, Cloudflare Worker also valid. Watchdog-only IAM. Heartbeat + deadline ⇒ teardown.
  - **B:** Provider-native deadlines only. Combinations without a verified deadline require acknowledgement (Codex Q1 B).
  - **C:** A user-owned always-on mini VM as the watchdog.
  - **D:** No extra watchdog. In-instance dead-man + daemon WAL only.
- **[Cursor Q3] How does the daemon get credentials after the GUI closes?**
  - **Harbinger answer (2026-10-19; recorded by Cursor):** A. Job-scoped credential lease issued at submit while the vault is unlocked. Daemon never holds the vault passphrase. New submits still need the vault.
  - **A (recommended):** Job-scoped credential lease issued at submit while the vault is unlocked. Daemon never holds the vault passphrase. New submits still need the vault.
  - **B:** Daemon keeps decrypted copies of all configured cloud keys for its lifetime.
  - **C:** After the GUI closes, the daemon cannot call providers. Collection waits for the next unlock; only dead-man + watchdog tear down.
  - **D:** Daemon prompts the OS keyring / user when it next needs a key (fails unattended).
- **[Cursor Q4] Who publishes the first-party worker images?**
  - **Harbinger answer (2026-10-19; recorded by Cursor):** A. User-owned registry (GCP Artifact Registry first). Toolkit ships Dockerfiles and a publish action. Digests pinned. Cloudflare jobs copy into `registry.cloudflare.com`.
  - **A (recommended):** User-owned registry (GCP Artifact Registry first). Toolkit ships Dockerfiles and a publish action. Digests pinned. Cloudflare jobs copy into `registry.cloudflare.com`.
  - **B:** Project-public GHCR images the Toolkit publishes.
  - **C:** No first-party image after the extraction PoC; user-supplied digest-pinned images only.
  - **D:** Build locally with Docker and push at each submit.
- **[Cursor Q5] What does the header ☁️ button open?**
  - **Harbinger answer (2026-10-19; recorded by Cursor):** A. One control. Click opens Cloud Jobs (badge = running count + reserved spend). A gear / shift-click opens Cloud Compute setup.
  - **A (recommended):** One control. Click opens Cloud Jobs (badge = running count + reserved spend). A gear / shift-click opens Cloud Compute setup.
  - **B:** Two header buttons: Jobs and Compute.
  - **C:** Keep ☁️ as Cloud Compute. Cloud Jobs is only from that window's sidebar and from origin-tab "view job".
  - **D:** Delete the Cloud Compute window. Setup becomes a pane inside Cloud Jobs.
- **[Cursor Q6] May a second machine watch the same jobs?**
  - **Harbinger answer (2026-10-19; recorded by Cursor):** A. If they share PostgreSQL, one leader daemon; the other GUI is read-only until it wins the lease. If they do not share PostgreSQL, jobs stay on the submitting machine.
  - **A (recommended):** If they share PostgreSQL, one leader daemon; the other GUI is read-only until it wins the lease. If they do not share PostgreSQL, jobs stay on the submitting machine.
  - **B:** Jobs are bound to the submitting machine always. Other machines see results only after collection.
  - **C:** Any machine may steal the lease and take over collection and teardown.
  - **D:** Hide other-machine jobs in v1. No observer mode.
- **[Cursor Q7] What should Cancel do?**
  - **Harbinger answer (2026-10-19; recorded by Cursor):** A. Same as the hard cap: checkpoint if supported, collect verified shards, teardown. Force stop is a second, recoloured action that skips checkpoint.
  - **A (recommended):** Same as the hard cap: checkpoint if supported, collect verified shards, teardown. Force stop is a second, recoloured action that skips checkpoint.
  - **B:** Immediate kill always.
  - **C:** Cancel only records intent; the user confirms teardown in the Resources view.
  - **D:** Offer Pause (instance keeps billing) and Cancel (teardown).
- **[Cursor Q8] Long GCP GPU jobs vs Cloud Run's one-hour GPU timeout?**
  - **Harbinger answer (2026-10-19; recorded by Cursor):** A. Grey out Cloud Run GPU when the estimate exceeds the verified timeout. GCP ComfyUI/LoRA in v1 uses GCE (or Batch on GCE). Cloud Run stays the CPU extraction/index path, and GPU only for short jobs that fit.
  - **A (recommended):** Grey out Cloud Run GPU when the estimate exceeds the verified timeout. GCP ComfyUI/LoRA in v1 uses GCE (or Batch on GCE). Cloud Run stays the CPU extraction/index path, and GPU only for short jobs that fit.
  - **B:** Automatically shard long GPU work into ≤1h Cloud Run tasks.
  - **C:** Allow Cloud Run GPU with a hard 1h cap and a warning.
  - **D:** Cloud Run is CPU-only on GCP in v1. All GCP GPU is GCE/Batch from day one.

### Mistral — 2026-10-19 (all seven answered)

Recommendation first in each list. Harbinger's answers recorded by
Mistral, 2026-10-19. Scope still awaits the team final round.

- **[Mistral Q1] Who may run live smoke tests, and under what gate?**
  Real-provider smoke tests spend real money; they are the same class
  of hazard as the RESOURCE RULE's benchmarks and full suites.
  - **Harbinger answer (2026-10-19; recorded by Mistral):** (a). Same
    chain as benchmarks: opt-in `live_cloud` pytest marker, requested
    on the bus to Codex, who relays to Harbinger and waits for
    go-ahead; one live run at a time.
  - **(a) Recommended:** same chain as benchmarks — opt-in `live_cloud`
    pytest marker, requested on the bus to Codex, who relays to
    Harbinger and waits for go-ahead; one live run at a time.
  - **(b):** a dedicated sandbox account with a hard per-run spend cap
    (e.g. $2); any agent may run them without the chain.
  - **(c):** agents never run live; Harbinger runs them by hand and
    hands back output; agents work only against FakeProvider and
    recorded HTTP.
- **[Mistral Q2] How does the user learn a job finished while the app was closed?**
  - **Harbinger answer (2026-10-19; recorded by Mistral):** (c). Desktop
    notifications from the daemon **plus** a configurable webhook/email
    sink, for when the desktop is off entirely. Both configurable in
    Settings.**
  - **(a) Recommended:** desktop notifications from the daemon (Linux
    session bus, best-effort equivalents elsewhere) for completion,
    failure and cap hits, configurable in Settings.
  - **(b):** badge only; no notifications; the header badge and Cloud
    Jobs window show the outcome on next open.
  - **(c):** a configurable webhook/email sink in addition to (a), for
    when the desktop is off entirely.
- **[Mistral Q3] What is the default region policy for placement?**
  - **Harbinger answer (2026-10-19; recorded by Mistral):** (a). A
    default region per provider in Settings; suggestions rank
    same-region candidates first and warn when a cheaper cross-region
    placement would move the job's data.**
  - **(a) Recommended:** a default region per provider in Settings;
    suggestions rank same-region candidates first and warn when a
    cheaper cross-region placement would move the job's data.
  - **(b):** cheapest region always, regardless of data movement;
    egress cost is shown but doesn't gate.
  - **(c):** a per-data-class region allowlist (extends OpenCode Q7):
    sensitive classes pin regions; everything else goes cheapest.
- **[Mistral Q4] Which platforms does the v1 daemon support?**
  - **Harbinger answer (2026-10-19; recorded by Mistral):** (a). Linux
    first; macOS/Windows later, meanwhile protected by watchdog +
    provider-native deadlines but no local collection.**
  - **(a) Recommended:** Linux first; macOS/Windows later, meanwhile
    protected by watchdog + provider-native deadlines but no local
    collection.
  - **(b):** all three platforms in v1, with the full cross-platform
    lock/IPC matrix.
  - **(c):** no separate daemon binary in v1; jobs live in the app
    process, relying purely on watchdog + deadlines when the app closes.
- **[Mistral Q5] May users edit the risk rules themselves?**
  - **Harbinger answer (2026-10-19; recorded by Mistral):** (c). Rules
    editable through a Settings UI, stored in PostgreSQL. (Differs from
    Mistral's read-only recommendation; shipped YAML remains the
    seed/default source.)**
  - **(a) Recommended:** shipped rules, read-only; users tune thresholds
    in Settings; rules change only via releases.
  - **(b):** a user overrides file layered over the shipped rules for
    power users, with a warning that custom rules can bypass
    safeguards.
  - **(c):** rules editable through a Settings UI, stored in
    PostgreSQL.
- **[Mistral Q6] How long does local job history persist?**
  Remote-data retention is settled (Codex Q4); the local rows are not.
  - **Harbinger answer (2026-10-19; recorded by Mistral):** (b). Rows
    prune after N days (default settable in Settings), with an
    export-before-delete option.
  - **(a) Recommended:** rows persist indefinitely; artifacts (logs,
    manifests) prune on a Settings TTL. Cheap rows, expensive blobs.
  - **(b):** rows prune after N days, with an export-before-delete
    option.
  - **(c):** archive to JSONL then delete from PostgreSQL on the same
    TTL as (b).
- **[Mistral Q7] What happens to the PoC UsageStore JSONL and the Dashboards charts?**
  - **Harbinger answer (2026-10-19; recorded by Mistral):** (a).
    Migrate into the PostgreSQL spend ledger as historical rows;
    Dashboards charts render from the new ledger with a source filter
    (PoC vs Cloud Jobs).**
  - **(a) Recommended:** migrate into the PostgreSQL spend ledger as
    historical rows; Dashboards charts render from the new ledger
    with a source filter (PoC vs Cloud Jobs).
  - **(b):** keep UsageStore JSONL for PoC-era rows and show only new
    cloud-jobs spend in Cloud Jobs; two sources forever.
  - **(c):** retire the Dashboards charts entirely; Cloud Jobs owns
    all spend visualization.

### Kimi — 2026-10-19 (all eight answered)

Recommendation first in each list. Harbinger's answers below; recorded by
Kimi, 2026-10-19. Scope still awaits the team final round.

- **[Kimi Q1] What is the unit of work for multi-item jobs?**
  - **Harbinger answer (2026-10-19; recorded by Kimi):** A. Shards. A job
    is a manifest of shards; retry, collection, progress, and cost
    attribution happen at shard granularity.
  - **A (recommended):** Shards. A job is a manifest of shards; retry,
    collection, progress, and cost attribution happen at shard
    granularity. LoRA is a one-shard job; a 10,000-file extraction
    retries only its failed slices.
  - **B:** One job per item (file/prompt/image), visually grouped by a
    batch id. Simplest ledger, but floods the jobs table.
  - **C:** Job-level only; partial failure means retry the whole job or
    collect it partial. Least bookkeeping, most re-spend.
- **[Kimi Q2] May multiple jobs share one provisioned instance?**
  - **Harbinger answer (2026-10-19; recorded by Kimi):** A, B, or C as a
    Settings choice. Instance packing is user-configurable: strict 1:1,
    sequential chaining, or parallel packing are all in scope; the
    lease/spend ledger and reconciler must be correct for whichever mode
    is selected. (No default recorded.)
  - **A (recommended):** Strict 1:1 job:instance in v1. Simplest
    accounting, teardown, and cap logic; refcounted cache volumes
    (Grok Q6) already amortize boot and weight downloads.
  - **B:** Sequential chaining — the daemon queues same-account jobs
    onto one warm instance. Saves idle boot minutes; complicates the
    lease/spend ledger.
  - **C:** Parallel packing with per-job quotas. Best utilization, worst
    blast radius.
- **[Kimi Q3] How are gated model repos (HuggingFace tokens) handled?**
  - **Harbinger answer (2026-10-19; recorded by Kimi):** A. No worker
    credentials, ever. The daemon resolves gated weights into the
    staging manifest from the local library under the weight
    cloud-classes (Grok Q3); custom gated pulls exist only inside
    user-supplied images.
  - **A (recommended):** No worker credentials, ever. The daemon
    resolves gated weights into the staging manifest from the local
    library under the weight cloud-classes (Grok Q3); custom gated pulls
    exist only inside user-supplied images.
  - **B:** A short-lived HF token is injected per job via the provider's
    secret mechanism. Convenient; punches the no-credential boundary.
  - **C:** v1 supports only publicly downloadable models; even
    first-party workers require user-baked images for gated weights.
- **[Kimi Q4] Is there a global emergency stop?**
  - **Harbinger answer (2026-10-19; recorded by Kimi):** A. Yes — one
    "Stop all cloud activity" action in the Cloud Jobs header:
    checkpoint-cancel everything (Cursor Q7 semantics), revoke leases,
    trigger watchdog teardown, block new submits until re-enabled;
    usable with the GUI closed via daemon IPC.
  - **A (recommended):** Yes — one "Stop all cloud activity" action in
    the Cloud Jobs header: checkpoint-cancel everything (Cursor Q7
    semantics), revoke leases, trigger watchdog teardown, block new
    submits until re-enabled; usable with the GUI closed via daemon IPC.
  - **B:** Per-provider stop toggles in Settings only.
  - **C:** No global control; per-job Cancel/Force stop is enough.
- **[Kimi Q5] Any remote or mobile monitoring in v1?**
  - **Harbinger answer (2026-10-19; recorded by Kimi):** C. Full remote
    manage in v1 — cancel/retry from a phone. The `api/` Django layer
    grows authenticated cloud-jobs endpoints; the credential-lease
    (Cursor Q3) and leader/observer (Cursor Q6) designs extend to remote
    clients, and the API must be designed for public-internet exposure
    (scoped tokens, TLS, audit log).
  - **A (recommended):** Desktop-only in v1. Daemon IPC stays local; the
    `api/` Django project is not extended for cloud jobs yet.
  - **B:** Read-only remote monitor — extend `api/` with token-auth'd
    cloud-jobs read endpoints for mobile/web.
  - **C:** Full remote manage (cancel/retry from a phone). Stretches the
    credential-lease design onto the public internet.
- **[Kimi Q6] Scheduled or delayed submission?**
  - **Harbinger answer (2026-10-19; recorded by Kimi):** B. Run-at-
    wall-clock-time scheduling in the daemon, in v1. The state machine
    gains clock-triggered transitions out of `queued`; at fire time the
    normal preflight runs (including the Q7 quota probe) and an out-of-
    stock choice still fails fast per Grok Q2.
  - **A (recommended):** Submit-now only in v1. No clock transitions in
    the state machine; scheduled starts become a later feature on the
    same JobSpec.
  - **B:** Run-at-wall-clock-time scheduling in the daemon.
  - **C:** Spot-window scheduling (start when price/capacity conditions
    are met). Needs the `waiting_for_capacity` machinery declined in
    Grok Q2.
- **[Kimi Q7] Should quota/capacity be a preflight probe?**
  - **Harbinger answer (2026-10-19; recorded by Kimi):** A. Yes — a
    quota/capacity probe runs in preflight right before costing;
    failure hard-blocks with the provider's quota-request link (Azure
    ACI GPU quotas default to 0, per Mistral §5). Consistent with
    fail-fast on out-of-stock (Grok Q2) and costs nothing.
  - **A (recommended):** Yes — a quota probe runs right before costing;
    failure hard-blocks with the provider's quota-request link (Azure
    ACI GPU quotas default to 0, per Mistral §5). Consistent with
    fail-fast on out-of-stock (Grok Q2) and costs nothing.
  - **B:** Skip the probe; surface provider quota errors at submit time.
  - **C:** Hold the job in `queued` until quota appears — waits forever
    if the user never files the request.
- **[Kimi Q8] Should submit end in a confirmation sheet?**
  - **Harbinger answer (2026-10-19; recorded by Kimi):** A. Yes — a Plan
    & cost sheet: providers, execution mode, storage method,
    staging-manifest size, estimated total with the breakdown, risk
    findings with ⚠; "Submit" is an explicit final click.
  - **A (recommended):** Yes — a Plan & cost sheet: providers, execution
    mode, storage method, staging-manifest size, estimated total with
    the breakdown, risk findings with ⚠; "Submit" is an explicit final
    click.
  - **B:** Inline estimates only, one-click submit. A misclick is a real
    invoice.
  - **C:** No confirmation; submit fires immediately with a toast. Only
    sane for free tiers this service does not have.

## 6. Design axes to cover (suggestions, not a checklist)

1. **Job catalogue.** Which workloads go first? Options include:
   - extraction;
   - ComfyUI batch generation;
   - LoRA training;
   - CLIP and embedding backfill;
   - upscaling;
   - phash/dedup indexing;
   - Siamese/ASP training.
2. **Execution model per provider.** Managed batch/serverless, or
   provisioning raw VMs/pods?
3. **Orchestration and lifetime.**
   - Does a job keep running after the app closes? Options: run in the
     app, run under a local daemon, or use a remote control plane.
   - How do jobs resume after a crash?
4. **Data plane.**
   - Use each provider's native object store, one canonical bucket, or
     existing rclone/sync remotes?
   - Egress cost, and privacy warnings (the §4.20/§4.21 rule).
5. **Worker runtime.**
   - Container images: build, registry, and versioning against the app
     version.
   - Model and weight caching on GPU hosts, using network volumes.
6. **Cost and safety.**
   - A price catalogue and pre-flight estimates.
   - Budget caps.
   - Spot/preemptible instances, with checkpoints so a job can resume.
   - Idle and max-runtime teardown.
   - Detecting orphaned resources.
7. **Credentials and accounts.**
   - Bring-your-own keys through VaultManager.
   - Least-privilege IAM templates for each provider.
8. **Scheduling.** Does the user pick the provider, or does the service
   choose automatically by price, availability or region?
9. **Manager UI.**
   - Where it lives, the views it has, live updates, and notifications.
   - How it relates to the existing Cloud Compute window and to the Deep
     Learning Runs view.
10. **Existing code.** Migrate `backend/src/web/cloud/compute/` into
    `backend/src/cloud/` behind shims, or start fresh?
11. **Testing.**
    - Fake providers and recorded HTTP.
    - Opt-in live smoke tests with real spend, gated by Harbinger the same
      way benchmarks are.

## 7. Final round and decision

### Final round (Harbinger + Claude, 2026-10-19)

Claude read all seven agent proposals and the 46 recorded answers to the
agents' questions, and found eight conflicts or gaps. Harbinger answered:

1. **How remote management reaches the jobs (Kimi Q5 C vs. no inbound
   ports): through a relay in the watchdog's account.**
   - The watchdog and the relay are **one deployable with two
     endpoints**: teardown, and command pull.
   - The daemon pulls commands, so no inbound ports are opened.
   - A remote retry stays inside the job's existing credential lease and
     retry budget. Anything new needs the vault on the desktop.
   - Codex Q1 C's full always-on remote controller stays deferred, because
     orchestration stays in the daemon.
2. **Pruning (Mistral Q6 b): the spend ledger is never pruned.** Job
   rows, events and logs prune after N days.
3. **Editing risk rules (Mistral Q5 c): everything is editable, with a
   warning.** This went against Claude's recommendation to lock the
   capability rules.
   - Overriding a capability rule puts a permanent ⚠ on every job it
     affects. One example is Cursor Q8's Cloud Run GPU timeout, whose
     grey-out is now a default the user can override.
   - If such a job fails at the provider, the failure is structural. It
     does not use up the retry budget or trigger fallback (Codex Q3).
4. **Instance packing default: one job per instance (1:1).** On a shared
   instance, a cap hit stops only that job, and the instance is torn down
   after its last job.
5. **Storage for Cloud Sync: the remote's own short-lived links where it
   has them, otherwise a transit bucket.** Dropbox temporary links and
   OneDrive upload sessions are examples. Google Drive uses the transit
   bucket, which is emptied after collection.
6. **Cloudflare Workers AI: auto-translate simple workflows.** This went
   against Claude's recommendation of a separate job kind.
   - Workflows that use only a base model and standard sampler nodes are
     offered Workers AI, with a ⚠ that results will differ.
   - Every other ComfyUI workflow shows Cloudflare greyed out, with the
     reason.
7. **Automatic fallback also covers out-of-stock,** when fallback is
   enabled. This applies at submit and when a scheduled job starts.
   Without fallback, an out-of-stock job fails immediately (Grok Q2 B).
8. **Release cut: one milestone, with ordered Gates A–G.**

Other points reconciled in the write-up:

- **PostgreSQL replaces SQLite.** Claude's §2 recommendation of SQLite is
  superseded, because `AGENTS.md` rules out SQLite.
- **If PostgreSQL is configured but unreachable,** new submits are
  blocked, and the daemon's write-ahead log keeps teardown and
  reconciliation running.
- **If PostgreSQL is not configured,** the Cloud Jobs window shows a setup
  prompt.
- **The emergency stop on macOS and Windows** goes through the
  watchdog/relay, because those platforms have no local daemon in v1
  (Mistral Q4).

### Decision: LOCKED

The scope, design rationale, gates, issues, backlog and rejected items
are in **`docs/moon/roadmaps/cloud_jobs.md`**, which the GitHub milestone
**Cloud Jobs Service** tracks. This section is only a pointer; don't copy
the roadmap here.

**The implementation gate is open, starting at Gate A.** Claim an issue on
the bus before starting, as usual.

— Claude, 2026-10-19

### Correction after the lock (Harbinger + Claude, 2026-10-19): the job store

The app has used the encrypted unified store (`library.db`, SQLCipher via
`base.database`) since 2026-07-27, and PostgreSQL is archived. The
PostgreSQL answers in this round came from a stale `AGENTS.md` line, which
is now fixed.

Harbinger's decision:

- Cloud Jobs uses its **own encrypted `cloud_jobs.db`** on the same
  engine. Its key reaches the daemon through the job-scoped credential
  lease.
- Leader/observer across machines (Cursor Q6) is **dropped**.
- E1 imports into `library.db`'s `embeddings` table.

Details: `docs/moon/roadmaps/cloud_jobs.md`.

### Coordination update — Codex, 2026-10-19

Harbinger appointed Codex coordinator and Grok reviewer/final editor. The [coordination handover](coordination_handover_2026-10-19.md) and current GitHub agent labels supersede earlier owner proposals. Historical decisions and attribution above remain unchanged.
