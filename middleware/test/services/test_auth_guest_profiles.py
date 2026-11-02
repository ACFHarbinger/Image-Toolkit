"""Guest sessions, preference-profile choice and API credential loading (Tauri login parity)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import middleware.src.constants as udef
import pytest
from middleware.src.services.auth import profiles as profile_api
from middleware.src.services.auth.hub import GUEST_OPENED, VaultHub
from middleware.src.services.auth.session import LiveVault, load_api_credentials, open_guest_session
from middleware.src.services.auth.status import GUEST_REASON, OPEN_REASON, auth_status
from middleware.src.settings.adapters import MemoryStore
from middleware.src.settings.scopes import SettingScope
from middleware.src.settings.service import SettingsService


class _Sealed:
    """Stands in for SecureJsonVault: 'encrypts' by writing a marker-wrapped copy."""

    def __init__(self, key: bytes, path: str) -> None:
        self.key, self.path = key, path

    def saveData(self, text: str) -> None:  # noqa: N802
        Path(self.path).write_text("SEALED:" + text, encoding="utf-8")

    def loadData(self) -> str:  # noqa: N802
        raw = Path(self.path).read_text(encoding="utf-8")
        if not raw.startswith("SEALED:"):
            raise RuntimeError("not sealed")
        return raw[len("SEALED:") :]


class _Manager:
    SecureJsonVault = _Sealed

    def __init__(self, stored: dict[str, Any] | None = None) -> None:
        self.secret_key = b"k" * 32
        self.api_credentials: dict[str, Any] = {}
        self.stored = stored if stored is not None else {}
        self.saved: list[dict[str, Any]] = []
        self.down = False

    def load_account_credentials(self) -> dict[str, Any]:
        return json.loads(json.dumps(self.stored))

    def save_data(self, text: str) -> None:
        self.stored = json.loads(text)
        self.saved.append(self.stored)

    def shutdown(self) -> None:
        self.down = True


# ── API credential files ────────────────────────────────────────────────────


@pytest.fixture
def api_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "api"
    folder.mkdir()
    monkeypatch.setattr(udef, "API_DIR", folder)
    monkeypatch.setattr(udef, "TOKEN_FILE", str(folder / "token.json"))
    return folder


def test_new_json_files_are_sealed_and_every_sealed_file_is_loaded(api_dir: Path) -> None:
    (api_dir / "google_api_key.json").write_text('{"key": "g"}', encoding="utf-8")
    (api_dir / "token.json").write_text('{"token": "t"}', encoding="utf-8")
    (api_dir / "dropbox_token.enc").write_text('SEALED:{"token": "d"}', encoding="utf-8")
    manager = _Manager()
    loaded = load_api_credentials(manager)
    assert (api_dir / "google_api_key.json.enc").read_text(encoding="utf-8").startswith("SEALED:")
    assert not (api_dir / "token.json.enc").exists()
    assert sorted(loaded) == ["dropbox_token", "google_api_key"]
    assert manager.api_credentials["google_api_key"] == {"key": "g"}
    assert manager.api_credentials["dropbox_token"] == {"token": "d"}


def test_loader_returns_names_only_and_skips_broken_files(api_dir: Path) -> None:
    (api_dir / "good.json.enc").write_text('SEALED:{"a": 1}', encoding="utf-8")
    (api_dir / "bad.json.enc").write_text("SEALED:not json", encoding="utf-8")
    (api_dir / "plain.json.enc").write_text("never sealed", encoding="utf-8")
    loaded = load_api_credentials(_Manager())
    assert loaded == ["good"]
    assert all(isinstance(name, str) for name in loaded)


def test_loader_without_key_or_directory_is_empty(
    api_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    keyless = _Manager()
    keyless.secret_key = None  # type: ignore[assignment]
    assert load_api_credentials(keyless) == []
    monkeypatch.setattr(udef, "API_DIR", tmp_path / "missing")
    assert load_api_credentials(_Manager()) == []


# ── profile choice ──────────────────────────────────────────────────────────

_STORED = {
    "account_name": "ana",
    "theme": "light",
    "active_tab_configs": {"convert": {"fmt": "png"}},
    "preferences": {"font_scale": 120, "ui_density": "Compact", "other": 1},
    "system_preference_profiles": {
        "Night": {
            "theme": "dark",
            "active_tab_configs": {"merge": {"engine": "orb"}},
            "font_scale": 90,
            "accent_color_dark": "#112233",
        },
        "Same": {"theme": "light", "active_tab_configs": {"convert": {"fmt": "png"}}},
    },
}


def test_picker_lists_default_previous_then_sorted_names() -> None:
    assert profile_api.profile_choices([]) == []
    assert profile_api.profile_choices(["Night", "Alpha"]) == ["Default", "Previous Profile", "Alpha", "Night"]


def test_previous_profile_changes_and_saves_nothing() -> None:
    manager = _Manager(json.loads(json.dumps(_STORED)))
    result = profile_api.apply_profile(manager, "Previous Profile")
    assert manager.saved == []
    assert result == {"theme": "light", "tab_configurations": {"convert": {"fmt": "png"}}, "changed": False}


def test_named_profile_sets_theme_tab_configs_and_appearance_and_saves_once() -> None:
    manager = _Manager(json.loads(json.dumps(_STORED)))
    result = profile_api.apply_profile(manager, "Night")
    assert len(manager.saved) == 1
    saved = manager.saved[0]
    assert saved["theme"] == "dark" and saved["active_tab_configs"] == {"merge": {"engine": "orb"}}
    assert saved["preferences"]["font_scale"] == 90 and saved["preferences"]["accent_color_dark"] == "#112233"
    assert saved["preferences"]["other"] == 1 and saved["preferences"]["ui_density"] == "Compact"
    assert result == {"theme": "dark", "tab_configurations": {"merge": {"engine": "orb"}}, "changed": True}


def test_profile_equal_to_the_vault_does_not_save() -> None:
    manager = _Manager(json.loads(json.dumps(_STORED)))
    assert profile_api.apply_profile(manager, "Same")["changed"] is False
    assert manager.saved == []


def test_default_resets_theme_tabs_and_removes_qt_appearance_keys() -> None:
    manager = _Manager(json.loads(json.dumps(_STORED)))
    result = profile_api.apply_profile(manager, "Default")
    saved = manager.saved[0]
    assert saved["theme"] == "dark" and saved["active_tab_configs"] == {}
    assert "font_scale" not in saved["preferences"] and "ui_density" not in saved["preferences"]
    assert saved["preferences"]["other"] == 1
    assert saved["system_preference_profiles"] == _STORED["system_preference_profiles"]
    assert result["theme"] == "dark" and result["tab_configurations"] == {}


def test_unknown_profile_is_refused_without_saving() -> None:
    manager = _Manager(json.loads(json.dumps(_STORED)))
    with pytest.raises(ValueError, match="Unknown preference profile"):
        profile_api.apply_profile(manager, "Nope")
    assert manager.saved == []


# ── guest sessions and the hub ──────────────────────────────────────────────


@pytest.fixture
def volatile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A private settings service and prefs binder so the real stores in the home folder are never touched."""
    import middleware.src.settings.adapters as adapters
    from middleware.src.sidecar.handlers import prefs as prefs_handler
    from middleware.src.sidecar.handlers import settings as settings_handler

    service = SettingsService(stores={scope: MemoryStore() for scope in SettingScope})
    persistent = MemoryStore()
    service.attach_store(SettingScope.ACCOUNT, persistent)
    monkeypatch.setattr(settings_handler, "_service", service)
    monkeypatch.setattr(adapters, "default_store", lambda scope, base_dir=None: persistent)
    monkeypatch.setattr(prefs_handler, "_prefs_path", None)
    monkeypatch.setattr(prefs_handler, "_keybindings_path", None)
    return {"service": service, "persistent": persistent, "prefs": prefs_handler}


