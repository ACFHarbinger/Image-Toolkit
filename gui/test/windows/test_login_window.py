from unittest.mock import MagicMock

import pytest
from gui.src.windows.authentication.login_window import LoginWindow
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


class TestLoginWindowNoTemplateSeeding:
    """Real secret material must never ship in an artifact, so the login flow
    no longer seeds a keystore/vault from assets/secrets. A login attempt for
    an unknown account must fail cleanly without materialising any secret file
    from a template."""

    def test_no_template_copy_helper(self, q_app):
        assert not hasattr(LoginWindow(), "_copy_template_crypto_files")

    def test_login_unknown_account_seeds_nothing(self, q_app, tmp_path, monkeypatch):
        from unittest.mock import patch

        from backend.src.constants import crypto as crypto_consts

        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        monkeypatch.setattr(crypto_consts, "ACTIVE_SECRETS_DIR", str(secrets_dir))

        window = LoginWindow()
        window._get_credentials = MagicMock(return_value=("ghost_acct", "whatever-123"))

        with (
            patch("gui.src.windows.authentication.login_window.QMessageBox.critical") as critical,
            patch("gui.src.windows.authentication.login_window.QMessageBox.warning"),
            patch("gui.src.windows.authentication.login_window.QMessageBox.information"),
        ):
            window.attempt_login()

        assert not window.is_authenticated
        critical.assert_called_once()  # clean error dialog, not a raw traceback
        # A fresh pepper may be generated, but no keystore/vault may be seeded.
        assert not list(secrets_dir.glob("*.p12"))
        assert not list(secrets_dir.glob("*.vault"))


class TestLoginWindowCreateAccount:
    def test_create_account_builds_keystore_from_nothing(self, q_app, tmp_path, monkeypatch):
        """Regression: create_account() must create the keystore before loading
        it. The JVM-era load_keystore() made an empty in-memory store on a
        missing file; the native one raises FileNotFoundError, so calling it
        ahead of create_key_if_missing() broke first-run account creation in
        the packaged app ("Keystore file not found: my_keystore-<name>.p12").
        Uses the real VaultManager + native crypto lib against a tmp secrets
        dir, with the asset-template copy stubbed out.
        """
        from unittest.mock import patch

        from backend.src.constants import crypto as crypto_consts

        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        monkeypatch.setattr(crypto_consts, "ACTIVE_SECRETS_DIR", str(secrets_dir))

        window = LoginWindow()
        window._load_api_files = MagicMock()
        window.close = MagicMock()
        window._get_credentials = MagicMock(return_value=("regr_acct", "regr-pass-123"))

        listener = MagicMock()
        window.login_successful.connect(listener)

        with (
            patch("gui.src.windows.authentication.login_window.QMessageBox.information"),
            patch(
                "gui.src.windows.authentication.login_window.QMessageBox.critical"
            ) as critical,
        ):
            window.create_account()

        critical.assert_not_called()
        assert window.is_authenticated
        assert (secrets_dir / "my_keystore-regr_acct.p12").exists()
        assert (secrets_dir / "my_secure_data-regr_acct.vault").exists()
        listener.assert_called_once_with(window.vault_manager)
        window.close.assert_not_called()

        window.vault_manager.shutdown()


class TestLoginWindowPreferenceProfile:
    def test_login_dropdown_with_profiles(self, q_app):
        import hashlib
        import json
        from unittest.mock import MagicMock, patch

        # Create instance of LoginWindow
        window = LoginWindow()
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
            patch("gui.src.windows.authentication.login_window.udef.update_cryptographic_values"),
            patch("gui.src.windows.authentication.login_window.VaultManager", return_value=mock_vault),
            patch("gui.src.windows.authentication.login_window.QInputDialog.getItem") as mock_get_item,
            patch("gui.src.windows.authentication.login_window.QMessageBox.information"),
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
            patch("gui.src.windows.authentication.login_window.udef.update_cryptographic_values"),
            patch("gui.src.windows.authentication.login_window.VaultManager", return_value=mock_vault),
            patch("gui.src.windows.authentication.login_window.QInputDialog.getItem") as mock_get_item,
            patch("gui.src.windows.authentication.login_window.QMessageBox.information"),
        ):
            # Test selecting "Previous Profile"
            mock_get_item.return_value = ("Previous Profile", True)
            window.attempt_login()

            # Verify save_data was NOT called because nothing changed
            mock_vault.save_data.assert_not_called()


