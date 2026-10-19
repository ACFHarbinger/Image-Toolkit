# Cloud Jobs Service — Gemini Proposal

**Gemini / Antigravity · 2026-10-19 · Proposal only; brainstorming round.**

Companion to `.agent/reports/team/cloud_jobs_service_2026-10-19.md`. Builds upon Harbinger's recorded decisions (all four workloads in v1, user-selectable execution model, standalone Cloud Jobs window, local daemon lifecycle, pluggable storage, and UI risk feedback) and synthesizes the proposals of Claude (asynchronous lifecycle, orphan sweeps, dead-man timers) and Codex (PostgreSQL compliance, durable attempts, capability catalogue).

---

## 1. Executive Summary & Core Architectural Pillars

The transition from the §4.21 synchronous Cloud Run PoC (`backend/src/web/cloud/compute/`) to a multi-cloud orchestration engine (`backend/src/cloud/`) spanning 8 providers (AWS, GCP, Azure, Cloudflare, Oracle, RunPod, Hyperstack, Thunder Compute) requires solving four fundamental engineering challenges:

1. **State Resiliency without SQLite:** AGENTS.md mandates PostgreSQL with `pgvector` and explicitly prohibits SQLite. The orchestrator must keep operational job state, attempt histories, and budget reservations in PostgreSQL, but ensure that the local background daemon can survive transient DB connection dropouts or desktop power transitions without dropping teardown obligations.
2. **Zero-Trust Cloud Sync Staging:** Enabling Cloud Sync remotes (Google Drive, OneDrive, Dropbox) as job storage cannot involve transmitting user OAuth refresh tokens or full credentials to untrusted cloud pods. We specify an ephemeral, local-daemon-mediated staging pipeline.
3. **Telemetry & Live Metric Streaming:** Long-running training (LoRA/LyCORIS) and heavy batch generation (ComfyUI) require live loss curves, step counters, and console logs in the manager UI without exposing inbound firewall ports or public IPs on the user's desktop.
4. **Declarative Risk & Capability Engine:** A pure-Python, Qt-free risk matrix evaluates `(JobSpec, ProviderCapabilities, UserSettings)` to emit reactive styling signals (recolouring, warning banners ⚠, and disabled/greyed-out controls).
5. **Atomic Vector & Embedding Ingestion:** Bulk cloud embeddings (CLIP) and perceptual hashes (phash) must merge safely into `pgvector` without race conditions against local library metadata modifications.

---

## 2. Orchestration, Persistence & Daemon Resiliency

```
┌────────────────────────────────────────────────────────┐
│ PySide6 GUI (Cloud Jobs Window & Request Builder)      │
│  - Observes job states & telemetry via IPC             │
│  - Evaluates UI Risk Engine & recolours controls       │
└───────────────────────▲────────────────────────────────┘
                        │ Authenticated Local IPC (Domain Socket / Pipe)
┌───────────────────────▼────────────────────────────────┐
│ Local Cloud Daemon (`backend/src/cloud/daemon.py`)      │
│  - Leader lease & advisory fencing                     │
│  - In-flight Reconciler & Dead-man sweep               │
│  - Memory-backed Write-Ahead Log (WAL)                 │
└───────────▲───────────────────────────────▲────────────┘
            │ SQL Transactions              │ Polling / Submit
┌───────────▼───────────┐       ┌───────────▼────────────┐
│ PostgreSQL System of  │       │ Cloud Provider APIs    │
│ Record (`cloud_jobs`, │       │ (RunPod, AWS, GCP,     │
│ `cloud_attempts`)     │       │  Hyperstack, etc.)     │
└───────────────────────┘       └────────────────────────┘
```

