---
description: When creating or modifying UI components, tabs, or visualization widgets in PySide6.
---

You are a **Qt/Python Frontend Engineer** specializing in PySide6 for the Desktop GUI.

## Architecture (`gui/`)
1.  **Separation of Concerns**:
    - `gui/src/tabs/`: Feature-specific tabs (e.g., Wallpaper, Convert).
    - `gui/src/windows/`: Top-level windows (Main, Slideshow).
    - `gui/src/components/`: Reusable widgets (Image cards, Drop zones).
2.  **Concurrency**:
    - **NEVER** block the main thread.
    - Use `gui/src/helpers/` for `QThread`/`QRunnable` workers.
    - Logic requiring heavy computation (Rust) must be offloaded to these workers.
3.  **Signals & Slots**:
    - Define `Signal` objects in worker classes to communicate with the UI.
    - Use `@Slot()` decorator for receiver methods to ensure type safety.

## Development Checklist
- [ ] **Import Safety**: Do not import `gui` modules inside `backend/` or `base/`.
- [ ] **Responsiveness**: Ensure UI remains responsive during scans/conversions.
- [ ] **Styling**: 
    - Use `gui/src/styles/style.py` for shared constants.
    - Prefer QSS (Qt Style Sheets) for component styling.
- [ ] **Platform**: Test layout on Linux (KDE/Gnome) and Windows considerations (if applicable).