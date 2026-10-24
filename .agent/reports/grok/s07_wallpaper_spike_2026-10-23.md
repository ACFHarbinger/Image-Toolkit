# S-07 per-monitor wallpaper and the slideshow presenter — go/no-go note

— Grok, 2026-10-23. Issue #893. Harbinger decides. This note is the checklist, not an OS sign-off. No wallpaper was changed.

## What was read

`set_wallpaper` in `frontend/src-tauri/src/wallpaper_commands.rs` logs that wallpaper setting is not fully implemented. It ignores `_monitors` and `_style`. When `XDG_CURRENT_DESKTOP` contains `GNOME`, it sets `org.gnome.desktop.background` `picture-uri` and `picture-uri-dark` to the first `path_map` value, as one canonical `file://` URI. Any other desktop returns an error. `WallpaperTab.tsx` still sends a per-monitor path map, monitor indexes, and a style.

`get_monitors` reads `app.available_monitors()` (name, size, position). `set_wallpaper` does not use that list.

The `slideshow` role in `frontend/src-tauri/windows/roles.json` is kind `native`, `hide_on_close` false, and `"deferred": "#893"`. No presenter window is created. Qt's companion is `SlideshowQueueWindow` in `gui/src/windows/slideshow_window.py`: a per-monitor reorderable queue. The catalog page `system.wallpaper` names `slideshow` as its companion window.

`toggle_slideshow_daemon` writes `slideshow_config.json` under the Tauri app config directory, then spawns `python middleware/main.py slideshow`. The Python daemon reads `~/.image-toolkit/.slideshow_config.json` (`DAEMON_CONFIG_PATH` in `middleware/src/constants/paths.py`). Those are different files. The spawn is bare `python`, not the supervisor sibling.

The per-monitor setters that exist today are Python:

- KDE: `get_kde_desktops_by_position` reads `screenCount` and `screenGeometry` (read-only). `_set_wallpaper_kde` writes per containment. This spike did not call the write.
- GNOME: `_set_wallpaper_gnome_spanned` composites one canvas from the monitor rectangles, because GNOME has one `picture-uri`. This spike did not call it.
- Windows: `_set_wallpaper_windows_multi` calls `IDesktopWallpaper.SetWallpaper` per monitor id. Not run here.

`system.wallpaper` in `migration/features.toml` is `pyside-only` (issue #913). Its three S-07 rows (linux, windows, macos) stay `checked = false`.

## Evidence

Read-only on this machine, 2026-10-23. `set_wallpaper`, `gsettings set`, and any Plasma write script were not run.

- Session: Wayland, `XDG_CURRENT_DESKTOP=KDE`, plasmashell 6.6.6. `gnome-shell` is not on PATH. `gsettings` is.
- `find_qdbus_binary()` returned `qdbus6`. `get_kde_desktops_by_position("qdbus6")` and `get_kde_desktops("qdbus6")` both returned two desktops: screen 0 at (0, 304) and screen 1 at (1897, 0). On this session `.screen` was not -1. The KDE module still documents Plasma 6.6.6 sessions where `.screen` stays -1 and only `screenGeometry` is usable. One matching reading does not retire that fallback.
- The same position query with `qdbus` returned no desktops. The CLI printed `qdbus: could not find a Qt installation of ''`. dbus-python is not installed, so the fallback could not run. `qdbus-qt6` is not on PATH.
- `gsettings get org.gnome.desktop.background picture-uri` returned a value while the session is KDE. That key is not the Plasma wallpaper. The Tauri GNOME branch would not run here, because the desktop string is `KDE`.

Automated webview checks do not establish per-monitor parity. This probe only shows that Plasma on this session can report two geometries.

## Recommendation

**No-go for retiring the PySide6 wallpaper row** (`system.wallpaper`, issue #913). The Tauri command cannot set a different image per monitor, ignores style, and on this KDE session it would return the unimplemented error. The presenter window is still deferred. The slideshow toggle writes a config file the Python daemon does not read.

Keep the Python KDE, spanned-GNOME, and Windows `IDesktopWallpaper` paths until a Tauri command calls them per monitor and the `slideshow` window exists. Do not tick the three ledger boxes from this note. Harbinger runs the checklist.

## Checklist for Harbinger

Leave every box unchecked until that run. Use a disposable image.

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

— Grok
