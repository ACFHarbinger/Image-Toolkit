"""Window lifecycle: tab switching, status bar, relaunch, key/close events.

Extracted from ``main_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import contextlib
import os
import sys

from gui.src.windows.settings.app_settings import AppSettings
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QScrollArea, QSystemTrayIcon

from ....utils.shortcut_manager import get_registry


class _LifecycleMixin:
    """Tab switching, status bar, relaunch, and key-press/close handling."""

    def on_command_changed(self, new_command: str):
        """
        Dynamically changes the tabs.
        Rescues widgets from ScrollAreas before clearing to prevent Segfaults.
        """
        count = self.tabs.count()
        for i in range(count):
            scroll_area = self.tabs.widget(i)
            if isinstance(scroll_area, QScrollArea):
                # takeWidget() unparents the widget and passes ownership back to us
                # preventing it from being destroyed.
                scroll_area.takeWidget()

        self.tabs.clear()

        tab_map = self.all_tabs.get(new_command, {})

        for tab_name, tab_widget in tab_map.items():
            scroll_wrapper = QScrollArea()
            scroll_wrapper.setWidgetResizable(True)
            scroll_wrapper.setFrameShape(QScrollArea.Shape.NoFrame)
            scroll_wrapper.setWidget(tab_widget)
            self.tabs.addTab(scroll_wrapper, tab_name)

    def update_header(self):
        try:
            self.cached_creds = self.vault_manager.load_account_credentials()
            account_name = self.cached_creds.get("account_name", "Authenticated User")
        except Exception:
            account_name = "Authenticated User"
        self.title_label.setText(f"Image Database and Toolkit - {account_name}")
        self.set_application_theme(self.current_theme)

    def restart_application(self):
        self.close()
        QApplication.instance().quit()  # pyrefly: ignore [missing-attribute]
        print("Application attempting relaunch...")
        try:
            os.execv(sys.executable, ["python"] + sys.argv)
        except OSError as e:
            QMessageBox.critical(
                self,
                "Relaunch Error",
                f"Failed to execute relaunch command:\n{e}\nPlease restart manually.",
            )
            print(f"FATAL: os.execv failed: {e}")

    # --- §2.10C — Non-blocking status bar API ---
    def show_status(self, message: str, timeout_ms: int = 3000) -> None:
        """Display *message* in the status bar for *timeout_ms* ms (0 = persistent)."""
        if hasattr(self, "_status_bar"):
            self._status_bar.showMessage(message, timeout_ms)

    def showEvent(self, event):
        super().showEvent(event)
        self._shown = True

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._save_session_recovery()
            if self.vault_manager is not None:
                self.vault_manager.shutdown()
            QApplication.quit()
        elif event.key() == Qt.Key.Key_T and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self._open_tab_search()
            event.accept()
        elif get_registry().matches(event, "general.save_tab_config"):
            self._open_save_tab_config_dialog()
            event.accept()
        elif (
            event.key() == Qt.Key.Key_Slash and event.modifiers() == Qt.KeyboardModifier.ControlModifier
        ) or event.key() == Qt.Key.Key_F1:
            self._open_shortcut_overlay()
            event.accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        # §2.12C — minimize to tray instead of quitting (opt-in)
        if getattr(self, "_minimize_to_tray", False) and self._tray_icon and self._tray_icon.isVisible():
            event.ignore()
            self.hide()
            self._tray_icon.showMessage(
                "Image Toolkit",
                "Minimised to tray. Double-click the icon to reopen.",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )
            return

        # §3.17 — persist window geometry so next launch restores it
        AppSettings.set_mainwindow_geometry(self.saveGeometry())  # pyrefly: ignore [bad-argument-type]
        self._save_session_recovery()

        if self.settings_window:
            self.settings_window.close()

        # Close all instantiated tabs to trigger their cleanup logic (cancellation of workers/timers)
        if hasattr(self, "all_tabs"):
            for category in self.all_tabs.values():
                for tab in category.values():
                    if tab:
                        with contextlib.suppress(Exception):
                            tab.close()

        if self.vault_manager is not None:
            self.vault_manager.shutdown()

        super().closeEvent(event)


__all__ = ["_LifecycleMixin"]
