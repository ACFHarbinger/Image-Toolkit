# #879 Supervisor Binding Enforcement and Spike Go/No-Go Notes

**Date:** 2026-10-23
**Agent:** Grok team (Harper, Benjamin, Lucas)
**Status:** Ready for implementation on feat/w0-15-supervisor-binding

## #879 Remaining Work (now unblocked by Gate A PASS)

Production supervisor must enforce PID/TTL/session binding at lease mint time. Currently optional (defaults 0/""). Daemon key files 0600 but same-OS-user readable.

### Proposed Changes

**vault_manager.py handoff_daemon_lease:**
Add `enforce_binding: bool = False`. If True, raise ValueError unless pid > 0, ttl_seconds > 0, and supervisor_session non-empty.

**supervisor.py:**
- Generate `self.supervisor_session = str(uuid.uuid4())` at start.
- After spawn of durable daemons (cloud_jobs, slideshow), call handoff_daemon_lease with child.pid, ttl=3600, session, enforce_binding=True.
- Set ITK_SUPERVISOR_SESSION in child env.
- Document residual: daemon should unlink key after load; stronger FD handoff is follow-up.

This makes binding mandatory in production path. Unseal already enforces sealed values.

Targeted tests only. Once landed, Gate B can open.

## Spike Go/No-Go Notes

### #889 S-03 Tray per OS
**Recommendation:** Conditional GO
Native tray and window roles landed (#873/#934/#966). Solid on X11/Windows/macOS. Wayland residuals (icon visibility, packaging). OS checklist for Harbinger required. No-go keeps PySide6 exception.

### #890 S-04 ComfyUI
**Recommendation:** Conditional GO
Isolated view feasible post #868 security. No native privileges. External browser fallback trivial. Security via capabilities/CSP. Heavy but within design.

### #892 S-06 Video
**Recommendation:** Conditional GO (partial)
Aligns with #887: GO for stills (C++ middle-frame + asset://). Basic playback and scrubbing via WebView <video>. Codec variance on Linux. No-go for high-perf animated until measured.

### #893 S-07 Wallpaper / Presenter
**Recommendation:** Conditional GO
Presenter window standard Tauri labeled window. Per-monitor requires OS-native calls (gsettings, WinAPI). Slideshow daemon in supervisor. OS checklist required.

A no-go keeps the PySide6 row as bounded ledger exception.

---
Claimed by Grok team. Codex reviews; Claude lands.
