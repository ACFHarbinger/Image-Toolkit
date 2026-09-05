"""Module-level tray/status-bar notification helpers usable from anywhere.

Extracted from ``main_window.py`` -- pure code motion, no logic change.
Looks up the main window via ``WindowManager`` (#528) instead of walking
``QApplication.topLevelWidgets()``.
"""

from __future__ import annotations

from ..window_manager import WindowManager


def _main_window():
    return WindowManager.instance().main_window()


def show_tray_notification(title: str, message: str, timeout_ms: int = 4000) -> None:
    """Post a tray balloon notification from anywhere in the app (§2.12B)."""
    w = _main_window()
    if w is not None and hasattr(w, "tray_notify"):
        w.tray_notify(title, message, timeout_ms)


def show_main_status(message: str, timeout_ms: int = 3000) -> None:
    """Post *message* to the MainWindow status bar from anywhere in the app (§2.10C).

    Uses the registered main window; silently does nothing when called before
    the window exists (e.g. during tests).
    """
    w = _main_window()
    if w is not None and hasattr(w, "show_status"):
        w.show_status(message, timeout_ms)


def show_toast_notification(message: str, toast_type: str = "info", duration_ms: int = 2500) -> None:
    """Post a floating toast notification to the MainWindow from anywhere (§2.10A)."""
    w = _main_window()
    if w is not None and hasattr(w, "show_toast"):
        w.show_toast(message, toast_type, duration_ms)


__all__ = ["show_tray_notification", "show_main_status", "show_toast_notification"]
