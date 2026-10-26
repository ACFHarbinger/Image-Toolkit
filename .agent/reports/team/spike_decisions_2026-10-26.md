# Feasibility spike decisions (S-01 to S-07)

Decided by Harbinger, 2026-10-26, on the spike notes in `.agent/reports/`. A "go" allows the production work on that path. A "no-go" applies to the **current implementation** and keeps its PySide6 row alive; it is not a verdict on feasibility.

| Spike | Decision | Basis |
|---|---|---|
| S-01 gallery stills (#887) | **Go** | Bounded middle-frame JPEG in `~/.image-toolkit/cache/render/`, shown through `asset://`. Animated playback stays a separate request and is not covered. |
| S-02 shared canvas host (#888) | **Go** | Already the base of Y-00 (#1001). |
| S-03 tray and window behaviour (#889) | **No-go on the current implementation; the approach is feasible** | Close-to-tray and background are achieved by handling `WindowEvent::CloseRequested` (already done in `frontend/src-tauri/src/window_registry.rs`). The PySide6 tray and window paths stay until that handling is verified per OS. |
| S-04 embedded ComfyUI (#890) | **Go** | Isolated iframe, automatic external-browser fallback. |
| S-05 drag and drop (#891) | **Go** | Inbound drops now; native drag-out is a scoped follow-up. |
| S-06 video (#892) | **Go** | HTML5 `<video>` over `asset://` with byte ranges; scoped transcode fallback. |
| S-07 wallpaper and presenter (#893) | **No-go on the current implementation; the approach is feasible** | The old Rust command ignored monitors and style. KDE per-monitor setting already exists as Plasma scripting (`middleware/src/core/wallpaper/_kde.py`, `_dbus.py`), and #913 (PR #1026) now routes the Tauri side through the sidecar to it. The PySide6 `system.wallpaper` row stays until the KDE checklist passes through that path and the `slideshow` presenter window exists. |

## Follow-ups this opens

- **S-03:** verify `CloseRequested` hide/restore and the tray on KDE and GNOME (Wayland, X11), then Windows and macOS; record results in the OS checklist.
- **S-07:** run the KDE checklist from `.agent/reports/grok/s07_wallpaper_spike_2026-10-23.md` against the new wallpaper capability; check that the slideshow toggle and the Python daemon read the same config file; build the `slideshow` presenter window (deferred in `roles.json`).
- **Still open for Harbinger:** the six OS checklist items in `migration/features.toml` (S-05 and S-07, three platforms each) and the archive of the four absorbed repos.
