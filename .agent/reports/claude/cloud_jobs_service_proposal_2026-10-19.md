# Cloud Jobs Service: Claude's proposal (2026-10-19)

Brief: `.agent/reports/team/cloud_jobs_service_2026-10-19.md`. This is a
proposal only.

## Summary

Today's §4.21 code was built for one synchronous, CPU-only Cloud Run call.
Its `run(job)` blocks until done, which is fine for a 2-minute FFmpeg job.
It cannot handle a GPU pod that takes 4 minutes to come up, runs for 3
hours, bills by the second, and must be torn down even if the app crashes.

The core of this proposal is therefore:

- an **asynchronous job lifecycle** whose state survives restarts;
- a **reconciler** that compares that state with what actually exists at
  each provider;
- **leak protection** as a feature from day one, not something added
  later.

Provider adapters and the manager UI sit on top of that core.

## Ideas

### 1. Provider-neutral job spec plus two backend families

- **`JobSpec`** (Qt-free, frozen dataclass). It holds:
  - `kind` (extract, comfy_batch, lora_train, embed, upscale, ...);
  - `resources` (vCPU, RAM, GPU class, VRAM floor, disk);
  - `inputs` and `outputs`, as content-addressed blobs;
  - `image` (the worker image tag);
  - `limits`: max runtime, max spend, and a spot-allowed flag;
  - `params`, typed per kind.

  It replaces today's extraction-only `CloudJob`. That class becomes one
  `kind`.
- **`InstanceBackend`**: provision, then bootstrap, then run the
  container, then collect, then tear down.
  - Fits Hyperstack, Thunder Compute, RunPod Pods, and plain
    EC2/GCE/Azure VMs.
  - Pro: cheapest per hour, and gives full control over the machine.
  - Con: we own provisioning, bootstrapping and teardown, which is where
    billing leaks come from.
- **`ManagedBatchBackend`**: submit a container job and let the provider
  schedule it.
  - Fits AWS Batch, GCP Batch or Cloud Run Jobs, Azure Container Apps
    Jobs, and RunPod Serverless.
  - Pro: the provider handles teardown, so leaks are much less likely.
  - Con: more setup per account (IAM, queues, registries), cold starts,
    and GPU availability that varies by region.
- **Recommendation:**
  - **CPU clouds:** start with managed batch.
  - **GPU clouds:** start with the instance backend. Hyperstack and
    Thunder are instance-shaped products; RunPod offers both.
  - The shared interface is a set of methods that never block:
    `submit / poll / cancel / logs / list_owned_resources / teardown`.

### 2. Job store and state machine that survive restarts

- **Storage:** a SQLite file at `~/.image-toolkit/cloud/jobs.db`, with a
  `jobs` table and an append-only `job_events` table (event-sourced).
  - Postgres is not used: the app must work without the database stack,
    and the frozen build can't see `env/vars.env`.
  - The existing `UsageStore` JSONL becomes a view over the store, or
    something the store writes into.
- **States:** `DRAFT → STAGING → SUBMITTED → PROVISIONING → RUNNING →
  COLLECTING → SUCCEEDED | FAILED | CANCELLED`. `TEARDOWN` is tracked
  separately as a must-complete obligation, because a job can be
  `FAILED` while its instance is still billing.
- **Reconciler loop:**
  - It runs in the app. Optionally it also runs in a small local daemon,
    following the wallpaper slideshow daemon pattern, so jobs are still
    watched while the app is closed.
  - Each tick, it polls the providers for every job that hasn't finished
    and moves states forward. It is idempotent, so a crash at any point is
    recoverable on the next start.

### 3. Leak protection (the main risk with GPU instances)

1. **Tag everything.** Every resource gets `it-job-id`, `it-owner` and
   `it-expires-at`, where the provider supports labels. Where it doesn't,
   the resource name carries a prefix.
2. **Orphan sweep** at startup and on demand. List every tagged resource
   at every configured provider and compare against the store. Anything
   unknown or expired is shown in the manager UI's Resources view, with a
   Terminate button. It is never killed silently.
3. **Dead-man's switch inside the instance.** The worker bootstrap
   schedules its own shutdown at `max_runtime`, and extends it only while
   it gets heartbeats or makes progress. This covers the case where the
   laptop is closed for a weekend.
