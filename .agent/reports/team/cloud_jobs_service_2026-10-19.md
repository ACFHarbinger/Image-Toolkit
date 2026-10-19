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

*(empty until the final brainstorming round)*
