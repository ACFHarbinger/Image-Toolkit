# Tauri Migration and Architecture Refactor

**Status:** LOCKED 2026-10-19. Harbinger and Claude locked this after an
eight-agent proposal round (Claude, Codex, Gemini, Grok, Cursor, Mistral,
Kimi, OpenCode) and a final brainstorming round.

- **Tracking:** two GitHub milestones, **Tauri Migration — Wave 0
  (Platform & Feasibility)** and **Tauri Migration — Feature Waves**.
  The tracking issue is [#864](https://github.com/ACFHarbinger/Image-Toolkit/issues/864), and the issues are listed in §3.
- **This document** holds the design and the order; the issues hold
  status and owners.

**Origin:** Harbinger asked for four things:

1. migrate every feature of the PySide6 GUI (`gui/`) to the Tauri app
   (`frontend/`);
2. refactor for DRY and SOLID;
3. make the architecture modular, with boundaries enforced by tooling;
4. write documentation that serves future human developers.

It runs alongside the Cloud Jobs Service (`cloud_jobs.md`).

**Sources:**

- The brief, all 54 recorded answers, and the final round (§7):
  `.agent/reports/team/tauri_migration_refactor_2026-10-19.md`.
- Each agent's proposal:
  `.agent/reports/<agent>/tauri_migration_refactor_proposal_2026-10-19.md`.

**Supersedes:** the "Tri-Interface Strategy" in `docs/moon/ROADMAP.md`.
There, PySide6 was the pro desktop and Tauri a companion hub; now Tauri
is the only desktop UI.

---

## 1. Target architecture

```
React (Vite) webview ─┬─ Rust shell: windows, tray, dialogs, DnD, asset:// (no logic)
                      └─ JSON-RPC/stdio ─▶ Python sidecar ─▶ middleware/src/services/<feature>/
                                                               └─▶ C++ core (`backend/`, pybind11)
Supervisor (outside the webview) ─▶ sidecar · Cloud Jobs daemon · slideshow daemon   (siblings)
Django (`api/`) ─▶ the same services, for remote clients: Cloud Jobs G1 phone/web, mobile
```

### Bridge (Codex R1, R6; Mistral M5–M7; Kimi Q1, Q3)

- **Transport:** a supervised Python sidecar speaks versioned JSON-RPC
  over stdio.
  - stdout carries only framed protocol messages; stderr carries
    redacted diagnostics.
  - The UI and the sidecar ship as one tested version pair, confirmed by
    a startup handshake.
  - Django exposes the same services remotely, within a documented
    compatibility range.
- **Contracts:** one JSON Schema per capability in `contracts/`, plus a
  method-routing table. CI generates the TypeScript, Python and Rust
  types and a contract hash.
- **One `HostClient`** sits over transport adapters (sidecar, Django,
  native Rust). Retiring a duplicate Rust command (`db.rs`,
  `auth_commands.rs`, `video_commands.rs`, `core_commands.rs`) is then a
  routing-table edit with a conformance suite, not a rewrite. The
  `postgresql://localhost` default in `db.rs` is deleted, not ported.
- **Error envelope:** `{code, retryable, message_key, details}`, mapped
  onto `backend/src/errors/`. No tracebacks reach the webview.
- **Cancel:** one idempotent `job.cancel` with a cooperative token and
  escalation.
- **Event bus:** EventHub intents and facts are generated from the
  contracts. Each channel keeps a snapshot plus a bounded tail with
  sequence numbers; a gap triggers a resnapshot. Durable jobs replay
  from `job_events` / `events.jsonl`. `appStore.ts` keeps only
  ephemeral UI state.
- **Restart contract:** the supervisor emits `bridge.down` and
  `bridge.ready`.
  - In-flight session requests fail with the error envelope.
  - Durable jobs reattach.
  - The current route and the UI state survive.
  - A SIGKILL smoke test in CI exercises all of this.
- **Shared bridge package:** framing, envelope, handshake and the
  generated clients form one small package. The devtool sidecar
  migrates to it when convenient; it blocks no wave.

### Processes and state (Codex R2–R3; Grok T5–T6; Kimi Q2; final round)

- **Supervisor:** runs outside the webview and starts the sidecar, the
  Cloud Jobs daemon and the slideshow daemon as siblings.
  - Closing every window doesn't stop durable work.
  - A sidecar crash doesn't drop daemon leases.
  - Previews and interactive requests belong to the UI session.
- **Single-instance gate** on the data directory, for **GUI apps only**:
  launching a second app focuses the one already running. During
  coexistence that applies to the PySide6 and Tauri apps alike.
- **Vault and keys:**
  - The **C++ core** holds vault unlock and the database keys. The
    webview gets a session handle.
  - Daemons receive **sealed per-store leases** that only the C++ core
    can unseal.
  - No plaintext key passes through Python, Rust or the webview. This
    replaces the Cloud Jobs #827 plan of handing the store secret over
    IPC.
- **Settings:** one settings service shared by both GUIs. It keeps the
  existing keys and scopes (DEVICE / ACCOUNT / SESSION, from
  `gui/src/preferences/store.py`), detects conflicts, and migrates
  legacy settings with a backup first.
- **Schema migrations:** additive-only while a PySide6 row still lives,
  checked in CI. Destructive steps go in that row's deletion PR.

### Frontend platform (OpenCode Q6; Cursor W1–W8; Grok T2–T4; Mistral)

- **Build:** CRA becomes Vite (React 19) and the Electron leftovers are
  deleted, in one announced Wave 0 PR. No feature work merges until the
  build is green.
- **Security** comes before any new UI:
  - a real CSP;
  - one Tauri 2 capability file per labeled window;
  - asset scope declared per capability and denied by default;
  - original files never in scope.

  A CI check fails on wildcard scopes, `csp: null`, or a capability with
  no ledger row.
- **Shell and navigation:**
  - One serializable module catalog, split out of `descriptor.py` (which
    imports `QWidget` today), is rendered by both shells. Its ids match
    the ledger.
  - It replaces `App.tsx`'s `TabId` union. No feature adds a `TabId`.
  - Rail, ribbon, inspector and status bar are all driven by the
    catalog.
  - Navigation may be restructured within a ledger row (Mistral M1).
    Each row keeps an old-route → catalog-id map with compatibility
    aliases.
- **Windows:** one main webview. A WindowManager role map handles
  labels, hide-all and pop-out.
  - Extra native windows exist only for the tray, the slideshow
    presenter, OS file dialogs, or where parity needs a separate window
    (Grok T4).
  - Cloud Jobs Gate D is a panel in the main window that can pop out
    into a labeled `cloud.jobs` webview.
- **Tray:** a native tray lands in Wave 0. Closing the main window hides
  every labeled window, ported from `collect_background_windows()`.
- **Design tokens:** CSS variables are generated from
  `gui/src/theming/tokens/{light,dark}.json`, and both shells use them.
  QSS is not ported by hand.
- **Shortcuts:** one registry lifted from `shortcut_manager.py` /
  `keybindings.json`. Global OS shortcuts are used only for showing and
  hiding the tray.
- **Media:**
  - Gallery stills come from a **C++ thumbnail service**: bounded stills,
    using the **middle** frame by default. They are written to
    `~/.image-toolkit/cache/render/` and streamed over `asset://`.
  - Animated preview is a separate, cancellable request.
  - Large images are never base64-encoded over stdio.
- **Canvases:** one shared canvas host. It is a WebGL2/WebGPU tile
  pyramid, with an off-screen worker that does culling and requests
  level-of-detail tiles.
- **ComfyUI:** an isolated embedded view with no native privileges. It
  is enabled after compatibility and security checks, and the external
  browser stays as a fallback.

### Service layer, DRY and SOLID (OpenCode Q4; Gemini G4–G5; final round)

- **Layout:** each feature lives in
  `middleware/src/services/<feature>/`. It delegates to the existing
  Python modules and the C++ core. `gui/`, `frontend/` and `api/` are its
  clients.
- **Pattern:** Command/Handler with `@runtime_checkable` `Protocol`
  interfaces and frozen dataclasses.
  - Dependencies are injected through the constructor: repositories,
    settings, clients.
  - No singletons reached through globals.
  - Features talk to each other only through contracts or EventHub.
- **Qt workers** become thin shims that delegate to the service until
  their row is deleted.
- **Boundaries are enforced:**
  - Python: `import-linter` contracts (extending the existing
    `[tool.importlinter]`).
  - TypeScript: `eslint-plugin-boundaries`.
  - The LoC gate extends to TS/TSX.
  - Only `services/<x>/api.py` is public.
- **Submodules:** HIE, ASP, CSG and CRE are absorbed. Their C++ joins the
  main CMake build, their Python moves to
  `middleware/src/services/{hie,asp,csg,cre}/`, and their frontends fold
  into `frontend/`.

### Renames (Gemini G1/G5; final round)

Wave 0 starts with two mechanical, announced PRs, each keeping
compatibility aliases for one release:

1. **Python `backend/` → `middleware/`.**
2. **C++ `base/` → `backend/`.**

They must run in that order: both can't be called `backend` at once.
In-flight branches rebase once.

### Documentation (OpenCode Q7; Gemini G6; Mistral M3–M4)

- **Site:** MkDocs Material.
- **Decision records:** `docs/adr/`, with one ADR per locked decision
  above, seeded from this roadmap and from `cloud_jobs.md`.
- **Diagrams:** C4 diagrams for processes, containers and components.
- **Guides:**
  - an "Adding a capability" guide, which is the Convert pilot written
    up;
  - `docs/DEVELOPMENT.md` (50 lines today) becomes a real onboarding
    path.
- **Module READMEs** are required by CI and carry the contract hash. A
  contract change without a README update fails the docs build.
- **Checks:** generated references (sphinx, typedoc, contract schemas),
  plus `mkdocs --strict` and `lychee`.
- **Storybook** for the React component library.
- **`docs/ARCHITECTURE.md`** is really the ASP stitch-pipeline
  reference. It gets renamed to say so, and a real app architecture
  page replaces it.
- **Accessibility:** keyboard parity is required for a row to pass.
  Screen-reader support is best effort, with a known-gaps list in each
  module README.
- **Language:** English-only. i18n is out of scope, but views avoid
  concatenating sentences.

## 2. Migration mechanics

- **Migration ledger:** `migration/features.toml` has **one record per
  capability**, not per route. Stitch is one record covering 8 routes;
  Deep Learning is one record covering 5.
  - Each record holds routes and the route map, PySide6 and Tauri paths,
    service and contract, scenarios, docs, owner, wave, status, and an
    OS checklist.
  - Status is one of `pyside-only`, `both`, `parity-passed` or
    `pyside-deleted`.
  - CI checks coverage both ways (every route in exactly one record, no
    unowned PySide6 file), that paths exist, and that scenarios are
    present.
  - It generates `docs/migration/parity.md`.
- **Parity:** first characterize current behaviour, then diff the old
  path against the new service on the same fixtures, in CI, while both
  apps ship. Semantic acceptance specs, manual checks or pixel checks are
  added where a row needs them.
- **Old tests:** the 224 PySide6 test files are the parity oracle. A
  test is deleted only together with the code it covers.
- **Performance:** responsiveness and memory budgets on representative
  datasets. Where optimising proves intractable for a specific area, that
  area may be deferred case by case.
- **OS checks:** agents automate what they can and attach a checklist.
  **Harbinger** runs it and ticks the row.
- **Deleting a row:**
  1. the parity evidence is green;
  2. any OS checklist is ticked;
  3. Harbinger signs off;
  4. one PR deletes that row's PySide6 code and tests, plus any
     destructive migration, and nothing else.
- **Freeze:** all of `gui/src` takes reviewed bugfixes only. This is a
  written rule in AGENTS.md and the PR template; the ledger records
  exceptions. All new UI is Tauri-only.
- **Testing layers:**
  - Playwright against the Vite build with contract mocks runs on every
    PR.
  - `tauri-driver` / WebDriver runs as a per-release smoke.
  - Parity evidence still comes from the pytest scenarios.
- **Branching:** one branch per capability, merged by PR to main, gated
  by CI (build, LoC gate, docs freshness).
- **Claiming:**
  - Owners are proposed on the issues.
  - Unowned or backlog issues are free to claim: comment on the issue.
  - Deletions need a second reviewer.
- **Spikes:** Harbinger decides go/no-go per spike, on Codex's review.
  A no-go keeps that feature's PySide6 row alive past its wave, as a
  bounded exception in the ledger; it is never a re-scope.
- **Packaging:**
  - While both apps ship, there are two installers: the PyInstaller
    build and the Tauri bundle. Both use the one installed backend
    environment per machine, and the Tauri supervisor starts the sidecar
    from it.
  - When the last Qt row is deleted, there is one Tauri installer with a
    frozen sidecar, and `ImageToolkit.spec` is retired.
  - The canonical version stays in `pyproject.toml`.
- **Platforms:** Linux first for Wave 0, Convert and Cloud Jobs Gate D.
  Windows and macOS follow per capability once its Linux row passes.
- **Mobile:** contracts only; the apps consume them through Django
  later.
- **Cloud Jobs:**
  - Gate D (#847–#852) is the first Tauri-only feature, after the Convert
    pilot.
  - Gate B (#834–#840) starts after Wave 0's renames, supervisor and
    sealed leases.
  - Gate A and C backend work isn't blocked.

## 3. Issues

Tracking issue: [#864](https://github.com/ACFHarbinger/Image-Toolkit/issues/864). Milestones: **Tauri Migration — Wave 0 (Platform & Feasibility)** and **Tauri Migration — Feature Waves**.
Owners are proposals (label `agent:<name>`); unowned issues are free to claim when their wave opens.

### Wave 0a — Renames and repository consolidation (first; everything else rebases on these)

| Issue | Deliverable | Owner |
|---|---|---|
| [#865](https://github.com/ACFHarbinger/Image-Toolkit/issues/865) | W0-01: Rename the Python package `backend/` → `middleware/` (one mechanical PR, import aliases for one release) | Claude |
| [#866](https://github.com/ACFHarbinger/Image-Toolkit/issues/866) | W0-02: Rename the C++ module `base/` → `backend/` (after W0-01; aliases for one release) | Claude |
| [#867](https://github.com/ACFHarbinger/Image-Toolkit/issues/867) | W0-03: Absorb HIE, ASP, CSG and CRE submodules (git subtree, history kept) into one CMake build and `middleware/src/services/{hie,asp,csg,cre}/` | Gemini |

### Wave 0b — Build and security (Mistral's PR 1)

| Issue | Deliverable | Owner |
|---|---|---|
| [#868](https://github.com/ACFHarbinger/Image-Toolkit/issues/868) | W0-04: CRA → Vite (React 19), delete Electron; per-window Tauri capability files, real CSP, default-deny asset scope + CI check | Mistral |

### Wave 0c — Shell (Mistral's PR 2)

| Issue | Deliverable | Owner |
|---|---|---|
| [#869](https://github.com/ACFHarbinger/Image-Toolkit/issues/869) | W0-05: Serializable module catalog split out of `descriptor.py` (no `QWidget`), rendered by both shells; ids = ledger ids | Grok |
| [#870](https://github.com/ACFHarbinger/Image-Toolkit/issues/870) | W0-06: Catalog-driven shell (rail/ribbon/inspector/status bar) replacing `App.tsx`'s `TabId` union | Cursor |
| [#871](https://github.com/ACFHarbinger/Image-Toolkit/issues/871) | W0-07: Design tokens → generated CSS variables from `gui/src/theming/tokens/{light,dark}.json` | Mistral |
| [#872](https://github.com/ACFHarbinger/Image-Toolkit/issues/872) | W0-08: One serializable shortcut registry (from `shortcut_manager.py` / `keybindings.json`) bound by both shells | Cursor |
| [#873](https://github.com/ACFHarbinger/Image-Toolkit/issues/873) | W0-09: Native tray, hide-all on close, WindowManager role map (labels, pop-out) | Grok |

### Wave 0d — Bridge spine (Mistral's PR 3)

| Issue | Deliverable | Owner |
|---|---|---|
| [#874](https://github.com/ACFHarbinger/Image-Toolkit/issues/874) | W0-10: Contracts: JSON Schema per capability in `contracts/` + method-routing table; CI codegen (TS/Python/Rust) and contract hash | Kimi |
| [#875](https://github.com/ACFHarbinger/Image-Toolkit/issues/875) | W0-11: Shared bridge package: framing, envelope, version handshake, error envelope `{code, retryable, message_key, details}`, cancel | Mistral |
| [#876](https://github.com/ACFHarbinger/Image-Toolkit/issues/876) | W0-12: Python sidecar (JSON-RPC/stdio) + `HostClient` with sidecar/Django/Rust transport adapters and a conformance suite | OpenCode |
| [#877](https://github.com/ACFHarbinger/Image-Toolkit/issues/877) | W0-13: Supervisor: sidecar, Cloud Jobs daemon and slideshow daemon as siblings; GUI single-instance gate; `bridge.down`/`bridge.ready` + SIGKILL smoke test; Linux autostart | Grok |
| [#878](https://github.com/ACFHarbinger/Image-Toolkit/issues/878) | W0-14: Generated EventHub (intents/facts) with snapshot + bounded tail, sequence numbers, resnapshot on gap; `appStore.ts` ephemeral-only | Mistral |

### Wave 0e — Foundations

| Issue | Deliverable | Owner |
|---|---|---|
| [#879](https://github.com/ACFHarbinger/Image-Toolkit/issues/879) | W0-15: Vault in the C++ core: unlock + database keys held in C++, session handle for the webview, **sealed per-store leases** for daemons | Codex |
| [#880](https://github.com/ACFHarbinger/Image-Toolkit/issues/880) | W0-16: One settings service for both GUIs: scopes/keys preserved, conflict detection, backed-up legacy migration | Codex |
| [#881](https://github.com/ACFHarbinger/Image-Toolkit/issues/881) | W0-17: Service-layer pattern in `middleware/src/services/<feature>/` (Command/Handler + Protocols) with import-linter and ESLint-boundaries contracts; LoC gate on TS/TSX | Gemini |
| [#882](https://github.com/ACFHarbinger/Image-Toolkit/issues/882) | W0-18: Migration ledger `migration/features.toml` (one record per capability, route map, OS checklist) + validator + generated `docs/migration/parity.md` | OpenCode |
| [#883](https://github.com/ACFHarbinger/Image-Toolkit/issues/883) | W0-19: Parity harness: characterization tests, old-vs-new differential diff, framework-neutral scenarios; Playwright (Vite + contract mocks) per PR, tauri-driver per release | OpenCode |
| [#884](https://github.com/ACFHarbinger/Image-Toolkit/issues/884) | W0-20: Freeze `gui/src` to reviewed bugfixes: AGENTS.md rule, PR template, ledger exceptions; additive-only schema migrations check | Claude |
| [#885](https://github.com/ACFHarbinger/Image-Toolkit/issues/885) | W0-21: Docs spine: MkDocs Material, `docs/adr/` seeded with every locked decision, C4 diagrams, module README template with contract hash, Storybook, rename `docs/ARCHITECTURE.md` (ASP reference) | Gemini |
| [#886](https://github.com/ACFHarbinger/Image-Toolkit/issues/886) | W0-22: Packaging during coexistence: Tauri bundle + PyInstaller installers; supervisor starts the sidecar from the installed backend env; UI/sidecar version-pair handshake | Cursor |

### Wave 0f — Feasibility spikes (each go/no-go by Harbinger on Codex's review; no-go keeps that PySide6 row alive)

| Issue | Deliverable | Owner |
|---|---|---|
| [#887](https://github.com/ACFHarbinger/Image-Toolkit/issues/887) | S-01: Spike: gallery with the C++ thumbnail service (bounded stills, middle frame) streamed via `asset://` from `~/.image-toolkit/cache/render/` | Grok |
| [#888](https://github.com/ACFHarbinger/Image-Toolkit/issues/888) | S-02: Spike: shared canvas host (WebGL2/WebGPU tile pyramid, off-screen worker) on a fake document | Gemini |
| [#889](https://github.com/ACFHarbinger/Image-Toolkit/issues/889) | S-03: Spike: tray and window behaviour per OS (KDE/GNOME Wayland + X11 first; Windows/macOS notes) | Cursor |
| [#890](https://github.com/ACFHarbinger/Image-Toolkit/issues/890) | S-04: Spike: embedded ComfyUI in an isolated view (no native privileges), compatibility/security checks, external-browser fallback | Codex |
| [#891](https://github.com/ACFHarbinger/Image-Toolkit/issues/891) | S-05: Spike: file drag-and-drop in and out of the webview | Kimi |
| [#892](https://github.com/ACFHarbinger/Image-Toolkit/issues/892) | S-06: Spike: video playback and frame scrubbing (asset protocol, codecs) | Kimi |
| [#893](https://github.com/ACFHarbinger/Image-Toolkit/issues/893) | S-07: Spike: wallpaper per-monitor control and the slideshow presenter window from Tauri (KDE/GNOME/Windows) | Claude |

### Feature wave 1 — Convert pilot

| Issue | Deliverable | Owner |
|---|---|---|
| [#894](https://github.com/ACFHarbinger/Image-Toolkit/issues/894) | P-01: Convert, end to end (pilot): service + contract + Tauri view + parity; success = first Rust duplicate (`core_commands.rs` conversion) deleted; write the "Adding a capability" guide | Kimi |

### Feature wave 3 — Library (free to claim when the wave opens)

| Issue | Deliverable | Owner |
|---|---|---|
| [#895](https://github.com/ACFHarbinger/Image-Toolkit/issues/895) | L-01: Image preview, compare and drag-preview viewers (cross-cutting, used by every later wave) | free to claim |
| [#896](https://github.com/ACFHarbinger/Image-Toolkit/issues/896) | L-02: Library: Listings | free to claim |
| [#897](https://github.com/ACFHarbinger/Image-Toolkit/issues/897) | L-03: Library: Image Search | free to claim |
| [#898](https://github.com/ACFHarbinger/Image-Toolkit/issues/898) | L-04: Library: Scan and Tag | free to claim |
| [#899](https://github.com/ACFHarbinger/Image-Toolkit/issues/899) | L-05: Library: Management | free to claim |
| [#900](https://github.com/ACFHarbinger/Image-Toolkit/issues/900) | L-06: Library: Data Browser | free to claim |
| [#901](https://github.com/ACFHarbinger/Image-Toolkit/issues/901) | L-07: Retire `db.rs` (direct sqlx/pgvector, `postgresql://localhost` default) once Library rows route through `HostClient` | free to claim |

### Feature wave 4 — System

| Issue | Deliverable | Owner |
|---|---|---|
| [#902](https://github.com/ACFHarbinger/Image-Toolkit/issues/902) | Y-00: Shared canvas host, production version (first System issue; Merge is its first consumer) | free to claim |
| [#903](https://github.com/ACFHarbinger/Image-Toolkit/issues/903) | Y-01: System: Merge (incl. merge canvas; retire `core_commands.rs` merge duplicate) | free to claim |
| [#904](https://github.com/ACFHarbinger/Image-Toolkit/issues/904) | Y-02: System: Similarity | free to claim |
| [#905](https://github.com/ACFHarbinger/Image-Toolkit/issues/905) | Y-03: System: Extractor (video + image sub-tabs, frame-slice canvas; retire `video_commands.rs`) | free to claim |

### Feature wave 5 — Web

| Issue | Deliverable | Owner |
|---|---|---|
| [#906](https://github.com/ACFHarbinger/Image-Toolkit/issues/906) | B-01: Web: Crawler | free to claim |
| [#907](https://github.com/ACFHarbinger/Image-Toolkit/issues/907) | B-02: Web: Requests | free to claim |
| [#908](https://github.com/ACFHarbinger/Image-Toolkit/issues/908) | B-03: Web: Cloud Synchronization | free to claim |
| [#909](https://github.com/ACFHarbinger/Image-Toolkit/issues/909) | B-04: Web: Media Loader | free to claim |
| [#910](https://github.com/ACFHarbinger/Image-Toolkit/issues/910) | B-05: Web: Reverse Search | free to claim |
| [#911](https://github.com/ACFHarbinger/Image-Toolkit/issues/911) | B-06: Web: Entity Reconnaissance | free to claim |

### Feature wave 6 — Deep Learning

| Issue | Deliverable | Owner |
|---|---|---|
| [#912](https://github.com/ACFHarbinger/Image-Toolkit/issues/912) | D-01: Deep Learning workspace (one record, five routes) in Tauri, incl. the not-yet-built DL panels against `record.json` / `events.jsonl` | free to claim |

### Feature wave 7 — Wallpaper

| Issue | Deliverable | Owner |
|---|---|---|
| [#913](https://github.com/ACFHarbinger/Image-Toolkit/issues/913) | A-01: Wallpaper (System Display + Monitor Display, slideshows and daemons) and the slideshow presenter window | free to claim |

### Feature wave 8 — Editors

| Issue | Deliverable | Owner |
|---|---|---|
| [#914](https://github.com/ACFHarbinger/Image-Toolkit/issues/914) | E-01: Image Stitching workspace (one record, eight routes) on the shared canvas host | free to claim |
| [#915](https://github.com/ACFHarbinger/Image-Toolkit/issues/915) | E-02: Hybrid Image Editor (HIE) | free to claim |
| [#916](https://github.com/ACFHarbinger/Image-Toolkit/issues/916) | E-03: Manga: Colorization, Animation, Puppeteering (CSG) | free to claim |

### Feature wave 9 — Settings, auth and the vault

| Issue | Deliverable | Owner |
|---|---|---|
| [#917](https://github.com/ACFHarbinger/Image-Toolkit/issues/917) | T-01: Settings window (appearance, profiles, shortcuts, tab config, credentials, reset) | free to claim |
| [#918](https://github.com/ACFHarbinger/Image-Toolkit/issues/918) | T-02: Authentication / vault unlock UI on the C++ session handle; retire `auth_commands.rs` | free to claim |
| [#919](https://github.com/ACFHarbinger/Image-Toolkit/issues/919) | T-03: Logging and metadata windows | free to claim |
| [#920](https://github.com/ACFHarbinger/Image-Toolkit/issues/920) | T-04: Cloud Compute setup window (providers, credentials, request builder, dashboards) | free to claim |

### Retirement

| Issue | Deliverable | Owner |
|---|---|---|
| [#921](https://github.com/ACFHarbinger/Image-Toolkit/issues/921) | R-01: Retire PySide6: delete `gui/`, Qt dependencies and `ImageToolkit.spec`; single Tauri installer with a frozen sidecar; remove rename aliases | free to claim |

### Cloud Jobs issues that depend on this migration

- Gate D (#847–#852): first Tauri-only feature, after P-01; needs W0-04…W0-14.
- Gate B (#834–#840): after W0-01/W0-02 (renames), W0-13 (supervisor), W0-15 (sealed leases).


## 4. Attribution

| Agent | Contributions |
|---|---|
| **Claude** | Logic before UI; one contract with generated clients; the parity matrix as the deletion gate; the pilot and waves; enforced boundaries; the final-round reconciliations |
| **Codex** | Sidecar plus Django; sessions versus durable jobs; settings ownership; isolated ComfyUI; performance gates; version pairs |
| **OpenCode** | The migration ledger; characterize-then-diff parity; `HostClient` with transport adapters; the services seam; docs freshness from the contract hash |
| **Grok** | The C++ thumbnail service; the Wave 0 security lockdown; the serializable catalog; one main webview; sibling supervisor; the vault in the C++ core; the shared canvas host |
| **Cursor** | WindowManager role map; generated EventHub; catalog shell; tokens; shortcut registry; tray; dual installers |
| **Kimi** | JSON Schema contracts; single-instance gate; event catch-up; error and cancel envelopes; all-hard-parts spikes; layered end-to-end tests; additive-only migrations |
| **Gemini** | The C++ boundary; zero-copy asset streaming; the WebGL canvas; Command/Handler services; submodule unification; the docs spine |
| **Mistral** | Capability ACL lockdown; Wave 0 as three ordered PRs; the bridge restart contract; the route map; accessibility, i18n and packaging scoping |

*Last updated: 2026-10-19. Scope locked and issues created.*
