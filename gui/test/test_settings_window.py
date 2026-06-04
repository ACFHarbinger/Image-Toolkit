from unittest.mock import patch
from pathlib import Path
from PySide6.QtWidgets import QMessageBox
from gui.src.windows.settings_window import SettingsWindow


class TestSettingsWindowLogs:
    def test_view_app_logs_button_exists(self, q_app):
        window = SettingsWindow()
        assert window.btn_view_logs is not None
        assert window.btn_view_logs.text() == "View App Logs"
        assert window.btn_view_daemon_logs is not None
        assert window.btn_view_daemon_logs.text() == "View Daemon Logs"

    def test_view_app_logs_file_missing(self, q_app):
        window = SettingsWindow()
        with (
            patch("gui.src.windows.settings_window.IMAGE_TOOLKIT_DIR", Path("/tmp/nonexistent_dir")),
            patch.object(QMessageBox, "information") as mock_info
        ):
            window._view_app_logs()
            mock_info.assert_called_once()
            assert "No Logs" in mock_info.call_args[0][1]

    def test_view_app_logs_file_exists(self, q_app, tmp_path):
        window = SettingsWindow()
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        log_file = log_dir / "image_toolkit.log"
        log_file.write_text("dummy logs")

        with (
            patch("gui.src.windows.settings_window.IMAGE_TOOLKIT_DIR", tmp_path),
            patch("gui.src.windows.settings_window.QDesktopServices.openUrl") as mock_open_url,
            patch("gui.src.windows.settings_window.QUrl.fromLocalFile") as mock_from_local_file
        ):
            window._view_app_logs()
            mock_from_local_file.assert_called_once_with(str(log_file))
            mock_open_url.assert_called_once()

    def test_view_daemon_logs_file_missing(self, q_app):
        window = SettingsWindow()
        with (
            patch("gui.src.windows.settings_window.IMAGE_TOOLKIT_DIR", Path("/tmp/nonexistent_dir")),
            patch.object(QMessageBox, "information") as mock_info
        ):
            window._view_daemon_logs()
            mock_info.assert_called_once()
            assert "No Logs" in mock_info.call_args[0][1]

    def test_view_daemon_logs_file_exists(self, q_app, tmp_path):
        window = SettingsWindow()
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        log_file = log_dir / "slideshow_daemon.log"
        log_file.write_text("dummy daemon logs")

        with (
            patch("gui.src.windows.settings_window.IMAGE_TOOLKIT_DIR", tmp_path),
            patch("gui.src.windows.settings_window.QDesktopServices.openUrl") as mock_open_url,
            patch("gui.src.windows.settings_window.QUrl.fromLocalFile") as mock_from_local_file
        ):
            window._view_daemon_logs()
            mock_from_local_file.assert_called_once_with(str(log_file))
            mock_open_url.assert_called_once()
