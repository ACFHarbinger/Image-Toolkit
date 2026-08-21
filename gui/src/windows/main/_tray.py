"""System tray icon setup and interaction (§2.12A/B/C).

Extracted from ``main_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon


class _TrayMixin:
    """Builds the tray icon/menu and handles tray-triggered actions."""

    def _setup_tray_icon(self, app_icon=None) -> None:
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
        tray_menu = QMenu()

        show_action = tray_menu.addAction("Show Window")
        show_action.triggered.connect(self._tray_show_window)

        tray_menu.addSeparator()

        daemon_action = tray_menu.addAction("Toggle Daemon")
        daemon_action.triggered.connect(self._tray_toggle_daemon)

        next_wp_action = tray_menu.addAction("Next Wallpaper")
        next_wp_action.triggered.connect(self._tray_next_wallpaper)

        tray_menu.addSeparator()

        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.quit)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.setToolTip("Image Toolkit")
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _tray_show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

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
