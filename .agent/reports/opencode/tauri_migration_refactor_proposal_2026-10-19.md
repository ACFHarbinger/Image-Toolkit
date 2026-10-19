# Tauri migration and architecture refactor — OpenCode proposal

— OpenCode, 2026-10-19. Proposal only. Builds on the brief, Claude's and
Codex's proposals; I do not restate the parts I agree with (logic before
UI, one service boundary, a sidecar for desktop plus Django for remote,
Vite/React 19, a parity gate).

This proposal adds the mechanisms the other two leave as prose:

1. a **machine-readable migration ledger** that is the inventory, the
   parity gate, the ownership map and the docs index at once;
2. a **characterization + differential parity harness**, so "parity" is
   behavior, not a screenshot or a checklist;
3. **enforcement of the freeze and the ratchet**, so 106k lines of
   PySide6 can only shrink and new UI cannot regress to Qt;
4. **one `HostClient` with transport adapters and an operation
   manifest**, which makes the bridge choice reversible and deletes the
   Rust duplicates without a flag day;
5. **a concrete home and seam rule for the service layer**, plus the
   pilot order that removes the existing duplication first;
6. **documentation that cannot silently rot**, because freshness is
   checked against the contract hash;
7. a **parallel-agent protocol** so seven agents do not collide on the
   same tab.

## Evidence I checked (not assumptions)

- `gui/src` is 704 `.py` files / 106,035 lines. `tabs/` is 48,657 and
  `windows/` 13,921. 42 of 73 files in `gui/src/helpers/` import
  PySide6.
- `_tab_registry.py` has **33 routes in 7 categories but only 26
  factories**: the 8 stitch routes share `stitch.workspace`, and the 5
  `ml.*` routes share the DL workspace
  (`gui/src/modules/application_catalog.py`, `register_stitch_workspace`,
  `register_dl_workspace`). Route count is a poor migration unit.
- `gui/src/modules/descriptor.py:12` imports `QWidget` at module scope
  and `ModuleDescriptor` carries `view_factory`/`instance`; the
  "declarative catalog" is not actually declarative. `catalog.py` is
  cleaner but lazily imports `WidgetHandle` from `runtime.py`.
- `backend/src/` has no `services/` directory; `backend/src/cloud/` is
  empty. `backend/controllers/backend_dispatch.py:24` imports
  `QSettings`, so "the backend is Qt-free" is true of `backend/src/`
  only.
- `frontend/src/api.ts` is 14 lines, hard-codes
  `http://127.0.0.1:8000/api`, and never checks `res.ok`.
- `frontend/src-tauri/src/` has 27 registered handlers. Duplicated
  logic: `db.rs` (424 lines, direct `sqlx`/pgvector), `auth_commands.rs`
  (328), `video_commands.rs` (323), `core_commands.rs` (87),
  `benchmark_commands.rs` (590). The C++ `base` binding is commented out
  in `Cargo.toml`.
- `tauri.conf.json`: `csp: null`, `assetProtocol.scope: ["**"]`.
- Every other Tauri app in the tree is Vite: `dev/app/` (Vite 6, React
  19.2.8, Tauri 2.11), ASP (Vite 7.1.5), CSG (Vite 7.1.5), HIE (Vite
  5). The main `frontend/` is the odd one out on CRA
  (`react-scripts` 5) with Electron leftovers.
- Enforcement already exists on the Python side only:
  `[tool.importlinter]` in `pyproject.toml:238-297` (4 contracts),
  `backend/validation/check_init_boundaries.py`, the LoC gate
  (`docs/loc_exceptions.txt`), `lychee` links. No frontend boundaries.
- Testing: 224 GUI test files under `gui/test/`, `--run-gui` /
  `pytest.mark.gui`; **no** Tauri e2e/WebDriver setup.
- `docs/ARCHITECTURE.md` (713 lines) is actually the ASP stitch-pipeline
  reference, not the app architecture. There is no `docs/adr/`.

## 1. The migration ledger: one machine-readable source of truth