4. **Budget guard.** Pre-flight cost estimate = price catalogue × resources
   × expected runtime.
   - It shows before Submit, along with egress.
   - There are per-job and monthly caps; going over is a hard stop, not a
     warning.

### 4. Data plane: presigned URLs, content-addressed staging

- **Staging bucket:** one per configuration, on S3, GCS or Azure Blob.
  - The GPU providers have no general-purpose object store we can rely on.
    RunPod's network volumes are region-bound. So GPU jobs stage through
    the user's chosen CPU-cloud bucket. This needs verifying per provider.
- **Credentials:** the app gives the worker **presigned GET and PUT URLs**,
  so instances never hold long-lived cloud credentials. This matters most
  on third-party GPU hosts.
- **No repeat uploads:** inputs are keyed by sha256, so a 6 GB base model
  or a dataset is uploaded once and reused.
- **Model and weight cache:** a persistent volume where the provider
  supports one (RunPod network volume, Hyperstack persistent volume).
  Otherwise, keep a pre-baked image variant.
- **Privacy:** the existing §4.20/§4.21 rule applies. Warn before anything
  leaves the machine.

### 5. One worker image, versioned with the app

- **Image:** `it-worker:<app-version>-<cpu|cuda>` on GHCR, with one
  entrypoint per job `kind`.
  - It reuses the real backend code (extraction, ComfyUI headless, the
    LoRA tuner, CLIP embedding) rather than reimplementing it in the way
    `infra/cloud/gcd/worker` does.
- **Progress protocol:** the worker writes `events.jsonl` in the same
  format as `training_runs.py` and uploads it every N seconds through its
  PUT URL.
  - The Deep Learning Runs view can show cloud training runs alongside
    local ones, with no new chart code.

### 6. Job catalogue: first candidates (Harbinger picks, see Q1)

| Kind | Where | Why it's a good early candidate |
|---|---|---|
| extraction (exists) | CPU | Port of the PoC; proves the new lifecycle with no GPU spend |
| ComfyUI batch generation | GPU | The highest-value offload; workflow JSON already exists |
| LoRA / LyCORIS training | GPU | Long-running; tests spot instances, checkpoints and resume |
| CLIP embedding backfill | GPU or CPU | Embarrassingly parallel, cheap, and fills pgvector |
| phash/dedup index of a large library | CPU | Fans out across many cheap CPU workers |

### 7. Hooks into the local GPU arbiter

- When `gpu_lease_arbiter` refuses a job because the estimated VRAM is
  more than the device has, offer **"Run in cloud instead"**, prefilled
  with the job's spec and a cost estimate.
- This is the most natural way into the feature, because it appears right
  where local runs fail. The OOMs in #483 and #485 were the original
  motivation for §4.21.

### 8. Manager UI: a "Cloud Jobs" window

- **Placement:** a standalone window, registered with `register_window` and
  opened from the header. It should also be reachable from Cloud Compute
  and from a tray or status-bar badge showing running jobs and spend
  today.
  - The Cloud Compute window stays the *setup* surface: providers,
    credentials, request builder, dashboards.
  - Monitoring is continuous, so it needs its own window.
- **Jobs view:**
  - A virtualised table: status, kind, provider, GPU, elapsed time, cost
    so far, and progress.
  - Filters by state, provider and kind.
- **Detail view:**
  - A state timeline from `job_events`, and a live log tail.
  - Metrics: GPU utilisation and VRAM, when the worker reports them.
  - A spend ticker, and an output list with "Open in gallery".
- **Actions:**
  - Cancel; retry; clone and edit; download outputs again.
  - Extend max runtime, for a running job.
  - Copy an SSH or console link, for instance backends.
- **Resources view:** the live, tagged resources at every provider
  (instances, volumes, buckets), with any orphans flagged and a Terminate
  button.
- **Spend view:**
  - Month to date against budget, broken down by provider.
  - The existing Dashboards charts move here, or stay in Cloud Compute and
    are linked from here.
- **Notifications:**
  - Desktop notifications for job finished, job failed, budget reaching
    80%, and orphan found.

### 9. Migrating the existing code

- Move `backend/src/web/cloud/compute/` into `backend/src/cloud/`,
  following the pattern from earlier refactors: leave re-export shims at
  the old path for one release.
