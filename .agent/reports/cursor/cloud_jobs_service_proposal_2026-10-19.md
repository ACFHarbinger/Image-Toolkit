# Cloud Jobs Service — Cursor proposal

**Cursor · 2026-10-19 · Proposal only. Nothing here is approved to build.**

Companion to `.agent/reports/team/cloud_jobs_service_2026-10-19.md`.
Builds on Harbinger's recorded answers (Claude Q1–Q10, Codex Q1–Q7,
Gemini Q1–Q5, OpenCode Q1–Q8, Grok Q1–Q8). Does not reopen them.

Claude, Codex, Gemini, OpenCode, and Grok already cover the async
lifecycle, PostgreSQL + daemon WAL, two backend families, risk rules,
GCP + RunPod first, admission caps, cache volumes, and headless jobs.
This note adds the **window map**, the **credential lease the daemon
needs after the GUI closes**, **where the Codex watchdog actually
runs**, and a sourced capability matrix that changes a few defaults.

Cursor owns WindowManager (#528). The recommendation is shaped by that:
Cloud Jobs fails as a second Cloud Compute, not as a missing adapter.

## Thesis

Do not invent a third submit form. Extractor already has "☁ Run on
Cloud" (`gui/src/tabs/core/extractor_tab/_cloud_dispatch.py`). Cloud
Compute already has a Request Builder pane that is a second, extraction-
shaped submit UI. The header already has one ☁️ button that opens Cloud
Compute (`gui/src/windows/main/_header_builder.py`).

The jobs service should be:

- **submit from the origin tab** (Extractor, ComfyUI, Train, Index)
  through one EventHub intent;
- **monitor and kill from a WindowManager-registered Cloud Jobs
  window**;
- **set up credentials and providers in the existing Cloud Compute
  window**.

Agree with: async state machine, PostgreSQL system of record, daemon
WAL, presigned staging, predictive hard cap, digest-pinned images,
GCP + RunPod first, headless v1, no attended ComfyUI desktop.

Disagree with: Claude copying an SSH/console link into the jobs window
(Grok Q8 C forbids floating IPs and forwarded ports). Disagree with
keeping Request Builder as a live submit surface. Disagree with treating
the Oracle Container Instance stub as a GPU path — that Terraform is
CPU-only.

## 0. Findings in this checkout (not live-run)

Checked 2026-10-19 against current provider docs and this tree.

| Evidence | Consequence |
|---|---|
| `CloudProviderAdapter.run(job)` is a blocking `POST /jobs` (`provider_adapter.py`). The GCD worker runs the workload before answering. Codex already flagged this. | The first managed-batch adapter is a **new** submit/poll/cancel contract wrapped around Cloud Run **Jobs**, not a thread around today's service. The PoC `Service` YAML (`infra/cloud/gcd/cloud-run-service.yaml`) is the wrong Cloud Run product for durable jobs. |
| That YAML already sets `timeoutSeconds: 3600`. The worker's `run_commands` default is 1700s. | Extraction on Cloud Run is already a one-hour box. Fine for the PoC. Not a LoRA host. |
| Cloud Run Jobs GPU docs (updated 2026-10-13): one GPU per instance (L4 or RTX PRO 6000); GPU jobs should set a task timeout of **one hour or less**. CPU jobs may run up to 168h. | Grey out Cloud Run GPU for ComfyUI/LoRA unless the estimate is under that timeout. GCP GPU training in v1 is GCE (or Batch on GCE), not Cloud Run. [GPU jobs](https://docs.cloud.google.com/run/docs/configuring/jobs/gpu), [GPU best practices](https://docs.cloud.google.com/run/docs/configuring/jobs/gpu-best-practices). |
| RunPod REST API **v1 retires 2026-11-15**. v2 is current. Network volumes attach at Pod create and replace `/workspace`; Serverless mounts at `/runpod-volume`. Concurrent writers on one volume can corrupt it. | The first GPU adapter is v2-only. Grok's one-cache-volume-per-account-and-region must serialise writes or use attempt scratch. [v1 overview](https://docs.runpod.io/api-reference/overview.md), [network volumes](https://docs.runpod.io/storage/network-volumes). |
| Thunder `mode` (`prototyping`/`production`) is **deprecated**. New integrations omit it and use `GET /v2/specs`. Omitting `public_key` still returns a generated private key once. | Adapter always sends a daemon-owned public key and never logs a private key (Grok is right). Do not send `mode`. [create instance](https://www.thundercompute.com/docs/api-reference/instances/create-instance). |
| Hyperstack create-VM body has `user_data` (cloud-init, **65535 bytes after Base64**) and `assign_floating_ip`. Labels are a **follow-up** `PUT /core/virtual-machines/{vm_id}/label`, not a create-time field. | Orphan tags must be a second call, persisted as a teardown obligation if the label PUT fails. Default `assign_floating_ip: false` (Grok Q8 C). Keep cloud-init tiny: pull the digest, don't embed the worker. [create VMs](https://docs.hyperstack.cloud/docs/api-reference/create-vms), [cloud-init](https://docs.hyperstack.cloud/docs/virtual-machines/initialization-configuration/), [labels](https://docs.hyperstack.cloud/docs/api-reference/add-vm-label). |
| Cloudflare Containers: CPU/RAM/disk only. Default custom cap 4 vCPU / 12 GiB / 20 GB. No CUDA in the current limits table. Durable Object named images must be digest-pinned on `registry.cloudflare.com`; GHCR is not a direct source. [limits](https://developers.cloudflare.com/containers/platform/limits/), [image management](https://developers.cloudflare.com/containers/guides/image-management/). | Matches Gemini Q3: Containers for eligible CPU, Workers AI as a fixed inference proxy, R2 for staging. The existing `infra/cloud/cloudflare/wrangler.toml` is Queues+R2+D1 — a coordinator stub, not the compute path Harbinger picked. |
| Oracle Container Instances shapes are CPU-only (`CI.Standard.E4/E5/A1.Flex`). GPU is Compute VM or Data Science Jobs. [CI shapes](https://docs.oracle.com/en-us/iaas/Content/container-instances/container-instance-shapes.htm), [compute shapes](https://docs.oracle.com/en-us/iaas/Content/Compute/References/computeshapes.htm). | `infra/cloud/oracle/oci-container-instance.tf` comments "GPU shapes available" and mentions `VM.GPU.A10`, but the resource is a CI with `CI.Standard.E4.Flex`. Treat that stub as the CPU managed path. GPU on Oracle is an instance backend. |
| Azure Container Apps **Jobs** exist; serverless GPU docs describe **apps**, not jobs. [Jobs](https://learn.microsoft.com/en-us/azure/container-apps/jobs), [serverless GPU](https://learn.microsoft.com/en-us/azure/container-apps/gpu-serverless-overview). | Azure GPU in v1 is VM/Batch until someone certifies GPU-on-Jobs. Grey it out. |
| `EventHub` already has `ImportPathsIntent` / `NavigateIntent`. Cloud Compute window already `register_window(self)` with **no role**. Header ☁️ always opens Cloud Compute. Extractor dispatch talks to `CloudExtractionWorker` on the GUI thread's worker, not a daemon. | Submit is an EventHub intent. Windows get roles `cloud.jobs` and `cloud.compute`. The PoC worker is not the lifetime answer. |
| VaultManager decrypts keys in-process under an RLock. There is no job-scoped lease API and no daemon-facing credential store. | Closing the app currently drops the only place provider keys live in memory. A daemon that outlives the GUI needs an explicit lease, or it cannot tear down. |

## 1. Window map — Cloud Jobs is an observer, not a product

Roles, registered with WindowManager:

| Role | Window | Job |
|---|---|---|
| `cloud.compute` | today's Cloud Compute | providers, VaultManager aliases, IAM templates, Request Builder submit (Q1 C), dashboards stay or link |
| `cloud.jobs` | new Cloud Jobs window | jobs table, detail (timeline, log tail, spend), resources/orphans, spend vs cap |
| `main` | header ☁️ | badge: running count + reserved spend; click opens `cloud.jobs` |

Submit lives where the work is already configured:

- Extractor keeps "Run in cloud" but publishes `SubmitCloudJobIntent`
  instead of constructing `CloudExtractionWorker`.
- ComfyUI / Train / Index do the same. OpenCode's placement planner
  runs in the backend; the tab shows the plan and the risk colouring
  (Claude Q8), then the daemon owns the job.
- Cloud Jobs can clone-and-edit a past job. That is retry, not a
  second builder.

Request Builder currently mixes extraction range, a prompt field, a
shape picker, and an in-window queue table. Harbinger kept both that
pane and origin-tab submit (Q1 C). The in-window queue still moves to
Cloud Jobs; both submit surfaces must emit the same `JobSpec` /
`SubmitCloudJobIntent` so they cannot drift into two `CloudJob`
schemas.

Deep Learning Runs stays the training record reader (Grok Q7 A). Cloud
Jobs shows spend and instances and links with `NavigateIntent`. Do not
clone loss charts into a fourth panel.

No SSH, no console URL, no forwarded port in this window. Claude's
"copy an SSH or console link" action is out. Thunder's port API and
Hyperstack `assign_floating_ip` stay off.

Tray: the daemon can post OS notifications for terminal states, cap
hits, and teardown failures (Grok already proposed this). No extra
tray window in v1. The header badge is the in-app record.

## 2. Credential lease — the daemon cannot hold the vault

Recorded lifetime: jobs keep running after the app closes. Recorded
accounts: BYO keys in VaultManager. Those two answers collide unless
we name the third object:

**A job-scoped credential lease**, issued at submit while the vault is
unlocked.

- Contents: provider account id, a short-lived token or a copy of the
  already-narrow IAM key, resource ids this job may mutate, expiry =
  max runtime + teardown grace.
- Storage: daemon sealed store under the config root (`0600`), not the
  vault file, not PostgreSQL in plaintext.
- The daemon uses the lease for poll / cancel / collect / teardown.
  It never sees the vault passphrase.
- New submits and "open Cloud Compute settings" still require the
  vault. If the lease expires while teardown is unfinished, the
  cloud-side watchdog (Codex Q1) is the remaining brake; the UI shows
  reduced protection.
- User-supplied images still get no VaultManager or database
  credentials (OpenCode Q3).

Tradeoff: a lease is another secret to sweep. The alternative is
either a daemon that holds every cloud key for its whole lifetime, or
a daemon that cannot call providers after logout — both worse for
the recorded teardown guarantee.

## 3. Watchdog hosting — pick a home for Codex Q1

Codex Q1 put a cloud-side cleanup watchdog next to the local daemon.
Nobody said where it runs. A watchdog that lives "in the abstract"
will not get deployed, and then laptop-sleep leaks GPU hours.

Recommend a **tiny job-scoped function in an account we already
touch**:

- First: a GCP Cloud Function / Cloud Run service on the same GCP
  project as the extraction adapter (GCP ships first).
- Also valid: a Cloudflare Worker in the user's CF account (CF is in
  scope; Workers are a natural heartbeat+deadline). The current
  `wrangler.toml` Queues stub is the ancestor of this, not of ComfyUI.
- Payload: resource ids, provider, deadline, last heartbeat. Authority:
  a watchdog-only IAM role that can stop/delete tagged resources and
  cannot read the image database or the vault.
- Heartbeat: the local daemon refreshes a presigned object or a Worker
  KV key. Silence past the deadline ⇒ teardown.

Provider-native deadlines stay required where verified (Cloud Run task
timeout, RunPod stop/timeout). Combinations without either a native
deadline or a deployed watchdog take Codex Q1's acknowledgement path.

Do not rent a always-on mini-VM as the watchdog. That is Codex Q1 C,
already deferred.

## 4. Worker images — user registry, digest-pinned, copied at the edge

Claude's `it-worker:<app-version>` on public GHCR is convenient and
makes us the supply chain. Cloudflare Durable Object images cannot
pull GHCR directly; they need `registry.cloudflare.com`. GCP-first
already implies Artifact Registry.

Recommend:

- Toolkit ships Dockerfiles (CPU extraction, CPU index, CUDA
  ComfyUI/train), versioned with the app.
- The user publishes them to **their** Artifact Registry (or GHCR) via
  a Cloud Compute action. Runtime references are digest-pinned.
- Cloudflare jobs copy that digest into the CF managed registry at
  submit. RunPod pulls the user registry with a registry-auth secret
  that the worker never sees as a general cloud key.
- User-supplied images remain allowed (Codex Q5 B / OpenCode Q3 C) with
  the recorded warning and no-credential boundary.

Three images, not one: the current FFmpeg-only GCD worker must not
grow a CUDA stack. Cold-start cost on instance GPUs is billed.

## 5. Capability matrix (v1 honesty)

Unsupported combinations are greyed out by the shared risk evaluator,
not documented as "coming soon" in the submit form.

| Provider | Managed batch | Instance | GPU in v1? | Storage notes |
|---|---|---|---|---|
| GCP | Cloud Run Jobs (CPU; GPU only if estimate ≤ verified 1h timeout) / Batch | GCE | Yes, via GCE/Batch for long GPU | GCS presign; first CPU path |
| RunPod | Serverless later | **Pods first** (API v2) | Yes | Network volume per account+datacenter; attempt scratch; no concurrent writers |
| AWS | Batch | EC2 | After first pair | S3 presign |
| Azure | Container Apps Jobs (CPU) | VM | VM only until GPU-on-Jobs is certified | Blob presign |
| Cloudflare | Containers (CPU) + Workers AI proxy | No | No custom CUDA | R2 staging; copy image into CF registry |
| Oracle | Container Instances (CPU) | GPU VMs | GPU = instance | Object Storage; do not send CI a GPU shape |
| Hyperstack | No | VM + cloud-init | Yes | Labels after create; no floating IP; spot is a flavor name |
| Thunder | No | VM; omit `mode`; always `public_key` | Yes | Templates unverified; no port forward |

PostgreSQL: same instance as the image library, separate schema
`cloud_jobs`. No SQLite. Daemon WAL is the offline brake, not a second
ledger.

## 6. Cancel, collection, notifications

User **Cancel** should match the recorded hard cap: checkpoint if
supported, collect verified shards, teardown. **Force stop** is a
second control, recoloured, skips checkpoint. Do not add Pause — a
paused instance is a billing leak with a friendly name.

Incremental collection (Grok) stays. Extractor frames and ComfyUI
images upload as they finish. Training checkpoints follow the existing
cadence.

Daemon OS notifications for terminal states, cap hits, teardown
failures. No webhook/email in v1.

## 7. Multi-machine

Grok: one daemon per OS user. If two machines share the same
PostgreSQL, Codex's advisory lock is the leader fence. A second GUI is
a read-only observer unless it wins the lease after the leader's
heartbeat expires. Collection and provider calls stay on the leader.
Credential leases do not automatically replicate to the other machine.

If they do not share PostgreSQL, jobs are bound to the submitting
machine's ledger. That is the default: this app already has a local
Postgres assumption.

## 8. Shape (when implementation is allowed)

- `gui/src/modules/events.py`: `SubmitCloudJobIntent`, `CloudJobUpdatedFact`.
- Window roles `cloud.jobs` / `cloud.compute`; header badge on the
  existing ☁️ control.
- `backend/src/cloud/lease.py`: job-scoped credential lease.
- `backend/src/cloud/watchdog.py` + `infra/cloud/gcd/watchdog/` (and/or
  a Worker next to the existing wrangler stub).
- Capability catalogue entries sourced from §5, including RunPod v2
  and Thunder-without-`mode`.
- Migrate `backend/src/web/cloud/compute/` behind shims as already
  decided. Replace blocking `run()`; do not wrap it.

Targeted tests: fake providers, fake clock, lease expiry during
teardown, label-PUT failure on Hyperstack, missing `public_key` on
Thunder (must not accept a returned private key into logs). Live paid
checks follow the resource rule through Codex.

## Questions for Harbinger

Harbinger's answers below supersede the original recommendations where
they differ. Recorded by Cursor, 2026-10-19. Q1 is C; Q2–Q8 are A.
Scope still awaits the team final round.

### Cursor Q1 — Where does the user submit a cloud job from?

- **Harbinger answer (2026-10-19):** C. Keep both Request Builder and
  origin-tab submit. They must share one `JobSpec` so the two surfaces
  cannot drift.
- **A (recommended):** From the origin tab (Extractor, ComfyUI, Train,
  Index) via `SubmitCloudJobIntent`. Cloud Jobs is monitor, kill,
  retry, clone. Cloud Compute Request Builder loses submit.
- **B:** Cloud Jobs window is the only submit surface. Origin tabs
  offer "Open in Cloud Jobs with this spec".
- **C:** Keep both Request Builder and origin-tab submit.
- **D:** Fold monitor into Cloud Compute; no separate Cloud Jobs
  window after all. (This would reopen Claude Q4.)

### Cursor Q2 — Where does the cloud-side cleanup watchdog run?

- **Harbinger answer (2026-10-19):** A.
- **A (recommended):** A tiny job-scoped function in an account we
  already use: GCP Cloud Function/Run first, Cloudflare Worker also
  valid. Watchdog-only IAM. Heartbeat + deadline ⇒ teardown.
- **B:** Provider-native deadlines only. Combinations without a
  verified deadline require acknowledgement (Codex Q1 B).
- **C:** A user-owned always-on mini VM as the watchdog.
- **D:** No extra watchdog. In-instance dead-man + daemon WAL only.

### Cursor Q3 — How does the daemon get credentials after the GUI closes?

- **Harbinger answer (2026-10-19):** A.
- **A (recommended):** Job-scoped credential lease issued at submit
  while the vault is unlocked. Daemon never holds the vault
  passphrase. New submits still need the vault.
- **B:** Daemon keeps decrypted copies of all configured cloud keys
  for its lifetime.
- **C:** After the GUI closes, the daemon cannot call providers.
  Collection waits for the next unlock; only dead-man + watchdog tear
  down.
- **D:** Daemon prompts the OS keyring / user when it next needs a
  key (fails unattended).

### Cursor Q4 — Who publishes the first-party worker images?

- **Harbinger answer (2026-10-19):** A.
- **A (recommended):** User-owned registry (GCP Artifact Registry
  first). Toolkit ships Dockerfiles and a publish action. Digests
  pinned. Cloudflare jobs copy into `registry.cloudflare.com`.
- **B:** Project-public GHCR images the Toolkit publishes.
- **C:** No first-party image after the extraction PoC; user-supplied
  digest-pinned images only.
- **D:** Build locally with Docker and push at each submit.

### Cursor Q5 — What does the header ☁️ button open?

- **Harbinger answer (2026-10-19):** A.
- **A (recommended):** One control. Click opens Cloud Jobs (badge =
  running count + reserved spend). A gear / shift-click opens Cloud
  Compute setup.
- **B:** Two header buttons: Jobs and Compute.
- **C:** Keep ☁️ as Cloud Compute. Cloud Jobs is only from that
  window's sidebar and from origin-tab "view job".
- **D:** Delete the Cloud Compute window. Setup becomes a pane inside
  Cloud Jobs.

### Cursor Q6 — May a second machine watch the same jobs?

- **Harbinger answer (2026-10-19):** A.
- **A (recommended):** If they share PostgreSQL, one leader daemon;
  the other GUI is read-only until it wins the lease. If they do not
  share PostgreSQL, jobs stay on the submitting machine.
- **B:** Jobs are bound to the submitting machine always. Other
  machines see results only after collection.
- **C:** Any machine may steal the lease and take over collection and
  teardown.
- **D:** Hide other-machine jobs in v1. No observer mode.

### Cursor Q7 — What should Cancel do?

- **Harbinger answer (2026-10-19):** A.
- **A (recommended):** Same as the hard cap: checkpoint if supported,
  collect verified shards, teardown. Force stop is a second,
  recoloured action that skips checkpoint.
- **B:** Immediate kill always.
- **C:** Cancel only records intent; the user confirms teardown in
  the Resources view.
- **D:** Offer Pause (instance keeps billing) and Cancel (teardown).

### Cursor Q8 — Long GCP GPU jobs vs Cloud Run's one-hour GPU timeout?

- **Harbinger answer (2026-10-19):** A.
- **A (recommended):** Grey out Cloud Run GPU when the estimate
  exceeds the verified timeout. GCP ComfyUI/LoRA in v1 uses GCE (or
  Batch on GCE). Cloud Run stays the CPU extraction/index path, and
  GPU only for short jobs that fit.
- **B:** Automatically shard long GPU work into ≤1h Cloud Run tasks.
- **C:** Allow Cloud Run GPU with a hard 1h cap and a warning.
- **D:** Cloud Run is CPU-only on GCP in v1. All GCP GPU is GCE/Batch
  from day one.

— Cursor, 2026-10-19
