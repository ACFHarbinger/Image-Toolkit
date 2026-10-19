# Cloud Jobs Service — Grok proposal

— Grok, 2026-10-19. Proposal only. Builds on Harbinger's recorded answers
(Claude Q1–Q10, Codex Q1–Q7, Gemini Q1–Q5, OpenCode Q1–Q8). Does not
re-open them.

## 1. What this adds

The recorded scope already has a PostgreSQL job ledger, a local daemon
with a WAL, two execution families, presigned staging, risk rules, and
GCP + RunPod first. The holes below are the ones that still change the
design.

### Cloud admission, next to the local GPU lease

`gpu_lease_arbiter.py` admits one local GPU workload at a time. Cloud
v1 can open many paid instances at once. Add a **cloud admission
snapshot** in the daemon, checked before any provider call:

- max concurrent jobs;
- max concurrent GPU instances;
- max spend reserved but not yet reconciled.

A job that fails admission stays `queued` locally. It does not
provision. Reservations use the same ledger as the monthly cap
(OpenCode Q5, Codex Q2). Tradeoff: a user who wants a burst must raise
the cap on purpose. That is cheaper than discovering twenty RunPod pods
after a multi-select.

### One daemon per OS user

The slideshow daemon is per machine, not per git checkout. This repo is
often open from several worktrees. The cloud daemon should be the same:
one process, a lock outside the repo, jobs tagged with the profile that
submitted them. A second app connects over the existing local IPC. It
must not start a second reconciler. Tradeoff: a stuck daemon blocks
every checkout until it is restarted. The Cloud Jobs window should show
daemon health, not only job rows.

### Preflight before any byte leaves

Two scans run in-process, with no provider call:

1. **Weight cloud class.** LoRA and ComfyUI jobs upload checkpoints.
   Some licenses forbid third-party hosting. Each local weight gets
   `allow`, `warn`, or `block`. Unknown hashes warn and need an
   acknowledgement. `block` never enters the staging manifest.
2. **Workflow secret scan.** ComfyUI graphs often carry API keys in
   node widgets. The scan flags high-entropy widget values and known
   key field names, names the node id, and refuses submit until the
   user strips or explicitly keeps that field. Logs and the flight
   recorder store the redacted graph only.

These sit beside OpenCode Q7's data classes. Data class covers the
user's images. These cover weights and graph secrets.

### Instance GPUs do not speak "run this container"

Checked 2026-10-19:

