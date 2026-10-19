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

- **Cursor** (2026-10-19):
  [Full proposal](../cursor/tauri_migration_refactor_proposal_2026-10-19.md).
  Adds the window and chrome the others leave as a table:
  - a **WindowManager role map** (labels, hide-all, pop-out) so Gate D
    is a panel with an optional `cloud.jobs` webview, not a new
    `TabId` and not a mandatory second window;
  - **EventHub as the generated in-app bus**; `appStore.ts` shrinks to
    ephemeral UI;
  - **Wave 0 shell**: catalog-driven rail/ribbon/inspector/status bar
    replacing `App.tsx`'s handwritten `TabId` union;
  - CSS variables from existing `gui/src/theming/tokens/`; one
    shortcut registry; native tray that ports
    `collect_background_windows()`;
  - dual installers until Qt is gone, then a frozen sidecar;
    `db.rs`'s `postgresql://localhost` default is deleted, not ported.
  Asks about Gate D window vs panel, EventHub vs `appStore`, tray
  timing, packaging, tokens, shortcuts, OS order, and `TabId`.
  - **Harbinger answered 2026-10-19:** W1–W8 all A. Gate D is a panel
    with pop-out; generated EventHub; Wave 0 tray and hide-all; dual
    installers then frozen sidecar; token CSS from existing JSON; one
    shortcut registry; Linux-first; `TabId` replaced by the catalog.

- **Kimi** (2026-10-19):
  [Full proposal](../kimi/tauri_migration_refactor_proposal_2026-10-19.md).
  Fills the seams the recorded answers leave open:
  - **Contract IDL:** JSON Schema per capability in `contracts/` plus a
    thin method-routing table; CI generates the TypeScript/Python/Rust
    types and the contract hash, so retiring a Rust duplicate is a
    route flip, not a rewrite;
  - **Coexistence rules for the shared encrypted store:** a
    single-instance gate on the data directory (no lock exists in
    either GUI today) and an expand/contract schema-migration
    discipline while a PySide6 row lives;
  - **Late-join event catch-up:** snapshot + bounded tail per EventHub
    channel, gaps resnapshot, durable jobs replay from persisted
    `job_events`/`events.jsonl`;
  - **Cancel/error envelopes:** one idempotent `job.cancel` with
    cooperative token + escalation, and a `{code, retryable,
    message_key, details}` error envelope mapped onto
    `backend/src/errors/`, no tracebacks in the webview;
  - **Two more Wave 0 spikes:** file drag-and-drop and video playback;
  - **Observability spine:** one log root across supervisor/sidecar/
    daemons, redacted **Diagnostics bundle** in Settings;
  - **Protocol unification:** the Cloud Jobs daemon speaks the sidecar
    envelope (its own method namespace), so the G1 remote client is a
    transport swap and Gate D is the first consumer of the canonical
    contract.
  Asks about the IDL, dual-app store access, event catch-up, Wave 0
  spike scope, the e2e harness, branch policy, schema-migration
  enforcement, and spike go/no-go authority. All eight pending.

- **Gemini** (2026-10-19):
  [Full proposal](../gemini/tauri_migration_refactor_proposal_2026-10-19.md).
  Focuses on DRY and SOLID enforcement and architectural boundaries:
  - **C++ Core (`base/`) Boundary:** Python sidecar exclusively hosts the
    compiled `base` pybind11 module; Rust remains a thin window/tray shell
    without C++ linkage, securing vault unlock and the SQLCipher key in C++
    memory without IPC exposure.
  - **Zero-Copy High-Throughput Binary Pipeline:** Bounded local cache
    directory (`~/.image-toolkit/cache/render/`) for rendered stills and tiles,
    streamed directly into the webview via Tauri's hardware-accelerated
    `asset://` protocol, avoiding stdio pipe choking and base64 bloat.
  - **WebGL2 / WebGPU Shared Canvas Host:** Dynamic tile-pyramid canvas
    managed by an off-screen Web Worker for panning, deep zooming, sub-pixel
    alignment, and seam editing across panoramas exceeding 50,000 px.
  - **SOLID Service Extraction:** Command/Handler pattern with Python
    `@runtime_checkable` `Protocol` interfaces in `backend/src/services/<feature>/`.
    Existing Qt workers become 15-line shims delegating to pure services until
    deleted.
  - **Submodule Consolidation:** Unify ASP, HIE, and CSG C++ routines into
    the root `base/CMakeLists.txt` build tree and relocate backend code into
    `backend/src/services/`.
  - **Human Developer Documentation Spine:** MkDocs Material documentation
    with immutable ADRs in `docs/adr/`, C4 architecture diagrams, a "How to Add
    a Capability" guide, and React component Storybook in `frontend/`.