**Problem.** A parity matrix written by hand in a report drifts on day
two, and with seven agents the question "who is porting what, and what
is safe to delete?" has no authoritative answer. The brief's design axis
5 asks for an inventory and a deletion protocol; a Markdown table cannot
enforce either.

**Shape.** One tracked file, `migration/features.toml` (TOML: no extra
dependency, diff-friendly), one record per **capability**:

```toml
[[feature]]
id = "convert"
title = "Convert"
routes = ["system.convert"]
pyside = ["gui/src/tabs/system/convert", "gui/src/helpers/core/conversion_worker.py"]
tauri = ["frontend/src/tabs/core/Convert"]
service = "backend/src/services/convert"
contract = "backend/src/services/convert/api.py"
scenarios = ["convert.raster.roundtrip", "convert.cancel.mid_batch"]
docs = "docs/modules/convert.md"
owner = "unassigned"
wave = 0
status = "pyside-only"   # pyside-only | both | parity-passed | pyside-deleted
```

`id` is the capability, not the route: stitch is one record with eight
routes, DL is one record with five. That matches the factory reality
above and avoids eight near-duplicate rows.

**CI invariants** (`backend/validation/check_migration_ledger.py`,
wired into `ci.yml` next to the existing `loc-gate`):

- every route in `_tab_registry.py` and `application_catalog.py` appears
  in exactly one record — no orphan routes, no phantom routes;
- every `pyside` and `tauri` path exists (or, for
  `status = "pyside-deleted"`, provably does not);
- `parity-passed` requires a scenario ID that exists and is not skipped;
- a discovered PySide6 file under `gui/src/{tabs,windows,components,
  elements}/` that belongs to no record fails the check, so "unowned"
  code cannot hide;
- `pyside-deleted` rows keep their `docs` and `contract` entries, so the
  deletion does not delete the knowledge.

The same file generates `docs/migration/parity.md` (human view) and the
GitHub milestone checklist (script), so the report, the docs and the
tracker cannot disagree. **Ownership claim = edit `owner` + `wave` in a
PR**, reviewed by whoever is coordinating (Claude/Codex), rather than a
bus line that scrolls away.

**Tradeoff.** One more registry and a validator to maintain. In return
the delete gate is mechanical, and no agent has to reconstruct state
from the bus. This directly implements the brief's "generated parity
matrix" idea while adding the missing ownership and bidirectional
coverage checks.

## 2. Parity is behavior: characterize first, then diff

**Problem.** "Same capability" is easy to declare and hard to prove.
Extracting a `QThread` worker into a service is exactly where behavior
drifts: signal ordering, cancellation points, error text, default
arguments, filesystem side effects. A click-through by a human will not
catch a changed default.

**Shape.**

1. **Characterization before extraction.** For each feature slice, add
   approval-style tests that pin *current* behavior *before* moving the
   code: inputs, outputs, error codes, emitted event order, and the
   files created. They call the Qt worker's logic (or the backend
   command it wraps) directly, not through a window. These are the
   safety net for the move, and they are deleted with the PySide6 code
   at the row's parity gate.
2. **Differential harness.** While both implementations exist, run the
   same scenario through the old path and the new service/sidecar and
   diff the artifacts and the event sequence (`TaskHandle` events, not
   Qt signals). This is the strongest parity signal available and it
   runs in CI without a GUI.
3. **Framework-neutral acceptance.** Reuse the intent of the existing
   `gui/test` scenarios (224 files, `pytest.mark.gui`) as declarative
   scenarios in the ledger, then let one scenario drive a Qt test and a
   Tauri e2e test. Do not force identical click sequences.
4. **Deterministic corpus** under `~/Downloads/Data/Tests/` per
   `AGENTS.md`; only small manifests/hashes are tracked in the repo.
   Golden binaries never enter git.

**Where this differs from the other proposals.** Claude says "one spec
passes twice"; Codex says "golden artifacts with tolerances". I'm adding
the *temporal* part: characterize the old implementation first, then
continuously diff old vs new during coexistence. That catches drift the
same day it is introduced, and it gives a defensible answer to "why is
this row allowed to be deleted?"

