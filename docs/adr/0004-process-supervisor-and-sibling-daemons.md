# ADR-0004: External Process Supervisor, Sibling Daemons, and Single-Instance Gate

- **Status:** Accepted (Locked 2026-10-19)
- **Tracking:** [#877](https://github.com/ACFHarbinger/Image-Toolkit/issues/877)

## Context

If background daemons (Cloud Jobs orchestration, wallpaper slideshow rotation) or the Python sidecar are spawned as direct child processes of a webview window, closing the window or crashing the sidecar can orphan cloud resources, drop credential leases, or kill active background jobs.

## Decision

1. **Supervisor outside the webview (`middleware/src/supervisor/`):** A dedicated supervisor manages the **Python sidecar**, the **Cloud Jobs daemon**, and the **slideshow daemon** as sibling processes.
2. **Lifecycle isolation:**
   - Closing all GUI windows does not stop durable background work.
   - A sidecar crash or restart does not drop daemon leases.
   - Interactive previews and session-scoped requests belong to the UI session and terminate when the session closes.
3. **GUI single-instance gate on the data directory:** Launching a second GUI instance (`PySide6` or `Tauri` during coexistence) acquires a lock on the data directory and focuses the already-running window instead of starting a second desktop process. CLI commands and headless workers are not blocked by the GUI gate.

## Consequences

- Long-running local and cloud jobs survive UI restarts and window close events.
- Coexisting PySide6 and Tauri desktop launches cannot corrupt the same user data directory concurrently.
