# Cloud Jobs Service — Codex proposal

— Codex, 2026-10-19. Proposal only; builds on Harbinger's ten recorded answers.

## 1. Durable orchestration and independent cleanup

Use PostgreSQL for jobs, attempts, events, resource ownership and budget reservations. This follows AGENTS.md's “No SQLite” rule; Claude's SQLite suggestion conflicts with it. Keep operational tables separate from image/pgvector tables. The local daemon owns provider calls; the Qt window observes events over authenticated local IPC. Provider calls and transfers stay off the UI thread.

Persist submission intent and an idempotency key before provisioning. Record each attempt independently. On a timeout, reconcile provider resources before resubmitting: a missing response does not mean the job failed to launch. Use a daemon lease and fencing token to prevent competing controllers. If PostgreSQL is unavailable, stop new submissions; remote deadlines must still protect existing resources. Tradeoff: PostgreSQL availability becomes necessary for scheduling.

Track execution, artifact collection and cleanup separately. “Computation succeeded; download pending; volume still billed” is a valid visible state. Do not label a job fully settled until owned resources are deleted or explicitly retained. Cancellation records intent, requests cancellation, verifies provider state, and keeps retrying cleanup.

A local daemon cannot guarantee teardown while its host is asleep, offline or broken. An OS shutdown inside a VM is not a universal billing stop. Recommend a remote cleanup watchdog or verified provider-native deadline, with job-scoped authority and an ownership ledger. Keep persistent volumes on an explicit retention list. Unknown resources are shown for review; resources positively owned by an expired attempt can be cleaned automatically under its agreed policy. Cloud API outages still prevent an absolute spend guarantee.

**Migration finding:** `gcd_adapter.py:run()` waits on HTTP POST `/jobs`; the worker executes the workload before replying. Wrapping that call in a thread does not create durable remote submit/status/cancel operations. Preserve shims, but add a durable execution identifier and remotely queryable state before advertising restart recovery. The current `usage.json` completion record is useful evidence, not a complete lifecycle API.

## 2. Compatibility and risk rules shared by UI and backend

Use a versioned capability catalogue keyed by provider, execution mode, region, storage method and workload runtime. Each entry records evidence URL/date, verified limits and account-specific availability. Distinguish unsupported, supported but unavailable, and unverified. Recheck immediately before submission; capacity observations are not reservations.

A Qt-free evaluator returns a stable rule ID, severity, affected fields, explanation and remedy. The backend enforces the same rules shown by the UI. Settings provide shared warning thresholds and enabled caps.

| Condition | Proposed response |
|---|---|
| Incompatible GPU/runtime, insufficient disk/VRAM, unsupported storage | Disable combination and explain remedy |
| Spot selected but actual workload/runtime lacks verified resume | Disable, following Harbinger's answer |
| Enabled budget cap cannot cover committed jobs plus this reservation | Block submission |
| Unknown price, stale quote, uncertain runtime, high transfer cost | Warning with missing evidence and estimate range |
| Failed preflight credentials or quota | Explain setup failure; prevent submission |
| Hard runtime limit threatens checkpoint/upload completion | Warn and reserve checkpoint/cleanup time |
| No verified remote deadline for unattended execution | Apply Q1 policy; never imply guaranteed cleanup |

Use the requested control/text recolouring plus warning icon and descriptive text. Preserve readable contrast; colour is not the sole signal. A risk preview should explain what changed when the user switches GPU, storage or mode. Tradeoff: capability maintenance is ongoing work, but prevents eight providers becoming eight inconsistent forms.

## 3. Honest estimates and bounded recovery

Suggest the cheapest compatible candidate with observed capacity, ranked by estimated *completed-job* cost. Include provisioning/image pull, compute, staging, egress, persistent storage and expected retries. Show an estimate range, timestamp and exclusions. Unknown pricing must not rank as zero; hourly price remains visible. Initially allow user runtime estimates, then learn from comparable completed runs without launching automatic paid benchmarks.

Reserve budget transactionally before submission so concurrent jobs cannot each consume the same remaining monthly allowance. Track estimated, reserved and provider-reported charges separately, including retained resources. A configured hard cap triggers admission control and termination early enough to allow shutdown latency; it is not a promise that delayed provider invoices cannot overshoot. A cap covers Toolkit-managed spending unless broader account billing is explicitly integrated.

