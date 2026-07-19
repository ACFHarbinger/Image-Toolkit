from unittest.mock import MagicMock

import pytest
from gui.src.windows.main.login_window import LoginWindow
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

pytestmark = pytest.mark.gui


class TestLoginWindowKeyPress:
    def test_escape_key_closes_window(self, q_app):
        # Create instance of LoginWindow
        window = LoginWindow()

        # Mock the close method to verify it's called
        window.close = MagicMock()

        # Create a QKeyEvent for escape
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)

        # Call the keyPressEvent directly
        window.keyPressEvent(event)

        # Assert that close was called
        window.close.assert_called_once()

    def test_other_key_does_not_close_window(self, q_app):
        window = LoginWindow()
        window.close = MagicMock()

        # Send key 'A' instead of Escape
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier)

        window.keyPressEvent(event)

        window.close.assert_not_called()


class TestLoginWindowCryptoAutoLoad:
    def test_copy_template_crypto_files(self, q_app, tmp_path):
        from unittest.mock import patch

        template_dir = tmp_path / "assets" / "secrets"
        template_dir.mkdir(parents=True, exist_ok=True)

        target_dir = tmp_path / "image-toolkit" / "secrets"

        # Create template files
        file1 = template_dir / "my_keystore.p12"
        file1.write_text("keystore data")
        file2 = template_dir / "pepper.txt"
        file2.write_text("pepper data")

        # Also create a file in target_dir beforehand to check it doesn't get overwritten
        target_dir.mkdir(parents=True, exist_ok=True)
        existing_file = target_dir / "pepper.txt"
        existing_file.write_text("original pepper data")

        window = LoginWindow()

        with (
            patch("gui.src.windows.main.login_window.udef.SECRETS_DIR", template_dir),
            patch("gui.src.windows.main.login_window.udef.LOCAL_SECRETS_DIR", target_dir),
        ):
            window._copy_template_crypto_files()

            # Check file1 (which didn't exist) was copied
            assert (target_dir / "my_keystore.p12").exists()
            assert (target_dir / "my_keystore.p12").read_text() == "keystore data"

            # Check file2 (which already existed) was not overwritten
            assert (target_dir / "pepper.txt").exists()
            assert (target_dir / "pepper.txt").read_text() == "original pepper data"


