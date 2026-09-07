"""R0.2 regressions for Settings' committed account-preference snapshot."""

from __future__ import annotations

import copy
import json
from unittest.mock import MagicMock

import pytest
from gui.src.preferences import PreferenceStore, PrefKeys
from gui.src.windows.settings.settings_window import SettingsWindow

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


def test_guest_settings_save_refreshes_account_snapshot(q_app):
    PreferenceStore.reset_instance()
    vault = _GuestVault()
    # Model an already-open main window: its adapter holds the snapshot from
    # before this Settings save. The old AppSettings setters wrote through
    # that snapshot and reverted freshly committed values.
    PreferenceStore.instance().attach_vault_credentials(
        vault.load_account_credentials(), vault, "Guest"
    )
    window = SettingsWindow()
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
    assert vault.data["theme"] == "dark"
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


def test_appearance_preview_does_not_mutate_main_window_credentials(q_app):
    window = SettingsWindow()
    main_window = MagicMock()
    main_window.cached_creds = {"preferences": {"accent_color_dark": "#112233"}}
    window.main_window_ref = main_window
    before = copy.deepcopy(main_window.cached_creds)

    window._preview_appearance()

    assert main_window.cached_creds == before
    _, kwargs = main_window.set_application_theme.call_args
    assert kwargs["preferences"]["app_zoom"] == window.pref_app_zoom