Retries consume the same logical job budget. Preserve completed extraction/generation/indexing shards; resume training only from validated checkpoints including optimizer/scheduler state where required. Record seeds, runtime/image digest, model hashes and checkpoint lineage. Cross-GPU resumes can change numerical results. Automatic fallback must stay inside the user's approved placement and data-location boundaries. Tradeoff: explicit attempts and provenance add storage, but prevent silent duplicate spend and confusing results.

## 4. Storage and result integrity

Define a storage adapter with stage, issue_access, stat/checksum, collect and release operations; advertise resumable transfer, worker access, locality, expiry/renewal and retention capabilities. A selected Cloud Sync remote may need an explicit intermediate bucket when the worker cannot access it directly. Show that route and its costs before submission; never silently switch storage.

Workers receive narrowly scoped, short-lived access, not VaultManager master credentials. URL expiry and renewal must cover long jobs without relying on an awake desktop. If that is unavailable, reject incompatible durations or use a supported identity mechanism. Model caches use content hashes and runtime compatibility keys. Retention, deletion, TTL and storage-budget policies are user-configurable in Settings (Q4). Shared cache deletion respects active users.

Every output bundle includes source hashes, task/model versions, attempt identity, checksums and a completion manifest. The local importer validates paths and content, then applies idempotent PostgreSQL transactions. Embeddings must match the intended model, dimension and source revision; stale output goes to review. Never give a remote worker direct image-database credentials. Tradeoff: collection can finish after computation and needs its own retry state.

## 5. Runtime packaging and provider evidence

Use a shared worker protocol with separate pinned extraction, inference/ComfyUI and training images. This avoids coupling FFmpeg-only jobs to a large training dependency stack. Support pinned node packs and user-supplied container images in v1 (Q5). Pin custom nodes, models and image digests; detect missing dependencies and incompatible worker protocols before paid provisioning. Share event semantics with training runs after checking its exact contract.

Provider documentation checked 2026-10-19:

- **Cloudflare:** documented Containers types expose CPU, memory and disk; current default custom limits are 4 vCPU, 12 GiB RAM and 20 GB disk, with increases by request. Propose eligible CPU tasks only after runtime/lifecycle validation. The reviewed table does not establish arbitrary CUDA container support. [Containers limits](https://developers.cloudflare.com/containers/platform/limits/).
- **Cloudflare Workers AI:** offers model inference on serverless GPUs through APIs. Treat this as a separate inference capability, not proof that arbitrary ComfyUI graphs or LoRA training images run there. Keep those combinations unverified/disabled until an exact supported execution path is established. [Workers AI](https://developers.cloudflare.com/workers-ai/).
- **Oracle:** CPU and GPU shapes make it a candidate for both instance workloads. [Compute shapes](https://docs.oracle.com/en-us/iaas/Content/Compute/References/computeshapes.htm). Billing after stopping varies by shape, so teardown must verify the appropriate provider action and remaining resources. [Stopped-instance billing](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/resource-billing-stopped-instances.htm).

These are targeted checks, not certification of all eight providers. AWS, GCP, Azure, RunPod, Hyperstack and Thunder still need a sourced mode/storage/region matrix and adapter contract validation. All eight remain in scope; unsupported combinations must not be represented as working adapters.

## 6. Delivery and verification

Proposed order: durable lifecycle and fake providers → extraction migration → ComfyUI → embedding/indexing → LoRA/LyCORIS. All four workloads remain in v1. Develop provider adapters against the same capability and lifecycle contract; do not promise every workload on every mode.

Targeted checks should cover lost submit responses, daemon restart, database outage, duplicate events, concurrent budget reservations, interrupted collection, expired access, stale embeddings and failed teardown. Use fake clocks/providers and sanitized fixtures under approved test paths. Live paid checks require explicit authorization; full suites and benchmarks follow the repository resource rule. No implementation or test runs are part of this proposal.

## Questions and recorded answers

Harbinger's answers below supersede the original recommendations where they differ. Recorded by Codex, 2026-10-19; the overall initiative remains in brainstorming pending the team scope decision.

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