**Tradeoff.** Writing characterization tests before the move costs time
on an implementation that will be deleted. It is also the only way to
prove the move was behavior-preserving, and it converts each deletion
into an evidence-backed event instead of a judgment call.

## 3. Enforce the freeze and ratchet the Qt surface

**Problem.** "All new UI is Tauri-only" and "refactor for DRY" are
conventions until CI says no. During a long migration the cheapest path
for any agent is to patch the Qt worker, which grows the very surface
being removed. Without a ratchet, the refactor can lose ground.

**Shape.**

- **Content-hash allowlist** for the PySide6 UI: commit the hash of
  every file under `gui/src/{tabs,windows,components,elements}/` (and
  the Qt-importing helpers). CI fails if a file is **added** or its
  content **changes**, unless the PR also edits the allowlist *and* the
  ledger status for that row. Bugfix exceptions are explicit and
  reviewer-approved; they still do not add routes.
- **Qt budget ratchet.** Count modules importing PySide6 under `gui/`
  (start at 42 helpers + the module/window files). Store the budget in
  the ledger or a small file; the PR that deletes code lowers it, and
  CI fails if the number rises. This generalizes the existing
  `import-linter` contract from "never" to "only downward" without
  rewriting the four existing contracts in `pyproject.toml:238-297`.
- **Frontend boundaries now.** The Python side already has
  `import-linter`; the frontend has only `tsc` on `frontend/src/math`.
  Add ESLint boundaries in Wave 0, before the feature waves, so new
  Tauri code is modular from its first line instead of retrofitted.
- **Delete the Electron/CRA leftovers in Wave 0** (root `package.json`
  scripts, `electron*` deps, `"main": "public/electron.js"`), because
  every day they stay they attract accidental work.

**Tradeoff.** A hash allowlist is blunt and will occasionally annoy a
legitimate urgent fix. That is the point: exceptions become visible and
reviewed, instead of silent growth. If it proves too rigid, relax to
"new files forbidden, existing files may only shrink" — still
monotonic.

## 4. One `HostClient`, transport adapters, one operation manifest

**Problem.** Codex notes `frontend/src/api.ts` and the 27 Rust commands
are parallel, partly duplicate implementations. Claude proposes deleting
the Rust duplicates. Neither says how to migrate call sites without a
flag day or a period where both can drift. Also, the transport decision
(Q0c) is genuinely open; the code should not bet the architecture on it
before it is settled.

**Shape.**

- Define a small **operation manifest** (generated from the service
  contracts) with stable operation names, request/response types and
  error codes. This is the same schema that generates the TS client.
- Frontend code calls `hostClient.<operation>()` exclusively. Transports
  are adapters behind it:
  - `SidecarTransport` — JSON-RPC/stdio (D52 precedent, `dev/app/`);
  - `HttpTransport` — the Django adapter and remote/mobile;
  - `RustTransport` — native only (dialogs, tray, notifications, OS).
- **Rust command retirement is a routing table edit**, not a rewrite:
  `convert_image_batch` moves from `RustTransport` to the sidecar
  adapter, its scenario must pass against the new transport, then the
  Rust body is deleted. The TS call site does not change. `db.rs`,
  `auth_commands.rs`, `video_commands.rs`, `core_commands.rs` are retired
  the same way, in the pilot/wave order, with `benchmark_commands.rs`
  handled last (it is benchmark tooling, not product logic).
- **Conformance suite per transport.** The same operation suite runs
  against the sidecar and HTTP adapters (fakes, no network), so the
  second adapter cannot quietly diverge.
- **Envelope**: protocol version, request id, operation id, typed
  payload, structured error. Job events carry job/attempt ids and
  monotonic sequence; reconnect uses cursor + snapshot. Cancellation is
  a request followed by an acknowledged terminal outcome. (Aligns with
  Codex §2 and the Cloud Jobs daemon IPC; reuse that event shape rather
  than inventing a third.)
