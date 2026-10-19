# Tauri Migration and Architecture Refactor — Claude's proposal (2026-10-19)

Brief: `.agent/reports/team/tauri_migration_refactor_2026-10-19.md`. This
is a proposal only.

## Summary

Porting 106,000 lines of PySide6 screen by screen into React would move
the existing duplication and Qt-shaped logic into a second language. The
order I'd use instead:

1. **Extract the logic.** Move it out of the Qt layer into Qt-free
   application services, each with one typed contract.
2. **Build the frontend platform once.** That means the build, tokens,
   components, routing and the bridge client.
3. **Port the views.** At that point the views are thin, so porting them
   is mostly mechanical.

That order is also the DRY/SOLID refactor. The migration and the refactor
are the same piece of work done in the right order, not two separate
projects. Deleting each PySide6 feature is gated on a parity matrix that
is generated rather than hand-maintained.

## Ideas

### 1. Application services: the logic moves out of the Qt layer first

- **What moves:**
  - the `QThread` workers in `gui/src/helpers/` (42 of its 73 files import
    PySide6);
  - tab-controller orchestration and validation;
  - the `classes/` bases' non-visual logic.

  It moves into `backend/src/services/<feature>/`. Each service is a
  plain class with constructor-injected dependencies (repositories,
  clients, settings) and one responsibility.
- **How long-running work reports back.** Every long-running operation
  returns a `TaskHandle`, a single protocol for progress, cancellation,
  results and errors. The Cloud Jobs `job_events` shape and its daemon
  IPC should be **the same event protocol, not a second one**.
- **Errors** map from the `ImageToolkitError` hierarchy to stable error
  codes that the frontend can switch on.
- **Pro:** both UIs become thin during the migration, so parity bugs
  become view bugs, not logic forks.
- **Con:** extraction happens before any visible Tauri progress. The
  pilot (idea 6) keeps that phase short and proves the pattern.

### 2. One contract, generated clients

- **Where types come from.** Service request and response models
  (Pydantic) are the single source. A generator emits:
  - a JSON Schema / OpenAPI document;
  - a TypeScript client and types for `frontend/`;
  - Rust types only where a Rust command needs them.
- **Drift is a build failure.** A CI check regenerates the client and
  fails on any diff, so the frontend and backend can't drift.
- **Rust duplicates go.** The duplicated Rust implementations are
  deleted: `db.rs` queries, convert, merge and video extraction. Rust
  keeps **only** native or OS work:
  - window management and the tray;
  - file dialogs and drag and drop;
  - notifications;
  - and, if profiling ever proves it necessary, a hot path. That would be
    the exception, not the default.

### 3. The bridge (open per Q0c): my recommendation is a hybrid with one service layer

- **A local Python sidecar** is the desktop bridge.
  - Tauri spawns and supervises it, and authenticates it with a
    per-launch token over localhost or stdio.
  - It is the devtool D51 precedent, so it adds no new runtime idea.
- **Django `api/` becomes a second adapter over the same services,** used
  for the remote, mobile and Cloud Jobs G1 cases. Neither adapter contains
  logic.
- **Rust commands** handle native work only, as above.
- **Why not Django alone?** Its startup cost and process model fit a
  server, not a desktop app that has to start offline. Also, the desktop
  must not depend on Celery or Redis being up.
- **Why not the sidecar alone?** Mobile and remote clients need a network
  API with real auth. Building that inside the sidecar would mean a second
  Django.

### 4. The frontend platform comes before porting

- **Build:** replace CRA (deprecated) with **Vite**, which the devtool
  uses, and drop the leftover Electron entries. Keep React 19, because HIE
  and the devtool already use it.
- **Tokens:** design tokens are generated from the `gui/src/theming`
  palettes, so the themes become CSS variables. Light and dark, and the
  user's custom themes, carry over as data.
