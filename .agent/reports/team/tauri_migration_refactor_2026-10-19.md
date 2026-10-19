# Tauri Migration and Architecture Refactor — Team Brainstorm

**Participants:** Harbinger and Claude, plus the invited agents Codex,
Gemini, Grok, Cursor, Mistral, Kimi and OpenCode.

**Origin:** Harbinger wants three things:

1. **Migrate every feature** of the PySide6 desktop GUI (`gui/`) to the
   Tauri app (`frontend/`).
2. **Refactor for DRY and SOLID**, and make the architecture more modular.
3. **Improve the documentation**, so that human developers working on the
   app in the future have an easier time.

This runs **alongside** the Cloud Jobs Service implementation
(`docs/moon/roadmaps/cloud_jobs.md`).

This is a **brainstorming round**. Agents ask Harbinger questions and
propose options; nothing here is approved for implementation yet. The
usual rule applies (`.agent/bus/onboarding/README.md` §4.2): claim on the
bus, wait for the phase gate, then code.

This is a **living document**:

- Add your proposal summary under §4 and your questions under §5.
- Don't rewrite other people's sections.
- Sign and date what you add.

---

## 1. Goal

1. **Feature parity in Tauri.** Every PySide6 feature works in the Tauri
   app. That includes every tab and sub-tab, every window, the tray,
   dialogs, the daemons' controls, settings and theming.
2. **Retire PySide6.** Harbinger decided this on 2026-10-19:
   - Both apps ship while the migration is under way.
   - **Each PySide6 feature is deleted once its Tauri replacement passes
     an agreed parity check.**
   - At the end, the PySide6 app is removed entirely.
3. **Refactor for DRY and SOLID.** Business logic gets one home behind
   clear interfaces. Duplicated implementations are removed. Modules
   depend on abstractions rather than on each other's internals.
4. **Modularity.** Features become self-contained modules with explicit
   boundaries. Those boundaries are enforced by tooling, not by
   convention.
5. **Documentation for human developers.** This covers onboarding, an
   architecture map, a "how to add a feature" guide, generated API
   references, and decision records.

## 2. Current state (build on this; don't assume)

### The two GUIs

| | PySide6 (`gui/src/`) | Tauri (`frontend/`) |
|---|---|---|
| Size | 704 files, about 106,000 lines | 69 TS/TSX files, plus 2,100 lines of Rust in `src-tauri/src/` |
| Structure | `tabs/` (48.7k lines), `components/` (14.1k), `windows/` (13.9k), `helpers/` (10k), `classes/` (6k), `elements/` (4.5k), plus `theming`, `modules`, `preferences` and `services` (0.5–2k each) | `tabs/` mirrors the old tab set: core, database, models, web, editor, apollo |
| Registry / build | Tab registry `gui/src/windows/main/_tab_registry.py`, about 60 route keys across `system.*`, `library.*`, `ml.*`, `dl.*`, `stitch.*`, `manga.*`, `web.*`, `editor.*` | Create React App (`react-scripts` 5, deprecated); `package.json` still has Electron entries |
| Backend access | — | Mostly `fetch` to the Django API at `127.0.0.1:8000/api` (`frontend/src/api.ts`); 26 Rust `#[tauri::command]`s |

Tauri's Rust commands (26 in total) cover:

- auth and settings;
- database search, tags and groups (through its own `db.rs`);
- wallpaper and slideshow;
- convert, merge and delete;
- video clip and frame extraction.

**Several of these re-implement in Rust what the Python backend already
does**: database queries, conversion, merging and extraction. That is a
DRY problem to resolve, not to copy forward.

### Backend and other surfaces

- **The backend is almost Qt-free already.** Only `backend/src/app.py`
  imports PySide6. A lot of logic still lives in the GUI layer, though:
  - 42 of the 73 files in `gui/src/helpers/` import PySide6. Many are
    `QThread` workers that wrap backend calls.
  - Tab controllers hold orchestration and validation.
- **Submodule front ends already exist.**
  - `submodules/HIE/frontend` is consumed by the main frontend as the
    `hie-frontend` package.
  - ASP and CSG each have their own Tauri front end.
  - In PySide6, the stitch and manga areas are hosted in `gui/`.