- **Security defaults**: replace `csp: null` and
  `assetProtocol.scope: ["**"]` before any remote content is embedded;
  media goes through authorized, scoped asset identities, never base64
  through the control channel.

**Tradeoff.** The adapter layer is indirection and a small cost per
operation. It makes the bridge choice reversible, gives one place to
enforce errors/cancellation/auth, and is the mechanism that actually
removes the duplicated Rust logic instead of just declaring it dead.

## 5. Service layer: home and seam rule

**Problem.** "Extract logic into Qt-free services" needs a concrete home
and a rule for what qualifies, or `gui/src/helpers` gets recreated under
a new name.

**Shape.**

- Home: `backend/src/services/<feature>/` (the brief already uses this
  shape; `backend/src/cloud/` becomes `services/cloud_jobs/` or an
  adapter over it). No new `core/` package.
- A **service** owns a use case and its transactional boundary. It is a
  plain class, constructor-injected with repository/client/settings
  protocols, and returns a `TaskHandle` for long work. It does **not**
  import Qt, HTTP, Django, or a view.
- `gui/src/helpers/*_worker.py` becomes a thin `QThread` adapter that
  calls one service method and forwards `TaskHandle` events to Qt
  signals. The orchestration that was in the worker moves; the signal
  plumbing stays only as long as PySide6 ships.
- `backend/src/app.py`'s PySide6 import and
  `backend/controllers/backend_dispatch.py`'s `QSettings` import are
  explicit leave-behinds to remove; the existing import-linter
  contract 1 forbids new ones.
- Composition root: one place builds concrete repositories and clients
  (`backend/src/services/composition.py` or the app bootstrap), so tests
  inject fakes and the two adapters share the same wiring.
- Split **metadata from factories** in `gui/src/modules/descriptor.py`:
  keep route/category/title/policy as serializable data; move
  `QWidget`/`view_factory` into the Qt runtime. That makes the route
  inventory usable by the ledger, docs and Tauri without importing Qt.

**Tradeoff.** `services/` will briefly duplicate some top-level backend
modules while they are wrapped. Rule: a service may delegate to
`backend/src/core`, `database`, etc.; it must not fork them. Each wave
ends with the old caller removed, so duplication is bounded by one
slice.

## 6. Pilot and wave order (seam-first, not screen-first)

Agree with Convert as the pilot, with one amendment: the pilot's
success criterion is **the first Rust duplicate deleted and the first
characterization suite green**, not just a Tauri Convert screen. That
proves the whole seam (contract → sidecar → service → old backend) on
low-risk code.

1. **Wave 0 — platform and freeze.** Vite cutover and Electron removal;
   ledger + validator; operation manifest and `HostClient`; sidecar
   supervision with readiness/version handshake; ESLint boundaries;
   hashed PySide6 allowlist; docs scaffolding; **capability spikes** for
   gallery, canvas, tray/Wayland, ComfyUI embedding with written
   go/no-go criteria (no benchmarks outside the Codex/Harbinger chain).
2. **Pilot — Convert.** Extract `conversion_worker` logic into
   `services/convert`; add characterization + differential tests;
   retire `core_commands.rs::convert_image_batch`; parity gate.
3. **Cloud Jobs Gate D** on the shared `HostClient` (no new UI in Qt).
4. **Area waves**, ordered by seam value per unit of risk:
   1. system merge/extractor/similarity (more Rust/core duplication);
   2. database/library (retire `db.rs`, `auth_commands.rs` last within
      this wave because vault/settings are load-bearing);
   3. web (crawler, requests, sync, media loader);
   4. video (retire `video_commands.rs`);
   5. deep learning + ComfyUI (webview after the Wave 0 spike);
   6. editors/canvases (stitch, HIE, manga; WebGL/OffscreenCanvas only
      if the spike says so);
   7. settings, tray, wallpaper daemons (OS-heavy; stage per platform).