- **Components:** a component library that mirrors `gui/src/components`:
  - a virtualised gallery (`@tanstack/react-virtual`) with the new
    height-resize grips, and single- and two-gallery variants;
  - forms bound to the contract;
  - the risk-feedback styling from Cloud Jobs (recoloured controls, ⚠
    warnings, greyed-out options), as a shared primitive;
  - dialogs and toasts.
- **Routing and registry:** routes are generated from one feature registry
  that replaces `_tab_registry.py`, so the sidebar, routes, the parity
  matrix and the docs all read from the same data.
- **Multi-window:** Tauri `WebviewWindow` for preview, compare, slideshow,
  Cloud Jobs and Settings. State is shared through the sidecar, not
  through the webviews talking to each other.

### 5. A parity matrix as the deletion gate

- **Inventory:** generated from `_tab_registry.py`, `windows/`, the tray
  menu, the dialogs and the daemon controls. That is about 60 routes plus
  the windows.
- **One row per feature:**
  - PySide6 location and Tauri location;
  - service contract;
  - acceptance scenarios;
  - status: `pyside-only`, `both`, `parity-passed` or `pyside-deleted`.
- **Where the scenarios come from:** the existing `--run-gui` pytest
  scenarios, rewritten as framework-neutral acceptance specs. One spec
  then drives both a Qt test and a Tauri end-to-end test (WebDriver
  through `tauri-driver`), so parity is the same spec passing twice.
- **Deletion protocol:**
  1. The parity spec is green in CI.
  2. Harbinger signs off on that row.
  3. A PR deletes the PySide6 code and tests for that row, and nothing
     else.

### 6. Migration order

1. **Wave 0, platform:**
   - the Vite move;
   - tokens and the core components;
   - the contract generator and generated client;
   - sidecar supervision;
   - the parity matrix;
   - documentation scaffolding (idea 8).
2. **Pilot:** **Convert** end to end. It's small, already partly in Tauri,
   and exercises a service, a `TaskHandle`, the gallery and settings. This
   is where the pattern gets proven or revised.
3. **The Cloud Jobs window** (Cloud Jobs Gate D), as the first Tauri-only
   feature. It is new code, so there's nothing to port.
4. **Area waves**, ordered by how hard and how central each area is:
   1. system: merge, extractor, similarity;
   2. library and database;
   3. web: crawler, requests, sync, media loader;
   4. wallpaper: daemons and per-monitor; OS-heavy;
   5. deep learning: the workspace, and ComfyUI embedding, now just a
      webview;
   6. editors and canvases: stitch, HIE, manga (ASP and CSG front ends
      plug in as packages, the way `hie-frontend` already does);
   7. Settings, the tray, authentication and the vault.
5. **Final:**
   - remove PySide6, `ImageToolkit.spec`, and the Qt dependencies;
   - rewrite the ROADMAP's Tri-Interface section;
   - packaging, signing and the updater for the Tauri bundle with the
     frozen sidecar.

### 7. Modularity that is enforced

- **One shape per feature module:**
  - `backend/src/services/<feature>/`, holding the service, the
    contract, and tests;
  - `frontend/src/features/<feature>/`, holding views, hooks, and tests;
  - a `feature.toml` manifest naming its routes, contracts, windows,
    settings keys, and owners.
- **Boundaries are checked in CI:**
  - **Python:** `import-linter` contracts:
    - services may not import web or GUI code;
    - features may not import other features' internals;
    - only `services/<x>/api.py` is public.
  - **TypeScript:** `eslint-plugin-boundaries`, with the same rules for
    `features/`.
  - **The LoC gate** stays and applies to TypeScript and TSX too.
- **SOLID in practice:**
  - repositories behind protocols, so tests use in-memory fakes;
  - no singletons reached through globals;
  - settings injected, not read ad hoc;
  - cross-feature communication only through contracts or the event bus.

### 8. Documentation for the next human

- **`docs/adr/`:** an Architecture Decision Record (ADR) for every locked
  decision, starting with the bridge, Vite, the parity gate and the
  service shape. Copy the decision tables already written in the devtool
  roadmap and the Cloud Jobs roadmap; don't rewrite them.
