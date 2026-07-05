import contextlib
import json
import os
from unittest.mock import patch

import pytest
from gui.src.windows.main.main_window import MainWindow
from PySide6.QtWidgets import QApplication

pytestmark = pytest.mark.gui

class MockVaultManager:
    def __init__(self, credentials):
        self.creds = credentials
        self.saved_data = None
        self.account_name = "test_user"
        self.secret_key = b"dummy_key_32_bytes_long_123456789"

        class MockSecureJsonVault:
            _vaults = {}
            def __init__(self, key, path):
                self.key = key
                self.path = path
            def saveData(self, data):
                MockSecureJsonVault._vaults[self.path] = data
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                with open(self.path, "w") as f:
                    f.write(data)
            def loadData(self):
                if os.path.exists(self.path):
                    with open(self.path, "r") as f:
                        return f.read()
                return MockSecureJsonVault._vaults.get(self.path, "{}")

        self.SecureJsonVault = MockSecureJsonVault

    def load_account_credentials(self):
        return self.creds

    def save_data(self, json_string):
        self.saved_data = json.loads(json_string)
        self.creds = self.saved_data

    def shutdown(self):
        pass


def cleanup_recovery_files():
    for recovery_dir in ("/home/pkhunter/.image-toolkit/recovery", os.path.expanduser("~/.image-toolkit/recovery")):
        enc_file = os.path.join(recovery_dir, "recovery_test_user.enc")
        if os.path.exists(enc_file):
            with contextlib.suppress(Exception):
                os.remove(enc_file)


class TestMainWindowSessionRecovery:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        cleanup_recovery_files()
        yield
        for widget in QApplication.topLevelWidgets():
            widget.close()
            widget.deleteLater()
        for _ in range(5):
            QApplication.processEvents()
        cleanup_recovery_files()

    def test_session_recovery_restore_all_tabs(self, q_app):
        # Setup initial credentials with recovery settings
        creds = {
            "account_name": "test_user",
            "preferences": {
                "session_recovery_level": "All Tabs"
            },
            "session_recovery_data": {
                "active_category": "Database Management",
                "active_tab": "Search Images",
                "tab_configs": {
                    "SearchTab": {"dummy_key": "dummy_value"}
                }
            }
        }
        vault = MockVaultManager(creds)

        # Patch set_config on SearchTab to check if it gets called
        with patch("gui.src.tabs.database.search_tab.SearchTab.set_config") as mock_set_config:
            window = MainWindow(vault_manager=vault) # pyrefly: ignore [bad-argument-type]
            # Process events to allow QTimer to fire
            QApplication.processEvents()

            # Check if active category is selected
            assert window.command_combo.currentText() == "Database Management"
            # Check if correct tab is active in the QTabWidget
            active_tab_index = window.tabs.currentIndex()
            assert window.tabs.tabText(active_tab_index) == "Search Images"
            # Check if set_config was called with the dummy config
            mock_set_config.assert_called_with({"dummy_key": "dummy_value"})

    def test_session_recovery_save_all_tabs(self, q_app):
        creds = {
            "account_name": "test_user",
            "preferences": {
                "session_recovery_level": "All Tabs"
            },
            "session_recovery_data": {}
        }
        vault = MockVaultManager(creds)

        with (
            patch("gui.src.tabs.database.search_tab.SearchTab.collect", return_value={"search_key": "val1"}),
            patch("gui.src.tabs.core.convert_tab.ConvertTab.collect", return_value={"convert_key": "val2"})
        ):
            window = MainWindow(vault_manager=vault) # pyrefly: ignore [bad-argument-type]
            QApplication.processEvents()

            # Let's change current category and tab
            window.command_combo.setCurrentText("System Tools")
            for index in range(window.tabs.count()):
                if window.tabs.tabText(index) == "Convert":
                    window.tabs.setCurrentIndex(index)
                    break

            # Trigger save
            window._save_session_recovery()

            # Verify saved data in vault / file
            saved = vault.saved_data
            assert saved is not None
            assert saved["session_recovery_data"]["active_category"] == "System Tools"
            assert saved["session_recovery_data"]["active_tab"] == "Convert"
            assert "SearchTab" in saved["session_recovery_data"]["tab_configs"]
            assert saved["session_recovery_data"]["tab_configs"]["SearchTab"] == {"search_key": "val1"}
            assert saved["session_recovery_data"]["tab_configs"]["ConvertTab"] == {"convert_key": "val2"}

    def test_session_recovery_restore_current_tab(self, q_app):
        creds = {
            "account_name": "test_user",
            "preferences": {
                "session_recovery_level": "Current Tab"
            },
            "session_recovery_data": {
                "active_category": "Database Management",
                "active_tab": "Search Images",
                "tab_configs": {
                    "SearchTab": {"search_key": "val1"},
                    "ConvertTab": {"convert_key": "val2"}
                }
            }
        }
        vault = MockVaultManager(creds)

        with (
            patch("gui.src.tabs.database.search_tab.SearchTab.set_config") as mock_search_set,
            patch("gui.src.tabs.core.convert_tab.ConvertTab.set_config") as mock_convert_set
        ):
            MainWindow(vault_manager=vault) # pyrefly: ignore [bad-argument-type]
            QApplication.processEvents()

            # Only SearchTab (which is the active one) should be loaded
            mock_search_set.assert_called_with({"search_key": "val1"})
            mock_convert_set.assert_not_called()

    def test_session_recovery_none(self, q_app):
        creds = {
            "account_name": "test_user",
            "preferences": {
                "session_recovery_level": "None"
            },
            "session_recovery_data": {
                "active_category": "Database Management",
                "active_tab": "Search Images",
                "tab_configs": {
                    "SearchTab": {"search_key": "val1"}
                }
            }
        }
        vault = MockVaultManager(creds)

        with patch("gui.src.tabs.database.search_tab.SearchTab.set_config") as mock_search_set:
            window = MainWindow(vault_manager=vault) # pyrefly: ignore [bad-argument-type]
            QApplication.processEvents()

            # Category/tab should default (e.g. System Tools) instead of restored
            assert window.command_combo.currentText() == "System Tools"
            mock_search_set.assert_not_called()

    def test_restore_last_dir_disabled(self, q_app):
        from backend.src.constants import LOCAL_SOURCE_PATH
        creds = {
            "account_name": "test_user",
            "preferences": {
                "restore_last_dir": False
            }
        }
        vault = MockVaultManager(creds)
        window = MainWindow(vault_manager=vault) # pyrefly: ignore [bad-argument-type]
        QApplication.processEvents()

        expected_dir = LOCAL_SOURCE_PATH
        assert window.convert_tab.format_subtab.last_browsed_dir == expected_dir
        assert window.extractor_tab.last_browsed_scan_dir == expected_dir
