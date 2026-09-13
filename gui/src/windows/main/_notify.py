"""Module-level tray/status-bar notification helpers usable from anywhere.

Extracted from ``main_window.py`` -- pure code motion, no logic change.
Looks up the main window via ``WindowManager`` (#528) instead of walking
``QApplication.topLevelWidgets()``.

Receivers implement the ``StatusSink`` protocol (R0.7, #553): ``MainWindow``
does so across its mixins (``tray_notify`` in ``_tray.py``, ``show_status``
in ``_lifecycle.py``, ``show_toast`` in ``main_window.py``). A registered
window that does not implement it is protocol drift -- logged as a warning,
never a silent no-op. No window registered yet (startup, tests) stays a
debug-level drop.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from ..window_manager import WindowManager

logger = logging.getLogger(__name__)


@runtime_checkable
class StatusSink(Protocol):
    """Anything able to receive tray/status/toast notifications."""

    def tray_notify(self, title: str, message: str, timeout_ms: int = 4000) -> None: ...
    def show_status(self, message: str, timeout_ms: int = 3000) -> None: ...
    def show_toast(
        self, message: str, toast_type: str = "info", duration_ms: int = 2500
    ) -> None: ...


def _sink(operation: str) -> StatusSink | None:
    w = _main_window()
    if w is None:
        logger.debug("Dropping %s: no main window registered", operation)
        return None
    if not isinstance(w, StatusSink):
        logger.warning(
            "Dropping %s: registered main window %r is not a StatusSink (protocol drift)",
            operation,
            type(w).__name__,
        )
        return None
    return w


def _main_window():
    return WindowManager.instance().main_window()


def show_tray_notification(title: str, message: str, timeout_ms: int = 4000) -> None:
    """Post a tray balloon notification from anywhere in the app (§2.12B)."""
    if (s := _sink("tray notification")) is not None:
        s.tray_notify(title, message, timeout_ms)


def show_main_status(message: str, timeout_ms: int = 3000) -> None:
    """Post *message* to the MainWindow status bar from anywhere in the app (§2.10C).

    Drops (debug-logged) when called before the window exists (e.g. during tests).
    """
    if (s := _sink("status message")) is not None:
        s.show_status(message, timeout_ms)


def show_toast_notification(message: str, toast_type: str = "info", duration_ms: int = 2500) -> None:
    """Post a floating toast notification to the MainWindow from anywhere (§2.10A)."""
    if (s := _sink("toast notification")) is not None:
        s.show_toast(message, toast_type, duration_ms)


__all__ = [
    "StatusSink",
    "show_tray_notification",
    "show_main_status",
    "show_toast_notification",
]
