# Cloud Jobs Service

**Status:** LOCKED 2026-10-19. Harbinger and Claude locked this scope
after an eight-agent proposal round (Claude, Codex, Gemini, Grok, Cursor,
Mistral, Kimi, OpenCode) and a final brainstorming round. GitHub milestone
**Cloud Jobs Service** (tracking issue [#824](https://github.com/ACFHarbinger/Image-Toolkit/issues/824)) tracks the work, using the `cloud-jobs-*` issues
listed per gate below. This document holds the design rationale and the
ordered plan; check the issues for status.

**Origin:**

- A new service in `backend/src/cloud/` that runs CPU-heavy and GPU-heavy
  jobs in the cloud, on eight providers:
  - **CPU:** AWS, GCP, Azure, Cloudflare, Oracle.
  - **GPU:** RunPod, Hyperstack, Thunder Compute, plus the GPU offerings
    of AWS, GCP, Azure and Oracle.
- A standalone **Cloud Jobs** window to monitor and manage those jobs.

This work absorbs and supersedes `new_features.md` §4.21 (the Cloud
Compute Offload proof of concept).

**Sources:**

- The brief and every recorded answer:
  `.agent/reports/team/cloud_jobs_service_2026-10-19.md`.
  - §5 holds 56 recorded answers from Harbinger, all made on 2026-10-19:
    10 questions from Claude and 46 from the other agents.
  - §7 holds the final-round reconciliations.
- Each agent's proposal:
  `.agent/reports/<agent>/cloud_jobs_service_proposal_2026-10-19.md`.

**Supersession:** Claude's proposal (§2) recommended SQLite. That is
superseded: `AGENTS.md` rules out SQLite, so PostgreSQL is the system of
record.

---

## 1. Architecture

### Core model (Qt-free, under `backend/src/cloud/`)

- **`JobSpec`** is the provider-neutral description of a job.
  - A job is a **manifest of shards**, and retry, collection, progress,
    cost attribution and cap checkpoints all work per shard. How each
    workload splits:
    - **extraction:** by file slice;
    - **ComfyUI:** by prompt slice, with fixed seeds;
    - **indexing:** by image-ID range;
    - **LoRA:** a single shard.
  - Origin-tab submit and Cloud Compute's Request Builder both build the
    same `JobSpec`, so the two can't drift apart.
- **Adapter contract.** Every provider adapter implements five methods:
  - `plan` (pure);
  - `submit`, `observe` and `teardown`;
  - `collect(attempt, shard)`.

  Each adapter also ships an SDK-free **capability manifest**: the
  execution modes, GPU classes and storage methods it supports, plus its
  limits. Provider SDKs are pinned and only used inside their adapter.
  An **adapter certification kit** grades each adapter at one of three
  levels: declared, recorded (passes recorded-HTTP fixtures), or
  live-smoke.
- **Two execution families, chosen by the user per job:**
  - **Instance:** provision a VM or pod, boot it with cloud-init that
    pulls our digest-pinned worker, run, collect, tear down.
  - **Managed batch/serverless.**

  Each workload has a default (managed batch for extraction, embedding
  and phash; instance for ComfyUI and LoRA), and the user can always
  override it.
- **State machine:** `queued → submitting → provisioning → running →
  collecting → settling → terminal`. `queued` has clock-triggered
  transitions so a job can be scheduled to start at a set time.
  - Before the first provider call, the service stores the job's intent
    and an idempotency key.
  - If a submit's outcome is unknown, the service resolves it by listing
    the provider resources tagged for that job, before any retry.
  - The **reconciler** is a pure function,
    `(state, observation, settings) → actions`, so it can be replayed
    after a crash. The UI only reads events.
- **Store:** PostgreSQL holds jobs, attempts, shards, an append-only
  `job_events` table, and the **spend ledger**.
  - Job rows, events and logs are pruned after N days, which is set in
    Settings, with an option to export before deleting.
  - **The spend ledger is never pruned.** Monthly caps, estimate
    calibration and the Dashboards charts depend on it.
  - The PoC's `UsageStore` JSONL moves into the ledger as historical
    rows, with a PoC-or-Cloud-Jobs source filter.
- **If PostgreSQL is unreachable or not configured:**
  - **Configured, temporarily unreachable:** new submits are blocked. The
    daemon's JSONL write-ahead log (WAL) keeps the teardown obligations
    and reconciliation running, and syncs back to the database when it
    recovers.
  - **Not configured:** the Cloud Jobs window shows a setup prompt
    instead of jobs.

### Safety

- **Preflight runs in a fixed order**, as pure code, and the UI and the
  backend submit path use the same pipeline:
  1. validate;
  2. data class, checked against the provider allowlist;
  3. ComfyUI widget secret scan;
  4. weight cloud-classes (`allow` / `warn` / `block`);
  5. quota/capacity probe;
  6. cost;
  7. risk rules;
  8. a **Plan & cost confirmation sheet**, where Submit is an explicit
     final click.

  What the individual checks do:
  - **Data classes:** private data gets a warning. Sensitive data is
    blocked from Cloud Sync remotes and third-party GPU hosts unless the
    user allows it.
  - **Secret scan:** it blocks submit until the user strips the flagged
    fields or explicitly keeps them. The finding names the node id, and
    the logs keep the redacted graph.
  - **Weight classes:** weights with unknown hashes produce a warning and
    need acknowledgement. Weights classed `block` never enter the
    staging manifest.
  - **Quota probe:** a failure hard-blocks the job and shows the
    provider's quota-request link.
- **Risk rules:**
  - Stored as YAML seed rules, written to PostgreSQL, and **editable in
    Settings**. Thresholds are shared with the cost caps.
  - Three severities: `block`, `warn` and `info`. Each rule targets a
    field path that the form binds to.
  - How the UI shows them:
    - it recolours the background and text of the affected controls;
    - it shows bright warning text with a ⚠ sign;
    - it greys out options that can't work with the configuration.
  - **Capability rules are editable too** (Harbinger, final round). One
    example is greying out Cloud Run GPU when the estimate is longer than
    its verified timeout.
    - Overriding a capability rule puts a **permanent ⚠** on every job it
      affects.
    - If such a job then fails at the provider, the failure is
      *structural*: it does **not** use up the retry budget and does
      **not** trigger automatic fallback.
  - The backend re-checks the rules at submit.
  - *Claude's note:* Claude recommended locking capability rules. They
    were kept editable at Harbinger's choice.
- **Cost:**
  - **Price catalogue:** curated and versioned, with `last_verified`
    dates and user overrides. It uses live price APIs where a provider has
    them. The catalogue also records:
    - billing granularity: rounding, minimums and public-IPv4 surcharges;
    - per-pair egress prices.
  - **Estimates** are deterministic, and the catalogue rows used are
    snapshotted on each job. "Cheapest" means the **estimated total job
    cost**, including startup, transfers, storage and expected retries.
    If the user sets a completion deadline, only candidates that meet it
    are ranked.
  - **Actual spend** comes from the providers' billing APIs where they
    have them. A calibration loop flags catalogue rows whose estimates
    keep drifting from actual spend.
  - **Settings:** estimates, warnings and hard caps can each be turned on
    or off and given values: per-job max runtime, per-job max spend, and
    a monthly cap. Admission caps limit concurrent jobs, concurrent GPU
    instances and reserved spend; extra jobs wait in `queued` and don't
    provision.
  - **When a hard cap is reached:** the service predicts forward, then
    checkpoints if the job supports it, cancels, and tears down. Partial
    outputs are kept.
- **Leak protection:**
  - every resource carries the tags `it-job-id`, `it-owner` and
    `it-expires-at`;
  - an orphan sweep runs at startup and on demand, and surfaces anything
    it finds in the Resources view; it never kills silently;
  - an in-instance dead-man's switch;
  - verified provider-native deadlines;
  - a cloud-side **watchdog**.

  Where protection is reduced, the job discloses it and the user must
  acknowledge it.
- **Stopping jobs:**
  - **Cancel:** checkpoint, collect verified shards, tear down.
  - **Force stop:** a separate, recoloured action that skips the
    checkpoint.
  - **"Stop all cloud activity":** a global emergency stop. It
    checkpoint-cancels everything, revokes leases, triggers watchdog
    teardown, and blocks new submits until re-enabled. It works with the
    GUI closed, through the daemon IPC. On macOS and Windows in v1, which
    have no local daemon, it goes through the watchdog/relay instead.
- **Credentials:**
  - Users bring their own accounts. Keys live in VaultManager, and the
    repo ships least-privilege IAM templates per provider.
  - At submit, while the vault is unlocked, the job gets a **job-scoped
    credential lease**. The daemon never holds the vault passphrase. A
    new submit always needs the vault.
  - **Workers never hold credentials:**
    - no VaultManager or database credentials;
    - no Cloud Sync OAuth tokens;
    - no Hugging Face tokens. Instead, the daemon resolves gated weights
      from the local library into the staging manifest.

    The exception is a user-supplied image that does its own gated pulls.
- **Untrusted output:** outputs are quarantined until collection is
  verified, and logs redact prompts and filenames by default.

### Orchestration

- **Local daemon**, Linux first in v1. macOS and Windows get watchdog and
  provider-deadline protection but no local collection, until their
  daemon ships.
  - One daemon per OS user, single-instance.
  - Local authenticated IPC with a protocol version handshake.
  - Crash-only recovery, and the WAL described above.
  - **Leader/observer across machines:** if two machines share PostgreSQL,
    one daemon leads and the other GUIs are read-only until they win the
    lease. If they don't share PostgreSQL, jobs stay on the machine that
    submitted them.
- **Watchdog and remote relay: one deployable with two endpoints.**
  - It lives in the user's GCP account (Cloud Function or Cloud Run) by
    default. A Cloudflare Worker is the alternative.
  - **Teardown endpoint:** heartbeat and deadline. When a job misses its
    heartbeat past the deadline, the watchdog tears it down.
  - **Command endpoint:** it carries remote-management commands from a
    phone or web client. The daemon pulls them over an outbound
    connection, so no inbound ports are needed.
    - A remote retry stays inside the job's existing credential lease and
      retry budget.
    - Anything new still needs the vault on the desktop.
    - Requirements: scoped tokens, TLS, and an audit log.
  - Orchestration stays in the daemon. A full always-on remote controller
    (Codex Q1 C) is still deferred; the relay only carries commands.
- **Recovery:**
  - By default, failed attempts retry a bounded number of times on the
    selected provider.
  - The user can opt in to **automatic fallback**, which moves the job
    within an approved provider/region/GPU list and retry budget.
  - **Out of stock** fails immediately. If fallback is enabled, it moves
    the job to the next approved option that passes the caps and the
    data-class rules, both at submit and when a scheduled job starts. The
    job records why it moved.
- **Instance packing** is chosen in Settings:
  - **1:1** (the default): one job per instance.
  - **Sequential chaining:** jobs run one after another on a warm
    instance.
  - **Parallel packing:** several jobs share an instance at once.

  On a shared instance, a job that hits its cap is stopped and
  checkpointed on its own. The instance is torn down when its last job
  ends.
- **Placement:** the user picks, and the service suggests.
  - The suggestion is a ranked card with a cost breakdown (egress,
    retained storage, expected retries) and a price-age confidence band.
    Applying a suggestion takes one click, and capacity is re-checked at
    submit.
  - Settings has a default region per provider. Same-region candidates
    rank first, and the card warns when a cheaper candidate in another
    region would move the job's data.

### Data plane

- **The user picks the storage method.** All of these plug into one
  storage interface:
  - **A bucket** (S3, GCS, Azure Blob or R2) with presigned URLs.
  - **Provider-native storage or volumes.**
  - **Cloud Sync remotes** (Google Drive, OneDrive, Dropbox). The daemon
    stages the data.
    - Where the remote has its own short-lived links (Dropbox temporary
      links, OneDrive upload sessions), the worker uses those.
    - Otherwise, for example on Google Drive, data goes through a
      transit bucket that is emptied after collection.
    - The UI shows which path a job will take.
- **Staging is content-addressed** by sha256, so a file is uploaded once
  and reused.
- **Model caches:** one content-addressed, reference-counted cache volume
  per provider account and region, plus a scratch disk per attempt that is
  deleted with the attempt. Sharing the cache can be turned off.
- **Retention** of staged inputs, model caches and outputs is set in
  Settings, with expiry and a storage budget.
- **Telemetry:** the worker appends to an `events.jsonl` through a
  presigned URL, in the `training_runs.py` format. The daemon polls it by
  byte range every 2–5 seconds and relays it to the GUI over IPC. No
  inbound ports are opened.
- **Outputs land in a per-job collection,** `Cloud Jobs/<job-id>`, along
  with its manifest. The user promotes results when satisfied.
  - **Library updates** (embedding vectors, phash index entries) are
    auto-imported only when the source hashes and model/schema versions
    still match. Anything that doesn't match goes to Review.
  - Index results are imported through a staging table, then a hash check,
    then an atomic upsert. Settings has a toggle to require manual review
    before importing.

### Workers

- **Images:** first-party CPU and CUDA worker images built from the real
  backend code.
  - The repo ships the Dockerfiles and a publish action that pushes to a
    registry **the user owns** (GCP Artifact Registry first).
  - Images are digest-pinned. For Cloudflare jobs, the image is copied
    into `registry.cloudflare.com`.
- **User-supplied, digest-pinned images** run under the provider's normal
  isolation and carry a prominent warning. The no-credential and
  untrusted-output rules still apply.
- **ComfyUI v1** accepts workflows that use version-pinned node packs, or a
  user-supplied image.
- **Provider templates** (for example Thunder's `comfy-ui`) are an explicit
  override, marked unverified.
- **v1 is headless:** no web UI, no floating IP, and no forwarded port.
- **Flight recorder:** each job can produce a redacted support bundle.

### UI

- **Cloud Jobs window** (`cloud.jobs`). The header has one ☁️ control:
  - **click** opens Cloud Jobs;
  - the **badge** shows how many jobs are running and the reserved spend;
  - **the gear, or shift-click,** opens the Cloud Compute window, which
    stays the setup surface.
- **Views:**
  - **Jobs:** a virtualised table with filters.
  - **Detail:**
    - a timeline built from `job_events`, and a live log;
    - GPU utilisation and VRAM metrics;
    - a spend-so-far counter against the reserved amount, and outputs;
    - a daemon status row: lease owner, WAL depth, last poll.
  - **Resources:** live tagged resources and orphans, with Terminate.
  - **Spend:** the Dashboards charts, now drawn from the ledger.
- **Notifications:** desktop notifications from the daemon, and a webhook
  or email sink for when the desktop is off. Both are set in Settings.
- **Cloud training runs** write the local `record.json` / `events.jsonl`
  layout. Deep Learning Runs, the report card and the checkpoint
  tournament read them, and Cloud Jobs links to the run.
- **"Run in cloud instead":** when `gpu_lease_arbiter` refuses a job
  locally, the app offers to run it in the cloud, with the spec and an
  estimate prefilled.

### Provider classification (re-verify at implementation time)

These facts come from what the agents read in providers' docs on
2026-10-19. Each adapter issue carries a **"re-verify against current
docs"** task.

| Provider | Managed batch / serverless | Instance | Notes to re-verify |
|---|---|---|---|
| GCP | Cloud Run (CPU, and GPU for short jobs only), Cloud Run Jobs / Batch | GCE (long GPU jobs) | Cloud Run GPU task timeout ≤ 1 h |
| RunPod | Serverless | Pods | API **v2 only**: v1 is said to retire 2026-11-15. Network volumes for caching |
| AWS | Batch (CPU **and** GPU) | EC2 | — |
| Azure | Container Apps Jobs (CPU) | VMs (GPU) | ACI GPU quota defaults to 0; serverless GPU is documented for apps, not Jobs |
| Oracle | Container Instances (CPU only; the existing Terraform comment is wrong) | Compute GPU shapes | — |
| Cloudflare | Containers (CPU only, no CUDA), Workers AI | — | R2 for staging. Workers AI only runs its own catalogue of models |
| Hyperstack | — | VMs | A stock endpoint; spot is a separate flavour name; labels need a follow-up PUT; keep `assign_floating_ip` false |
| Thunder Compute | — | Instances | Always pass `public_key` (otherwise the API may return a generated private key); `mode` is deprecated |

**Cloudflare Workers AI** (Harbinger, final round): when a ComfyUI
workflow uses only a base model and standard sampler nodes, offer Workers
AI with a ⚠ saying the results will differ (a different model build, and
no custom nodes). Any other ComfyUI job shows Cloudflare greyed out, with
the reason. *Claude's note:* Claude recommended a separate job kind
instead; auto-translation was Harbinger's choice.

---

## 2. Gates and issues

One milestone. Build gates in order: each gate assumes the one before it.

- **Gates A and B spend no money.** They run on fakes and recorded HTTP.
- **Live smoke tests** start at Gate C. They use the `live_cloud` pytest
  marker and go through the same chain as benchmarks: request on the bus
  to Codex, who gets Harbinger's go-ahead. One live run at a time.
- **Workload order:** extraction → ComfyUI → embedding/indexing →
  LoRA/LyCORIS. Each step gets restart and cleanup checks.
- **Provider order:** GCP and RunPod first, then the remaining six.

Tracking issue: [#824](https://github.com/ACFHarbinger/Image-Toolkit/issues/824).

### Gate A — Core contracts (no spend)

| Issue | Deliverable |
|---|---|
| [#825](https://github.com/ACFHarbinger/Image-Toolkit/issues/825) | A1: Move `backend/src/web/cloud/compute/` into `backend/src/cloud/`, with re-export shims for one release |
| [#826](https://github.com/ACFHarbinger/Image-Toolkit/issues/826) | A2: `JobSpec`, shard manifest, adapter contract and capability-manifest schema |
| [#827](https://github.com/ACFHarbinger/Image-Toolkit/issues/827) | A3: PostgreSQL store (jobs, attempts, shards, `job_events`, spend ledger), retention pruning with export, and the `UsageStore` migration |
| [#828](https://github.com/ACFHarbinger/Image-Toolkit/issues/828) | A4: State machine and pure reconciler, with idempotency keys, submit reconciliation and clock-triggered `queued` |
| [#829](https://github.com/ACFHarbinger/Image-Toolkit/issues/829) | A5: FakeProvider fault timelines, recorded-HTTP harness, crash-point matrix, adapter certification kit |
| [#830](https://github.com/ACFHarbinger/Image-Toolkit/issues/830) | A6: Risk rule engine (YAML seed, PostgreSQL storage, editable, permanent ⚠ on capability overrides, structural-failure semantics) |
| [#831](https://github.com/ACFHarbinger/Image-Toolkit/issues/831) | A7: Preflight pipeline (data classes and allowlist, secret scan, weight classes, quota probe) |
| [#832](https://github.com/ACFHarbinger/Image-Toolkit/issues/832) | A8: Cost model (catalogue, live prices, snapshots, total-job ranking, deadline, caps, admission, reservations, billing reconciliation, calibration) |
| [#833](https://github.com/ACFHarbinger/Image-Toolkit/issues/833) | A9: Storage interface (bucket with presigned URLs, provider volumes, Cloud Sync via temp links or transit bucket), content-addressed staging, retention |

### Gate B — Daemon and safety

| Issue | Deliverable |
|---|---|
| [#834](https://github.com/ACFHarbinger/Image-Toolkit/issues/834) | B1: Cloud jobs daemon (Linux): single instance, authenticated IPC, WAL, leader/observer lease |
| [#835](https://github.com/ACFHarbinger/Image-Toolkit/issues/835) | B2: Job-scoped credential lease |
| [#836](https://github.com/ACFHarbinger/Image-Toolkit/issues/836) | B3: Watchdog and relay deployable (GCP first, Cloudflare Worker alternative): teardown endpoint, plus disclosure when protection is reduced |
| [#837](https://github.com/ACFHarbinger/Image-Toolkit/issues/837) | B4: Leak protection (tags, orphan sweep, in-instance dead-man's switch, provider-native deadlines) |
| [#838](https://github.com/ACFHarbinger/Image-Toolkit/issues/838) | B5: Cancel, Force stop, and "Stop all cloud activity" (relay fallback on platforms without a daemon) |
| [#839](https://github.com/ACFHarbinger/Image-Toolkit/issues/839) | B6: Notifications (desktop, plus webhook/email sink) |
| [#840](https://github.com/ACFHarbinger/Image-Toolkit/issues/840) | B7: Worker images (CPU/CUDA Dockerfiles, publish to a user-owned registry, digest pinning, cloud-init boot, user images, `events.jsonl` telemetry, flight recorder) |

### Gate C — First providers end to end (GCP + RunPod; extraction, then ComfyUI)

| Issue | Deliverable |
|---|---|
| [#841](https://github.com/ACFHarbinger/Image-Toolkit/issues/841) | C1: GCP adapter (Cloud Run, Cloud Run Jobs / Batch, GCE for long GPU jobs) |
| [#842](https://github.com/ACFHarbinger/Image-Toolkit/issues/842) | C2: RunPod adapter (API v2; Pods and Serverless; network-volume cache) |
| [#843](https://github.com/ACFHarbinger/Image-Toolkit/issues/843) | C3: Workload 1, extraction, ported onto the new lifecycle |
| [#844](https://github.com/ACFHarbinger/Image-Toolkit/issues/844) | C4: Workload 2, ComfyUI batch generation (pinned node packs, prompt-slice shards, `Cloud Jobs/<job-id>` outputs) |
| [#845](https://github.com/ACFHarbinger/Image-Toolkit/issues/845) | C5: Placement card, default mode per workload, region defaults, automatic fallback including out-of-stock |
| [#846](https://github.com/ACFHarbinger/Image-Toolkit/issues/846) | C6: `live_cloud` smoke-test marker and runbook (through the benchmark chain) |

### Gate D — Cloud Jobs window

| Issue | Deliverable |
|---|---|
| [#847](https://github.com/ACFHarbinger/Image-Toolkit/issues/847) | D1: `cloud.jobs` window shell, with the header ☁️ control and badge |
| [#848](https://github.com/ACFHarbinger/Image-Toolkit/issues/848) | D2: Jobs table and Detail view (timeline, live log, metrics, spend, outputs, daemon status) |
| [#849](https://github.com/ACFHarbinger/Image-Toolkit/issues/849) | D3: Resources view (orphans, Terminate) and Spend view (Dashboards drawn from the ledger) |
| [#850](https://github.com/ACFHarbinger/Image-Toolkit/issues/850) | D4: Submit surfaces (origin tabs and Request Builder sharing one `JobSpec`), risk-feedback UI, Plan & cost confirmation sheet |
| [#851](https://github.com/ACFHarbinger/Image-Toolkit/issues/851) | D5: Cloud Jobs settings (caps, thresholds, rule editor, retention, packing, fallback, notifications, regions) |
| [#852](https://github.com/ACFHarbinger/Image-Toolkit/issues/852) | D6: "Run in cloud instead" from `gpu_lease_arbiter` |

### Gate E — Remaining workloads

| Issue | Deliverable |
|---|---|
| [#853](https://github.com/ACFHarbinger/Image-Toolkit/issues/853) | E1: Workload 3, CLIP/phash indexing (image-ID shards, staging table, hash check, atomic upsert, review toggle) |
| [#854](https://github.com/ACFHarbinger/Image-Toolkit/issues/854) | E2: Workload 4, LoRA/LyCORIS training (checkpoints, spot with resume, Deep Learning Runs records, no worker Hugging Face credentials) |

### Gate F — Remaining providers

Each adapter issue includes:

- the adapter itself;
- an IAM template;
- a capability manifest;
- recorded fixtures;
- a live smoke test;
- a task to re-verify the provider's details against its current docs.

| Issue | Deliverable |
|---|---|
| [#855](https://github.com/ACFHarbinger/Image-Toolkit/issues/855) | F1: AWS adapter (Batch for CPU/GPU, EC2) |
| [#856](https://github.com/ACFHarbinger/Image-Toolkit/issues/856) | F2: Azure adapter (Container Apps Jobs for CPU, VMs for GPU, ACI quota check) |
| [#857](https://github.com/ACFHarbinger/Image-Toolkit/issues/857) | F3: Oracle adapter (Container Instances for CPU, Compute GPU shapes; fix the Terraform comment) |
| [#858](https://github.com/ACFHarbinger/Image-Toolkit/issues/858) | F4: Cloudflare adapter (Containers for CPU, R2, Workers AI auto-translation of simple workflows) |
| [#859](https://github.com/ACFHarbinger/Image-Toolkit/issues/859) | F5: Hyperstack adapter (instances, stock probe, spot flavours, follow-up label PUT) |
| [#860](https://github.com/ACFHarbinger/Image-Toolkit/issues/860) | F6: Thunder Compute adapter (instances, mandatory `public_key`, templates as unverified override) |

### Gate G — Extended orchestration

| Issue | Deliverable |
|---|---|
| [#861](https://github.com/ACFHarbinger/Image-Toolkit/issues/861) | G1: Remote management through the relay's command endpoint (phone/web client, scoped tokens, TLS, audit log) |
| [#862](https://github.com/ACFHarbinger/Image-Toolkit/issues/862) | G2: Scheduled (wall-clock) submission |
| [#863](https://github.com/ACFHarbinger/Image-Toolkit/issues/863) | G3: Instance packing (sequential chaining and parallel packing; per-job cap stops) |

### Backlog (deferred past v1)

| Item | Reason |
|---|---|
| Attended cloud ComfyUI desktop | Harbinger (Grok Q8 C): a separate product, not part of the jobs service |
| macOS/Windows daemon | Linux first (Mistral Q4); watchdog and deadlines protect those platforms meanwhile |
| Strict-isolation profile for user images | OpenCode Q3: deferred hardening; v1 uses normal provider isolation with a warning |
| Full always-on remote controller | Codex Q1 C: the relay carries commands only, and orchestration stays in the daemon |
| Upscaling and Siamese/ASP training workloads | Not among the four v1 workloads; they reuse the same `JobSpec` later |

## 3. Explicitly rejected

| Item | Reason |
|---|---|
| SQLite job store (Claude's §2) | `AGENTS.md`: "No SQLite". PostgreSQL is the system of record |
| `waiting_for_capacity` hold and spot-window scheduling | Grok Q2 B: out-of-stock fails immediately (or falls back, if enabled) |
| Origin-tab-only submit | Cursor Q1 C: Request Builder submit stays too, sharing the `JobSpec` |
| Project-managed provider accounts | OpenCode Q4: bring-your-own accounts only |
| Credentials inside workers (Hugging Face tokens, OAuth, vault keys) | Kimi Q3 A, Gemini Q1 A, OpenCode Q3 |
| Automatic custom-image builds per workflow | Codex Q5 C: the largest security and maintenance burden |

## 4. Attribution

- **Claude:** asynchronous lifecycle, leak protection, two backend
  families, the arbiter hook, the Cloud Jobs window, and the final-round
  reconciliations.
- **Codex:** PostgreSQL, durable attempts and submit reconciliation,
  remote cleanup, total-job cost, validated imports, workload order.
- **Gemini:** daemon WAL, Cloud Sync ephemeral staging, `events.jsonl`
  telemetry, Cloudflare scope, the `pgvector` import gate.
- **Grok:** admission caps, weight classes, secret scan, cloud-init boot,
  cache volumes, training records, Hyperstack and Thunder findings.
- **Cursor:** window map, credential lease, watchdog home, user registry,
  leader/observer, Cancel vs Force stop, the Cloud Run GPU timeout, RunPod
  v2.
- **Mistral:** state machine and reconciler, risk rule set, placement card,
  test harness, AWS and Azure findings, daemon UX.
- **Kimi:** shards, adapter contract, preflight pipeline, deterministic
  costs and calibration, emergency stop, gated-model handling.
- **OpenCode:** supervisor contract, adapter certification, user-image
  trust tiers, flight recorder, crash-point matrix, GCP + RunPod first.

*Last updated: 2026-10-19. Scope locked and issues created.*
