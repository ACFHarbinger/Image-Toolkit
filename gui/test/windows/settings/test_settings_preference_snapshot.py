"""R0.2 regressions for Settings' committed account-preference snapshot."""

from __future__ import annotations

import copy
import json
from unittest.mock import MagicMock

import pytest
from gui.src.preferences import PreferenceStore, PrefKeys
from gui.src.windows.settings.settings_window import SettingsWindow
from gui.src.windows.window_service import WindowService

pytestmark = pytest.mark.gui


class _GuestVault:
    is_guest = True

    def __init__(self) -> None:
        self.data = {
            "account_name": "Guest",
            "theme": "light",
            "active_tab_configs": {},
            "system_preference_profiles": {},
            "preferences": {"unchanged": "kept"},
        }

    def load_account_credentials(self) -> dict:
        return copy.deepcopy(self.data)

    def save_data(self, text: str) -> None:
        self.data = json.loads(text)


class _AccountVault(_GuestVault):
    is_guest = False

    def __init__(self) -> None:
        super().__init__()
        self.data["account_name"] = "Account"


class _FakeMainWindow:
    """Mirrors MainWindow's _refresh_account_credentials() contract (#548)
    without the rest of MainWindow -- WindowService only needs this much."""

    def __init__(self, vault_manager) -> None:
        self.vault_manager = vault_manager
        self.cached_creds: dict = {}

    def _refresh_account_credentials(self, credentials: dict) -> None:
        self.cached_creds = credentials
        PreferenceStore.instance().attach_vault_credentials(
            credentials, self.vault_manager, credentials.get("account_name", "Guest")
        )

    def set_minimize_to_tray(self, *_a, **_k) -> None:
        pass

    def set_application_theme(self, *_a, **_k) -> None:
        pass

    def _apply_startup_preferences(self) -> None:
        pass

    def _apply_active_tab_configs(self, previous_configs=None) -> None:
        pass


def test_guest_settings_save_refreshes_account_snapshot(q_app):
    PreferenceStore.reset_instance()
    vault = _GuestVault()
    # Model an already-open main window: its adapter holds the snapshot from
    # before this Settings save. The old AppSettings setters wrote through
    # that snapshot and reverted freshly committed values.
    PreferenceStore.instance().attach_vault_credentials(
        vault.load_account_credentials(), vault, "Guest"
    )
    main_window = _FakeMainWindow(vault)
    window = SettingsWindow(window_service=WindowService(main_window))
    window.vault_manager = vault
    window.current_account_name = "Guest"
    window.runtime_shell_check.setChecked(True)
    window.recursive_scan_check.setChecked(False)
    window.fav_list_widget.addItem("/tmp/favourite")
    window.mal_fetch_method_combo.setCurrentIndex(0)

    window._update_settings_logic()

    store = PreferenceStore.instance()
    assert store.get(PrefKeys.RECURSIVE_SCAN) is False
    assert store.get(PrefKeys.FAVOURITE_DIRECTORIES) == ["/tmp/favourite"]
    assert store.get(PrefKeys.EXPERIMENTAL_RUNTIME_SHELL) is True
    # Nothing in this test selects a theme radio; the vault's own "light"
    # (from _GuestVault.data) survives unchanged, same as the untouched
    # "unchanged" preference below.
    assert vault.data["theme"] == "light"
    assert vault.data["preferences"]["unchanged"] == "kept"

    # A fresh store represents the next guest session: it must recover the
    # same committed values instead of the adapter snapshot from before Save.
    PreferenceStore.reset_instance()
    restarted = PreferenceStore.instance()
    restarted.attach_vault_credentials(vault.load_account_credentials(), vault, "Guest")
    assert restarted.get(PrefKeys.RECURSIVE_SCAN) is False
    assert restarted.get(PrefKeys.FAVOURITE_DIRECTORIES) == ["/tmp/favourite"]
    assert restarted.get(PrefKeys.EXPERIMENTAL_RUNTIME_SHELL) is True
    PreferenceStore.reset_instance()


def test_runtime_shell_flag_survives_account_settings_save_and_restart(q_app):
    """Typed follow-up writes must not overwrite the committed shell flag."""
    PreferenceStore.reset_instance()
    vault = _AccountVault()
    PreferenceStore.instance().attach_vault_credentials(
        vault.load_account_credentials(), vault, "Account"
    )
    main_window = _FakeMainWindow(vault)
    window = SettingsWindow(window_service=WindowService(main_window))
    window.vault_manager = vault
    window.current_account_name = "Account"
    window.runtime_shell_check.setChecked(True)
    window.recursive_scan_check.setChecked(False)
    window.fav_list_widget.addItem("/tmp/favourite")

    window._update_settings_logic()

    PreferenceStore.reset_instance()
    restarted = PreferenceStore.instance()
    restarted.attach_vault_credentials(vault.load_account_credentials(), vault, "Account")
    assert restarted.get(PrefKeys.EXPERIMENTAL_RUNTIME_SHELL) is True
    assert restarted.get(PrefKeys.RECURSIVE_SCAN) is False
    assert restarted.get(PrefKeys.FAVOURITE_DIRECTORIES) == ["/tmp/favourite"]
    PreferenceStore.reset_instance()


def test_appearance_preview_does_not_persist_to_the_vault(q_app):
    """Preview updates the live in-memory cached_creds (so WindowService's
    own preferences()/zoom_in()/zoom_out() see the change immediately) but
    must never write to the vault -- that only happens on Save."""
    vault_manager = MagicMock()
    vault_manager.load_account_credentials.return_value = {"account_name": "Test", "theme": "dark"}
    vault_manager.is_guest = False
    main_window = MagicMock()
    main_window.vault_manager = vault_manager
    main_window.cached_creds = {"preferences": {"accent_color_dark": "#112233"}}
    window = SettingsWindow(window_service=WindowService(main_window))

    window._preview_appearance()

    vault_manager.save_data.assert_not_called()
    main_window.set_application_theme.assert_called_once()
    # WindowService.preview_appearance() primes cached_creds["preferences"]
    # BEFORE calling set_application_theme(theme) with no explicit kwarg --
    # the real MainWindow.set_application_theme() falls back to reading
    # cached_creds["preferences"] itself, so this is what it would see.
    assert main_window.cached_creds["preferences"]["app_zoom"] == window.pref_app_zoom
