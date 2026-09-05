"""System tray icon setup and interaction (§2.12A/B/C).

Extracted from ``main_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import contextlib
import os

from backend.src._version import __version__
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QStyle, QSystemTrayIcon


class _TrayMixin:
    """Builds the tray icon/menu and handles tray-triggered actions."""

    def _setup_tray_icon(self, app_icon=None) -> None:
        # Idempotent: a QSystemTrayIcon parented to the window stays alive and
        # visible after ``self._tray_icon`` is reassigned, so calling this a
        # second time (startup pref + first close-to-tray) left two identical
        # icons in the tray. Re-show the existing one instead.
        existing = getattr(self, "_tray_icon", None)
        if existing is not None:
            existing.show()
            return

        icon = app_icon
        if icon is None or not isinstance(icon, QIcon):
            _asset = os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "..",
                "..",
                "assets",
                "images",
                "image_toolkit_icon.png",
            )
            _asset = os.path.normpath(_asset)
            if os.path.exists(_asset):
                icon = QIcon(_asset)
            else:
                icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

        self._tray_icon = QSystemTrayIcon(icon, parent=self)
        # Parent the menu to the window so it shares the app's WM identity
        # (app_id / WM_CLASS) — a parentless popup surface can otherwise be
        # picked up as a separate taskbar entry on some Wayland compositors.
        tray_menu = QMenu(self)

        show_action = tray_menu.addAction("Show Window")
        show_action.triggered.connect(self._tray_show_window)

        tray_menu.addSeparator()

        daemon_action = tray_menu.addAction("Toggle Daemon")
        daemon_action.triggered.connect(self._tray_toggle_daemon)

        next_wp_action = tray_menu.addAction("Next Wallpaper")
        next_wp_action.triggered.connect(self._tray_next_wallpaper)

        tray_menu.addSeparator()

        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(self._quit_application)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.setToolTip(f"Image Toolkit — v{__version__}")
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _tray_show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        # Restore any secondary windows (Settings, previews, …) that were
        # hidden alongside the main window when it went to background.
        for w in getattr(self, "_bg_hidden_windows", []):
            with contextlib.suppress(RuntimeError):
                if w is not None:
                    w.show()
        self._bg_hidden_windows = []

    def _tray_toggle_daemon(self) -> None:
        wt = getattr(self, "wallpaper_tab", None)
        if wt and hasattr(wt, "toggle_daemon"):
            current = getattr(wt, "btn_daemon_toggle", None)
            checked = current.isChecked() if current else False
            wt.toggle_daemon(not checked)

    def _tray_next_wallpaper(self) -> None:
        wt = getattr(self, "wallpaper_tab", None)
        if wt and hasattr(wt, "_cycle_slideshow_wallpaper"):
            wt._cycle_slideshow_wallpaper(increment=True)

    def _on_tray_activated(self, reason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.Trigger,
        ):
            self._tray_show_window()


    def tray_notify(self, title: str, message: str, timeout_ms: int = 4000) -> None:
        """Show a tray balloon notification (§2.12B). No-op when tray is unavailable."""
        if self._tray_icon and self._tray_icon.isVisible():
            self._tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, timeout_ms)

    def set_minimize_to_tray(self, enabled: bool) -> None:
        """Toggle minimize-to-tray behaviour (§2.12C). Controlled via settings."""
        self._minimize_to_tray = enabled


__all__ = ["_TrayMixin"]
