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