### 2.1 Storage Architecture: PostgreSQL + Resilient Daemon WAL
- **System of Record:** PostgreSQL hosts `cloud_jobs`, `cloud_job_attempts`, `cloud_resources`, and `cloud_budget_reservations`. This strictly adheres to AGENTS.md governance while avoiding Claude's SQLite proposal.
- **Daemon Isolation & Resiliency:** The local daemon (`backend/src/cloud/daemon.py`, modelled after `slideshow_daemon.py`) holds a PostgreSQL connection pool. To handle machine sleep, logoff, or temporary DB restarts, the daemon maintains an in-memory/JSONL Write-Ahead Log (`~/.image-toolkit/cloud/daemon_wal.jsonl`) recording unconfirmed teardown obligations and provider submission intents.
- **Fencing & Reentrancy:** Uses PostgreSQL advisory locks (`pg_try_advisory_lock`) to guarantee that only one controller daemon manages provider lifecycle at any given time. If the GUI starts with no daemon running, it spawns the daemon as a detached subprocess.

### 2.2 Attempt-Based State Machine
Jobs advance through deterministic, auditable states:
`DRAFT` → `VALIDATING` → `STAGING` → `SUBMITTED` → `PROVISIONING` → `RUNNING` → `COLLECTING` → `SETTLING` → `COMPLETED` | `FAILED` | `CANCELLED`

- `TEARDOWN_PENDING` and `TEARDOWN_VERIFIED` are tracked orthogonal to computational success, guaranteeing that a failed job cannot leak billed resources.
- Every submission generates a distinct UUID `attempt_id` with idempotency tokens passed to provider APIs.

---

## 3. Data Plane & Zero-Trust Cloud Sync Staging

Harbinger approved three user-selectable storage modes: (1) Presigned object bucket (S3/GCS/Azure/R2), (2) Native provider volumes, and (3) Existing Cloud Sync remotes (Google Drive/OneDrive/Dropbox).

### 3.1 The Cloud Sync Security Problem
Cloud instances (e.g. RunPod, Hyperstack, Thunder Compute) cannot be trusted with long-lived OAuth refresh tokens or VaultManager secrets. Furthermore, arbitrary cloud containers lack FUSE drivers to mount consumer cloud drives.

### 3.2 The Ephemeral Staging Pipeline
```
[User Cloud Sync Remote] (Drive / Dropbox)
         ▲
         │ (Authenticated local pull via backend/src/web/cloud/sync/)
[Local Cloud Daemon]
         │ (Presigned PUT to ephemeral S3 / GCS / R2 staging object)
         ▼
[Staging Storage] ──(Short-lived GET / PUT)──► [Remote Worker Pod]
```
- For Cloud Sync remotes: The local daemon orchestrates transfer between the remote sync target and an ephemeral staging bucket using presigned URLs with strict time limits ($TTL \le 60\text{ min}$, auto-renewed by daemon while active).
- For Native Provider Volumes: Workers write directly to network volumes (e.g., RunPod Network Volume, Hyperstack Volume). The daemon issues collection commands once jobs enter `COLLECTING`.
- **Egress & Privacy Guard:** Pre-flight inspection calculates total outbound payload size and displays clear warnings before dispatching unencrypted imagery to external clouds.

---

## 4. Telemetry, Real-Time Logs & Progress Streaming

For ComfyUI batch runs and LoRA training jobs that run for hours, users require real-time visibility into iteration steps, loss curves, and diagnostic logs.

### 4.1 Append-Only Event Sink (`events.jsonl`)
- Standardizes remote worker telemetry on the existing local training run layout (`backend/src/core/training_runs.py`).
- Workers emit JSONL telemetry lines to a dedicated `events.jsonl` in the job's staging directory:
  ```json
  {"step": 150, "loss": 0.0842, "lr": 0.0001, "vram_used_mb": 18420, "timestamp": 1729358400.12}
  ```
- **Daemon Ingestion:** The local daemon performs HTTP byte-range requests or S3 `GetObject(Range=...)` polling on `events.jsonl` every 2–5 seconds, streaming incremental parsed events over local IPC to the Qt Manager window.
- **Zero Inbound Ports:** No public ports, ngrok tunnels, or dynamic DNS needed on the user's workstation.

---

## 5. Declarative UI Risk & Greying-Out Engine