def _hub(**kwargs: Any) -> VaultHub:
    return VaultHub(opener=lambda *_: None, **kwargs)


def test_anonymous_guest_gets_a_random_name(volatile: dict[str, Any]) -> None:
    hub = _hub()
    result = hub.guest(None)
    assert result["success"] and result["anonymous"] is True and result["message"] == GUEST_OPENED
    assert re.fullmatch(r"guest_[0-9a-f]{8}", result["account"])
    assert hub.guest("")["account"] != result["account"]
    hub.lock(hub.session.account)


def test_named_guest_keeps_its_trimmed_name_and_reports_a_guest_status(volatile: dict[str, Any]) -> None:
    hub = _hub()
    result = hub.guest("  Rui  ")
    assert result["account"] == "Rui" and result["anonymous"] is False
    status = hub.status("Rui")
    assert status["unlocked"] is True and status["reason"] == GUEST_REASON != OPEN_REASON
    hub.lock("Rui")
    assert hub.status("Rui")["unlocked"] is False


def test_guest_settings_stay_in_memory_and_vanish_on_lock(volatile: dict[str, Any]) -> None:
    hub = _hub()
    hub.guest("Rui")
    service = volatile["service"]
    service.store_for(SettingScope.ACCOUNT).set("theme", "light")
    assert volatile["persistent"].get("theme") is None
    assert volatile["prefs"]._prefs_path is not None
    prefs_file = volatile["prefs"]._prefs_path
    hub.lock("Rui")
    assert volatile["service"].store_for(SettingScope.ACCOUNT) is volatile["persistent"]
    assert volatile["prefs"]._prefs_path is None
    assert not Path(prefs_file).parent.exists()