- **Hyperstack** is a VM API (`POST /v1/core/virtual-machines` on
  `infrahub-api.nexgencloud.com`), with cloud-init `user_data`,
  flavors, and `GET /v1/core/stocks`. Regions in the stock docs:
  `CANADA-1`, `NORWAY-1`, `US-1`. CPU-only flavors exist
  (`gpu` empty). Spot is a **separate model name** in the stock
  payload, not a boolean on every flavor. No managed-batch API showed
  up in the quickstart or create-VM docs. Orphan tagging on the VM
  create body was not in the snippet reviewed; do not assume labels
  until that field is verified.
  Sources: [quickstart](https://docs.hyperstack.cloud/docs/api-reference/quickstart),
  [create VMs](https://docs.hyperstack.cloud/docs/api-reference/create-vms),
  [stocks](https://docs.hyperstack.cloud/docs/hardware/gpu-stock-information).
- **Thunder Compute** is instance create
  (`POST /v1/instances/create` on `api.thundercompute.com:8443`) with
  `gpu_type`, `num_gpus`, `mode` (`prototyping` or `production`), a
  template (`base`, `comfy-ui`, `ollama`, or a snapshot), and a port
  API. If `public_key` is omitted, the API can generate a private key.
  The adapter must always send a daemon-owned public key and must not
  log a returned private key. No batch API showed up in the instance
  docs.
  Sources: [create instance](https://www.thundercompute.com/docs/api-reference/instances/create-instance),
  [templates](https://www.thundercompute.com/docs/console/operations/creating-instances).

So "one versioned worker image" is true for GCP Batch / Cloud Run.
On Hyperstack and Thunder the boot path is cloud-init that **pulls a
digest-pinned image**, or a provider template that we do not build.
Provider templates are a different trust tier: useful cold start,
unverified runtime. The risk evaluator should treat "spot" as a flavor
capability, because Hyperstack encodes it in the model name.

### Stock is a state, not only a sort key

Hyperstack exposes a stock endpoint. RunPod capacity fluctuates the
same way. If the chosen flavor is out of stock, the job should be able
to sit in `waiting_for_capacity` on the daemon, polling on a bounded
interval, until a user deadline. No VM is billed in that state.
Crossing to a different GPU or provider still follows Codex Q3: ask,
unless automatic fallback is on.

### Cache topology is separate from retention

Codex Q4 decides how long caches live. It does not decide whether the
second job pays the download again. Recommend **one cache volume per
provider account and region**, content-addressed, with a refcount of
jobs using it, plus a per-job scratch disk that always dies with the
attempt. Sharing is a Settings switch. Deleting the shared volume waits
until the refcount is zero.

### Training records stay training records

Cloud LoRA jobs should materialize the same
`training_runs/<id>/record.json` and `events.jsonl` layout that
`training_runs.py` already defines (`STATUS_RUNNING`, `STATUS_SUCCESS`,
`STATUS_CANCEL`, `STATUS_ERROR`). The daemon writes those files from
the polled sink (Gemini Q2). Deep Learning Runs, the report card, and
the checkpoint tournament then read a cloud run the same way they read
a local one. The Cloud Jobs window keeps spend, instances, and
teardown. Each view links to the other. A second training UI inside
Cloud Jobs would fork that contract.

### Headless by default

Thunder's port API and Hyperstack's floating IP make an attended
ComfyUI desktop easy to bolt on. v1 jobs should still be headless:
no public IP and no forwarded port unless the user starts an attended
session. That session is time-boxed, named in the resource ledger, and
torn down with the job. An open port is a resource leak even when the
GPU bill looks fine.

### Incremental collection

Extraction segments and finished ComfyUI images upload as they
complete. Training keeps the checkpoint cadence already required for
preemption. Cancel and hard-cap teardown keep shards whose checksums
verified. End-only collection throws away a finished hour when the
download fails.

### Closed-app signal

The daemon posts an OS notification for terminal states, cap hits, and
teardown failures. No outbound webhook in v1. The window's badge is the
record when the user is at the machine.

## 2. Provider classification (this pass)

| Provider | v1 execution | Notes from this pass |
|---|---|---|
| GCP | Managed batch first (Cloud Run / Batch), VM later | Already decided as a first provider |
| RunPod | Pods first, Serverless later | Already decided as the first GPU path |
| AWS, Azure | Batch and VM, after the first pair | Unchanged |
| Cloudflare | Containers for eligible CPU, Workers AI as a fixed inference proxy, R2 for staging | Matches Gemini Q3. Not a ComfyUI/LoRA host in v1 |
| Oracle | CPU and GPU instances | Stopped-shape billing still has to be verified per shape before teardown is called done |
| Hyperstack | Instance only, CPU flavors and GPU flavors | Stock API is the capacity signal. Spot is a distinct model. Boot with cloud-init |
| Thunder Compute | GPU instance only | Templates and snapshots exist. Treat `comfy-ui` as an unverified template, not as our worker |

Unsupported combinations stay disabled in the capability catalogue.
"In scope" is not "every workload on every provider."

## 3. Shape

- `backend/src/cloud/admission.py` — pure decision from a snapshot.
  No Qt, no network.
- `backend/src/cloud/preflight.py` — weight class and workflow secret
  findings, each with a stable rule id.
- `backend/src/cloud/capacity.py` — `waiting_for_capacity` transitions.
- Instance adapters implement `boot_script(digest)` rather than
  `run(job)`.
- Daemon is the only writer of `record.json` for cloud training runs.
  Local trainers keep their own writer.

Targeted tests use fake providers and a fake clock. Live Hyperstack or
Thunder calls spend money and stay behind the benchmark gate.

## 4. Questions for Harbinger

Harbinger's answers below supersede the original recommendations where
they differ. Recorded by Grok, 2026-10-19. Q2 is B and Q8 is C.

### Grok Q1 — How many cloud jobs may run at once?

- **Harbinger answer (2026-10-19):** A. Settings caps: max concurrent
  jobs, max concurrent GPU instances, and max reserved spend. Extra
  jobs wait locally in `queued` and do not provision.
- **A (recommended).** Settings caps: max concurrent jobs, max
  concurrent GPU instances, and max reserved spend. Extra jobs wait
  locally in `queued` and do not provision.
- **B.** No concurrency cap. The monthly spend cap is the only brake.
- **C.** One GPU job at a time, always. CPU batch jobs are unlimited
  aside from the spend cap.

### Grok Q2 — What happens when the chosen GPU is out of stock?

- **Harbinger answer (2026-10-19):** B. Fail the job immediately and
  leave retry to the user. No `waiting_for_capacity` hold in v1.
- **A (recommended).** Hold the job locally in `waiting_for_capacity`
  until a user deadline, polling the provider stock or capacity API.
  Do not start a different GPU or provider unless automatic fallback
  is already enabled.
- **B.** Fail the job immediately and leave retry to the user.
- **C.** Automatically move to the next GPU class that fits the cap
  and the data-class allowlist.

### Grok Q3 — May a job upload local model weights?

- **Harbinger answer (2026-10-19):** A. Each weight has a cloud class:
  `allow`, `warn`, or `block`. Unknown hashes warn and require
  acknowledgement. `block` is omitted from the staging manifest.
- **A (recommended).** Each weight has a cloud class: `allow`, `warn`,
  or `block`. Unknown hashes warn and require acknowledgement.
  `block` is omitted from the staging manifest.
- **B.** One global switch: the user accepts uploading weights to
  configured providers.
- **C.** Never upload weights. Jobs may use only weights already on a
  provider cache volume.

### Grok Q4 — What should preflight do with secrets inside a ComfyUI graph?

- **Harbinger answer (2026-10-19):** A. Scan widget values. Block submit
  until the user strips the flagged fields or explicitly keeps them.
  Logs store the redacted graph. The finding names the node id.
- **A (recommended).** Scan widget values. Block submit until the user
  strips the flagged fields or explicitly keeps them. Logs store the
  redacted graph. The finding names the node id.
- **B.** Reject any graph that is not in the pinned pack's known node
  set. No user override.
- **C.** Upload the graph as-is and show a single warning.

### Grok Q5 — What boots a Hyperstack or Thunder job?

- **Harbinger answer (2026-10-19):** A. Cloud-init always pulls our
  digest-pinned worker image. A provider template such as Thunder's
  `comfy-ui` is an explicit override, marked unverified, and still gets
  the secret scan, the no-credential rule, and hard caps.
- **A (recommended).** Cloud-init always pulls our digest-pinned worker
  image. A provider template such as Thunder's `comfy-ui` is an
  explicit override, marked unverified, and still gets the secret scan,
  the no-credential rule, and hard caps.
- **B.** Prefer the provider template when one exists. Our image is the
  fallback.
- **C.** Provider templates only on Thunder. Our image everywhere else,
  with no template override.

### Grok Q6 — Where do reusable model files live between jobs?

- **Harbinger answer (2026-10-19):** A. One cache volume per provider
  account and region, content-addressed, reference-counted by running
  jobs. Each attempt also has a scratch disk that is deleted with the
  attempt. Sharing can be turned off in Settings.
- **A (recommended).** One cache volume per provider account and
  region, content-addressed, reference-counted by running jobs. Each
  attempt also has a scratch disk that is deleted with the attempt.
  Sharing can be turned off in Settings.
- **B.** Per-job disk only. Every job re-downloads what it needs.
- **C.** The user attaches an existing volume by hand on each job.

### Grok Q7 — How should a cloud training run appear in the app?

- **Harbinger answer (2026-10-19):** A. The daemon writes the same
  `record.json` and `events.jsonl` layout as a local run. Deep Learning
  Runs, the report card, and the checkpoint tournament read it. Cloud
  Jobs shows spend and instances and links to that run.
- **A (recommended).** The daemon writes the same `record.json` and
  `events.jsonl` layout as a local run. Deep Learning Runs, the report
  card, and the checkpoint tournament read it. Cloud Jobs shows spend
  and instances and links to that run.
- **B.** Cloud training appears only in the Cloud Jobs window. Deep
  Learning Runs stays local-only.
- **C.** Cloud Jobs grows its own copy of the training panels.

### Grok Q8 — Does v1 open a ComfyUI web UI on the instance?

- **Harbinger answer (2026-10-19):** C. A separate "cloud ComfyUI
  desktop" product, not part of the jobs service. The jobs service does
  not open a web UI, floating IP, or forwarded port.
- **A (recommended).** No. v1 jobs are headless. No floating public IP
  and no forwarded port. An attended UI can be a later session type
  that is time-boxed and torn down with the job.
- **B.** Every ComfyUI job opens the web UI through an SSH tunnel or
  the provider port API until the job ends.
- **C.** A separate "cloud ComfyUI desktop" product, not part of the
  jobs service.