- `GCDCloudRunAdapter` becomes the first `ManagedBatchBackend`. It's a
  synchronous HTTP call wrapped as submit, then complete.
- The Cloudflare and Oracle stubs are dropped from scope unless Harbinger
  wants them kept.

### 10. Testing

- **Fake backends:** a `FakeInstanceBackend` and a `FakeBatchBackend` with
  scripted lifecycles. These cover the reconciler, leak sweep, and budget
  guard tests with no network.
- **Adapter tests** use recorded HTTP fixtures.
- **Live smoke tests** (`--run-cloud`): opt-in, with real spend, so they
  need Harbinger's authorisation the same way benchmarks do. Each one
  should be "smallest instance, 60-second job, verify teardown".

## Risks

1. **Billing leaks.** The biggest risk; §3 is the mitigation.
2. **Provider API churn.** Hyperstack and Thunder Compute are young APIs.
   Keep their adapters thin, pin versions, and use recorded fixtures.
3. **GPU availability.** On-demand capacity for popular GPUs is often
   exhausted.
   - Mitigation: let the user rank fallback GPU classes and providers.
   - Show "no capacity" as its own state, not an error.
4. **Cold start and image size.** A CUDA image with ComfyUI is many GB.
   - Pull time costs money on instance backends.
   - Mitigation: cache on persistent volumes, and keep the CPU and GPU
     images separate.
5. **Credential exposure.** It increases with each provider added.
   - Use least-privilege IAM templates in `infra/cloud/<provider>/`.
   - Keep secrets only in VaultManager.
   - Give workers presigned URLs only.
6. **Scope.** Six providers × several job kinds is a lot.
   - Ship one CPU provider and one GPU provider end to end first.
   - Then add the others behind the same interface.

## Q. Questions for Harbinger

Recommended option first.

1. **Which workloads go first?**
   - (a) **ComfyUI batch generation and LoRA training on GPU**, plus the
     extraction port on CPU.
   - (b) Extraction and indexing only, i.e. CPU first, with GPU later.
   - (c) Everything in the catalogue at the same time.
2. **Execution model.**
   - (a) **Managed batch on the CPU clouds, instance backends on the GPU
     clouds.**
   - (b) Instances everywhere, which is simpler with one code path but
     makes leaks more likely.
   - (c) Managed or serverless everywhere. This rules out Hyperstack and
     Thunder, which are instance-shaped.
3. **Job lifetime when the app closes.**
   - (a) **Jobs keep running in the cloud, and a local daemon watches them
     and does teardown.**
   - (b) Jobs keep running, and the app reconciles them on its next start
     (only the in-instance dead-man's switch protects in between).
   - (c) Closing the app cancels running jobs.
4. **Where the manager UI lives.**
   - (a) **A standalone "Cloud Jobs" window** opened from the header, with
     a running-jobs badge.
   - (b) A new "Jobs" pane inside the existing Cloud Compute window.
   - (c) A main-window tab.
5. **Data staging.**
   - (a) **One user-chosen bucket (S3, GCS or Azure Blob), with presigned
     URLs.**
   - (b) Each provider's native storage. GPU clouds don't have
     general-purpose storage, so this would need volumes there.
   - (c) Reuse the existing rclone or sync remotes (Google Drive and
     similar). This is slow for large models.
6. **Provider choice.**
   - (a) **The user picks the provider, and the service suggests the
     cheapest one with capacity.**
   - (b) Fully automatic placement by price and availability.
   - (c) Manual choice only.
7. **Default budget safety.**
   - (a) **A required per-job max runtime and max spend, plus a monthly
     cap, all with defaults the user can edit.**
   - (b) Warnings only, no hard stops.
   - (c) No guardrails beyond the estimate.
8. **Spot or preemptible instances.**
   - (a) **Allowed per job for kinds that can resume from a checkpoint
     (training), and off by default.**
   - (b) Never allowed.
   - (c) On by default.
9. **Existing `web/cloud/compute` code.**
   - (a) **Migrate it into `backend/src/cloud/` with shims.**
   - (b) Start fresh and delete the PoC.
   - (c) Leave it alone and build alongside it.
10. **Do the Cloudflare and Oracle stubs stay in scope?**
    - (a) **Drop them; they aren't in your provider list.**
    - (b) Keep them as backlog items.

— Claude, 2026-10-19
