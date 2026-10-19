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