class TestLoginWindowPreferenceProfile:
    def test_login_dropdown_with_profiles(self, q_app):
        import hashlib
        import json
        from unittest.mock import MagicMock, patch

        # Create instance of LoginWindow
        window = LoginWindow()
        window._copy_template_crypto_files = MagicMock()
        window._get_credentials = MagicMock(return_value=("testuser", "password"))
        window._load_api_files = MagicMock()
        window.close = MagicMock()

        # Mock VaultManager
        mock_vault = MagicMock()
        mock_vault.PEPPER = "pepper"

        # Calculate correct password hash
        password_combined = ("password" + "salt" + "pepper").encode("utf-8")
        correct_hash = hashlib.sha256(password_combined).hexdigest()

        stored_data = {
            "account_name": "testuser",
            "hashed_password": correct_hash,
            "salt": "salt",
            "system_preference_profiles": {
                "Work Profile": {
                    "theme": "light",
                    "active_tab_configs": {"Convert": "PNG Config"},
                    "accent_color_dark": "#ff0000",
                    "accent_color_light": "#00ff00",
                    "font_scale": 120,
                    "ui_density": "Compact",
                }
            },
            "theme": "dark",
            "active_tab_configs": {},
            "preferences": {"session_recovery_level": "All Tabs"},
        }
        mock_vault.load_account_credentials.return_value = stored_data
        window.vault_manager = mock_vault

        # Patch udef, VaultManager, and QInputDialog.getItem to return "Default"
        with (
            patch("gui.src.windows.main.login_window.udef.update_cryptographic_values"),
            patch("gui.src.windows.main.login_window.VaultManager", return_value=mock_vault),
            patch("gui.src.windows.main.login_window.QInputDialog.getItem") as mock_get_item,
            patch("gui.src.windows.main.login_window.QMessageBox.information"),
        ):
            # Test selecting "Default"
            mock_get_item.return_value = ("Default", True)
            window.attempt_login()

            # Verify QInputDialog was called with correct items
            mock_get_item.assert_called_once()
            items_arg = mock_get_item.call_args[0][3]
            assert "Default" in items_arg
            assert "Previous Profile" in items_arg
            assert "Work Profile" in items_arg
            assert items_arg.index("Default") == 0  # Default index for dialog is 0

            # Verify saved data resets to Default settings
            mock_vault.save_data.assert_called_once()
            saved_json = mock_vault.save_data.call_args[0][0]
            saved_data = json.loads(saved_json)
            assert saved_data["theme"] == "dark"
            assert saved_data["active_tab_configs"] == {}
            assert saved_data["preferences"]["accent_color_dark"] == "#00bcd4"
            assert saved_data["preferences"]["accent_color_light"] == "#007AFF"
            assert saved_data["preferences"]["font_scale"] == 100
            assert saved_data["preferences"]["ui_density"] == "Comfortable"
            # Crucially: session_recovery_level is NOT impacted
            assert saved_data["preferences"]["session_recovery_level"] == "All Tabs"

    def test_login_dropdown_select_previous_profile(self, q_app):
        import hashlib
        from unittest.mock import MagicMock, patch

        # Create instance of LoginWindow
        window = LoginWindow()
        window._copy_template_crypto_files = MagicMock()
        window._get_credentials = MagicMock(return_value=("testuser", "password"))
        window._load_api_files = MagicMock()
        window.close = MagicMock()

        # Mock VaultManager
        mock_vault = MagicMock()
        mock_vault.PEPPER = "pepper"

        # Calculate correct password hash
        password_combined = ("password" + "salt" + "pepper").encode("utf-8")
        correct_hash = hashlib.sha256(password_combined).hexdigest()

        stored_data = {
            "account_name": "testuser",
            "hashed_password": correct_hash,
            "salt": "salt",
            "system_preference_profiles": {
                "Work Profile": {
                    "theme": "light",
                    "active_tab_configs": {"Convert": "PNG Config"},
                    "accent_color_dark": "#ff0000",
                    "accent_color_light": "#00ff00",
                    "font_scale": 120,
                    "ui_density": "Compact",
                }
            },
            "theme": "dark",
            "active_tab_configs": {},
            "preferences": {"session_recovery_level": "All Tabs"},
        }
        mock_vault.load_account_credentials.return_value = stored_data
        window.vault_manager = mock_vault

        # Patch udef, VaultManager, and QInputDialog.getItem to return "Previous Profile"
        with (
            patch("gui.src.windows.main.login_window.udef.update_cryptographic_values"),
            patch("gui.src.windows.main.login_window.VaultManager", return_value=mock_vault),
            patch("gui.src.windows.main.login_window.QInputDialog.getItem") as mock_get_item,
            patch("gui.src.windows.main.login_window.QMessageBox.information"),
        ):
            # Test selecting "Previous Profile"
            mock_get_item.return_value = ("Previous Profile", True)
            window.attempt_login()

            # Verify save_data was NOT called because nothing changed
            mock_vault.save_data.assert_not_called()


class TestGuestMode:
    def test_guest_login_empty_username(self, q_app):
        from unittest.mock import patch

        window = LoginWindow()
        window.username_input.setText("")

        with patch("gui.src.windows.main.login_window.QMessageBox.warning") as mock_warn:
            window.attempt_guest_login()
            mock_warn.assert_called_once()
            assert not window.is_authenticated

    def test_guest_login_successful(self, q_app):
        from unittest.mock import MagicMock, patch

        window = LoginWindow()
        window.username_input.setText("guest_user")
        window.close = MagicMock()

        mock_listener = MagicMock()
        window.login_successful.connect(mock_listener)

        with (
            patch("gui.src.windows.main.login_window.QMessageBox.information") as mock_info,
        ):
            window.attempt_guest_login()

            assert window.is_authenticated
            assert window.vault_manager is not None
            assert window.vault_manager.is_guest is True
            assert window.vault_manager.account_name == "guest_user"
            mock_info.assert_called_once()
            mock_listener.assert_called_once_with(window.vault_manager)
            window.close.assert_called_once()

    def test_guest_vault_memory_operations(self):
        from backend.src.core.vault_manager import VaultManager

        vault = VaultManager.create_guest_vault("volatile_guest")
        assert vault.is_guest is True
        creds = vault.load_account_credentials()
        assert creds["account_name"] == "volatile_guest"

        # Save data in memory
        new_data = {"account_name": "volatile_guest", "theme": "light", "custom": "value"}
        import json
        vault.save_data(json.dumps(new_data))

        loaded = vault.load_account_credentials()
        assert loaded["custom"] == "value"
        assert loaded["theme"] == "light"