- **A per-module README template**, checked by CI to exist for each
  feature module. It covers purpose, contract, events, settings, and how
  to test.
- **A "how to add a feature" guide**, which is the pilot written up as a
  walkthrough.
- **A generated architecture map:**
  - module and dependency graphs from `import-linter` and the manifests;
  - the API reference from the contract (OpenAPI), sphinx for the
    services, typedoc for the frontend;
  - all of it built by mkdocs in CI, so a broken docs build fails the PR.
- **`docs/DEVELOPMENT.md`** grows from 50 lines into a real onboarding
  path: setup, run, test, debug the sidecar, and where things live.

### 9. Testing

- **Contract tests** per service.
- **Vitest** for the frontend, replacing CRA's Jest.
- **End to end:** `tauri-driver` / WebDriver through the parity specs.
- **Visual regression** for the component library only, not for every
  screen.

## Risks

1. **Big-bang drift.** Two apps diverge while both are maintained.
   Mitigation: logic lives only in services, and PySide6 gets fixes only
   for features that are already `both`.
2. **OS-specific behaviour.** KDE wallpaper, the tray on Wayland, and
   multi-monitor setups behave differently. The logic is already in
   Python and the daemons, so the risk is in the controls and the tray.
   These need live desktop tests, which agents can't do. Harbinger
   validates them.
3. **Canvas performance.** The stitch, merge and frame-slice editors may
   need WebGL or OffscreenCanvas. They are the last wave, so the platform
   has matured by then.
4. **Sidecar packaging.** Freezing torch and CUDA wheels into a sidecar is
   large, and startup time matters. This needs a spike in Wave 0.
5. **Scope collision.** The same files will be touched by this work and
   the Cloud Jobs Gates A–C backend work. Mitigation: services extraction
   doesn't touch `backend/src/cloud/`, and Cloud Jobs gets
   `services/cloud_jobs` from the start.

## Q. Questions for Harbinger

Recommended option first.

1. **Pilot feature.**
   - (a) **Convert**: small, partly ported already, and exercises every
     layer.
   - (b) Wallpaper: the hardest OS integration, so the biggest risks show
     up early.
   - (c) Library search: the most-used feature and the largest data path.
2. **Python packaging in the shipped app.**
   - (a) **A frozen sidecar (PyInstaller) bundled through Tauri's
     `externalBin`, with heavy ML extras downloaded on first use.**
   - (b) A frozen sidecar that includes all ML dependencies; a large
     installer.
   - (c) An external Python environment that the user installs; small,
     but harder to set up.
3. **What "parity" means.**
   - (a) **Same capabilities and same settings keys, with the layout free
     to improve.** Deviations go in the parity row.
   - (b) Pixel-close replicas of the PySide6 screens.
   - (c) Capabilities only; settings can be reset.
4. **Branching.**
   - (a) **Main, behind the parity matrix.** Both apps ship, so there is
     nothing to hide in a long-lived branch.
   - (b) An integration branch per wave, as with milestone #10.
   - (c) One long-lived migration branch.
5. **Platforms during the migration.**
   - (a) **Linux/KDE first, then Windows, then macOS,** with per-platform
     parity columns.
   - (b) All three at every wave.
6. **Framework.**
   - (a) **Keep React 19 on Vite,** matching HIE and the devtool.
   - (b) Svelte or Solid, which are lighter but rewrite HIE integration.
7. **Mobile apps.**
   - (a) **Consume the same generated contracts through the Django
     adapter;** no mobile UI work in this milestone.
   - (b) Add mobile parity to this milestone.
8. **Who validates OS-specific parity** (tray, wallpaper, multi-monitor,
   Wayland)?
   - (a) **Harbinger, from a checklist per row; agents prepare the
     checklist and the automated part.**
   - (b) Automated tests only, accepting the gaps.

— Claude, 2026-10-19