- **Mistral** (2026-10-19):
  [Full proposal](../mistral/tauri_migration_refactor_proposal_2026-10-19.md).
  Adds the pieces the recorded answers leave mechanism-less:
  - **Tauri 2 capability ACL as the Wave 0 lockdown mechanism** (Grok
    T2): one capability file per labeled window, asset scope declared
    per capability instead of the global `tauri.conf.json` (`csp: null`,
    `scope: ["**"]` today), and a CI check failing on wildcards and on
    capabilities with no ledger row.
  - **Wave 0 as three ordered PRs** — build/security, then shell, then
    bridge spine — with an explicit done checklist, since the recorded
    Wave 0 decisions already number nine.
  - **Bridge restart contract:** `bridge.down`/`bridge.ready` events,
    error envelope for in-flight requests, durable jobs reattach, and
    a SIGKILL smoke test in CI. Complements Kimi Q3 (late-join
    catch-up); this covers crash recovery.
  - **A `routes: {old → catalog_id, alias?}` field per ledger row**, so
    navigation intent survives and shortcuts, docs and stored settings
    keep working after route consolidation.
  Asks about navigation restructuring, post-pilot wave order,
  accessibility parity scope, i18n scope, sidecar embedding during
  coexistence, the restart contract, and bridge-code sharing with the
  devtool sidecar.

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

### Cursor — 2026-10-19 (all eight answered)

Harbinger's answers below match the recommendations. Recorded by Cursor, 2026-10-19. Scope still awaits the team final round.

- **[Cursor W1] How does Cloud Jobs Gate D appear in Tauri?**
  - **Harbinger answer (2026-10-19; recorded by Cursor):** A. Panel in `main` with a WindowManager pop-out that creates a labeled `cloud.jobs` webview. Header badge stays on `main`. Child window has no `**` asset scope.
  - **A (recommended):** Panel in `main` with a WindowManager pop-out that creates a labeled `cloud.jobs` webview. Header badge stays on `main`. Child window has no `**` asset scope.
  - **B:** Always a native `cloud.jobs` webview, for parity with the locked PySide6 standalone window.
  - **C:** Route only. No pop-out in v1.
  - **D:** A new `TabId` in today's `App.tsx` switcher, so Gate D can ship before the catalog shell.
- **[Cursor W2] What is the in-app event bus?**
  - **Harbinger answer (2026-10-19; recorded by Cursor):** A. Generated EventHub intents/facts. Sidecar emits them. `appStore.ts` is ephemeral UI only.
  - **A (recommended):** Generated EventHub intents/facts. Sidecar emits them. `appStore.ts` is ephemeral UI only.
  - **B:** React store (`appStore.ts` / Redux) is the source of truth. EventHub dies with Qt.
  - **C:** No in-webview bus. Every view polls the sidecar.
  - **D:** Keep EventHub (Qt) and `appStore.ts` (Tauri) with a manual mapping until the last Qt row.
- **[Cursor W3] When does close-to-background / tray land?**
  - **Harbinger answer (2026-10-19; recorded by Cursor):** A. Wave 0 native tray. Closing `main` hides every labeled window (port of `collect_background_windows`). Supervisor keeps sidecar and daemons.
  - **A (recommended):** Wave 0 native tray. Closing `main` hides every labeled window (port of `collect_background_windows`). Supervisor keeps sidecar and daemons.
  - **B:** Tray after the Convert pilot. Until then, closing `main` quits the UI; daemons keep running.
  - **C:** No tray until PySide6 is gone. Tauri uses the OS taskbar minimize only.
  - **D:** Qt keeps the only tray for the whole coexistence period.