5. **Final**: remove PySide6, `ImageToolkit.spec`, Qt deps; rewrite the
   ROADMAP Tri-Interface section; package the frozen sidecar; delete
   CRA/Electron remnants and `benchmark_commands` scaffolding.

Each wave ends with: characterization tests green, differential clean,
parity row `parity-passed`, deletion PR, ledger ratchet lowered, docs
updated. That is the definition of "done".

## 7. Documentation that cannot silently rot

**Problem.** The brief asks for docs a future human can use. The repo's
current `docs/ARCHITECTURE.md` is a 713-line ASP stitch reference, not
an app architecture map; there is no ADR directory; and generated
references go stale unless CI checks them. The agent reports are not
onboarding docs and should not become them.

**Shape.**

- **Fix the names first.** Rename the current `docs/ARCHITECTURE.md` to
  what it is (`docs/asp/stitching.md` or similar) and write a real
  architecture map: process diagram (Tauri shell, sidecar, Django,
  daemons, DB), ownership of each boundary, and the request lifecycle
  for one command and one durable job.
- **ADRs** in `docs/adr/NNNN-title.md`, one per *locked* decision (the
  bridge, Vite, ledger, parity gate, service home). Copy the decision
  tables already in the devtool and Cloud Jobs roadmaps rather than
  rewriting them; link back. An ADR is immutable except for
  status/superseded-by.
- **Per-module README** generated from the ledger, containing purpose,
  public contract, events, settings keys, owner, how to run its
  targeted tests, and a **contract hash** in front matter.
- **Freshness check**: CI recomputes the contract hash; if it changed
  and the README's hash did not, the docs build fails. This is the one
  mechanism that makes "docs updated" enforceable without reading
  intent. `mkdocs build --strict` plus the existing `lychee` hook
  covers links; sphinx/typedoc cover generated references.
- **A walkthrough**: the Convert pilot written up as "how to add or
  migrate a feature", including the ledger edit, characterization test,
  differential run, and deletion PR. That is the guide a new developer
  (or agent) actually follows.
- Explicitly separate **human docs** (`docs/…`) from **agent process
  history** (`.agent/…`), as Codex also recommends.

**Tradeoff.** Contract hashes will produce some documentation churn on
every API change. That is the correct pressure: either the doc changed
or the reviewer consciously re-affirms it.

## 8. Parallel-agent protocol

**Problem.** Seven agents, one shared checkout, 33 routes and 704 files.
The historical failure mode in the onboarding README is exactly this:
duplicate questions, work started before a gate, and "done" that was
not landed.

**Shape.**

- **One claim = one ledger row** (`owner` + `wave`), posted on the bus
  with the row id. No code before the claim and the wave gate.
- **One PR = one row (or one Wave 0 platform slice) + its deletion.**
  Wide mechanical PRs (Vite cutover, formatting) are separate and
  announced.
- **Reviewer split**: Codex reviews anything touching jobs/durability
  and the resource-rule-sensitive harnesses; Claude coordinates the
  ledger; a second agent reviews each deletion (deletions are
  irreversible and easy to get wrong).
- **No agent runs** the parity corpus, benchmarks, or full suites
  outside the existing Codex/Harbinger chain. Targeted
  characterization/differential runs on small fixtures are fine.
- **Definition of done** is the wave checklist above, not a bus post
  claiming completion.

**Tradeoff.** More process than "just port it". It is cheaper than
re-resolving the same tab twice or deleting code whose scenarios were
never green.

## Risks

1. **Ledger overhead** — if the validator or the ownership rule becomes
   heavy, agents will bypass it and the matrix rots. Keep the file small
   and the validator fast (one targeted test).
2. **Characterization cost** — pinning current behavior can encode bugs
   as expected behavior. Mark known-wrong behaviors explicitly as
   `# known-bug` with a linked issue, so the move preserves them but the
   migration does not bless them.
3. **Differential harness blind spots** — non-deterministic outputs
   (timestamps, ordering, GPU nondeterminism) need tolerances; start
   with deterministic operations (convert, merge, extract) and expand.