def test_failed_guest_start_reports_a_message_and_opens_nothing(volatile: dict[str, Any]) -> None:
    def broken(_name: str) -> Any:
        raise RuntimeError("secret detail")

    hub = _hub(guest_opener=broken)
    result = hub.guest("Rui")
    assert result["success"] is False and "secret detail" not in result["message"]
    assert hub.session is None


def test_unlock_after_guest_restores_persistent_settings(volatile: dict[str, Any]) -> None:
    live = LiveVault("ana", _Manager(json.loads(json.dumps(_STORED))), ["Night"], ["google_api_key"])
    hub = VaultHub(opener=lambda *_: live)
    hub.guest("Rui")
    result = hub.unlock("ana", "pw")
    assert result["success"] and result["profiles"] == ["Night"] and result["credentials"] == ["google_api_key"]
    assert volatile["service"].store_for(SettingScope.ACCOUNT) is volatile["persistent"]
    assert volatile["prefs"]._prefs_path is None


def test_guest_vault_is_volatile_and_supports_profiles() -> None:
    guest = open_guest_session("Rui")
    assert guest.is_guest and guest.account == "Rui" and guest.profiles == []
    assert guest.apply_profile("Default")["theme"] == "dark"
    guest.shutdown()
    assert guest.open is False
    with pytest.raises(ValueError):
        open_guest_session("   ")


def test_hub_apply_profile_returns_the_theme_and_tabs_and_refuses_other_accounts(volatile: dict[str, Any]) -> None:
    manager = _Manager(json.loads(json.dumps(_STORED)))
    hub = VaultHub(opener=lambda *_: LiveVault("ana", manager, ["Night"]))
    hub.unlock("ana", "pw")
    ok = hub.apply_profile("ana", "Night")
    assert ok["success"] and ok["theme"] == "dark" and ok["tab_configurations"] == {"merge": {"engine": "orb"}}
    assert hub.apply_profile("bob", "Night")["success"] is False
    missing = hub.apply_profile("ana", "Nope")
    assert missing["success"] is False and "Unknown" in missing["message"]
    assert auth_status("ana", hub.session)["reason"] == OPEN_REASON