- **Precedents to reuse or learn from:**
  - **The devtool v2 Tauri rewrite** (`docs/moon/roadmaps/development_tool.md`,
    decisions D41–D64): Vite, React 19, Tauri 2, and a Python sidecar
    chosen as the integration model (D51).
  - **Earlier refactors (all milestones closed):**
    - GUI Refactoring Roadmap (#10, 32 issues);
    - Architecture Deep-Dive (#9, 14 issues);
    - UI Shell & Module Runtime (#8, 18 issues), which produced
      `ModuleCatalog` / `WorkspaceDescriptor`;
    - App Theming (#6).

    Read what they settled before proposing the same thing again.
  - **The 500-code-line LoC gate** (`backend.validation.count_loc`,
    `loc_exceptions.txt`).
  - **Docs:** `docs/ARCHITECTURE.md` (713 lines), `docs/DEVELOPMENT.md`
    (50 lines), mkdocs and sphinx under `docs/`. There is no ADR
    directory.
- **Work that interacts with this initiative:**
  - **Cloud Jobs** (milestone #12):
    - **Harbinger, 2026-10-19:** new UI is built **in Tauri only**,
      starting with the Cloud Jobs window (Gate D, #847–#852).
    - Backend Gates A–C continue as planned.
    - Cloud Jobs G1 needs a phone/web client, and its daemon IPC and
      event stream are relevant to the bridge choice.
  - **The Deep Learning Tab Rebuild** (milestone #11, one issue still
    open): any UI work on it that hasn't started is reviewed case by case.
  - **The ROADMAP's "Tri-Interface Strategy"** (`docs/moon/ROADMAP.md`:
    PySide6 as the pro desktop, Tauri as the network hub, plus mobile)
    is **superseded** by this initiative and must be rewritten as part of
    the outcome.
- **Things that were hard in PySide6 and may get easier or harder in a
  webview:**
  - **Embedded ComfyUI:** banned in PySide6 after the #729 WebEngine
    SIGSEGV. In Tauri it is a webview or iframe.
  - **Per-monitor wallpaper:** KDE, GNOME and Windows, plus the slideshow
    daemons.
  - **The system tray.**
  - **Large virtualised galleries and thumbnails,** and local-file media
    access.
  - **Canvas-heavy editors:** stitch, merge canvas, frame-slice canvas.
  - **VaultManager unlock and `libitk_crypto`.**
  - **Multi-window flows:** preview, compare, slideshow, Cloud Compute,
    and settings.

## 3. Process

1. **Proposals only.** Don't build anything yet.
2. **Write your proposal** to
   `.agent/reports/<your-name>/tauri_migration_refactor_proposal_2026-10-19.md`.
   Each proposal should cover:
   - **Ideas.** For each idea: what it is, the problem it solves, a rough
     implementation shape, and its tradeoffs and risks.
   - **Questions for Harbinger.** For each question, give 2–4 concrete
     options and your recommendation.
   - **Coverage.** Depth beats forced coverage. Pick the axes in §6 where
     you have real ideas, and ground claims in file paths.
3. **Report back.**
   - Post a one-line pointer on `.agent/bus/<date>.md`.
   - Add a short summary and link under §4.
   - Copy your questions into §5 and tag each one with your name.
   - Record Harbinger's answers inline, as in the Cloud Jobs round.
4. **Commit your own files** on main (`git add` only your paths; this is a
   shared checkout).
5. **Final brainstorming round.** Harbinger and Claude review everything
   together, then resolve conflicts and gaps. The outcome is recorded in
   §7.
6. **Decision.** Harbinger and Claude lock the scope. Then they:
   - write a roadmap (a new `docs/moon/roadmaps/tauri_migration.md`, with
     the ROADMAP strategy section rewritten);
   - create a GitHub milestone and issues.

## 4. Proposals (add yours here)

- **Claude** (2026-10-19):
  [Full proposal](../claude/tauri_migration_refactor_proposal_2026-10-19.md).
  Recommends:
  - **Logic before UI.** Move logic out of the Qt layer first, into Qt-free
    application services with typed contracts. Generate one schema from
    those contracts, and from it the TypeScript client (and the Rust types
    where needed). Delete the duplicate Rust implementations.
  - **A parity matrix.** It is generated from the tab registry, the
    windows and the tray, and it serves as the deletion gate for each
    PySide6 feature.
  - **The frontend platform** comes before porting:
    - Vite instead of CRA;
    - design tokens ported from `gui/src/theming`;
    - shared components (virtualised gallery, resize grips, forms);
    - routes driven by the registry.
  - **Porting order:**
    1. a pilot feature, end to end;
    2. the Cloud Jobs window, as the first Tauri-only feature;
    3. waves by area.
  - **Boundaries** enforced by `import-linter` and ESLint boundaries,
    feature-module manifests, ADRs, a per-module README template, and
    generated API docs.

- **Codex** (2026-10-19):
  [Full proposal](../codex/tauri_migration_refactor_proposal_2026-10-19.md).
  Recommends vertical feature extraction; a versioned stdio sidecar with
  Django over the same services; explicit separation of session requests
  from durable jobs; shared settings ownership preserving existing scopes;
  scoped media access and isolated ComfyUI; behavior/performance parity;
  tested UI/sidecar version pairs; and, following Harbinger’s answers,
  primarily consolidated submodule frontends with selective shared interfaces.
  Performance budgets allow case-specific deferral of intractable optimization. Builds on existing catalog/preferences contracts. Flags the current
  mixed HTTP/Rust/Python launch paths and broad asset scope as early work.
  Moves minimal vault/settings/packaging and hard-feature feasibility early.

- **OpenCode** (2026-10-19):
  [Full proposal](../opencode/tauri_migration_refactor_proposal_2026-10-19.md).
  Recommends:
  - **A machine-readable migration ledger** (`migration/features.toml`):
    capability-level records (33 routes collapse to 26 factories; stitch
    is one record with 8 routes) that serve as inventory, parity gate,
    ownership map and docs index. CI validates route coverage both ways,
    path existence/deletion, and scenario presence.
  - **Characterize before extracting, then differentially diff** old vs
    new services on the same fixtures while both apps ship; reuse the
    `gui/test` scenarios as framework-neutral acceptance.
  - **Enforce the freeze**: a content-hash allowlist for PySide6 UI plus
    a downward-only Qt-import budget, so 106k lines can only shrink, and
    ESLint boundaries before the feature waves.
  - **One `HostClient` + operation manifest + transport adapters**
    (sidecar stdio / Django HTTP / native Rust). Retiring `db.rs`,
    `auth_commands.rs`, `video_commands.rs`, `core_commands.rs` becomes a
    routing-table edit with a conformance suite per transport, not a
    rewrite.
  - **Services in `backend/src/services/`**, thin Qt worker adapters,
    serializable route metadata split out of `descriptor.py` (which
    imports `QWidget` today), and a "no forking core" seam rule.
  - **Seam-first pilot/order**: Convert's success criterion is the first
    Rust duplicate deleted, not just a new screen. Wave 0 includes
    written go/no-go capability spikes for gallery, canvas, tray/Wayland
    and ComfyUI.
  - **Docs that cannot rot**: rename the current `docs/ARCHITECTURE.md`
    (it is the ASP stitching reference), add ADRs, per-module READMEs
    with a contract hash checked in CI, and the Convert pilot as the
    "how to migrate a feature" walkthrough.
  - **Parallel-agent protocol**: one ledger row = one claim = one PR
    (code + tests + deletion + docs), second reviewer for deletions.

- **Grok** (2026-10-19):
  [Full proposal](../grok/tauri_migration_refactor_proposal_2026-10-19.md).
  Builds on the recorded sidecar, settings, and submodule answers.
  Adds:
  - a **bounded thumbnail service** so the webview never decodes
    original huge or animated files (the `PixmapBudget` failure mode).
    Harbinger: a **C++ service** writes the stills, and the default
    frame is the **middle** frame;
  - **Wave 0 lockdown** of `tauri.conf.json` (`csp: null`, asset scope
    `**`) before Cloud Jobs Gate D;
  - a **serializable module catalog** split from `descriptor.py`'s
    `QWidget` factories, shared by both shells and aligned with the
    migration ledger;
  - **one main webview**, with extra native windows only for tray,
    slideshow, and file dialogs. Harbinger: also a separate window
    where that is required for feature parity;
  - a **supervisor that siblings** the sidecar, cloud-jobs daemon, and
    slideshow daemon, so a window close does not drop leases;
  - **vault unlock inside the sidecar**, session handle in the webview,
    leases in daemons. Harbinger: the **C++ core** (`base/`) holds
    unlock and the database key instead;
  - **one shared canvas host** for stitch, merge, and frame-slice;
  - **new Deep Learning panels in Tauri** against `record.json` /
    `events.jsonl`. No PostgreSQL.

## 5. Questions for Harbinger (tag with your name; Harbinger answers inline)

Answered directly in chat on 2026-10-19, before the round opened:

- **[Claude Q0a] Process:** a team brainstorm round, this one.
- **[Claude Q0b] End state:** **PySide6 is removed after parity.**
  - Both apps ship during the migration.
  - Each PySide6 feature is deleted once its Tauri version passes the
    agreed parity check.
- **[Claude Q0c] How Tauri talks to the Python backend: OPEN, for this
  brainstorm to decide.** Candidates:
  - a local Python sidecar (the devtool D51 precedent);
  - the existing Django REST/WebSocket API;
  - Rust commands for native work;
  - a mix of these.

  Proposals should compare them, cover process lifecycle, packaging and
  startup cost, and say how the Cloud Jobs daemon IPC and G1 remote client
  fit in.
- **[Claude Q0d] Work in flight:** **all new UI is built in Tauri only,**
  starting with Cloud Jobs Gate D. Backend work continues. Deep Learning
  rebuild UI that hasn't started is reviewed case by case.

Claude's remaining questions are in its proposal (§Q).

### Codex — 2026-10-19 (all seven answered)

- **[Codex R1] Which desktop bridge should we standardize on?**
  - **Harbinger answer (2026-10-19; recorded by Codex):** A. Supervised Python sidecar over versioned JSON-RPC/stdio; Django exposes the same services remotely; Rust handles native integration.
  - **A (recommended):** supervised Python sidecar with versioned JSON-RPC over stdio; Django exposes the same services remotely; Rust handles native integration.
  - **B:** supervised local Django API for desktop and remote clients; fewer transports, larger desktop server footprint.
  - **C:** sidecar with authenticated loopback HTTP and streamed events; easier browser tooling, but requires port discovery and local endpoint security.
- **[Codex R2] Should local work survive closing every app window?** Cloud jobs already must survive.
  - **Harbinger answer (2026-10-19; recorded by Codex):** A. Durable long-running local jobs survive closing all windows under an independent supervisor; previews and interactive requests remain session-owned. Cloud jobs retain their independent lifecycle.
  - **A (recommended):** mark long jobs as durable and run them under a supervisor independent of the UI; previews and interactive requests remain session-owned.
  - **B:** keep all submitted local jobs running until completion, even short jobs; more background resource use.
  - **C:** cancel local jobs on exit after warning; cloud jobs retain their existing independent lifecycle.
- **[Codex R3] How should settings behave while both GUIs ship?**
  - **Harbinger answer (2026-10-19; recorded by Codex):** A. Both GUIs use one settings service with preserved keys/scopes, conflict detection and a backed-up migration of legacy settings.
  - **A (recommended):** both use one settings service with preserved keys/scopes and conflict detection; migrate legacy data with a backup.
  - **B:** import once into Tauri, then keep separate settings; simpler, but changes stop following the user between apps.
  - **C:** keep independent stores with bidirectional synchronization; more conflict and recovery complexity.
- **[Codex R4] How should ComfyUI be hosted?**
  - **Harbinger answer (2026-10-19; recorded by Codex):** A. Isolated embedded ComfyUI view without native privileges, enabled after compatibility/security checks, with an external-browser fallback.
  - **A (recommended):** isolated embedded view without native privileges, enabled after a compatibility/security check, plus an external-browser fallback.
  - **B:** external browser only throughout the migration; lower integration cost.
  - **C:** a dedicated isolated Tauri window, keeping the main workspace separate; still requires the same checks.
- **[Codex R5] What performance evidence should block retiring a PySide6 feature?**
  - **Harbinger answer (2026-10-19; recorded by Codex):** A as the target, with C permitted for specific areas where optimization proves intractable. Aim for agreed responsiveness and memory budgets; defer difficult optimizations rather than blocking the entire migration. This is a case-specific exception, not a blanket removal of performance gates.
  - **A (recommended):** agreed responsiveness and memory budgets on representative datasets, alongside functional parity.
  - **B:** no material regression against measured PySide6 baselines; faster to define, but can preserve existing slow behavior.
  - **C:** functional parity first; performance tuning afterward, accepting temporary regressions.
  Measurements requiring benchmarks or full suites still follow the Codex/Harbinger authorization chain.
- **[Codex R6] How should desktop/backend updates stay compatible?**
  - **Harbinger answer (2026-10-19; recorded by Codex):** A. Ship desktop UI and sidecar as a tested version pair; remote servers negotiate a documented compatibility range.
  - **A (recommended):** ship desktop UI and its sidecar as one tested version pair; remote servers negotiate a documented compatibility range.
  - **B:** allow independent UI/sidecar updates within a supported protocol range; more flexible, larger compatibility matrix.
  - **C:** require exact versions for desktop and remote clients alike; simplest rules, disruptive coordinated upgrades.
- **[Codex R7] How should HIE, ASP and CSG join the main app?**
  - **Harbinger answer (2026-10-19; recorded by Codex):** Mostly C, with A where it makes sense. Prefer folding HIE/ASP/CSG frontend code into the main app; retain reusable views/shared host interfaces selectively where useful. Standalone shells are not a universal requirement.
  - **A (recommended):** package their views behind a small shared host interface; retain their standalone shells as adapters.
  - **B:** launch their standalone apps from the main app; simpler integration, fragmented navigation and state.
  - **C:** fold their frontend code into the main app; fewer shells, tighter release coupling and more disruptive repository changes.

### OpenCode — 2026-10-19 (all eight answered)

- **[OpenCode Q1] What is the unit of migration?**
  - **Harbinger answer (2026-10-19; recorded by OpenCode):** A. Capability/workspace is the unit; stitch is one record with eight routes and DL one with five.
  - **A (recommended):** capability/workspace, not route. One ledger record
    per user-visible capability; stitch is one record with eight routes and
    DL one with five, matching the 26 factories behind the 33 routes.
  - **B:** per route key. Finer progress, but shared stitch/DL workspaces get
    fragmented ownership and duplicated scaffolding.
  - **C:** per screen/tab as laid out today. Most literal, preserves the
    current UI's accidental grouping.
  - **D:** per service first, screens later. Cleanest seam, no visible
    migration for a long time and no early parity evidence.
- **[OpenCode Q2] How do we prove parity before deleting PySide6 code?**
  - **Harbinger answer (2026-10-19; recorded by OpenCode):** A, with B or C where a row requires it. Characterize-then-diff is the default; semantic acceptance specs and manual/pixel checks are permitted as complements, not replacements.
  - **A (recommended):** characterize current behavior first, then diff the
    old path and the new service on the same fixtures in CI while both ship;
    add framework-neutral acceptance for the UI.
  - **B:** one semantic acceptance spec that passes in both UIs. Cheaper, but
    only proves the paths the spec clicks.
  - **C:** a manual checklist signed per row. Simplest, weakest.
  - **D:** pixel/visual comparison. Catches layout drift, proves nothing
    about logic or data.
- **[OpenCode Q3] How strictly do we freeze new PySide6 work?**
  - **Harbinger answer (2026-10-19; recorded by OpenCode):** B. Freeze all of `gui/src` to reviewed bugfixes only. The ledger still records any exception, but the hash-allowlist/Qt-budget automation is not adopted.
  - **A (recommended):** content-hash allowlist plus a downward-only Qt
    import budget; no new/changed PySide6 UI without a reviewed ledger
    update, bugfixes possible but visible.
  - **B:** freeze all of `gui/src` to reviewed bugfixes only. Simpler, not
    automated.
  - **C:** convention only. Fastest in the moment; the surface grows back.
  - **D:** no freeze; fix bugs in both apps as needed. Highest drift and
    double-work cost.
- **[OpenCode Q4] Where does the canonical service layer live?**
  - **Harbinger answer (2026-10-19; recorded by OpenCode):** A. `backend/src/services/<feature>/`, delegating to `backend/src/core|database|web`, with `gui/`, `frontend/` and `api/` as clients.
  - **A (recommended):** `backend/src/services/<feature>/`, delegating to
    `backend/src/core|database|web`, with `gui/`, `frontend/` and `api/` as
    clients.
  - **B:** a new top-level `core/` package extracted from `backend/`. Cleaner
    in theory, repo-wide move before any feature is ported.
  - **C:** keep logic in today's `backend/src/` modules and add thin facades.
    Least churn, no explicit seam.
  - **D:** put services in `gui/src/services/` and call them through the
    sidecar. Reuses existing code, keeps domain logic in the layer being
    deleted.
- **[OpenCode Q5] What happens to the 224 PySide6 test files during the migration?**
  - **Harbinger answer (2026-10-19; recorded by OpenCode):** A. They remain the parity oracle; a test is deleted only with the code it covers and the Tauri replacement.
  - **A (recommended):** they are the parity oracle until their row passes;
    delete a test only with the code it covers and the Tauri replacement.
  - **B:** delete tests as soon as the code is extracted. Smaller load, loses
    the evidence.
  - **C:** maintain both suites in full until final deletion. Safest, every
    change written twice for months.
  - **D:** freeze them now and rely on the new harness. Fastest to converge,
    un-migrated areas unguarded.
- **[OpenCode Q6] When do we cut over CRA → Vite and delete Electron?**
  - **Harbinger answer (2026-10-19; recorded by OpenCode):** A. Wave 0, one announced PR; no feature work merges until build and the existing test are green.
  - **A (recommended):** Wave 0, one announced PR (Vite + React 19; remove
    `react-scripts`, Electron deps/scripts and `public/electron.js`); no
    feature work merges until build and existing test are green.
  - **B:** dual-build CRA and Vite for one wave, then delete CRA. Lower risk,
    two build configs to keep green.
  - **C:** defer until after the pilot. Early momentum, deprecated toolchain
    for every new file.
  - **D:** stay on CRA for the whole migration. Least immediate work, worst
    long-term cost.
- **[OpenCode Q7] How do we keep documentation from going stale?**
  - **Harbinger answer (2026-10-19; recorded by OpenCode):** A. Contract-hash freshness in CI, complementing generated references, `mkdocs --strict` and `lychee`.
  - **A (recommended):** contract-hash freshness in CI. Each module README
    carries the contract hash; a contract change without a README update
    fails the docs build. Generated references plus `mkdocs --strict` and
    `lychee` cover the rest.
  - **B:** review checklist only. Docs drift between releases.
  - **C:** generated docs only. Zero reference drift, no rationale or
    onboarding narrative.
  - **D:** treat the `.agent/` reports as the documentation. Complete
    history, not a usable developer guide.
- **[OpenCode Q8] How should parallel agents claim and land migration work?**
  - **Harbinger answer (2026-10-19; recorded by OpenCode):** C. Free-for-all claiming on GitHub issues; the ledger from Q1 still provides the inventory/delete gate, but it is not the ownership mechanism.
  - **A (recommended):** ledger-row ownership, one row per PR (code + tests
    + deletion + docs), claim on the bus and in the ledger, wait for the
    wave gate, second reviewer for deletions.
  - **B:** area owners (system, library, web, DL, editors, OS). Less
    negotiation, one agent becomes the area bottleneck.
  - **C:** free-for-all claiming on GitHub issues. Flexible, brings back the
    historical collision/duplicate-work failure mode.
  - **D:** one agent at a time. Simplest coordination, slowest by roughly
    the number of agents available.

### Grok — 2026-10-19 (all eight answered)

Harbinger's answers below supersede the original recommendations where they differ. Recorded by Grok, 2026-10-19. T1 uses a C++ still writer and the middle frame. T4 is mostly A, with B where parity requires a separate window. T6 places unlock and the database key in the C++ core. Scope still awaits the team final round.

- **[Grok T1] Where do gallery pixels come from?**
  - **Harbinger answer (2026-10-19; recorded by Grok):** A C++ service writes the bounded stills. The default frame number is the middle frame. The webview displays those cache files. This replaces the Python service and the first-frame default in A. B, C, and D were not selected.
  - **A (recommended):** A Qt-free thumbnail service writes bounded stills (first frame, max edge). The webview displays those cache files only. Animated preview is a separate, cancellable request for the focused item.
  - **B:** A Rust thumbnail command decodes for the grid, so the grid does not wait on the Python sidecar.
  - **C:** The webview decodes original files directly through the asset protocol.
  - **D:** Keep today's Rust `db.rs` / image commands as the thumbnail path until the library wave.
- **[Grok T2] When do we close the open asset scope and null CSP?**
  - **Harbinger answer (2026-10-19; recorded by Grok):** A. Wave 0, before Cloud Jobs Gate D or any other new UI. Default deny. Each feature declares roots. Originals are not in the scope.
  - **A (recommended):** Wave 0, before Cloud Jobs Gate D or any other new UI. Default deny. Each feature declares roots. Originals are not in the scope.
  - **B:** Tighten the scope as each feature migrates. Gate D may ship on the current `**` scope.
  - **C:** Leave `csp: null` and `scope: ["**"]` until PySide6 is gone.
- **[Grok T3] What is the navigation source of truth while both shells ship?**
  - **Harbinger answer (2026-10-19; recorded by Grok):** A. One serializable catalog, split out of `descriptor.py` so it does not import `QWidget`. Qt and Tauri both render it. Ids match the migration ledger.
  - **A (recommended):** One serializable catalog, split out of `descriptor.py` so it does not import `QWidget`. Qt and Tauri both render it. Ids match the migration ledger.
  - **B:** Tauri routes are handwritten. `ModuleCatalog` stays Qt-only until that area is deleted.
  - **C:** The React router becomes the source of truth now. The Qt registry is frozen and edited only to delete rows.
- **[Grok T4] How many native windows does the desktop have?**
  - **Harbinger answer (2026-10-19; recorded by Grok):** Mostly A, and B where a separate window is required for full feature parity. Default is one main webview. Add a dedicated Tauri window when a PySide6 window cannot reach parity as a route or panel.
  - **A (recommended):** One main webview. Preview, compare, settings, and Cloud Jobs are routes or panels. Extra native windows only for the tray, the slideshow/wallpaper presenter, and OS file dialogs.
  - **B:** One Tauri window for each current PySide6 window.
  - **C:** Several webviews inside one native frame, one per major area.
- **[Grok T5] Who starts the sidecar and the long-lived daemons?**
  - **Harbinger answer (2026-10-19; recorded by Grok):** A. A supervisor outside the webview starts the sidecar, the cloud-jobs daemon, and the slideshow daemon as siblings. Closing the window does not stop them. A sidecar crash does not drop daemon leases.
  - **A (recommended):** A supervisor outside the webview starts the sidecar, the cloud-jobs daemon, and the slideshow daemon as siblings. Closing the window does not stop them. A sidecar crash does not drop daemon leases.
  - **B:** The sidecar parents the daemons. The supervisor only restarts the sidecar, which then reattaches.
  - **C:** The Tauri shell starts all of them as `externalBin` children. Their lifetime follows the shell.
- **[Grok T6] Where may the vault password and database key live?**
  - **Harbinger answer (2026-10-19; recorded by Grok):** The C++ core module (`base/`) holds vault unlock and the database key. Not the Python sidecar (A), not the Tauri OS keychain (B), and not Rust (C).
  - **A (recommended):** Unlock stays in the sidecar. The webview holds a session handle only. Daemons hold leases, as Cloud Jobs already requires. Logs never contain the password or the SQLCipher key.
  - **B:** The Tauri shell stores the password in the OS keychain and passes it to the sidecar at launch.
  - **C:** Rust holds the unwrapped database key for the process lifetime and proxies queries itself.
- **[Grok T7] How should stitch, merge, and frame-slice canvases be ported?**
  - **Harbinger answer (2026-10-19; recorded by Grok):** A. One shared canvas host. A Wave 0 spike uses a fake document. Stitch is the first real editor after the Convert pilot. A failed budget uses the Codex R5 case-specific deferral.
  - **A (recommended):** One shared canvas host. A Wave 0 spike uses a fake document. Stitch is the first real editor after the Convert pilot. A failed budget uses the Codex R5 case-specific deferral.
  - **B:** Each editor keeps its own canvas. No shared host.
  - **C:** Leave the editor canvases on PySide6 until every other area has been deleted.
- **[Grok T8] What happens to Deep Learning UI that has not been built yet?**
  - **Harbinger answer (2026-10-19; recorded by Grok):** A. Freeze new Qt panels. Build the remaining Deep Learning UI in Tauri against the existing `record.json` / `events.jsonl` contract.
  - **A (recommended):** Freeze new Qt panels. Build the remaining Deep Learning UI in Tauri against the existing `record.json` / `events.jsonl` contract.
  - **B:** Finish the open Qt issue first, then freeze `gui/` Deep Learning panels.
  - **C:** Make the Deep Learning workspace the migration pilot, ahead of Convert.

## 6. Design axes to cover (suggestions, not a checklist)

1. **Bridge architecture.**
   - The options are a sidecar, Django, Rust, or a hybrid. Each needs a
     story for:
     - **contract and schema generation**, so types are never written
       twice;
     - **job progress and events**, which overlaps with Cloud Jobs
       `job_events` and the daemon IPC;
     - **cancellation;**
     - **error mapping**, to the `ImageToolkitError` hierarchy;
     - **auth**, including the vault.
2. **Logic extraction.**
   - What moves from `gui/src/helpers`, the tab controllers and
     `classes/` into backend application services?
   - How do services look under SOLID: interfaces, dependency injection,
     single responsibility?
   - How are the duplicate Rust implementations removed?
3. **Frontend platform.**
   - The build: Vite, or something else? Keep React (which HIE and the
     devtool use)?
   - State management, routing and the registry, and the
     window/multi-webview model.
   - The design system: porting the themes, and the component library.
   - Accessibility and keyboard shortcuts.
4. **The hard parts.**
   - wallpaper, the tray and the daemons;
   - large galleries and local media;
   - canvases and editors (WebGL, OffscreenCanvas, workers);
   - drag and drop;
   - ComfyUI embedding;
   - video;
   - the vault and crypto;
   - per-OS behaviour: Linux/KDE first?
5. **Migration mechanics.**
   - The parity definition and checks.
   - The feature inventory.
   - Order of waves, and the pilot.
   - Running both apps side by side: shared settings and config, shared
     database.
   - The deletion protocol.
   - Branch and merge policy: integration branches, as with milestone #10,
     or main?
6. **Modularity.**
   - The feature-module shape: a backend service, a contract and a
     frontend package.
   - Dependency rules and their enforcement: `import-linter`, ESLint
     boundaries, the LoC gate.
   - How the submodule front ends (HIE, ASP, CSG) plug in.
7. **Documentation.**
   - Contributor onboarding, and the architecture map and diagrams.
   - Per-module READMEs.
   - ADRs.
   - Generated references: sphinx, typedoc, the OpenAPI/contract schema.
   - Docs checked in CI.
   - A "how to add a feature" walkthrough.
8. **Testing.**
   - Contract tests.
   - Frontend unit tests: Vitest or Jest.
   - End-to-end tests: `tauri-driver`, WebDriver or Playwright.
   - Turning the existing pytest GUI scenarios into parity acceptance
     tests.
   - Visual regression.
9. **Packaging and distribution.**
   - Bundling the Python backend: a frozen sidecar or an external venv.
   - Updater, signing and installers.
   - What happens to `ImageToolkit.spec` and PyInstaller.
10. **Coexistence with in-flight work.**
    - Cloud Jobs Gate D in Tauri.
    - The Deep Learning rebuild workspace.
    - Mobile apps, which reuse the contracts.

## 7. Final round and decision

*(empty until the final brainstorming round)*
