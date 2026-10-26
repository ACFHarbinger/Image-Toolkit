# Finishing the Tauri migration: Harbinger's checklist

Written 2026-10-26. Tick a box only after you have seen it work. A ledger row (`migration/features.toml`) becomes `pyside-deleted` only after its parity is green, its OS boxes are ticked and you sign it off, in that row's own deletion PR. Items marked **(agent)** are not yours to do; they are listed so you can see what blocks you.

## 0. State at a glance

- [x] Spikes S-01, S-02, S-04, S-05, S-06 decided: **go** (`spike_decisions_2026-10-26.md`).
- [x] S-03 and S-07 decided: no-go on the current implementation only; approach feasible.
- [x] HIE, CSG, CRE and ASP archived on GitHub; their code relocated (#1042, #1044, #1045, #1046).
- [x] The 54 open issues from the old repos moved into Image-Toolkit (#1050 to #1103); the old repos are archived again.
- [ ] Ledger: 22 rows `pyside-only`, 9 `both`, 0 `pyside-deleted`. Target: none left `pyside-only`.

## 1. Before you test anything: make main trustworthy (agents)

- [ ] **(agent)** Gemini lands #1039: tag `pre-submodules-removal`, delete `submodules/`, remove the two loaders and stale references, close Dependabot #1005.
- [ ] **(agent, Codex)** Configure and build `backend/` once. The CMake path fix for `backend/tests` (now `backend/src/asp`) has never been built.
- [ ] **(agent)** CI green apart from lychee: `tsc`, vitest, `cargo`, the GUI suite, `ruff` (about 143 findings in the moved stitching code).
- [ ] **(agent)** Three stitching tests fail and were not compared with before the move: `test_audit_recomputes_strip_banding`, `test_gui_progress_pipeline_still_subclasses_without_session_override`, `test_compute_all_metrics_emits_strip_banding`.
- [ ] **(agent)** Pre-existing failures on main: `test_service_pattern` convert tests, `test_library_listings`.
- [ ] **(agent, Codex)** Review `middleware/src/sidecar/server.py` dispatch (it was rebuilt by hand during the round-5 landing), `feat/a01-wallpaper` and `feat/w0-03-submodule-services` (WIP, pushed unreviewed; its ASP service has top-level `cv2`/`numpy` imports).
- [ ] **(agent, Gemini)** Reconcile the two HIE editor views (`HieEditorTab` kept; `HieEditorView` not wired).
- [ ] **(agent, Codex)** Dependabot #1004 to #1007 and `pixi-update` #1032 reviewed.

## 2. Operating-system checks (you)

Run on a disposable image / session. The window has never been launched by an agent.

### 2a. Tray and window behaviour (S-03, #889)

**KDE Wayland**
- [ ] The tray icon appears and survives a plasmashell redraw.
- [ ] Left click restores `main` and focuses it; Show Window does the same; left click does not open the menu.
- [ ] Closing `main` hides `main` and a visible `cloud-jobs` pop-out; both leave the taskbar.
- [ ] Closing `main` again while both are hidden, then Show Window, restores both.
- [ ] Closing only the pop-out hides it and leaves `main` up.
- [ ] Quit exits the shell; a supervisor-owned sidecar and slideshow daemon keep running.
- [ ] Stop all cloud activity stays disabled and sends no daemon command.
- [ ] The tray menu is not a second taskbar entry.

**GNOME Wayland**
- [ ] The same eight checks. Record whether the icon is an AppIndicator or missing.
- [ ] If GNOME shows no icon without an extension, record the extension. Close-to-hide still works.

**X11 (KDE and GNOME)**
- [ ] The same eight checks with `XDG_SESSION_TYPE=x11`.
- [ ] Record whether the icon is StatusNotifierItem or XEmbed.

**Windows**
- [ ] The notification-area icon restores `main` and a hidden pop-out on left click and on Show Window.
- [ ] Close hides both and skips the taskbar; a second close still restores both.
- [ ] Quit exits the shell and leaves a supervisor-started daemon running.
- [ ] A second launch focuses the running window (single-instance gate).

**macOS**
- [ ] The menu-bar icon restores `main` and a hidden pop-out on left click and on Show Window.
- [ ] Close hides both; Quit exits the shell and leaves the daemon running.
- [ ] The menu does not become a second Dock icon.

### 2b. Wallpaper and slideshow presenter (S-07, #893)

**KDE Wayland**
- [ ] One set puts a different still on each monitor (match by position when `.screen` is -1, by index otherwise).
- [ ] Fill, fit and stretch change the containment, not only the path.
- [ ] A `qdbus` that prints "could not find a Qt installation" does not block the set when `qdbus6` works.
- [ ] The `slideshow` window is real, shows one monitor's queue, and opening it does not change the desktop.
- [ ] Starting the slideshow from the Tauri tab advances each monitor, and the daemon reads the file the tab wrote.
- [ ] Hiding the main window does not kill that daemon.

**GNOME Wayland**
- [ ] Two monitors show two different images; with one `picture-uri`, the spanned canvas covers both and the seams match the monitor origins.
- [ ] `picture-uri-dark` matches, or the dark theme is written down as a gap.
- [ ] Style is applied; a second set replaces the canvas file.
- [ ] The presenter window and daemon interval match the KDE checks.

**Windows**
- [ ] `IDesktopWallpaper` sets a different image per monitor id; the spanned fallback is used only without COM, and recorded.
- [ ] A single-monitor set uses the selected Windows wallpaper style.
- [ ] The presenter is a top-level window on the chosen monitor; the daemon keeps running after the shell hides.

**macOS**
- [ ] Record the desktop API (the Tauri command has no per-monitor setter here).
- [ ] The presenter opens on the chosen display and the daemon survives hide.

### 2c. File drag and drop (S-05, ledger rows on `library.preview`)

For each of Linux, Windows and macOS (three ledger boxes):
- [ ] Linux: dropping files from the file manager onto the app is accepted; non-image or traversal paths are rejected.
- [ ] Linux: dragging a preview out copies the file in Dolphin and in a second file manager (record which).
- [ ] Windows: inbound drop works; decide the Windows path normalization (open follow-up).
- [ ] Windows: outbound drag-out via `DownloadURL`; record whether Explorer accepts it.
- [ ] macOS: inbound drop works; outbound drag-out recorded as supported or a gap.
- [ ] Tick the three `os_checklist` entries in `migration/features.toml` for `library.preview` (or have an agent do it).

## 3. Per-feature sign-off, then deletion of the Qt side

For each row: parity harness green, its OS boxes (if any) ticked, you launch it in the Tauri app and use it. Then its deletion PR sets `pyside-deleted`. Status shown is today's.

**Wave 0/1**
- [ ] `developer.benchmarks` (both)
- [ ] `system.convert` (pyside-only)
- [ ] `cloud.jobs` (pyside-only)

**Library (wave 3)**
- [ ] `library.listings` (both)
- [ ] `library.search` (both)
- [ ] `library.preview` (pyside-only, has OS boxes)
- [ ] `library.scan`
- [ ] `library.management`
- [ ] `library.data-browser`

**System (wave 4)**
- [ ] `system.merge` (placement canvas still on PySide6)
- [ ] `system.similarity`
- [ ] `system.extractor` (frame-slice canvas still on PySide6)

**Web (wave 5)**
- [ ] `web.crawler`
- [ ] `web.requests`
- [ ] `web.drive-sync`
- [ ] `web.media-loader`
- [ ] `web.reverse-search` (both)
- [ ] `web.entity-recon` (both)

**Deep Learning (wave 6)**
- [ ] `dl`

**Wallpaper (wave 7)**
- [ ] `system.wallpaper` (has OS boxes; needs section 2b)

**Editors (wave 8)**
- [ ] `stitch`
- [ ] `editor.hybrid`
- [ ] `manga.colorization` (both)
- [ ] `manga.animation` (both)
- [ ] `manga.puppeteering` (both)

**Settings, auth and logs (wave 9)**
- [ ] `window.settings`
- [ ] `window.auth`
- [ ] `window.logging`, `developer.logs`, `developer.metadata`
- [ ] `window.cloud-compute` (both)

Anything you decide to keep on PySide6 is recorded as a bounded `[[exception]]` in the ledger with a reason, so the retirement gate can pass.
- [ ] Decide for the tray/window row (S-03) and the wallpaper row (S-07): exception, or finish the Tauri path.

## 4. Cloud Jobs (separate track, #824)

- [ ] Codex's formal Gate A PASS (#825 to #833).
- [ ] Gate B (#834 to #840) opened only after Gate A PASS.
- [ ] Gates C, E, F, G left for later; confirm they stay out of the migration finish line.
- [ ] Cloud Jobs window (D1 to D6) used once against the fake provider, no paid or live run.

## 5. Retire PySide6 (#921)

All must be true first:
- [ ] Every ledger row is `pyside-deleted` or a recorded exception.
- [ ] Every spike decision recorded (done) and every OS box above ticked.
- [ ] `submodules/` is gone and the loaders removed (#1039).
- [ ] You approve deleting `gui/`, the Qt dependencies and `ImageToolkit.spec`.
- [ ] A single Tauri installer with a frozen sidecar builds and installs on Linux, then Windows and macOS (#886 is coexistence only).
- [ ] Rename aliases removed (the one-release `backend/`, `base/` import aliases).
- [ ] Then close #864 and #867.

## 6. Housekeeping

- [ ] Triage the 54 issues moved from the old repos (#1050 to #1103): 3 HIE phases, 32 from CSG (standalone editor slices, tutor alpha, plugin registry), 19 from ASP (M-series, SFW corpus, outreach). Label and assign them, or fold them into the roadmap.
- [ ] Fix lychee (links to the archived repos and `moon/` paths).
- [ ] Unreviewed branches: `feat/a01-wallpaper`, `feat/w0-03-submodule-services`: merge or delete.
- [ ] Old local worktrees under `~/Downloads/Data/Tests/` removed.
- [ ] Release acceptance (#492 to #497) re-scoped for the Tauri app.
