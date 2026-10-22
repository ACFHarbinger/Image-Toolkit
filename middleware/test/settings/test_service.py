"""SettingsService tests (W0-16 / #880)."""

from __future__ import annotations

import json

import pytest

from middleware.src.settings import ConflictError, SettingScope, SettingsService
from middleware.src.settings.adapters import JsonFileStore, MemoryStore


def _service(tmp_path) -> SettingsService:
    return SettingsService(
        stores={
            SettingScope.DEVICE: JsonFileStore(tmp_path / "device.json"),
            SettingScope.ACCOUNT: JsonFileStore(tmp_path / "account.json"),
            SettingScope.SESSION: MemoryStore(),
        }
    )


def test_scope_routing_and_persistence(tmp_path) -> None:
    service = _service(tmp_path)
    assert service.scope_of("theme") is SettingScope.ACCOUNT
    assert service.scope_of("preferences/minimize_to_tray") is SettingScope.DEVICE
    assert service.scope_of("session/MainWindow/scroll") is SettingScope.SESSION

    service.set("theme", "light")
    service.set("preferences/minimize_to_tray", True)
    service.set("session/MainWindow/scroll", 42)

    assert service.get("theme") == "light"
    assert service.get("preferences/minimize_to_tray") is True
    assert service.session_value("MainWindow", "scroll") == 42

    # a fresh instance over the same files sees the persisted values
    reloaded = _service(tmp_path)
    assert reloaded.get("theme") == "light"
    assert reloaded.get("preferences/minimize_to_tray") is True
    assert reloaded.session_value("MainWindow", "scroll") is None  # SESSION is memory


def test_defaults_and_casting(tmp_path) -> None:
    service = _service(tmp_path)
    assert service.get("theme") == "dark"  # catalog default
    service.set("preferences/initial_cache_maxsize", "300")  # str coerced
    assert service.get("preferences/initial_cache_maxsize") == 300
    assert service.get("unknown/never/seen", "fallback") == "fallback"


def test_cast_falls_back_to_default_on_garbage(tmp_path) -> None:
    service = _service(tmp_path)
    service.set("preferences/recent_dirs_count", "not-a-number")
    assert service.get("preferences/recent_dirs_count") == 10  # int-cast default


def test_bytes_round_trip_through_json(tmp_path) -> None:
    service = _service(tmp_path)
    payload = b"\x01\x02\x03geometry"
    service.set("mainwindow/geometry", payload)
    assert service.get("mainwindow/geometry") == payload
    raw = json.loads((tmp_path / "device.json").read_text(encoding="utf-8"))
    assert raw["mainwindow/geometry"] == {"$bytes": "01020367656f6d65747279"}


def test_set_if_unchanged_detects_concurrent_writer(tmp_path) -> None:
    service = _service(tmp_path)
    service.set("theme", "dark")
    service.set_if_unchanged("theme", "dark", "light")  # expectation matches
    assert service.get("theme") == "light"

    with pytest.raises(ConflictError) as exc_info:
        service.set_if_unchanged("theme", "dark", "blue")  # stale expectation
    assert exc_info.value.key == "theme"
    assert exc_info.value.actual == "light"
    assert service.get("theme") == "light"  # the CAS did not overwrite


def test_subscribers_are_notified(tmp_path) -> None:
    service = _service(tmp_path)
    events: list[tuple] = []
    unsubscribe = service.subscribe(lambda k, v, s: events.append((k, v, s)))
    service.set("theme", "light")
    unsubscribe()
    service.set("theme", "dark")
    assert events == [("theme", "light", SettingScope.ACCOUNT)]


def test_remove_and_contains(tmp_path) -> None:
    service = _service(tmp_path)
    service.set("theme", "light")
    assert service.contains("theme")
    service.remove("theme")
    assert not service.contains("theme")
    assert service.get("theme") == "dark"