4. **Bridge churn** — the adapter layer absorbs it, but the operation
   manifest must be the only source of truth; hand-written TS types are
   the failure mode.
5. **Webview feasibility** — gallery, canvas, tray and ComfyUI may
   change the wave order. The Wave 0 spikes exist to find that out
   before the platform is committed, not after.
6. **Coexistence drift** — two apps writing the same settings/DB. The
   sidecar/HTTP service layer must be the single writer during the
   migration; the Qt adapter becomes a client, not a peer.

## Q. Questions for Harbinger

Recommended option first. These are new; the brief's answered questions
and the Claude/Codex questions are not repeated. Harbinger answered all
eight on 2026-10-19; the recorded answers are at the end of this file.

### [OpenCode Q1] What is the unit of migration?

- **(a) Recommended: capability/workspace, not route.** One ledger
  record per user-visible capability; stitch is one record with eight
  routes and DL one with five, matching the 26 factories behind the 33
  routes. Avoids eight near-duplicate ports and one shared workspace
  being rebuilt inconsistently.
- **(b) Per route (`system.convert`, `stitch.graph`, …).** Finer
  progress tracking, but the shared stitch/DL workspaces get fragmented
  ownership and duplicated scaffolding.
- **(c) Per screen/tab as currently laid out in PySide6.** Most literal,
  but it preserves the current UI's accidental grouping instead of
  defining capabilities.
- **(d) Per service first, screens later.** Cleanest backend seam, but
  no visible migration for a long time and no early parity evidence.

### [OpenCode Q2] How do we prove parity before deleting PySide6 code?

- **(a) Recommended: characterize-then-diff.** Pin current behavior with
  approval-style tests before extraction, then run the old path and the
  new service on the same fixtures and diff outputs/events in CI while
  both exist. Add framework-neutral acceptance for the UI.
- **(b) One semantic acceptance spec that passes in both UIs**
  (Claude/Codex direction). Cheaper, but only proves the paths the spec
  clicks, not defaults/edge behavior.
- **(c) Manual checklist signed per row.** Simplest, weakest; misses
  silent behavior changes.
- **(d) Pixel/visual comparison** for the screens. Catches layout drift,
  proves nothing about logic or data.

### [OpenCode Q3] How strictly do we freeze new PySide6 work?

- **(a) Recommended: hash allowlist + downward-only Qt budget.** No
  new/changed PySide6 UI files without an explicit, reviewed
  allowlist/ledger update; the Qt-import count can only fall. Bugfixes
  are possible but visible.
- **(b) Freeze all of `gui/src` to bugfixes only**, reviewed case by
  case. Simpler rule, but blocks legitimate fixes and is not
  automated.
- **(c) Convention only.** Fastest in the moment, and the surface will
  grow back.
- **(d) No freeze; fix bugs in both apps as needed.** Most comfortable
  for users during the migration, highest drift and double-work cost.

### [OpenCode Q4] Where does the canonical service layer live?

- **(a) Recommended: `backend/src/services/<feature>/`**, with
  `backend/src/core|database|web` as implementations it delegates to,
  and `gui/` + `frontend/` + `api/` as clients. Matches the brief and
  the Cloud Jobs plan.
- **(b) A new top-level `core/` package** extracted out of `backend/`.
  Cleaner boundary in theory, but a repo-wide move and new packaging
  before any feature is ported.
- **(c) Keep logic in today's `backend/src/` modules and add thin
  facades there.** Least churn, but no explicit seam and the Qt workers
  keep owning orchestration.
- **(d) Put services in `gui/src/services/` and let Tauri call them
  through the sidecar.** Reuses the existing small `gui/src/services`,
  but keeps domain logic in the layer being deleted.

### [OpenCode Q5] What happens to the 224 PySide6 test files during the migration?

- **(a) Recommended: they are the parity oracle until their row passes.**
  Keep them runnable, tag the ones that encode behavior as oracle
  scenarios, and delete a test only in the same PR that deletes its
  PySide6 code and lands the Tauri replacement.
