# Cloud Jobs Service — Mistral proposal

— Mistral, 2026-10-19. Proposal only. Builds on Harbinger's recorded
answers: Claude Q1–Q10, Codex Q1–Q7, Gemini Q1–Q5, OpenCode Q1–Q8,
Grok Q1–Q8, Cursor Q1–Q8.

## 0. Consensus I build on, not re-argue

- Asynchronous job state machine replacing the blocking `run(job)`.
- PostgreSQL as system of record (AGENTS.md's "No SQLite" rule rules out
  Claude's SQLite store); daemon WAL fallback per Gemini Q4.
- Local daemon + cloud-side watchdog + verified provider deadlines
  (Codex Q1); one daemon per OS user (Grok).
- Presigned-URL staging; workers never hold VaultManager or database
  credentials; job-scoped credential lease (Cursor Q3).
- BYO accounts in VaultManager; digest-pinned worker images in a
  user-owned registry (OpenCode Q4, Cursor Q4).
- Risk-reactive job form: recolour, ⚠ banner, grey-out (Claude Q8).
- GCP + RunPod first (OpenCode Q1); extraction → ComfyUI → indexing →
  training sequencing (Codex Q7).

My additions below: the concrete reconciler semantics, the risk rule
format Claude Q8 asked for, egress-aware placement suggestions, a
zero-spend test harness, two sourced provider classifications, and
daemon UX. Questions for Harbinger in §7.

## 1. Concrete state machine and reconciler duties

Claude proposed the state machine; this is the concrete transition set
the reconciler and UI would share:

```
queued → submitting → provisioning → running → collecting → settling
       → terminal: completed | failed | cancelled | capped
```

- `submitting` persists intent and an idempotency key **before** the
  first provider call. Ambiguous submits (timeout, lost response) are
  resolved by listing provider resources tagged with the job id before
  any retry — never by blind resubmit (Codex).
- `collecting` and `settling` are separate: computation can succeed
  while collection and cleanup still run. A job is not `completed`
  until the resource ledger is empty or every remaining resource is on
  the explicit retention list (Codex's settled-not-billed state).
- The reconciler is a pure function
  `(stored job state, provider observation, settings) → action list`,
  run at daemon start and every poll cycle. Every transition appends an
  event row; the UI only ever reads events, never polls providers.
- Crash recovery = replay: after a daemon restart, the reconciler
  derives current truth from provider observation, not from hoping the
  last local write landed.

Risk: none unique. Cost: one `job_events` table and disciplined
single-writer access through the leader lease (Cursor Q6).

## 2. Risk rules as versioned data (the rule set Claude Q8 asked for)

One shipped artifact per app release — a `risk_rules.yaml` next to
Codex's versioned capability catalogue — evaluated by a pure-Python
engine with no Qt import, so it is testable in plain pytest.

Rule schema:

```yaml
- id: spot-without-resume
  when: job.spot == true and not capability(job.kind).resume_from_checkpoint
  severity: block            # block | warn | info
  targets: [form.spot]
  message: "Spot needs a checkpointable workload"
  remedy: "Pick on-demand or a workload that can resume"
```

- `block` → the UI greys out the control and the backend refuses the
  submit; `warn` → recolour + ⚠ banner; `info` → inline note. The UI
  binds `targets` generically, so adding a rule needs no Qt change.
- Thresholds (spend, egress, runtime) are **not** in the rules file;
  they come from Settings, shared with the Q7 cost safeguards. Users
  tune numbers; the repo ships logic.
- The backend re-evaluates the same rules at submit time — the UI hint
  can be stale, the submit check cannot.
- Seed rules: spot without verified resume; storage method the
  provider/mode can't use (Claude Q8's example); unknown or stale price;
  estimated egress over threshold; Cloud Run GPU when the estimate
  exceeds the verified 1 h timeout (Cursor Q8); deadline unreachable;
  GPU class over the cloud-class `block` list (Grok Q3); cache sharing
  off making a job re-download huge weights; sensitive data class vs
  provider allowlist (OpenCode Q7).

## 3. Placement suggestion card

Harbinger chose "user picks, service suggests cheapest with capacity"
(Claude Q6) and total-job-cost ranking (Codex Q2). Concrete UI shape:

- A suggestion card above the provider picker: ranked candidates with
  a cost breakdown table (provisioning, compute, staging, **egress,
  retained storage, expected retries**), a price-age timestamp, and a
  confidence band — not a bare dollar figure.
- Egress is in the ranking, not a footnote: cross-region cheap compute
  regularly loses to egress on the staging-heavy workloads
  (extraction, embedding backfill).
- One-click "apply suggestion" fills the form; the user stays free to
  pick anything valid (grey-out rules still apply).
- Capacity is observed at suggestion time and re-checked at submit;
  out-of-stock candidates fall to B (fail immediately, Grok Q2) with
  the next-ranked suggestion shown in the error.

## 4. Zero-spend test harness

Extends OpenCode's crash-point matrix with the concrete fixtures:

- **FakeProvider** adapters implementing the adapter contract
  in-process, scripted with fault timelines: spot kills mid-epoch,
  provider 5xx storms, submit timeouts, orphaned volumes, deadline
  races. Injected clock; tests run in milliseconds.
- **Recorded HTTP fixtures** per real provider (request/response pairs
  captured once) so adapter serialization and pagination don't drift.
- **Reconciler replay tests**: `(state, observation)` pairs as plain
  data files, asserting the action list — the reconciler's purity makes
  this a table test.
- The deterministic suite runs under normal pytest. Live smoke tests
  are a separate opt-in marker, gated per question Q1 below.

## 5. Provider classification notes (checked 2026-10-19)

- **AWS** fits both backend families: AWS Batch supports GPU jobs on EC2
  GPU instance types, including multi-node parallel jobs for
  distributed GPU training ([AWS Batch GPU
  jobs](https://docs.aws.amazon.com/batch/latest/userguide/gpu-jobs.html)).
  So the AWS managed-batch path is not CPU-only, unlike Azure's.
- **Azure**: Container Instances offers GPU SKUs with pre-provisioned
  CUDA drivers, but default GPU quotas start at 0 and require support
  requests per region ([ACI GPU
  deploy](https://learn.microsoft.com/en-us/azure/container-instances/container-instances-gpu-deploy)).
  With Cursor's finding that Container Apps Jobs is documented
  CPU-oriented, Azure in v1 should be: CPU via managed batch, GPU via
  the instance family (VM), and GPU managed-batch greyed out until the
  account's ACI quota is verified.

## 6. Daemon UX

- A daemon status row in the Cloud Jobs header: running indicator,
  lease owner (for Cursor's leader/observer machines), WAL depth, last
  poll time. A broken daemon is the one failure the window must
  surface loudly — everything else is per-job.
- Job detail: attempt timeline rendered from the event log, live log
  tail (Gemini Q2's `events.jsonl` relay), spend-so-far vs reserved.
- Unattended outcomes (finished/failed/capped) need a notification
  path — question Q2.

## 7. Questions for Harbinger

Each with options; recommendation first.

**Harbinger answered all seven on 2026-10-19:** Q1 (a) benchmark
chain; Q2 (c) desktop notifications plus a configurable webhook/email
sink; Q3 (a) default region per provider; Q4 (a) Linux first; Q5 (c)
rules editable through a Settings UI, stored in PostgreSQL (differs
from my read-only recommendation — shipped YAML stays the seed
source); Q6 (b) rows prune after N days with export-before-delete; Q7
(a) migrate UsageStore into the PostgreSQL spend ledger with a source
filter. Full option text in the shared report §5.

### Q1 — Who may run live smoke tests, and under what gate?

Real-provider smoke tests spend real money. AGENTS.md's RESOURCE RULE
gates benchmarks and full suites through Codex + your authorization;
live cloud runs are the same class of hazard.

- **(a) Recommended: same chain as benchmarks.** Live smoke tests are
  opt-in (`pytest -m live_cloud`), requested on the bus to Codex, who
  relays to you and waits for go-ahead; one live run at a time.
- **(b) A dedicated sandbox account with a hard per-run spend cap**
  (e.g. $2); any agent may run them without the chain.
- **(c) Agents never run live.** You run them by hand and hand back
  the output; agents work only against FakeProvider and recorded HTTP.

### Q2 — How does the user learn a job finished while the app was closed?

- **(a) Recommended: desktop notifications from the daemon** (Linux
  session bus, best-effort equivalents elsewhere) for completion,
  failure and cap hits, configurable in Settings.
- **(b) Badge only**: no notifications; the header badge and Cloud
  Jobs window show the outcome on next open.
- **(c) A configurable webhook/email sink** in addition to (a), for
  when the desktop is off entirely.

### Q3 — What is the default region policy?

The placement ranking needs to know when crossing regions is allowed.

- **(a) Recommended: a default region per provider in Settings.**
  Suggestions rank same-region candidates first and warn when a
  cheaper cross-region placement would move the job's data.
- **(b) Cheapest region always**, regardless of data movement; egress
  cost is shown but doesn't gate.
- **(c) A per-data-class region allowlist** (extends OpenCode Q7):
  sensitive classes pin regions; everything else goes cheapest.

### Q4 — Which platforms does the v1 daemon support?

The slideshow-daemon precedent is Linux-first (`desktop/linux/`).

- **(a) Recommended: Linux first.** macOS/Windows later; meanwhile
  those platforms still get teardown protection from the watchdog and
  provider-native deadlines, but no local collection.
- **(b) All three in v1**, with the full cross-platform lock/IPC/IPC
  matrix OpenCode sketched.
- **(c) No separate daemon binary in v1**: jobs live in the app
  process, relying purely on watchdog + deadlines when the app closes.

### Q5 — May users edit the risk rules themselves?

- **(a) Recommended: shipped rules, read-only.** Users tune
  thresholds in Settings; rules ship with the app and change only via
  releases.
- **(b) A user overrides file** layered over the shipped rules for
  power users, with a UI warning that custom rules can bypass
  safeguards.
- **(c) Rules editable through a Settings UI**, stored in PostgreSQL.

### Q6 — How long does local job history persist?

Remote-data retention is answered (Codex Q4); the local rows are not.

- **(a) Recommended: rows persist indefinitely; artifacts (logs,
  manifests) prune on a Settings TTL.** Cheap rows, expensive blobs.
- **(b) Rows prune after N days** with an export-before-delete option.
- **(c) Archive to JSONL then delete** from PostgreSQL on the same TTL
  as (b).

### Q7 — What happens to the PoC UsageStore JSONL and the Dashboards charts?

- **(a) Recommended: migrate into the PostgreSQL spend ledger** as
  historical rows; the Cloud Compute Dashboards charts render from the
  new ledger with a source filter (PoC vs Cloud Jobs).
- **(b) Keep UsageStore JSONL for the PoC-era rows** and show only new
  cloud-jobs spend in Cloud Jobs; two sources forever.
- **(c) Retire Dashboards charts entirely**; Cloud Jobs owns all spend
  visualization.
