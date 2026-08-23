"""Regression tests: settings must be saved when minimize-to-tray is active.

Bug: when _minimize_to_tray=True, closeEvent returned immediately after hiding
the window without calling AppSettings.set_mainwindow_geometry() or
_save_session_recovery(). The tray Quit action called QApplication.quit()
directly, also bypassing all save logic.

Fix:
  - closeEvent tray branch now saves geometry + session before hiding.
  - Tray Quit action calls _quit_application() which saves before quitting.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.gui


# ---------------------------------------------------------------------------
# Minimal _LifecycleMixin host (avoids spinning up the full MainWindow)
# ---------------------------------------------------------------------------

def _make_lifecycle_host(minimize_to_tray: bool):
    """Return a minimal object that mixes in _LifecycleMixin."""
    from gui.src.windows.main._lifecycle import _LifecycleMixin
    from PySide6.QtCore import QByteArray
    from PySide6.QtWidgets import QWidget

    class Host(_LifecycleMixin, QWidget):
        def __init__(self):
            QWidget.__init__(self)
            self._minimize_to_tray = minimize_to_tray
            self._tray_icon = None
            self.settings_window = None
            self.all_tabs = {}
            self.vault_manager = MagicMock()
            self.vault_manager.is_guest = False
            self.vault_manager.load_account_credentials.return_value = {
                "preferences": {"session_recovery_level": "None", "restore_last_tab": False}
            }
            # Stub _save_session_recovery and _setup_tray_icon
            self._save_session_recovery = MagicMock()
            self._setup_tray_icon = MagicMock()
            self._defer_close_for_extractions = MagicMock(return_value=False)

        def saveGeometry(self):  # type: ignore[override]
            return QByteArray()

    return Host()


# ---------------------------------------------------------------------------
# closeEvent — minimize-to-tray path
# ---------------------------------------------------------------------------

class TestCloseEventTrayPath:
    def test_geometry_saved_before_hide(self, q_app):
        """AppSettings.set_mainwindow_geometry must be called before the window is hidden."""
        host = _make_lifecycle_host(minimize_to_tray=True)

        with patch(
            "gui.src.windows.main._lifecycle.AppSettings"
        ) as mock_settings:
            from PySide6.QtGui import QCloseEvent
            event = QCloseEvent()
            host.closeEvent(event)

        mock_settings.set_mainwindow_geometry.assert_called_once()
        assert not host.isVisible()

    def test_session_recovery_saved_before_hide(self, q_app):
        """_save_session_recovery must be called before the window is hidden."""
        host = _make_lifecycle_host(minimize_to_tray=True)

        with patch("gui.src.windows.main._lifecycle.AppSettings"):
            from PySide6.QtGui import QCloseEvent
            event = QCloseEvent()
            host.closeEvent(event)

        host._save_session_recovery.assert_called_once()

    def test_event_is_ignored_not_accepted(self, q_app):
        """The close event must be ignored (window stays alive as a process)."""
        host = _make_lifecycle_host(minimize_to_tray=True)

        with patch("gui.src.windows.main._lifecycle.AppSettings"):
            from PySide6.QtGui import QCloseEvent
            event = QCloseEvent()
            host.closeEvent(event)

        assert event.isAccepted() is False


# ---------------------------------------------------------------------------
# closeEvent — normal (non-tray) path: existing behaviour must be unchanged
# ---------------------------------------------------------------------------

class TestCloseEventNormalPath:
    def test_geometry_saved_on_normal_close(self, q_app):
        host = _make_lifecycle_host(minimize_to_tray=False)

        with patch("gui.src.windows.main._lifecycle.AppSettings") as mock_settings:
            from PySide6.QtGui import QCloseEvent
            event = QCloseEvent()
            host.closeEvent(event)

        mock_settings.set_mainwindow_geometry.assert_called_once()

    def test_session_recovery_saved_on_normal_close(self, q_app):
        host = _make_lifecycle_host(minimize_to_tray=False)

        with patch("gui.src.windows.main._lifecycle.AppSettings"):
            from PySide6.QtGui import QCloseEvent
            event = QCloseEvent()
            host.closeEvent(event)

        host._save_session_recovery.assert_called_once()


# ---------------------------------------------------------------------------
# _quit_application — tray Quit path
# ---------------------------------------------------------------------------

class TestQuitApplication:
    def test_geometry_saved_before_quit(self, q_app):
        host = _make_lifecycle_host(minimize_to_tray=True)

        with patch("gui.src.windows.main._lifecycle.AppSettings") as mock_settings, \
             patch("gui.src.windows.main._lifecycle.QApplication.quit"):
            host._quit_application()

        mock_settings.set_mainwindow_geometry.assert_called_once()

    def test_session_recovery_saved_before_quit(self, q_app):
        host = _make_lifecycle_host(minimize_to_tray=True)

        with patch("gui.src.windows.main._lifecycle.AppSettings"), \
             patch("gui.src.windows.main._lifecycle.QApplication.quit"):
            host._quit_application()

        host._save_session_recovery.assert_called_once()

    def test_vault_shutdown_before_quit(self, q_app):
        host = _make_lifecycle_host(minimize_to_tray=True)

        with patch("gui.src.windows.main._lifecycle.AppSettings"), \
             patch("gui.src.windows.main._lifecycle.QApplication.quit"):
            host._quit_application()

        host.vault_manager.shutdown.assert_called_once()

    def test_qapplication_quit_is_called(self, q_app):
        host = _make_lifecycle_host(minimize_to_tray=True)

        with patch("gui.src.windows.main._lifecycle.AppSettings"), \
             patch("gui.src.windows.main._lifecycle.QApplication.quit") as mock_quit:
            host._quit_application()

        mock_quit.assert_called_once()

    def test_save_happens_before_quit(self, q_app):
        """Strict ordering: save must complete before QApplication.quit fires."""
        call_order = []
        host = _make_lifecycle_host(minimize_to_tray=True)
        host._save_session_recovery = MagicMock(side_effect=lambda: call_order.append("save"))

        with patch("gui.src.windows.main._lifecycle.AppSettings") as mock_settings:
            mock_settings.set_mainwindow_geometry.side_effect = lambda _: call_order.append("geometry")
            with patch(
                "gui.src.windows.main._lifecycle.QApplication.quit",
                side_effect=lambda: call_order.append("quit"),
            ):
                host._quit_application()

        assert call_order.index("geometry") < call_order.index("quit")
        assert call_order.index("save") < call_order.index("quit")