- **(b) Delete tests as soon as the code is extracted.** Smaller
  maintenance load, but loses the evidence that the port is correct.
- **(c) Maintain both suites in full until final deletion.** Safest, but
  every behavior change is written twice for months.
- **(d) Freeze them now (no new PySide6 tests)** and rely on the new
  harness. Fastest to converge, but regressions in un-migrated areas go
  unguarded.

### [OpenCode Q6] When do we cut over CRA → Vite and delete Electron?

- **(a) Recommended: Wave 0, in one announced PR.** Vite + React 19,
  remove `react-scripts`, the Electron deps/scripts and
  `public/electron.js`; no feature work merges until the build and the
  existing test are green. It unblocks boundaries and e2e.
- **(b) Dual-build CRA and Vite for one wave**, then delete CRA. Lower
  risk of breaking the app, but two build configs to keep green.
- **(c) Defer until after the pilot.** Keeps early momentum, but every
  new Tauri file is written against the deprecated toolchain.
- **(d) Stay on CRA for the whole migration.** Least immediate work,
  worst long-term cost; CRA is deprecated.

### [OpenCode Q7] How do we keep documentation from going stale?

- **(a) Recommended: contract-hash freshness in CI.** Each module README
  carries the contract hash; if the contract changes without the README,
  the docs build fails. Generated references (OpenAPI/sphinx/typedoc)
  and `mkdocs --strict`/`lychee` cover the rest.
- **(b) Review checklist only.** No tooling; docs drift between
  releases.
- **(c) Generated docs only.** Zero drift for references, but no
  rationale, ownership or onboarding narrative.
- **(d) Treat the `.agent/` reports as the documentation.** Most
  complete history, but it is process narrative, not a usable developer
  guide.

### [OpenCode Q8] How should parallel agents claim and land migration work?

- **(a) Recommended: ledger-row ownership + one row per PR.** Claim
  `owner`/`wave` on the bus and in the ledger, wait for the wave gate,
  land code + tests + deletion + docs together; deletions get a second
  reviewer.
- **(b) Area owners** (one agent per area: system, library, web, DL,
  editors, OS). Less negotiation per row, but a single agent becomes the
  bottleneck for a whole area.
- **(c) Free-for-all task claiming** on GitHub issues. Flexible, but
  the historical duplicate-work/collision failure mode returns.
- **(d) One agent at a time for the whole migration.** Simplest
  coordination, slowest by roughly the number of agents available.

## Recorded answers (2026-10-19)

Harbinger answered all eight; these supersede the recommendations where
they differ.

- **Q1 → (a)** Capability/workspace is the migration unit.
- **Q2 → (a), with (b) or (c) where a row requires it.** Characterize-then-diff
  is the default; semantic acceptance specs and manual/pixel checks are
  complements, not replacements.
- **Q3 → (b)** Freeze all of `gui/src` to reviewed bugfixes only. The
  content-hash allowlist and automated Qt budget are not adopted; the ledger
  still records any approved exception.
- **Q4 → (a)** `backend/src/services/<feature>/`.
- **Q5 → (a)** The PySide6 tests remain the parity oracle until their row
  passes.
- **Q6 → (a)** CRA→Vite and Electron removal in one Wave 0 PR.
- **Q7 → (a)** Contract-hash docs freshness in CI.
- **Q8 → (c)** Free-for-all claiming on GitHub issues. The ledger remains the
  inventory and deletion gate, but not the ownership mechanism; the wave gate
  and one-row-per-PR landing rule still apply per the brief.

Two consequences worth carrying into the roadmap:

- Q3(b) means the freeze is a review rule, so the ledger's path/coverage
  validation is now the *only* automated guard against new PySide6 surface;
  it should reject new unowned files even though it cannot reject edits.
- Q8(c) means agents must claim GitHub issues directly and the roadmap must
  define issue granularity (one capability row per issue) before implementation
  starts, or two agents will take the same tab.

— OpenCode, 2026-10-19
