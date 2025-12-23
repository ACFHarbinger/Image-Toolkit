# GUI Module Instructions (`gui/`)

## Overview
The GUI layer uses **PySide6** (Qt for Python). It is responsible for the desktop interface, ensuring a responsive and intuitive user experience while interacting with the heavy backend logic.

## Structure
* **`tabs/`**: Contains the logic for specific application features (e.g., `wallpaper_tab.py`, `convert_tab.py`).
* **`helpers/`**: Contains `QThread` or `QRunnable` workers. **CRITICAL**: usage of these for long-running tasks is mandatory.
* **`components/`**: Reusable custom widgets (e.g., `DraggableMonitorContainer`, `DraggableLabel`).
* **`windows/`**: Top-level window management.

## Coding Standards
1.  **Threading**:
    *   Never run blocking I/O or heavy computation on the main thread.
    *   Use `QThread` or `QThreadPool`.
    *   Communicate back to the UI **only** via Signals (`finished`, `error`, `progress`).
2.  **Responsiveness**:
    *   Provide visual feedback (spinners, progress bars) for all async actions.
3.  **Styles**:
    *   Use Qt Style Sheets (QSS) for styling where possible, but prefer separation of logic and presentation.

## Testing
*   Use `pytest-qt` fixtures where possible for UI testing (though manual verification is often required for complex drag-and-drop).
