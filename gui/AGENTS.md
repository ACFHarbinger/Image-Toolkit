# GUI Module Instructions (`gui/`)

## Overview
The GUI layer uses **PySide6** (Qt for Python). It is responsible for the desktop interface, ensuring a responsive and intuitive user experience. It interacts with the `backend` modules, which efficiently delegate heavy tasks to the compiled Rust `base` layer.

## Structure
* **`tabs/`**: Contains the logic for specific application features (e.g., `wallpaper_tab.py`, `convert_tab.py`).
    *   These modules instantiate backend classes (e.g., `ImageFormatConverter`) to perform work.
* **`helpers/`**: Contains `QThread` or `QRunnable` workers.
    *   **CRITICAL**: All calls to backend functions that might involve IO or CPU-heavy Rust operations MUST be done here, off the main thread.
* **`components/`**: Reusable custom widgets (e.g., `DraggableMonitorContainer`, `DraggableLabel`).
* **`windows/`**: Top-level window management.

## Coding Standards
1.  **Threading**:
    *   Never run blocking I/O or heavy computation on the main thread.
    *   Even though Rust functions are fast, they are blocking calls in Python. Run them in `QThread` or `QThreadPool`.
    *   Communicate back to the UI **only** via Signals (`finished`, `error`, `progress`).
2.  **Responsiveness**:
    *   Provide visual feedback (spinners, progress bars) for all async actions.
3.  **Styles**:
    *   Use Qt Style Sheets (QSS) for styling where possible, but prefer separation of logic and presentation.

## Testing
*   Use `pytest-qt` fixtures where possible for UI testing.
*   Mock backend responses to test UI states without invoking the actual Rust logic.