Harbinger mandated that job configuration react dynamically: recolouring control backgrounds/text, displaying bright warnings with ⚠ icons, and greying out incompatible options.

### 5.1 Architecture (`backend/src/cloud/risk_evaluator.py`)
To keep the logic testable without Qt, the risk engine is implemented as a pure-Python evaluator:

```python
@dataclass(frozen=True)
class RiskDiagnosis:
    severity: Literal["SAFE", "ADVISORY", "CAUTION", "BLOCKED"]
    rule_id: str
    affected_fields: list[str]
    message: str
    remedy: str | None = None
```

### 5.2 Rule Taxonomy & Styling Matrix

| Level | Condition Trigger | UI Visual Treatment | Action Permitted |
|---|---|---|---|
| **SAFE** | Compatible shape, on-demand instance, cost under warning threshold. | Normal theme styling. | Submit enabled. |
| **ADVISORY** | Estimated cost > $5.00, cold-start duration > 3 min, Cloud Sync staging hop. | Accent highlight border, subtle informational text. | Submit enabled. |
| **CAUTION** | Spot instance selected with non-resumable task, high egress volume (>10GB), cost > 75% of monthly budget. | Amber/Orange background tint (`#3d2800`), bright yellow text, ⚠ warning banner with explicit risk explanation. | Submit enabled with confirmation dialog. |
| **BLOCKED** | Spot chosen for uncheckpointed LoRA, VRAM requirement > GPU memory, missing Vault credentials, monthly budget exceeded. | Greyed-out control (`opacity: 0.4`), disabled state, red error banner (`#4a1010`) explaining remedy. | Submit strictly disabled. |

---

## 6. Provider Classification Matrix (v1 Verification)

Verification based on provider capabilities as of 2026-10-19:

| Provider | Mode Supported | GPU / Hardware Scope | Storage Native | Best Workload Fit |
|---|---|---|---|---|
| **AWS** | Managed Batch (`AWS Batch`) & Instance (`EC2`) | Full CPU & NVIDIA GPU (T4, A10G, L4, A100) | S3 | All workloads; enterprise batch. |
| **GCP** | Managed Batch (`Cloud Run Jobs`, `GCP Batch`) & Instance (`GCE`) | Full CPU & NVIDIA GPU (T4, L4, A100) | GCS | Extraction (Cloud Run) & GPU batch. |
| **Azure** | Managed Batch (`Container Apps Jobs`, `Azure Batch`) & Instance (`Azure VM`) | Full CPU & NVIDIA GPU (T4, A100) | Azure Blob | General enterprise compute. |
| **RunPod** | Instance (`Pods`) & Serverless (`Serverless v2`) | NVIDIA Consumer/Datacenter (RTX 3090, 4090, A4000, A5000, A100) | Network Volumes & S3-compatible | ComfyUI batch generation & LoRA training. |
| **Hyperstack** | Instance (`VM On-Demand / Spot`) | NVIDIA Datacenter (A100, H100, L40) | Attached NVMe / Volumes | High-throughput LoRA/LyCORIS training. |
| **Thunder Compute**| Instance (`Instances`) | NVIDIA Consumer & Datacenter (RTX 4090, A5000, A6000) | Local Scratch | Low-cost ComfyUI & LoRA training. |
| **Cloudflare** | Container MicroVMs (`Cloudflare Containers`) & Storage (`R2`) | CPU only (up to 4 vCPU, 12GB RAM, 20GB disk); no custom CUDA container support. | R2 (0 egress fees) | CPU Extraction & phash/CLIP indexing; R2 staging. |
| **Oracle (OCI)** | Instance (`OCI Compute`) & Container (`Container Instances`) | Ampere A1 (ARM CPU), x86 CPU, NVIDIA A10/A100 | OCI Object Storage | High-efficiency CPU batch & long-running GPU training. |

---

## 7. Workload 4: Vector & Embedding Ingestion Protocol

Embedding/indexing jobs (CLIP vectors and phash computation) produce updates for the local `pgvector` index.