- **[Cursor W4] How do we package while both apps ship?**
  - **Harbinger answer (2026-10-19; recorded by Cursor):** A. Dual installers until the last Qt row is deleted (current PyInstaller AppImage/deb + Tauri bundle). Then one Tauri installer with a frozen sidecar. `ImageToolkit.spec` dies with PySide6. Canonical version stays `pyproject.toml`.
  - **A (recommended):** Dual installers until the last Qt row is deleted (current PyInstaller AppImage/deb + Tauri bundle). Then one Tauri installer with a frozen sidecar. `ImageToolkit.spec` dies with PySide6. Canonical version stays `pyproject.toml`.
  - **B:** One installer that can launch either UI.
  - **C:** Tauri-only packaging from Wave 0; PySide6 is source-run during the migration.
  - **D:** PyInstaller remains the only release channel; Tauri is an unpackaged extra.
- **[Cursor W5] Where do visual tokens come from?**
  - **Harbinger answer (2026-10-19; recorded by Cursor):** A. Generate CSS variables from `gui/src/theming/tokens/{light,dark}.json` in Wave 0. Both shells consume them. Do not hand-port QSS.
  - **A (recommended):** Generate CSS variables from `gui/src/theming/tokens/{light,dark}.json` in Wave 0. Both shells consume them. Do not hand-port QSS.
  - **B:** New Tauri visual language. Qt stays on QSS until deleted.
  - **C:** Import the QSS files as raw CSS.
  - **D:** Unstyled until after functional parity.
- **[Cursor W6] Where do keyboard shortcuts live?**
  - **Harbinger answer (2026-10-19; recorded by Cursor):** A. One serializable registry lifted from `shortcut_manager.py` / `keybindings.json`. Both shells bind it. Tauri global shortcuts only for tray show/hide.
  - **A (recommended):** One serializable registry lifted from `shortcut_manager.py` / `keybindings.json`. Both shells bind it. Tauri global shortcuts only for tray show/hide.
  - **B:** Hand-write React hotkeys per view.
  - **C:** Defer shortcuts until after visual parity.
  - **D:** OS-level global shortcuts for every action.
- **[Cursor W7] Which OS is Gate D allowed to miss?**
  - **Harbinger answer (2026-10-19; recorded by Cursor):** A. Linux is the Wave 0 + Convert + Cloud Jobs Gate D platform. Windows and macOS follow per capability after the Linux row passes.
  - **A (recommended):** Linux is the Wave 0 + Convert + Cloud Jobs Gate D platform. Windows and macOS follow per capability after the Linux row passes.
  - **B:** Linux and Windows from Wave 0; macOS later.
  - **C:** All three from Wave 0.
  - **D:** Whatever the implementing agent can run.
- **[Cursor W8] What happens to `App.tsx`'s handwritten `TabId` union?**
  - **Harbinger answer (2026-10-19; recorded by Cursor):** A. Wave 0 replaces it with the serializable catalog. Existing `*Tab.tsx` files remain views behind catalog ids. No feature adds a `TabId` member, including Cloud Jobs.
  - **A (recommended):** Wave 0 replaces it with the serializable catalog. Existing `*Tab.tsx` files remain views behind catalog ids. No feature adds a `TabId` member, including Cloud Jobs.
  - **B:** Keep `TabId` until each tab is rewritten. Catalog is Qt-only until then.
  - **C:** Dual navigation (catalog + `TabId`) until the Convert pilot lands.
  - **D:** Freeze `App.tsx` as-is and put new UI in a parallel shell tree.

### Kimi — 2026-10-19 (all eight pending)

Recommendation first in each list. None re-ask a recorded answer; full
rationale in the
[proposal](../kimi/tauri_migration_refactor_proposal_2026-10-19.md).

- **[Kimi Q1] Which IDL generates the contract types?**
  - **A (recommended):** JSON Schema per capability in `contracts/`,
    plus a thin method-routing table; CI generates TS/Python/Rust types
    and the contract hash. Fits stdio and Django alike, no new runtime
    deps.
  - **B:** OpenAPI 3.1 for everything, stdio methods as operations. One
    spec, but HTTP framing fights JSON-RPC ergonomics.
  - **C:** Hand-written TypeScript + zod as the source, generate the
    rest. The sidecar — the runtime of record — would consume Python
    generated from hand-written TS.
  - **D:** protobuf/buf. Strongest codegen, heaviest toolchain; event
    streams need a second story.
