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
            patch(
                "gui.src.windows.settings_window.IMAGE_TOOLKIT_DIR",
                Path("/tmp/nonexistent_dir"),
            ),
            patch.object(QMessageBox, "information") as mock_info,
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
            patch(
                "gui.src.windows.settings_window.QDesktopServices.openUrl"
            ) as mock_open_url,
            patch(
                "gui.src.windows.settings_window.QUrl.fromLocalFile"
            ) as mock_from_local_file,
        ):
            window._view_app_logs()
            mock_from_local_file.assert_called_once_with(str(log_file))
            mock_open_url.assert_called_once()

    def test_view_daemon_logs_file_missing(self, q_app):
        window = SettingsWindow()
        with (
            patch(
                "gui.src.windows.settings_window.IMAGE_TOOLKIT_DIR",
                Path("/tmp/nonexistent_dir"),
            ),
            patch.object(QMessageBox, "information") as mock_info,
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
            patch(
                "gui.src.windows.settings_window.QDesktopServices.openUrl"
            ) as mock_open_url,
            patch(
                "gui.src.windows.settings_window.QUrl.fromLocalFile"
            ) as mock_from_local_file,
        ):
            window._view_daemon_logs()
            mock_from_local_file.assert_called_once_with(str(log_file))
            mock_open_url.assert_called_once()

    def test_credentials_ui_elements_exist(self, q_app):
        window = SettingsWindow()
        assert window.credentials_list is not None
        assert window.btn_export_creds is not None
        assert window.btn_import_cred is not None
        assert window.btn_delete_cred is not None
        assert window.credentials_list.count() == 0

    def test_refresh_credentials_list(self, q_app):
        from unittest.mock import MagicMock

        window = SettingsWindow()
        mock_vault = MagicMock()
        mock_vault.api_credentials = {
            "google_api_key": {"val": 123},
            "client_secret": {"val": 456},
        }
        window.vault_manager = mock_vault
        window._refresh_credentials_list()
        assert window.credentials_list.count() == 2
        assert window.credentials_list.item(0).text() == "client_secret"
        assert window.credentials_list.item(1).text() == "google_api_key"

    def test_export_credentials_to_backup(self, q_app, tmp_path):
        from unittest.mock import MagicMock

        window = SettingsWindow()
        mock_vault = MagicMock()
        mock_vault.api_credentials = {
            "google_api_key": {"val": 123},
            "client_secret": {"val": 456},
        }
        window.vault_manager = mock_vault

        # Setup mock paths
        mock_root = tmp_path / "project_root"
        mock_api = tmp_path / "api"
        mock_api.mkdir(parents=True, exist_ok=True)
        # Create a dummy token.json
        import json

        with open(mock_api / "token.json", "w") as f:
            json.dump({"token": "xyz"}, f)

        with (
            patch("gui.src.windows.settings_window.ROOT_DIR", mock_root),
            patch("gui.src.windows.settings_window.API_DIR", mock_api),
            patch.object(QMessageBox, "information") as mock_info,
        ):
            window._export_credentials_to_backup()
            mock_info.assert_called_once()

            backup_dir = mock_root / "backup"
            assert backup_dir.exists()
            assert (backup_dir / "google_api_key.json").exists()
            assert (backup_dir / "client_secret.json").exists()
            assert (backup_dir / "token.json").exists()

            # Verify contents
            with open(backup_dir / "google_api_key.json", "r") as f:
                assert json.load(f) == {"val": 123}

    def test_import_credential(self, q_app, tmp_path):
        from unittest.mock import MagicMock

        window = SettingsWindow()
        mock_vault = MagicMock()
        mock_vault.api_credentials = {}
        mock_vault.secret_key = "some_key"

        # Mock SecureJsonVault's saveData to write the file
        mock_vault_instance = MagicMock()

        def mock_save_data(data):
            path = mock_vault.SecureJsonVault.call_args[0][1]
            with open(path, "w") as f:
                f.write("encrypted_dummy")

        mock_vault_instance.saveData.side_effect = mock_save_data
        mock_vault.SecureJsonVault.return_value = mock_vault_instance

        window.vault_manager = mock_vault

        # Create dummy json file to import
        import json

        dummy_import_file = tmp_path / "new_creds.json"
        with open(dummy_import_file, "w") as f:
            json.dump({"api_key": "imported_secret"}, f)

        mock_api = tmp_path / "api"
        mock_api.mkdir(parents=True, exist_ok=True)

        with (
            patch("gui.src.windows.settings_window.API_DIR", mock_api),
            patch(
                "gui.src.windows.settings_window.QFileDialog.getOpenFileName",
                return_value=(str(dummy_import_file), "JSON"),
            ),
            patch(
                "gui.src.windows.settings_window.QInputDialog.getText",
                return_value=("imported_alias", True),
            ),
            patch.object(QMessageBox, "information") as mock_info,
            patch.object(QMessageBox, "critical") as mock_crit,
        ):
            window._import_credential()
            if mock_crit.called:
                print("CRITICAL MSG:", mock_crit.call_args[0][2])
            mock_info.assert_called_once()

            # Check that files were created
            assert (mock_api / "imported_alias.json").exists()
            assert (mock_api / "imported_alias.json.enc").exists()

            # Check that it is loaded in-memory and UI refreshed
            assert "imported_alias" in mock_vault.api_credentials
            assert mock_vault.api_credentials["imported_alias"] == {
                "api_key": "imported_secret"
            }
            assert window.credentials_list.count() == 1
            assert window.credentials_list.item(0).text() == "imported_alias"

    def test_delete_credential(self, q_app, tmp_path):
        from unittest.mock import MagicMock

        window = SettingsWindow()
        mock_vault = MagicMock()
        mock_vault.api_credentials = {"to_delete": {"key": "secret"}}
        window.vault_manager = mock_vault

        # Mock list widget selection
        window._refresh_credentials_list()
        window.credentials_list.setCurrentRow(0)

        # Create dummy files to delete
        mock_api = tmp_path / "api"
        mock_api.mkdir(parents=True, exist_ok=True)
        raw_file = mock_api / "to_delete.json"
        enc_file = mock_api / "to_delete.json.enc"
        raw_file.touch()
        enc_file.touch()

        with (
            patch("gui.src.windows.settings_window.API_DIR", mock_api),
            patch.object(
                QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes
            ),
            patch.object(QMessageBox, "information") as mock_info,
        ):
            window._delete_credential()
            mock_info.assert_called_once()

            # Verify files deleted
            assert not raw_file.exists()
            assert not enc_file.exists()

            # Verify memory and UI updated
            assert "to_delete" not in mock_vault.api_credentials
            assert window.credentials_list.count() == 0


class TestSettingsWindowSessionRecovery:
    def test_session_recovery_combo_exists_and_defaults(self, q_app):
        window = SettingsWindow()
        assert window.session_recovery_combo is not None
        items = [
            window.session_recovery_combo.itemText(i)
            for i in range(window.session_recovery_combo.count())
        ]
        assert "None" in items
        assert "Current Tab" in items
        assert "All Tabs" in items
        assert window.session_recovery_combo.currentText() == "None"

    def test_session_recovery_reset(self, q_app):
        window = SettingsWindow()
        window.session_recovery_combo.setCurrentText("All Tabs")
        window.reset_settings()
        assert window.session_recovery_combo.currentText() == "None"