### 7.1 Staging & Atomic Ingestion Pipeline
1. **Output Bundle:** The cloud worker outputs a compressed Parquet/Arrow archive containing `(image_sha256, model_tag, embedding_vector, phash_hex, computed_at)`.
2. **Hash Match Verification:** Before modifying the local database, the local importer queries `images` by `image_sha256`. If the image was deleted, modified, or re-extracted locally during the cloud run, the vector is routed to a Review Queue.
3. **Chunked Transactional Upsert:** Validated vectors are loaded into a temporary staging table (`staging_image_vectors`) and committed via an atomic `INSERT INTO image_vectors ... ON CONFLICT (image_id, model_id) DO UPDATE`.
4. **Zero Remote DB Exposure:** Remote workers never receive direct network access or credentials to the local PostgreSQL database.

---

## 8. Delivery Phasing & Testing Architecture

Following the sequenced roadmap approved by Harbinger (Extraction → ComfyUI → Embedding/Indexing → LoRA/LyCORIS):

- **Phase 1: Foundation & Extraction Migration**
  - Migrate `backend/src/web/cloud/compute/` into `backend/src/cloud/`, preserving shims.
  - Implement PostgreSQL schema, daemon process shell, and provider capability registry.
  - Implement Cloudflare R2 / S3 / GCS presigned storage adapters.
- **Phase 2: ComfyUI Batch Generation & Cloud Jobs Manager Window**
  - Launch standalone Cloud Jobs Manager window with live badge.
  - Implement RunPod & Thunder Compute instance adapters.
  - Wire UI Risk Engine & dynamic control styling.
- **Phase 3: Embedding/Indexing & Vector Ingestion**
  - Implement batch CLIP/phash worker container.
  - Wire atomic Parquet vector ingestion into `pgvector`.
- **Phase 4: LoRA / LyCORIS Training & Full Teardown Telemetry**
  - Containerize training worker with checkpoint upload and restart recovery.
  - Wire live `events.jsonl` telemetry into Manager UI loss chart.

### Testing Governance
In strict accordance with the repository resource rule:
- Full test suites and benchmark runs are deferred to Codex with Harbinger authorization.
- Fast, local unit checks (`pytest backend/test/cloud/ -k "unit"`, `ruff check`, `py_compile`) test adapter serialization, state machines, and risk rules using mock HTTP adapters and synthetic pricing fixtures.

---

## 9. Questions and Recorded Answers

Harbinger answered all five questions on 2026-10-19. The recorded answers below govern the design:

### [Gemini Q1] Cloud Sync Remote (Drive/Dropbox/OneDrive) Staging Protocol
- **Harbinger answer (2026-10-19; recorded by Gemini):** **Option A.** Local daemon ephemeral staging: the local daemon downloads needed inputs from the Cloud Sync remote (or reads local sync mirror), stages them to an ephemeral presigned bucket/storage endpoint, and uploads final outputs back to the remote upon collection. Remote workers only touch short-lived presigned URLs and never hold Cloud Sync credentials.
- **Option A (Recommended): Local Daemon Ephemeral Staging.** The local daemon downloads needed inputs from the Cloud Sync remote (or reads local sync mirror), stages them to an ephemeral presigned bucket/storage endpoint, and uploads final outputs back to the remote upon collection. Remote workers only touch short-lived presigned URLs and never hold Cloud Sync credentials.
- **Option B: Direct In-Worker Cloud Sync with Ephemeral OAuth Tokens.** The daemon issues short-lived, downscoped access tokens to the worker container, which runs headless rclone/SDK to fetch directly from Google Drive/OneDrive.
- **Option C: Restrict Cloud Sync Remotes to Staging Targets Only.** Cloud Sync remotes can be selected as final archival destinations, but the intermediate job execution must use native provider storage or S3/GCS.

