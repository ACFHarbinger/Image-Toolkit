"""Window lifecycle: tab switching, status bar, relaunch, key/close events.

Extracted from ``main_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import contextlib
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication, QMessageBox, QScrollArea, QSystemTrayIcon

from gui.src.styles.background_canvas import BackgroundCanvasController
from gui.src.windows.settings.app_settings import AppSettings

from ...utils.manager.shortcut_manager import get_registry


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

    def paintEvent(self, event):
        painter = QPainter(self)
        current_tab = None
        if hasattr(self, "tabs") and self.tabs is not None:
            current_tab = self.tabs.tabText(self.tabs.currentIndex())
        BackgroundCanvasController.instance().render_background(painter, self.rect(), active_tab=current_tab)
        painter.end()
        super().paintEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self._shown = True


        # §2.12A tray-icon setup is intentionally NOT auto-constructed here
        # (or anywhere else during startup). Every timing attempt tried --
        # synchronous in __init__, QTimer.singleShot(0), (1500), and this
        # window's own first showEvent() -- still crashed a meaningful
        # fraction of launches with a null-pointer SIGSEGV in libQt6Gui.so.6
        # (nearby offsets: +0x136666, +0x14071e, +0x1342c4), no preceding
        # QSocketNotifier warning. This matches this project's own Addendum
        # 13 precedent for a different Qt subsystem: a genuinely unstable
        # native call under this Plasma6/Wayland/Qt6 combination isn't fixed
        # by *when* it's called, only by not calling it unconditionally at
        # all. See Addendum 27 in
        # .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md.
        #
        # `_setup_tray_icon()` itself (in _tray.py) is untouched and still
        # fully callable -- e.g. from a future opt-in settings toggle -- for
        # anyone who wants the tray icon back and is willing to accept the
        # crash risk on an affected environment; this just removes the
        # unconditional automatic call every session paid regardless of
        # whether tray features were ever used.

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._save_session_recovery()
            if self.vault_manager is not None:
                self.vault_manager.shutdown()
            QApplication.quit()
        elif event.key() == Qt.Key.Key_T and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self._open_tab_search()
            event.accept()
        elif get_registry().matches(event, "general.global_search"):
            self._open_global_search()
            event.accept()
        elif get_registry().matches(event, "general.workflow_templates"):
            self._open_workflow_templates_dialog()
            event.accept()
        elif get_registry().matches(event, "general.save_tab_config"):
            self._open_save_tab_config_dialog()
            event.accept()
        elif get_registry().matches(event, "general.load_tab_config"):
            self._open_load_tab_config_dialog()
            event.accept()
        elif (
            event.key() == Qt.Key.Key_Slash and event.modifiers() == Qt.KeyboardModifier.ControlModifier
        ) or event.key() == Qt.Key.Key_F1:
            self._open_shortcut_overlay()
            event.accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        # §2.12C — minimize to tray / background mode instead of quitting (opt-in)
        if getattr(self, "_minimize_to_tray", False):
            # Only *create* when there is no tray icon yet. Recreating on a
            # transient ``not isVisible()`` (common right after .show() on
            # Wayland/Plasma before the tray host has registered it) spawns a
            # duplicate icon -- _setup_tray_icon() is idempotent and re-shows
            # the existing one on its own.
            if getattr(self, "_tray_icon", None) is None:
                self._setup_tray_icon()
            else:
                self._tray_icon.show()
            # Persist geometry and tab settings before going to background so
            # the next real quit (via tray menu or OS shutdown) sees up-to-date
            # state even if the process is killed uncleanly while hidden.
            AppSettings.set_mainwindow_geometry(self.saveGeometry())  # pyrefly: ignore [bad-argument-type]
            self._save_session_recovery()
            event.ignore()
            self.hide()
            if getattr(self, "_tray_icon", None) and self._tray_icon.isVisible():
                self._tray_icon.showMessage(
                    "Image Toolkit",
                    "Application running in background. Click tray icon to reopen.",
                    QSystemTrayIcon.MessageIcon.Information,
                    2500,
                )
            return


        # Bug 1: if extractions are still running, hide every window and keep
        # the process alive headlessly until they finish, then quit. Only
        # UI-bound work is cancelled on close; the extraction itself continues
        # uninterrupted.
        if self._defer_close_for_extractions():
            event.ignore()
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

    def _quit_application(self) -> None:
        """Save settings then perform a clean application quit.

        Used by the tray icon's Quit action so that session recovery data
        and window geometry are persisted even when the user quits from the
        system tray (where closeEvent is bypassed by QApplication.quit()).
        """
        AppSettings.set_mainwindow_geometry(self.saveGeometry())  # pyrefly: ignore [bad-argument-type]
        self._save_session_recovery()
        if self.vault_manager is not None:
            self.vault_manager.shutdown()
        QApplication.quit()

    def _defer_close_for_extractions(self) -> bool:
        """Return True (and arm a deferred close with progress dialog) when an extraction is
        still running, so background work finishes before exit (Bug 1)."""
        extractor = getattr(self, "extractor_tab", None)
        if extractor is None or not getattr(extractor, "has_active_extractions", lambda: False)():
            return False

        self._close_pending = True
        self.hide()
        for window in list(QApplication.topLevelWidgets()):
            if window is not self and window.isVisible():
                with contextlib.suppress(Exception):
                    window.hide()

        from gui.src.components.dialogs.extraction_close_progress_dialog import (
            ExtractionCloseProgressDialog,
        )

        completed = 0
        total = 1
        current_title = ""
        if hasattr(extractor, "get_tasks_progress"):
            completed, total, current_title = extractor.get_tasks_progress()
        elif hasattr(extractor, "extraction_progress_bar"):
            completed = extractor.extraction_progress_bar.value()
            total = max(extractor.extraction_progress_bar.maximum(), 1)

        def _on_cancel():
            if hasattr(extractor, "cancel_queue"):
                extractor.cancel_queue()
            if hasattr(extractor, "cancel_extraction"):
                extractor.cancel_extraction()
            self._finish_deferred_close()

        def _on_confirm():
            self._finish_deferred_close()

        dialog = ExtractionCloseProgressDialog(
            parent=None,
            on_cancel=_on_cancel,
            on_confirm=_on_confirm,
            total=total,
            completed=completed,
        )
        if current_title:
            dialog.update_progress(completed, total, current_title)

        if hasattr(extractor, "set_close_progress_dialog"):
            extractor.set_close_progress_dialog(dialog)
        else:
            extractor._close_progress_dialog = dialog
        extractor.set_close_when_finished(dialog.on_all_finished)
        dialog.show()

        return True

    def _finish_deferred_close(self) -> None:
        """Called once extractions finish or are cancelled; performs
        the real close now that no worker is active."""
        if not getattr(self, "_close_pending", False):
            return
        self._close_pending = False
        self.close()


__all__ = ["_LifecycleMixin"]
