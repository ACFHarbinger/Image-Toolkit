"""Module-level tray/status-bar notification helpers usable from anywhere.

Extracted from ``main_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication


def show_tray_notification(title: str, message: str, timeout_ms: int = 4000) -> None:
    """Post a tray balloon notification from anywhere in the app (§2.12B)."""
    for w in QApplication.topLevelWidgets():
        if hasattr(w, "tray_notify"):
            w.tray_notify(title, message, timeout_ms)
            return


def show_main_status(message: str, timeout_ms: int = 3000) -> None:
    """Post *message* to the MainWindow status bar from anywhere in the app (§2.10C).

    Finds the first MainWindow in QApplication.topLevelWidgets(); silently
    does nothing when called before the window exists (e.g. during tests).
    """
    for w in QApplication.topLevelWidgets():
        if hasattr(w, "show_status"):
            w.show_status(message, timeout_ms)
            return



def show_toast_notification(message: str, toast_type: str = "info", duration_ms: int = 2500) -> None:
    """Post a floating toast notification to the MainWindow from anywhere (§2.10A)."""
    for w in QApplication.topLevelWidgets():
        if hasattr(w, "show_toast"):
            w.show_toast(message, toast_type, duration_ms)
            return

__all__ = ["show_tray_notification", "show_main_status", "show_toast_notification"]

