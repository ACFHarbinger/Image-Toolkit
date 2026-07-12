from pathlib import Path
from unittest.mock import patch

import pytest
from gui.src.windows.settings.settings_window import SettingsWindow
from PySide6.QtWidgets import QMessageBox

pytestmark = pytest.mark.gui


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
                "gui.src.windows.settings.settings_window.IMAGE_TOOLKIT_DIR",
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
            patch("gui.src.windows.settings.settings_window.IMAGE_TOOLKIT_DIR", tmp_path),
            patch(
                "gui.src.windows.settings.settings_window.QDesktopServices.openUrl"
            ) as mock_open_url,
            patch(
                "gui.src.windows.settings.settings_window.QUrl.fromLocalFile"
            ) as mock_from_local_file,
        ):
            window._view_app_logs()
            mock_from_local_file.assert_called_once_with(str(log_file))
            mock_open_url.assert_called_once()

    def test_view_daemon_logs_file_missing(self, q_app):
        window = SettingsWindow()
        with (
            patch(
                "gui.src.windows.settings.settings_window.IMAGE_TOOLKIT_DIR",
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
            patch("gui.src.windows.settings.settings_window.IMAGE_TOOLKIT_DIR", tmp_path),
            patch(
                "gui.src.windows.settings.settings_window.QDesktopServices.openUrl"
            ) as mock_open_url,
            patch(
                "gui.src.windows.settings.settings_window.QUrl.fromLocalFile"
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
            patch("gui.src.windows.settings.settings_window.ROOT_DIR", mock_root),
            patch("gui.src.windows.settings.settings_window.API_DIR", mock_api),
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
            patch("gui.src.windows.settings.settings_window.API_DIR", mock_api),
            patch(
                "gui.src.windows.settings.settings_window.QFileDialog.getOpenFileName",
                return_value=(str(dummy_import_file), "JSON"),
            ),
            patch(
                "gui.src.windows.settings.settings_window.QInputDialog.getText",
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
            patch("gui.src.windows.settings.settings_window.API_DIR", mock_api),
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


class TestSettingsWindowRecursiveScan:
    def test_recursive_scan_checkbox_exists_and_defaults(self, q_app):
        window = SettingsWindow()
        assert window.recursive_scan_check is not None
        assert window.recursive_scan_check.isChecked() is True

    def test_recursive_scan_reset(self, q_app):
        window = SettingsWindow()
        window.recursive_scan_check.setChecked(False)
        window.reset_settings()
        assert window.recursive_scan_check.isChecked() is True

    def test_recursive_scan_save_and_load(self, q_app):
        window = SettingsWindow()
        window.recursive_scan_check.setChecked(False)

        from gui.src.windows.settings.app_settings import AppSettings
        AppSettings.set_recursive_scan(True)
        assert AppSettings.recursive_scan() is True

        from unittest.mock import MagicMock
        window.vault_manager = MagicMock()
        window.vault_manager.load_account_credentials.return_value = {
            "theme": "dark",
            "active_tab_configs": {},
            "system_preference_profiles": {},
            "preferences": {}
        }

        with patch.object(QMessageBox, "information"):
            window._update_settings_logic()

        assert AppSettings.recursive_scan() is False

        # Reset setting to default True
        AppSettings.set_recursive_scan(True)


class TestSettingsWindowFavouriteDirectories:
    def test_favourites_ui_elements_exist(self, q_app):
        window = SettingsWindow()
        assert window.fav_list_widget is not None
        assert window.btn_add_fav_browse is not None
        assert window.btn_remove_fav is not None
        assert window.fav_path_input is not None
        assert window.btn_add_fav_path is not None

    def test_add_manual_favourite_success(self, q_app, tmp_path):
        window = SettingsWindow()
        window.fav_list_widget.clear()

        # Create a dummy folder to add
        fav_dir = tmp_path / "my_fav_dir"
        fav_dir.mkdir()

        window.fav_path_input.setText(str(fav_dir))
        window._add_manual_favourite()

        # Verify it was added to the UI list widget
        assert window.fav_list_widget.count() == 1
        assert window.fav_list_widget.item(0).text() == str(fav_dir)
        # Check manual input cleared
        assert window.fav_path_input.text() == ""

    def test_add_manual_favourite_nonexistent(self, q_app):
        window = SettingsWindow()
        window.fav_list_widget.clear()

        nonexistent = "/tmp/some_extremely_unlikely_nonexistent_directory_name"
        window.fav_path_input.setText(nonexistent)

        with patch.object(QMessageBox, "warning") as mock_warning:
            window._add_manual_favourite()
            mock_warning.assert_called_once()
            assert "does not exist" in mock_warning.call_args[0][2]

        assert window.fav_list_widget.count() == 0

    def test_add_manual_favourite_duplicate(self, q_app, tmp_path):
        window = SettingsWindow()
        window.fav_list_widget.clear()
        fav_dir = tmp_path / "my_fav_dir"
        fav_dir.mkdir()

        window.fav_list_widget.addItem(str(fav_dir))
        window.fav_path_input.setText(str(fav_dir))

        with patch.object(QMessageBox, "information") as mock_info:
            window._add_manual_favourite()
            mock_info.assert_called_once()
            assert "already in your favourites" in mock_info.call_args[0][2]

        assert window.fav_list_widget.count() == 1

    def test_browse_add_favourite(self, q_app, tmp_path):
        window = SettingsWindow()
        window.fav_list_widget.clear()
        fav_dir = tmp_path / "browse_fav"
        fav_dir.mkdir()

        with patch("gui.src.windows.settings.settings_window.QFileDialog.getExistingDirectory", return_value=str(fav_dir)):
            window._browse_add_favourite()

        assert window.fav_list_widget.count() == 1
        assert window.fav_list_widget.item(0).text() == str(fav_dir)

    def test_remove_selected_favourite(self, q_app):
        window = SettingsWindow()
        window.fav_list_widget.clear()
        window.fav_list_widget.addItem("/path/one")
        window.fav_list_widget.addItem("/path/two")

        # Select first item
        window.fav_list_widget.setCurrentRow(0)
        window._remove_selected_favourite()

        assert window.fav_list_widget.count() == 1
        assert window.fav_list_widget.item(0).text() == "/path/two"

    def test_remove_selected_favourite_none_selected(self, q_app):
        window = SettingsWindow()
        window.fav_list_widget.clear()
        window.fav_list_widget.addItem("/path/one")

        # Clear selection
        window.fav_list_widget.clearSelection()
        window.fav_list_widget.setCurrentItem(None) # pyrefly: ignore [bad-argument-type]
        with patch.object(QMessageBox, "warning") as mock_warning:
            window._remove_selected_favourite()
            mock_warning.assert_called_once()

        assert window.fav_list_widget.count() == 1

    def test_save_and_load_favourite_directories(self, q_app, tmp_path):
        window = SettingsWindow()
        window.fav_list_widget.clear()

        fav1 = str(tmp_path / "fav1")
        fav2 = str(tmp_path / "fav2")
        Path(fav1).mkdir(parents=True, exist_ok=True)
        Path(fav2).mkdir(parents=True, exist_ok=True)

        window.fav_list_widget.addItem(fav1)
        window.fav_list_widget.addItem(fav2)

        from unittest.mock import MagicMock
        window.vault_manager = MagicMock()
        window.vault_manager.load_account_credentials.return_value = {
            "theme": "dark",
            "active_tab_configs": {},
            "system_preference_profiles": {},
            "preferences": {}
        }

        from gui.src.windows.settings.app_settings import AppSettings
        # Clean current favourites first
        AppSettings.set_favourite_directories([])

        with patch.object(QMessageBox, "information"):
            window._update_settings_logic()

        assert AppSettings.favourite_directories() == [fav1, fav2]

        # Clean up
        AppSettings.set_favourite_directories([])


class TestSettingsWindowMalFetchMethod:
    def test_mal_fetch_method_combo_exists_and_defaults_to_jikan(self, q_app):
        window = SettingsWindow()
        assert window.mal_fetch_method_combo is not None
        assert window.mal_fetch_method_combo.currentData() == "jikan"

    def test_mal_fetch_method_combo_has_all_three_methods(self, q_app):
        from backend.src.web.clients.mal_dispatcher import MAL_FETCH_METHODS

        window = SettingsWindow()
        combo = window.mal_fetch_method_combo
        keys = {combo.itemData(i) for i in range(combo.count())}
        assert keys == {key for key, _label in MAL_FETCH_METHODS}

    def test_mal_fetch_method_reset(self, q_app):
        window = SettingsWindow()
        idx = window.mal_fetch_method_combo.findData("scrape")
        window.mal_fetch_method_combo.setCurrentIndex(idx)
        window.reset_settings()
        assert window.mal_fetch_method_combo.currentData() == "jikan"

    def test_mal_fetch_method_save_and_load(self, q_app):
        from unittest.mock import MagicMock

        from gui.src.windows.settings.app_settings import AppSettings

        window = SettingsWindow()
        idx = window.mal_fetch_method_combo.findData("scrape")
        window.mal_fetch_method_combo.setCurrentIndex(idx)

        window.vault_manager = MagicMock()
        window.vault_manager.load_account_credentials.return_value = {
            "theme": "dark",
            "active_tab_configs": {},
            "system_preference_profiles": {},
            "preferences": {},
        }

        with patch.object(QMessageBox, "information"):
            window._update_settings_logic()

        assert AppSettings.mal_fetch_method() == "scrape"

        # Reset setting to default
        AppSettings.set_mal_fetch_method("jikan")

