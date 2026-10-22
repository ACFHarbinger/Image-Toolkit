# ADR-0001: Tauri 2 as Sole Target Desktop UI and PySide6 Freeze

- **Status:** Accepted (Locked 2026-10-19)
- **Tracking:** [#864](https://github.com/ACFHarbinger/Image-Toolkit/issues/864), [#884](https://github.com/ACFHarbinger/Image-Toolkit/issues/884), [#921](https://github.com/ACFHarbinger/Image-Toolkit/issues/921)
- **Supersedes:** "Tri-Interface Strategy" in `docs/moon/ROADMAP.md`

## Context

Image-Toolkit previously maintained a "Tri-Interface Strategy" where `gui/` (PySide6 / Qt for Python) acted as the primary pro desktop interface while `frontend/` (React + Tauri) served as a secondary companion hub. Maintaining two desktop UIs caused duplicated business logic in Qt workers and Rust Tauri commands, split styling systems (QSS vs CSS), and recurring native runtime conflicts on Linux (GTK file portals, WebEngine vs JVM/native RTTI).

## Decision

1. **Tauri 2 (`frontend/`) is the sole target desktop UI.** Every capability in the PySide6 GUI (`gui/`) is migrated wave-by-wave to Tauri, after which `gui/`, Qt dependencies, and `ImageToolkit.spec` are deleted (#921).
2. **`gui/src` is frozen to reviewed bugfixes only (`W0-20` / #884).** While both shells coexist, no new Qt panels, routes, refactors, or features may land in `gui/src`. Any exception requires a bounded `[[exception]]` record in `migration/features.toml` with `feature`, `path`, `reason`, `issue`, `approved_by`, and optional `expires`.
3. **Thin Tauri Rust shell.** `frontend/src-tauri/` is restricted to OS window management, system tray, native file dialogs, drag-and-drop, and `asset://` streaming. All domain orchestration lives in `middleware/src/services/` and the C++ `backend` core.

## Consequences

- All new desktop features (starting with Cloud Jobs Gate D, #847–#852, after the Convert pilot #894) are built exclusively in Tauri.
- Existing PySide6 tabs remain operational until their capability row in `migration/features.toml` passes differential parity, OS verification, and Harbinger sign-off.