- **[Kimi Q2] May both GUIs run at once against one `library.db`?**
  - **A (recommended):** No. Single-instance gate on the data directory;
    second launch focuses the running app (tray show/hide). The lock
    lives in the data dir so both apps share it; WAL stays on for
    readers within one process.
  - **B:** Yes — WAL + busy_timeout; accept `database is locked` stalls
    in the other app during long writes.
  - **C:** Yes, with the second app opening the store read-only. Safe
    for the library, but the second app can't edit anything.
- **[Kimi Q3] How do late-joining views catch up on events?**
  - **A (recommended):** Snapshot + bounded tail per EventHub channel,
    sequence-numbered; gaps trigger a resnapshot; durable jobs replay
    from persisted `job_events`/`events.jsonl`.
  - **B:** Full persisted event log replay for every channel. Simplest
    model, permanent storage and ordering cost.
  - **C:** No replay. Late joiners poll current state; pop-outs and
    reopened windows show stale progress until the next state change.
- **[Kimi Q4] Which hard parts get Wave 0 spikes?**
  - **A (recommended):** The four already listed, plus file
    drag-and-drop and video playback (fake-document spikes like the
    canvas one).
  - **B:** Only the four already listed; DnD and video are handled
    inside their feature waves.
  - **C:** Every §6.4 hard part gets a spike, including wallpaper and
    per-OS tray specifics. Wave 0 becomes a milestone of its own.
- **[Kimi Q5] What runs end-to-end in CI?**
  - **A (recommended):** Layered. Playwright against the Vite build
    with contract mocks is the per-PR gate; tauri-driver WebDriver is a
    per-release smoke. Parity evidence still comes from the pytest
    scenarios (OpenCode Q2/Q5).
  - **B:** tauri-driver for everything. Real shell, slow and flaky CI.
  - **C:** Component/unit tests only; e2e deferred until a wave needs
    it.
- **[Kimi Q6] Where does migration work land?**
  - **A (recommended):** Per-capability branches, PR to main, CI gates
    (build, LoC gate, docs freshness). Matches free-for-all claiming
    (OpenCode Q8) and keeps main releasable for dual installers
    (Cursor W4).
  - **B:** Direct commits to main, CI as the only gate. No review
    checkpoint for deletions.
  - **C:** Long-lived integration branch per wave, merged at wave end.
    Defers all parity evidence to merge day.
- **[Kimi Q7] How is schema-migration discipline enforced during
  coexistence?**
  - **A (recommended):** CI checks additive-only: a migration touching a
    live Qt row's tables must add, not rename/drop; destructive steps
    ride with the row's deletion PR.
  - **B:** Reviewer discipline only; the rule lives in AGENTS.md.
  - **C:** No rule — both apps release in lockstep. False while dual
    installers ship (Cursor W4).
- **[Kimi Q8] Who decides Wave 0 spike go/no-go, and what does "no-go"
  mean?**
  - **A (recommended):** Harbinger decides per spike, on Codex's review,
    with a written no-go outcome: that feature's PySide6 row stays
    alive past its wave (bounded exception list in the ledger), not a
    re-scope of the initiative.
  - **B:** No-go ⇒ initiative re-scope discussion per case.
  - **C:** Spikes are informational; waves decide by budget (Codex R5)
    alone.

### Gemini — 2026-10-19 (all six pending)

- **[Gemini G1] C++ Core (`base/`) Binding Architecture:**
  - **A (recommended):** Python sidecar exclusively hosts `base/`. The compiled `base` pybind11 module remains exclusively in the Python sidecar process. Rust remains a lightweight native shell without C++ linkage. Vault unlock is passed from webview to sidecar over stdio, where C++ secures the credentials in memory.
  - **B:** Dual linkage. Rust links directly to `base/` via C FFI for vault and database key management, while Python links to `base/` via pybind11 for image processing and computer vision algorithms.
  - **C:** Native Rust crypto re-implementation. Rust calls `libitk_crypto.so` directly via Rust FFI to manage vault unlocking, bypassing both Python and `base/`.