class TestGuestMode:
    def test_repeated_guest_login_emits_success_once(self, q_app):
        from unittest.mock import patch

        window = LoginWindow()
        listener = MagicMock()
        window.login_successful.connect(listener)

        with patch(
            "gui.src.windows.authentication.login_window.QMessageBox.information"
        ):
            window._do_guest_login("guest_user", anonymous=False)
            window._do_guest_login("guest_user", anonymous=False)

        listener.assert_called_once_with(window.vault_manager)
        assert window._auth_transition_pending
        assert not window.login_button.isEnabled()

    def test_startup_failure_reenables_login_controls(self, q_app):
        from unittest.mock import patch

        window = LoginWindow()
        vault = MagicMock()
        window.vault_manager = vault
        window.is_authenticated = True
        assert window._begin_auth_transition()

        with patch(
            "gui.src.windows.authentication.login_window.QMessageBox.critical"
        ) as critical:
            window.auth_transition_failed("construction failed")

        assert not window._auth_transition_pending
        assert window.login_button.isEnabled()
        assert window.create_button.isEnabled()
        assert window.vault_manager is None
        assert not window.is_authenticated
        vault.shutdown.assert_called_once()
        critical.assert_called_once()

    def test_guest_login_empty_username_falls_back_to_anonymous(self, q_app):
        """Empty username in guest mode should generate an anonymous random username."""
        from unittest.mock import MagicMock, patch

        window = LoginWindow()
        window.username_input.setText("")
        window.close = MagicMock()

        with (
            patch("gui.src.windows.authentication.login_window.QMessageBox.information"),
        ):
            window.attempt_guest_login()
            # Should have authenticated anonymously — no warning expected
            assert window.is_authenticated
            assert window.vault_manager is not None
            assert window.vault_manager.is_guest is True
            # Username should have been auto-generated (starts with 'guest_')
            assert window.vault_manager.account_name.startswith("guest_")

    def test_toggle_guest_mode_ui(self, q_app):
        """Toggling guest mode switches button labels and field visibility."""
        window = LoginWindow()
        window.show()
        q_app.processEvents()
        # Initial state: normal mode
        assert window._mode == window._MODE_NORMAL
        assert window.password_input.isVisible()
        assert not window.guest_info_label.isVisible()

        # Enter guest mode
        window.toggle_guest_mode()
        assert window._mode == window._MODE_GUEST
        assert not window.password_input.isVisible()
        assert window.guest_info_label.isVisible()
        assert window.create_button.text() == "Login Anonymously"
        assert window.login_button.text() == "Login as Guest"
        assert "Account Access" in window.guest_toggle_button.text()

        # Return to normal mode
        window.toggle_guest_mode()
        assert window._mode == window._MODE_NORMAL
        assert window.password_input.isVisible()
        assert not window.guest_info_label.isVisible()
        assert window.create_button.text() == "Create Account"
        assert window.login_button.text() == "Login"
        assert "Guest Mode" in window.guest_toggle_button.text()

    def test_guest_login_successful(self, q_app):
        from unittest.mock import MagicMock, patch

        window = LoginWindow()
        window.username_input.setText("guest_user")
        window.close = MagicMock()

        mock_listener = MagicMock()
        window.login_successful.connect(mock_listener)

        with (
            patch("gui.src.windows.authentication.login_window.QMessageBox.information") as mock_info,
        ):
            window.attempt_guest_login()

            assert window.is_authenticated
            assert window.vault_manager is not None
            assert window.vault_manager.is_guest is True
            assert window.vault_manager.account_name == "guest_user"
            mock_info.assert_called_once()
            mock_listener.assert_called_once_with(window.vault_manager)
            # Issue #81 (round 8): LoginWindow no longer closes itself right
            # after emitting login_successful -- app.py's launch_main_gui()
            # closes it later, only once MainWindow is actually constructed
            # and shown. Closing synchronously here left a zero-top-level-
            # windows-open gap that silently quit the whole app via Qt's
            # default quitOnLastWindowClosed. See login_window.py's comment
            # at this call site and .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md.
            window.close.assert_not_called()

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
