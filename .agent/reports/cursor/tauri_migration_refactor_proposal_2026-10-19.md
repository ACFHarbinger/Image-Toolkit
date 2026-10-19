# Tauri migration and architecture refactor — Cursor proposal

**Cursor · 2026-10-19 · Proposal only. Nothing here is approved to build.**

Companion to `.agent/reports/team/tauri_migration_refactor_2026-10-19.md`.
Builds on Harbinger's recorded answers (Claude Q0a–Q0d, Codex R1–R7,
OpenCode Q1–Q8, Grok T1–T8). Does not reopen them. Does not propose
PostgreSQL. The library stays on the encrypted SQLCipher store;
`cloud_jobs.db` stays its own encrypted file.

Claude, Codex, OpenCode, and Grok already cover services-first
extraction, the stdio sidecar, the migration ledger, CSP lockdown,
thumbnails in C++, and one serializable catalog. This note adds the
**window and chrome** those four leave as a table: WindowManager,
EventHub, tray, tokens, shortcuts, and the handwritten Tauri shell
that would otherwise become a second app.

Cursor owns WindowManager (#528). The recommendation is shaped by
that: the migration fails as a second shell, not as a missing React
tab.

## Thesis

Do not invent a second navigation model, a second event bus, a second
theme format, or a second shortcut table. PySide6 already has
`ModuleCatalog`, `EventHub`, `WindowManager`, `gui/src/theming/tokens/`,
and `shortcut_manager.py`. The current Tauri `App.tsx` is a handwritten
`TabId` union that ignores all of them.

Wave 0 should make Tauri consume those contracts, then port thin
views. Cloud Jobs Gate D sits on that shell. It is not a reason to
grow `TabId`.

Agree with: sidecar stdio JSON-RPC, Django for remote, Rust native
only, capability/workspace ledger, characterize-then-diff, Vite in
Wave 0, C++ stills, sibling supervisor, vault unlock in `base/`.

Disagree with: growing `frontend/src/App.tsx`'s `TabId` for Cloud
Jobs; treating every `register_window()` as a Tauri `WebviewWindow`
on day one; "fixing" `db.rs` onto SQLCipher instead of deleting it;
keeping `appStore.ts` as a second settings/auth source of truth.

## 0. Findings in this checkout (not live-run)

| Evidence | Consequence |
|---|---|
| `WindowManager` is used. `register_window` callers: `main_window` (`role="main"`), `settings_window`, `cloud_compute_window`, `image_preview_window`, `image_compare_window`, `slideshow_window`, `metadata_editor_window`, `log_window`. Only `main` has a role. | Tauri needs the same registry of **labels**, not a new window taxonomy. Cloud Compute still has no role; Gate D should not repeat that. |
| `_lifecycle.py` `collect_background_windows()` hides every registered visible window when the app goes to background, so a leftover Settings/Preview does not spawn a second taskbar icon (`test_app_wm_identity.py`, `test_background_hides_secondary_windows.py`). | Extra Tauri windows without an equivalent hide/show protocol recreate issue #2. Design this before Gate D opens a second webview. |
| Tray lives in `gui/src/windows/main/_tray.py`. Close-to-background is a setting (`preferences/definitions.py`). Duplicate-tray bugs are already test-covered. | Tray is native Rust, not a webview. The supervisor (T5) keeps processes; the tray keeps the UI reachable. |
| `gui/src/modules/events.py` already has `NavigateIntent`, `ImportPathsIntent`, `InspectImageIntent`, `SelectionChangedFact`, `TelemetryUpdatedFact`. Search, Extractor, wallpaper, and the DL workspace publish them. | The sidecar event protocol and the in-webview bus are the same schema. `appStore.ts` (`VaultCredentials`, `UserPreferences`, `BackgroundTask`) duplicates Codex R3 settings and R2 jobs. |
| `frontend/src/App.tsx` defines a `TabId` union (`convert`…`hie`) and a 500-line switcher. It does not read `ModuleCatalog`. Settings is a `SettingsDialog`, not the Settings window. | This is a second catalog. T3 already picked one serializable catalog. Wave 0 deletes the union as the navigation source of truth, or Cloud Jobs becomes `TabId = "cloud-jobs"`. |
| `frontend/src-tauri/capabilities/default.json` lists only window `"main"`. Codex already warned that Tauri **merges** capabilities when a view belongs to more than one. | A Gate D `cloud.jobs` webview that is not in this file will not get dialog/core permissions, or will inherit `**` if someone adds it carelessly. A route inside `main` needs no new window capability. |
| `frontend/src-tauri/src/lib.rs` defaults `DATABASE_URL` to `postgresql://localhost/image_toolkit` and `db.rs` talks sqlx/pgvector. PostgreSQL is archived. | Do not migrate this connection. Delete `db.rs` behind the HostClient routing table (OpenCode). The sidecar talks to `library.db` through C++ `base.database`. |
| `tauri.conf.json` `"version": "0.1.0"`; root `pyproject.toml` is `1.0.0`. Bundle target is `deb` only. | Version pair (R6) is already lying. Wave 0 reads the canonical version. Packaging is not "copy the spec". |
| `gui/src/theming/tokens/{light,dark}.json` plus `theme-tokens.schema.json` already exist. QSS is generated from tokens. | Do not invent a Tailwind palette. Emit CSS variables from those JSON files. Both shells consume them during coexistence. |
| `gui/src/utils/manager/shortcut_manager.py` plus `~/.image-toolkit/keybindings.json`. `_lifecycle.py` already calls `get_registry()`. | One registry, serializable, bound by both shells. Do not hand-write `useHotkeys` per tab. |
| `ImageToolkit.spec` is the PySide6 freeze (AppImage/deb, `libitk_crypto`, `sys._MEIPASS`). Tauri bundle is a separate `.deb` with no sidecar. | Coexistence means two installers until the last Qt row dies. Then one Tauri installer plus a frozen sidecar. |

## 1. Window map — roles, not a window per `register_window()`

Grok T4: one main webview by default; a native window only when
parity requires it. Cloud Jobs was locked as a **standalone PySide6
window**. Those two answers need a rule, not another product.

Proposed classification:

| Surface | Default in Tauri | Native window only if |
|---|---|---|
| Main shell | `main` webview | — |
| Settings, Cloud Compute, Cloud Jobs, log, metadata | route or panel in `main` | user pops it out |
| Preview, compare | panel; **pop-out** creates a labeled window | dual-monitor / always-on-top spike fails as a panel |
| Slideshow / wallpaper presenter | native (OS surface) | — |
| Tray, file dialogs | native, not a webview | — |

Pop-out is the WindowManager pattern already used for preview and
compare: `windows.open(role)` from the shell, label in
`capabilities/`, no `**` asset scope on child windows (T2). Closing
`main` to the tray hides every labeled window, same as
`collect_background_windows()`.

Cloud Jobs Gate D therefore ships as a **panel with a pop-out**, not
as a new `TabId` and not as a mandatory second webview. The header
badge (Cloud Jobs Cursor Q5) lives on `main`.

Rust keeps a `window_registry` keyed by the same roles the catalog
uses (`main`, `cloud.jobs`, `cloud.compute`, `preview`, `compare`,
`settings`, `log`). JS does not call `WebviewWindow` constructors
ad hoc.

## 2. EventHub is the bus; `appStore.ts` is not

`EventHub` is already the cross-module contract. Generate TypeScript
types from the same dataclasses (or the OpenAPI/JSON Schema Claude
wants for services). The webview holds a subscriber. The sidecar
emits facts for jobs, telemetry, and catalog changes. Durable jobs
do not live in `Map<string, BackgroundTask>` inside React.

`appStore.ts` shrinks to ephemeral UI (which panel is open, local
form dirty flags). Auth state is a session handle from `base/`
(T6), not `VaultCredentials` in React context. Settings go through
the Codex R3 service.

Search → Merge via `NavigateIntent` keeps working when Search is a
Tauri route and Merge is still Qt, because the sidecar owns the
intent and the catalog owns the id. That is the coexistence path.
Two handwritten routers cannot.

## 3. Shell chrome, once

Port the experimental shell, do not restyle `App.tsx`:

- left rail = `NavigationRailWidget` driven by the serializable
  catalog (T3);
- inner destinations = `TopSegmentedRibbonWidget` for workspaces
  (Stitch, DL);
- right inspector = `ContextInspectorPanel` via
  `ToggleInspectorIntent`;
- footer = `TelemetryStatusBar` via `TelemetryUpdatedFact`;
- header ☁️ = Cloud Jobs badge, gear opens Cloud Compute (already
  answered).

Existing Tauri tab components (`ConvertTab.tsx`, …) become **views
behind catalog ids**, not the navigation source. Wave 0 replaces the
`TabId` union. No feature work adds a member to it.

HIE/ASP/CSG fold in as views (R7), hosted by this shell, not as a
second rail.

## 4. Tokens, shortcuts, tray

- **Tokens:** `gui/src/theming/tokens/*.json` → CSS variables in
  Wave 0 with the Vite cutover. Custom user themes stay data. Do not
  port 300 QSS files by hand; components consume tokens.
- **Shortcuts:** lift `shortcut_manager` definitions into a Qt-free
  JSON next to the catalog. Both shells bind it. Webview
  `preventDefault` for in-app ids; Tauri global shortcuts only for
  tray show/hide.
- **Tray:** native. Close-to-background setting is already a
  preference key; the settings service preserves it (R3). The tray
  menu talks to the supervisor (show UI, Stop all cloud activity,
  quit UI but leave daemons).

## 5. Packaging and the PostgreSQL landmine

During coexistence: keep the PyInstaller AppImage/deb for PySide6;
add a Tauri installer for the new app. After the last Qt row is
deleted: one Tauri bundle whose `externalBin` is a frozen sidecar
evolved from `ImageToolkit.spec` (crypto lib, `base`, no Qt).
`just release::bump` still owns the version; `tauri.conf.json`
stops carrying `0.1.0`.

`db.rs` / `postgresql://localhost` is not a migration task. It is
deleted when the first HostClient transport reaches library search.
Do not add SQLCipher to Rust.

Linux is the Wave 0 + Convert + Gate D platform, matching the
Cloud Jobs Linux-first daemon. Windows/macOS follow per capability
after the Linux row passes. `tauri.conf.json` `targets: ["deb"]`
already admits that.

## 6. Shape (when implementation is allowed)

- `gui/src/modules/catalog.py` emits JSON; `descriptor.py` keeps
  Qt factories until the row dies.
- `frontend/src/shell/` — rail, ribbon, inspector, status bar,
  header badge — reads the catalog. `App.tsx` TabId union goes.
- `frontend/src-tauri/src/window_registry.rs` — labels, hide-all,
  pop-out. Capabilities list every label. No `**` on children.
- Generated `frontend/src/events.ts` from `events.py` / the
  contract schema.
- CSS variables from `gui/src/theming/tokens/`.
- Convert pilot still deletes `core_commands.rs` convert/merge
  (OpenCode). Library wave deletes `db.rs`.

Targeted tests: catalog JSON without PySide6; hide-all does not
leave a labeled window visible; capability of `cloud.jobs` child
cannot read an original path; token CSS contains the same
`--it-accent` as `light.json`; `tauri.conf.json` version equals
`pyproject.toml`. No full suite.

## Questions for Harbinger

Harbinger's answers match the recommendations. Recorded by Cursor,
2026-10-19. W1–W8 are all A. Scope still awaits the team final round.

### Cursor W1 — How does Cloud Jobs Gate D appear in Tauri?

- **Harbinger answer (2026-10-19):** A.
- **A (recommended):** Panel in `main` with a WindowManager pop-out
  that creates a labeled `cloud.jobs` webview. Header badge stays on
  `main`. Child window has no `**` asset scope.
- **B:** Always a native `cloud.jobs` webview, for parity with the
  locked PySide6 standalone window.
- **C:** Route only. No pop-out in v1.
- **D:** A new `TabId` in today's `App.tsx` switcher, so Gate D can
  ship before the catalog shell.

### Cursor W2 — What is the in-app event bus?

- **Harbinger answer (2026-10-19):** A.
- **A (recommended):** Generated EventHub intents/facts. Sidecar
  emits them. `appStore.ts` is ephemeral UI only.
- **B:** React store (`appStore.ts` / Redux) is the source of truth.
  EventHub dies with Qt.
- **C:** No in-webview bus. Every view polls the sidecar.
- **D:** Keep EventHub (Qt) and `appStore.ts` (Tauri) with a manual
  mapping until the last Qt row.

### Cursor W3 — When does close-to-background / tray land?

- **Harbinger answer (2026-10-19):** A.
- **A (recommended):** Wave 0 native tray. Closing `main` hides every
  labeled window (port of `collect_background_windows`). Supervisor
  keeps sidecar and daemons.
- **B:** Tray after the Convert pilot. Until then, closing `main`
  quits the UI; daemons keep running.
- **C:** No tray until PySide6 is gone. Tauri uses the OS taskbar
  minimize only.
- **D:** Qt keeps the only tray for the whole coexistence period.

### Cursor W4 — How do we package while both apps ship?

- **Harbinger answer (2026-10-19):** A.
- **A (recommended):** Dual installers until the last Qt row is
  deleted (current PyInstaller AppImage/deb + Tauri bundle). Then one
  Tauri installer with a frozen sidecar. `ImageToolkit.spec` dies
  with PySide6. Canonical version stays `pyproject.toml`.
- **B:** One installer that can launch either UI.
- **C:** Tauri-only packaging from Wave 0; PySide6 is source-run
  during the migration.
- **D:** PyInstaller remains the only release channel; Tauri is an
  unpackaged extra.

### Cursor W5 — Where do visual tokens come from?

- **Harbinger answer (2026-10-19):** A.
- **A (recommended):** Generate CSS variables from
  `gui/src/theming/tokens/{light,dark}.json` in Wave 0. Both shells
  consume them. Do not hand-port QSS.
- **B:** New Tauri visual language. Qt stays on QSS until deleted.
- **C:** Import the QSS files as raw CSS.
- **D:** Unstyled until after functional parity.

### Cursor W6 — Where do keyboard shortcuts live?

- **Harbinger answer (2026-10-19):** A.
- **A (recommended):** One serializable registry lifted from
  `shortcut_manager.py` / `keybindings.json`. Both shells bind it.
  Tauri global shortcuts only for tray show/hide.
- **B:** Hand-write React hotkeys per view.
- **C:** Defer shortcuts until after visual parity.
- **D:** OS-level global shortcuts for every action.

### Cursor W7 — Which OS is Gate D allowed to miss?

- **Harbinger answer (2026-10-19):** A.
- **A (recommended):** Linux is the Wave 0 + Convert + Cloud Jobs
  Gate D platform. Windows and macOS follow per capability after the
  Linux row passes.
- **B:** Linux and Windows from Wave 0; macOS later.
- **C:** All three from Wave 0.
- **D:** Whatever the implementing agent can run.

### Cursor W8 — What happens to `App.tsx`'s handwritten `TabId` union?

- **Harbinger answer (2026-10-19):** A.
- **A (recommended):** Wave 0 replaces it with the serializable
  catalog. Existing `*Tab.tsx` files remain views behind catalog ids.
  No feature adds a `TabId` member, including Cloud Jobs.
- **B:** Keep `TabId` until each tab is rewritten. Catalog is
  Qt-only until then.
- **C:** Dual navigation (catalog + `TabId`) until the Convert
  pilot lands.
- **D:** Freeze `App.tsx` as-is and put new UI in a parallel shell
  tree.

— Cursor, 2026-10-19