- **[Gemini G2] High-Throughput Binary & Canvas Tile IPC Protocol:**
  - **A (recommended):** Zero-copy local file cache + Tauri asset streaming protocol. Services write rendered tiles/frames to a bounded scratch cache (`~/.image-toolkit/cache/render/`). JSON-RPC responses return local URIs, which the webview streams directly via Tauri's hardware-accelerated `asset://` protocol.
  - **B:** Length-prefixed binary multiplexing on stdio. Custom binary framing interleaved with JSON-RPC over the stdio stream.
  - **C:** Pure Base64 in JSON-RPC. Encode all image buffers directly into standard JSON-RPC payloads, accepting CPU and memory overhead for simplicity.
- **[Gemini G3] Shared Canvas Host Rendering Engine:**
  - **A (recommended):** WebGL2 / WebGPU dynamic tile-pyramid canvas. An off-screen Web Worker calculates viewport frustum culling and requests dynamic level-of-detail tiles, rendered via a custom WebGL2 texture shader.
  - **B:** HTML5 Canvas 2D with viewport windowing. Use standard 2D canvas context with software-based coordinate slicing.
  - **C:** Embedded OpenSeadragon / Leaflet library. Adapt an off-the-shelf deep-zoom viewer library for stitching and editing canvases.
- **[Gemini G4] Service Extraction Pattern for Qt Workers & Controllers:**
  - **A (recommended):** Command/Handler pattern with Protocol interfaces. Extract domain logic into pure Python `Service` classes implementing `@runtime_checkable` `Protocol`s with frozen dataclasses. PySide6 `QThread` workers become 15-line shims delegating to the service, and the sidecar exposes the identical service methods over stdio.
  - **B:** Internal event bus refactor. Replace worker threads with a decoupled internal event queue where UI and services communicate purely via message events.
  - **C:** Direct procedural function extraction. Extract worker `run()` bodies into procedural helper functions without formal interfaces or dependency injection.
- **[Gemini G5] Submodule C++ and Backend Unification (ASP, HIE, CSG):**
  - **A (recommended):** Unified CMake & service namespaces. Merge submodule C++ build routines into the main `base/CMakeLists.txt` and relocate Python backend code to `backend/src/services/{asp,hie,csg}/`, sharing OpenCV and crypto linkages.
  - **B:** Independent Python wheels. Package each submodule as a distinct Python wheel installed into the runtime venv.
  - **C:** Child subprocess sidecars. Keep submodules as independent external processes spawned and controlled via stdio child processes.
- **[Gemini G6] Developer Documentation & Architecture Knowledge Base:**
  - **A (recommended):** MkDocs Material documentation + ADRs + component Storybook. Establish `docs/adr/` for decision records, C4 model diagrams in MkDocs, a concrete "Adding a Capability" guide, and Storybook in `frontend/` for React components, all validated in CI.
  - **B:** Sphinx Python autodoc only. Rely primarily on Sphinx generated documentation from Python docstrings.
  - **C:** Repo-root Markdown files. Maintain plain Markdown files in the repository root without static site generation or Storybook.

### Mistral — 2026-10-19 (all seven answered)

Harbinger answered all seven on 2026-10-19, matching the
recommendations. Full rationale in the
[proposal](../mistral/tauri_migration_refactor_proposal_2026-10-19.md).

- **[Mistral M1] May the Tauri app consolidate user-visible
  navigation?** OpenCode Q1 fixed the ledger unit, not whether the
  user's navigation may change (33 routes, 26 factories today).
  - **Harbinger answer (2026-10-19):** A. Restructuring allowed within
    a row where behavior is preserved; the row records its old-route →
    catalog-id map; routes referenced by shortcuts, docs or stored
    settings get compat aliases. Cross-row merges need Harbinger
    sign-off.
  - **B:** strict 1:1 route parity until every row passes;
    consolidation is a post-migration release.
  - **C:** free restructure; the catalog is the only map.
- **[Mistral M2] Which area wave follows the Convert pilot and Cloud
  Jobs Gate D?**
  - **Harbinger answer (2026-10-19):** A. Library/database (gallery,
    search, tags, groups) — first full exercise of the C++ thumbnail
    pipeline (T1) and asset-protocol streaming.
  - **A (recommended):** library/database (gallery, search, tags,
    groups). Largest user value, first full exercise of the C++
    thumbnail pipeline (T1) and asset-protocol streaming.
  - **B:** editors (stitch, merge, frame-slice). Retires the hardest
    canvases while the Wave 0 canvas spike is fresh; front-loads the
    risk.
  - **C:** web/system (crawlers, utilities, preferences). Thinnest UIs,
    cheapest porting muscle, least user-visible progress.
  - **D:** Harbinger assigns per agent availability; no fixed order.
