# Tauri Migration + Architecture Refactor — Kimi proposal

— Kimi, 2026-10-19. Proposal only; nothing here is approved for
implementation. Builds on every recorded answer: Claude Q0a–Q0d, Codex
R1–R7, OpenCode Q1–Q8, Grok T1–T8, Cursor W1–W8. SQLCipher
(`library.db` via `base.database`, Cloud Jobs' own `cloud_jobs.db`) —
no PostgreSQL anywhere in this proposal.

The consensus covers the bridge shape, services home, migration unit,
parity method, freeze, Wave 0 platform, and chrome. My additions live
in the seams nobody has drawn yet: the contract IDL (§1), coexistence
rules for the shared encrypted store (§2), event catch-up for late
joiners (§3), cancel/error envelopes across the bridge (§4), two more
Wave 0 spikes (§5), observability for the multi-process app (§6), and
protocol unification with the Cloud Jobs daemon (§7). Questions in §8.

## 1. Contract IDL: name the source of truth for generated types

Codex R1 fixed the transports (supervised stdio sidecar, Django adapter
for remote, Rust for native); nobody has named the IDL the generated
TypeScript/Rust/Python types come from (Claude's "one typed contract",
Cursor's "generated EventHub", OpenCode's "contract hash" all assume
it).

- Canonical **JSON Schema documents, one per capability**, in
  `contracts/<capability>.schema.json`. Envelope schemas live once:
  request/response/error/event.
- CI codegen: TypeScript types (for the webview and EventHub facts),
  Python validation (sidecar boundary checks), Rust types (native
  commands). No hand-written mirror types; the contract hash OpenCode
  Q7 checks lives in the same CI job.
- Versioned per contract; compatibility range per Codex R6 (tested
  pairs for desktop, negotiated range for remote).
- Risk: JSON Schema can't express method routing — keep a thin
  `contracts/methods.toml` (method → schema refs) as the routing table
  OpenCode's `HostClient` already needs. Retiring a Rust duplicate
  becomes: implement behind the method table, flip the route, delete.

## 2. Coexistence rules for the one encrypted store

Both apps ship for months and both open `~/.image-toolkit/library.db`
(SQLCipher via `base.database`). Two GUI processes writing one SQLite
file is the biggest unmentioned operational hazard in the plan: even in
WAL mode writers serialize, and a long GUI transaction in one app
surfaces as `database is locked` in the other — or worse, a schema
migration mid-session in the app the user *isn't* looking at.

- **Single-instance gate keyed to the data directory.** Second launch
  focuses the running instance (tray show/hide, Cursor W3) and exits.
  No plugin exists in `frontend/src-tauri/` today; Qt side needs the
  same lock, so the lock file lives in the data dir, not in either GUI.
- **Expand/contract schema discipline.** While a Qt row lives, its
  migrations are additive-only (new tables/columns, no renames or
  drops the old build reads). Contract = the PySide6 tests (OpenCode
  Q5) plus a CI check that migration SQL against a row's schema is
  additive. Deletion of a row unlocks its pending destructive
  migration.
- Settings coexistence stays as Codex R3 answered; this rule is about
  the library store only.

## 3. Event catch-up for late joiners

Cursor W1 gives Gate D a pop-out webview; Cursor W2 makes the EventHub
generated with the sidecar as emitter. A pop-out that opens mid-job,
or a main window reopened after close-to-tray, has missed events.

- Per-channel **snapshot + bounded tail**: every emitter keeps current
  state plus the last N events (sequence-numbered). A new subscriber
  gets snapshot+tail; a sequence gap triggers a resnapshot, never a
  replay-from-zero.
- Durable jobs (Codex R2, Cloud Jobs) replay from their persisted
  `job_events` / `events.jsonl` — the Cloud Jobs pattern becomes the
  EventHub's persistence story instead of a second mechanism.
- Fire-and-forget ephemeral events (hover, progress ticks below a
  threshold) are marked non-durable in the contract and dropped from
  the tail.

## 4. Cancel and error envelopes across the bridge

§6.1 of the brief lists cancellation and error mapping as open; the
answers fixed who runs jobs, not the envelopes.

- **Cancel**: one method `job.cancel(job_id)`, idempotent, wired
  webview → sidecar → service → C++ worker as a cooperative token with
  a hard-escalation timeout. Contract states `cancelling → cancelled`
  mirror Cloud Jobs' Cancel/Force-stop pair (Cursor Q7 in the cloud
  round), so the two UIs and the remote client present one semantics.
- **Error envelope**: `{code, retryable, message_key, details}` with a
  registered code table mapping onto `backend/src/errors/`
  (`ImageToolkitError` hierarchy). The webview never sees tracebacks
  or raw provider strings — same redaction rule the cloud jobs logs
  use. `message_key` (not free text) keeps both shells' wording
  identical and lets docs link error codes to remedies.

## 5. Two more Wave 0 spikes: file drag-and-drop, video playback

Grok T7 put canvas on the Wave 0 spike list; Codex R7 moved hard-
feature feasibility early. Two more hard parts from brief §6.4 deserve
the same cheap fake-document treatment before their waves commit:

- **File drag-and-drop**: OS file drops into the webview, internal
  drags between panels (e.g., images into the stitch canvas), and the
  asset-scope interaction (Grok T2: originals are not in scope — so
  drops must hand paths, never file:// URLs, into the app).
- **Video playback**: what the webview plays natively vs. what stays
  on the C++ frame-extraction path (which already exists in both
  `video_commands.rs` and the Python backend — one more Rust duplicate
  to retire per §1's routing table).

A failed spike follows the same go/no-go path as the canvas one (Q8).

## 6. Observability spine for the multi-process app

After this refactor the desktop is a supervisor + sidecar + slideshow
daemon + cloud-jobs daemon (Grok T5) — four processes, one user bug
report. Proposal:

- One log root, structured JSONL lines with `process`, `ts`, `level`,
  `job_id?`, `message_key`; the Qt logging config is the seed.
- A **Diagnostics bundle** action in Settings: zips the last N days of
  logs with secrets redacted (the cloud flight-recorder rule again).
  This is the migration-era support tool and outlives it.

## 7. One protocol for sidecar and Cloud Jobs daemon

The Cloud Jobs daemon already has IPC and an event stream; Gate D is
Tauri-only (Claude Q0d) and G1 needs a phone/web client. If the daemon
speaks the same envelope as the sidecar (methods + event channels from
§1/§3), then the remote client is the Django adapter Codex R1 chose
anyway, exposed — a transport swap, not a second protocol, and Gate D
becomes the first real consumer of the canonical contract. Daemon
methods get their own `cloud_jobs` namespace in the same method table.

## 8. Questions for Harbinger

Recommendation first in each list. None re-ask a recorded answer.

### Q1 — Which IDL generates the contract types?

- **(a) Recommended: JSON Schema per capability** in `contracts/`, with
  a thin method-routing table; CI generates TS/Python/Rust types and
  the contract hash. Fits stdio and Django alike, no new runtime deps.
- **(b):** OpenAPI 3.1 for everything, stdio methods as operations.
  One spec, but OpenAPI's HTTP framing fights JSON-RPC ergonomics.
- **(c):** Hand-written TypeScript + zod as the source, generate the
  rest. TS-idiomatic, but the sidecar (the runtime of record) consumes
  generated Python from hand-written TS.
- **(d):** protobuf/buf. Strongest codegen, heaviest toolchain, and
  event streams need a second story.

### Q2 — May both GUIs run at once against one library.db?

- **(a) Recommended: no.** Single-instance gate on the data directory;
  second launch focuses the running app (tray show/hide). Both apps
  get the same lock; WAL stays on for readers *within* one process.
- **(b):** Yes — WAL + busy_timeout; accept `database is locked`
  stalls in the other app during long writes.
- **(c):** Yes, with the second app opening the store read-only.
  Safe for the library, but the second app is a zombie (no edits,
  settings per Codex R3 still need a writer).

### Q3 — How do late-joining views catch up on events?

- **(a) Recommended: snapshot + bounded tail per channel**, sequence-
  numbered, gaps trigger resnapshot; durable jobs replay from
  persisted `job_events`/`events.jsonl`.
- **(b):** Full persisted event log replay for every channel. Simplest
  mental model, storage and ordering cost forever.
- **(c):** No replay. Late joiners poll current state; events are
  fire-and-forget. Cheapest; pop-outs and reopened windows show stale
  progress until the next state change.

### Q4 — Which hard parts get Wave 0 spikes?

- **(a) Recommended: the four already listed, plus file drag-and-drop
  and video playback** (fake-document spikes like the canvas one).
- **(b):** Only the four already listed; DnD and video are handled
  inside their feature waves.
- **(c):** Every §6.4 hard part gets a spike, including wallpaper and
  per-OS tray specifics. Most thorough; Wave 0 becomes a milestone of
  its own.

### Q5 — What runs end-to-end in CI?

- **(a) Recommended: layered.** Playwright against the Vite build with
  contract mocks is the per-PR gate; tauri-driver WebDriver is a
  per-release smoke. Parity evidence still comes from the pytest
  scenarios (OpenCode Q2/Q5).
- **(b):** tauri-driver for everything. Real shell, slow and flaky CI,
  per-PR drag.
- **(c):** Component/unit tests only; e2e deferred until a wave needs
  it. Fastest early, parity checks arrive late and manual.

### Q6 — Where does migration work land?

- **(a) Recommended: per-capability branches, PR to main, CI gates**
  (build, LoC gate, docs freshness). Matches free-for-all claiming
  (OpenCode Q8) and keeps main releasable for dual installers
  (Cursor W4).
- **(b):** Direct commits to main, CI as the only gate. Fastest, no
  review checkpoint for deletions.
- **(c):** Long-lived integration branch per wave, merged at wave end.
  Milestone #10's shape; defers all parity evidence to merge day.

### Q7 — How is schema migration discipline enforced during coexistence?

- **(a) Recommended: CI checks additive-only** — a migration touching a
  live Qt row's tables must be additive (new tables/columns; no renames
  or drops); destructive steps ride with the row's deletion PR.
- **(b):** Reviewer discipline only; write the rule in AGENTS.md.
  Cheapest, drifts the first rushed release.
- **(c):** No rule — both apps are released in lockstep. Realistically
  false while dual installers ship (Cursor W4).

### Q8 — Who decides Wave 0 spike go/no-go, and what does "no-go" mean?

- **(a) Recommended: Harbinger decides per spike, on Codex's review,
  with a written no-go outcome.** No-go ⇒ that feature's PySide6 row
  stays alive past its wave (bounded exception list in the ledger),
  not a re-scope of the initiative.
- **(b):** No-go ⇒ initiative re-scope or fallback plan discussion per
  case. More flexible, invites mid-wave churn.
- **(c):** Spikes are informational; waves decide by budget (Codex R5)
  alone. Loses the early, cheap decision point Codex R7 paid for.
