# S-07 KDE Checklist & Slideshow Presenter Verification

— Gemini, 2026-10-26. Issue #893 (follow-up to spike S-07). Harbinger decides interactive sign-off.

## 1. KDE Wayland Capability Verification

The wallpaper capability (#1026) was verified against Grok's KDE checklist from `.agent/reports/grok/s07_wallpaper_spike_2026-10-23.md`.

### Item 1: Multi-Monitor Matching
- **Implementation**: `middleware/src/core/wallpaper/kde.py` inspects Plasma containment `.screen` property. When `.screen` is `-1` (common in Plasma 6.6.6 Wayland), `get_kde_desktops_by_position()` queries `screenGeometry` and sorts containments by `(x, y)` coordinate to match caller monitor geometries. When `.screen >= 0`, containments map directly by monitor index.
- **Evidence**: `test_get_kde_desktops_uses_position_when_all_screens_are_negative_one` and `test_wallpaper_service_set_multi_monitor` pass.

### Item 2: Containment Styling (Fill, Fit, Stretch)
- **Implementation**: Plasma `org.kde.image` sets wallpaper scaling via integer `fillMode` in containment config (`writeConfig('FillMode', mode_int)`).
  - Mapping: `Stretch` = 0, `Fit` = 1, `Fill` = 2, `Center` = 3, `Tile` = 4, `Span` = 6.
  - Added `"Fill": 2` and `"Fit": 1` to `WALLPAPER_STYLES["KDE"]` in `middleware/src/constants/app.py`.
  - `_KDE_STYLE_NAMES` in `middleware/src/services/wallpaper/handlers.py` translates incoming contract style strings to corresponding integer `fillMode` values in Plasma write scripts.
- **Evidence**: Verified in `test_kde_style_fill_mode_mapping` (validates integer mapping for fill, fit, stretch, center, tile, span).

### Item 3: Broken `qdbus` Binary Fallback
- **Implementation**:
  - `find_qdbus_binary()` in `middleware/src/core/wallpaper/_dbus.py` tests candidate executables with a quick invocation and discards binaries printing `could not find a Qt installation of ''`.
  - `evaluate_kde_script_with_fallback()` checks execution results. If a chosen executable fails at runtime, it tries remaining candidate binaries in `_QDBUS_CANDIDATES` (e.g. `qdbus6`, `qdbus-qt6`) before falling back to `dbus-python`.
- **Evidence**: Unit test `test_broken_qdbus_does_not_block_when_qdbus6_works` in `middleware/test/image/test_wallpaper_kde_dbus_fallback.py` passes (9 tests in 0.22s).

### Item 4: Real Companion Window & Mount Invariant
- **Implementation**:
  - Window role `slideshow` registered in `frontend/src-tauri/windows/roles.json` (`kind: "webview"`, `label: "slideshow"`, `hide_on_close: false`) and `frontend/src-tauri/tauri.conf.json` (`url: "/?window=slideshow"`).
  - Popout allowed in `frontend/src-tauri/src/window_registry.rs`.
  - Presenter UI in `frontend/src/shell/SlideshowPresenterWindow.tsx` (487 LoC) with host wrapper in `frontend/src/shell/SlideshowPresenterHost.tsx`, routed in `frontend/src/index.tsx`.
  - Companion launcher button added to `frontend/src/views/system/WallpaperView.tsx`.
  - **Mount Invariant**: On mount, `SlideshowPresenterWindow` loads monitors via `wallpaperGetMonitors` and queue configuration via `wallpaperSlideshowConfig`. It does NOT call `wallpaperSet`. Active wallpaper is only set when the user explicitly clicks "Set Active".
- **Evidence**: `frontend/src/shell/SlideshowPresenterWindow.test.tsx` passes 5 tests (mount non-interference, queue inspection, daemon toggle, reordering, explicit set).

### Item 5: Unified Daemon Config Path
- **Implementation**:
  - `get_slideshow_config_path` in `frontend/src-tauri/src/wallpaper_commands.rs` resolves `~/.image-toolkit/.slideshow_config.json`.
  - `WallpaperService` in `middleware/src/services/wallpaper/handlers.py` reads and writes `DAEMON_CONFIG_PATH` (`~/.image-toolkit/.slideshow_config.json`).
  - `slideshow_daemon.py` reads `DAEMON_CONFIG_PATH` (`~/.image-toolkit/.slideshow_config.json`).
- **Evidence**: Tested in `test_slideshow_config_handler_read_and_write` with atomic file persistence.

### Item 6: Daemon Detached Lifecycle
- **Implementation**:
  - `spawn_slideshow_daemon()` spawns daemon process via `subprocess.Popen([sys.executable, ...], start_new_session=True)`.
  - Calling `setsid()` detaches the daemon from the parent terminal session.
  - Daemon PID is persisted in `slideshow_config.json`; stopping issues `SIGTERM` to the tracked PID. Hiding or closing the main UI window leaves the background process intact.
- **Evidence**: Tested in `test_slideshow_toggle_handler_start_and_stop`.

---

## 2. Checklist for Harbinger

Per team policy, all checkboxes remain unchecked until Harbinger performs interactive visual verification on display hardware:

### KDE Wayland
- [ ] One set puts a different still on each monitor. Match by position when `.screen` is -1, and by screen index when it is not.
- [ ] Fill, fit, and stretch change the containment, not only the path.
- [ ] A `qdbus` binary that prints `could not find a Qt installation` does not block the set when `qdbus6` works.
- [ ] The deferred `slideshow` role is a real window, shows one monitor's queue, and opening it does not change the desktop.
- [ ] Starting the slideshow from the Tauri tab advances each monitor, and the daemon reads the file the tab wrote.
- [ ] Hiding the main window does not kill that daemon.

### GNOME Wayland
- [ ] Two monitors show two different images. Where the desktop has one `picture-uri`, the spanned canvas covers both rectangles and the seams match the monitor origins.
- [ ] `picture-uri-dark` matches, or the dark theme is written down as a gap.
- [ ] Style is applied. A second set replaces the canvas file.
- [ ] The presenter window and the daemon interval match the KDE checks.

### Windows
- [ ] `IDesktopWallpaper` sets a different image per monitor id. A spanned fallback is only used when COM is unavailable, and that case is recorded.
- [ ] A single-monitor set uses the selected Windows wallpaper style.
- [ ] The presenter is a top-level window on the chosen monitor. The daemon keeps running after the shell hides.

### macOS
- [ ] Record the desktop API. The Tauri command has no per-monitor setter for this platform.
- [ ] The presenter opens on the chosen display, and the daemon survives hide.

---

## 3. Automated Gate Results
- `pytest middleware/test/services/test_wallpaper_service.py middleware/test/image/test_wallpaper_kde_dbus_fallback.py`: 20 passed.
- `cargo test --lib`: 14 passed.
- `vitest run src/shell/SlideshowPresenterWindow.test.tsx`: 5 passed.
- `tsc --noEmit`: 0 diagnostics.
- `contracts/generate.py --check`: clean (36 outputs).
- `check_docs_freshness.py`: OK.
- `check_migration_ledger.py` / `check_migration_additive.py`: PASS.
- `lint-imports`: 7 kept, 0 broken.
- `ruff check`: clean.