- **[Mistral M3] What does accessibility parity mean per row?**
  - **Harbinger answer (2026-10-19):** A. Keyboard parity is a row-pass
    criterion; screen-reader support is best-effort with a known-gaps
    list in each module README, revisited after PySide6 is gone.
  - **A (recommended):** keyboard parity is a row-pass criterion (one
    shortcut registry, W6, makes it checkable); screen-reader support
    is best-effort with a known-gaps list in each module README,
    revisited after PySide6 is gone.
  - **B:** full screen-reader parity is a row-pass criterion; deletion
    blocked until each row passes an a11y audit.
  - **C:** keyboard parity only; screen-reader work explicitly out of
    scope for this initiative.
- **[Mistral M4] Is i18n in scope?** The Qt GUI has no QTranslator or
  message-catalog infrastructure today (English-only).
  - **Harbinger answer (2026-10-19):** A. Status quo — English-only,
    out of scope for this initiative; ported views still avoid
    hard-coded sentence concatenation so extraction stays cheap later.
  - **A (recommended):** status quo — English-only, out of scope for
    this initiative; ported views still avoid hard-coded sentence
    concatenation so extraction stays cheap later.
  - **B:** wire i18n in Wave 0 (message catalog + key extraction);
    every ported view uses keys from day one; translations later.
  - **C:** full localization before the PySide6 deletion gate.
- **[Mistral M5] How does the Tauri bundle embed the Python sidecar
  during coexistence?** W4 decided dual installers and the eventual
  frozen sidecar, not what the Tauri installer launches for Python
  while both apps ship.
  - **Harbinger answer (2026-10-19):** A. Both installers use the one
    installed backend environment per machine; the Tauri supervisor
    spawns the sidecar from it. Freezing happens only at Qt deletion,
    as W4 already decided.
  - **A (recommended):** both installers use the one installed backend
    environment per machine; the Tauri supervisor spawns the sidecar
    from it. One Python to update during coexistence; freezing happens
    only at Qt deletion, as W4 already decided.
  - **B:** the Tauri installer embeds its own sidecar now
    (PyInstaller-collected or python-build-standalone). Heavier
    installer; two Python environments to keep in sync mid-migration.
  - **C:** the sidecar runs from a uv-managed, first-launch-resolved
    environment (lock file shipped, interpreter fetched on demand).
    Reproducible, adds a first-run network dependency.
- **[Mistral M6] What is the recovery contract when the supervisor
  restarts the sidecar?**
  - **Harbinger answer (2026-10-19):** A. `bridge.down`/`bridge.ready`
    events, error envelope for in-flight session requests, durable
    jobs reattach on `bridge.ready`, route and ephemeral UI state
    preserved, and a SIGKILL smoke test in CI.
  - **A (recommended):** `bridge.down`/`bridge.ready` events, error
    envelope for in-flight session requests, durable jobs reattach on
    `bridge.ready`, route and ephemeral UI state preserved, and a
    SIGKILL smoke test in CI.
  - **B:** the webview fully reloads on sidecar restart. Simplest
    mental model; loses all UI state on every crash.
  - **C:** each view implements its own recovery. Flexible, unbounded
    divergence across 26 rows.
- **[Mistral M7] Does the main app share bridge code with the devtool
  sidecar?** The devtool precedent (D51, `dev/tool/devtool.py`) chose
  the same model Codex R1 chose for the main app.
  - **Harbinger answer (2026-10-19):** A. One small bridge package
    (framing, envelope, version handshake, generated clients) consumed
    by both; the devtool migrates opportunistically, blocking no wave.
  - **A (recommended):** extract one small bridge package (framing,
    envelope, version handshake, generated clients) consumed by both;
    the devtool migrates opportunistically, blocking no wave.
  - **B:** the main app builds its own bridge; the devtool keeps its
    private one. Accept the duplicate until the devtool's next major
    revision.
  - **C:** make the devtool's sidecar the canonical package and consume
    it from the main app. Couples the app's release cadence to a dev
    utility.

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