### [Gemini Q2] Telemetry & Live Training Logs Protocol
- **Harbinger answer (2026-10-19; recorded by Gemini):** **Option A.** Presigned append-only event sink (`events.jsonl` matching `training_runs.py` format) with daemon byte-range polling every 2–5 seconds, streaming over local IPC to GUI. Zero inbound open ports.
- **Option A (Recommended): Presigned Append-Only Event Sink (`events.jsonl`) with Daemon Polling.** The remote worker appends telemetry lines to an `events.jsonl` on staging storage (matching `training_runs.py` format). The local daemon polls byte ranges every 2–5 seconds and relays updates over local IPC to the GUI.
- **Option B: Outbound Serverless WebSocket Relay.** A lightweight serverless relay (e.g. Cloudflare Worker) bridges events pushed by the worker to a persistent outbound WebSocket held by the local daemon.
- **Option C: Terminal Batch Retrieval Only.** No live metric streaming during execution; console logs and checkpoint reports are downloaded as a batch artifact only upon job completion or termination.

### [Gemini Q3] Cloudflare Provider Workload Scope in v1
- **Harbinger answer (2026-10-19; recorded by Gemini):** **Option B.** Full compute + Workers AI proxying: use Cloudflare Containers for eligible CPU tasks and map compatible prompt-based inference to Cloudflare Workers AI fixed endpoints, while using R2 for zero-egress staging.
- **Option A (Recommended): R2 Zero-Egress Staging + Cloudflare Containers for CPU Tasks Only.** Utilize R2 as an inexpensive staging tier across all clouds, and Cloudflare Containers for CPU extraction and phash/CLIP indexing. Exclude custom GPU training and arbitrary ComfyUI graphs on Cloudflare in v1.
- **Option B: Full Compute + Workers AI Proxying.** Use Containers for CPU workloads and map compatible prompt inference requests to Cloudflare Workers AI fixed endpoints.
- **Option C: Edge Storage & Webhook Tier Only.** Restrict Cloudflare strictly to R2 storage and edge coordination; run all compute on the other 7 providers.

### [Gemini Q4] Database Resiliency & Headless Daemon Operations
- **Harbinger answer (2026-10-19; recorded by Gemini):** **Option A.** PostgreSQL system of record with daemon in-memory/WAL fallback for teardown obligations and reconciliation during transient DB disconnects or shutdown.
- **Option A (Recommended): PostgreSQL System of Record with Daemon In-Memory/WAL Fallback.** PostgreSQL stores all persistent job history, attempts, and budget ledgers. The local daemon keeps an append-only JSONL Write-Ahead Log of teardown obligations so that if PostgreSQL is temporarily unreachable during desktop shutdown, teardown enforcement continues unimpeded and syncs back on recovery.
- **Option B: Strict PostgreSQL Dependency.** The daemon operates strictly via active PostgreSQL connections. If PostgreSQL is offline, the daemon halts and relies entirely on cloud-side dead-man timers for instance termination.
- **Option C: Separate Daemon State File.** Maintain active orchestration state exclusively in a daemon JSON state file (`.cloud_daemon_state.json`, similar to `slideshow_daemon.py`), writing to PostgreSQL only upon job completion.

### [Gemini Q5] Workload 4 (CLIP/phash) Vector Indexing Safety Gate
- **Harbinger answer (2026-10-19; recorded by Gemini):** **Option A with optional C as an on/off setting.** Validated results stage through a hash verification table into an atomic transactional upsert by default; a Settings toggle allows requiring manual user review before importing.
- **Option A (Recommended): Staging Table + Content Hash Verification + Atomic Chunked Upsert.** Worker outputs a Parquet vector archive. The local importer verifies image SHA-256 and modification timestamps against the local database, stages validated rows into a temporary table, and executes an atomic transaction with conflict resolution. Mismatches route to a Review list.
- **Option B: Direct Bulk Upsert.** Ingest vectors directly via PostgreSQL `COPY` or bulk `INSERT ... ON CONFLICT DO UPDATE`, trusting the cloud batch output manifest without pre-flight hash re-verification.
- **Option C: Mandatory Manual Import Review.** Ingested vector batches are never auto-committed; they must be visually inspected and manually approved by the user in the Manager UI.
