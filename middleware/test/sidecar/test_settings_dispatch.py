"""settings.* reaches the settings service through the sidecar dispatcher
(D5 / #851). The service factory is monkeypatched onto tmp_path stores so
the sidecar never touches the real ``~/.image-toolkit`` tree."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

from middleware.src.bridge import PROTOCOL_NAME
from middleware.src.settings import cloud_jobs
from middleware.src.settings.adapters import JsonFileStore, MemoryStore
from middleware.src.settings.scopes import SettingScope
from middleware.src.settings.service import SettingsService
from middleware.src.sidecar.handlers import settings as settings_handlers
from middleware.src.sidecar.server import SidecarServer


def _request(server: SidecarServer, method: str, params: dict[str, Any], request_id: str) -> dict[str, Any]:
    return server.handle_frame({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})  # type: ignore[return-value]


@pytest.fixture()
def server(tmp_path: Path, monkeypatch) -> SidecarServer:
    service = SettingsService(
        stores={
            SettingScope.DEVICE: JsonFileStore(tmp_path / "device.json"),
            SettingScope.ACCOUNT: JsonFileStore(tmp_path / "account.json"),
            SettingScope.SESSION: MemoryStore(),
        }
    )
    monkeypatch.setattr(settings_handlers, "settings_service", lambda: service)
    server = SidecarServer(stdout=io.StringIO())
    handshake = _request(
        server,
        "system.handshake",
        {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        "handshake",
    )
    assert "settings" in handshake["result"]["capabilities"]
    return server


def test_get_returns_catalog_default_and_scope(server: SidecarServer) -> None:
    response = _request(server, "settings.get", {"key": "theme"}, "get")
    assert response["result"] == {"key": "theme", "value": "dark", "scope": "account"}


def test_set_then_get_round_trips(server: SidecarServer) -> None:
    _request(server, "settings.set", {"key": "theme", "value": "light"}, "set")
    response = _request(server, "settings.get", {"key": "theme"}, "get")
    assert response["result"]["value"] == "light"


def test_cloud_jobs_get_returns_the_full_document(server: SidecarServer) -> None:
    response = _request(server, "settings.get", {"key": cloud_jobs.CLOUD_JOBS_SETTINGS_KEY}, "get")
    document = response["result"]["value"]
    assert document["packing_mode"] == "one_to_one"
    assert document["notify_desktop"] is True
    assert response["result"]["scope"] == "account"


def test_cloud_jobs_set_validates_and_persists(server: SidecarServer) -> None:
    document = cloud_jobs.cloud_settings_document(None) | {"monthly_cap_usd": 75.0}
    response = _request(
        server,
        "settings.set",
        {"key": cloud_jobs.CLOUD_JOBS_SETTINGS_KEY, "value": document},
        "set",
    )
    assert response["result"]["value"]["monthly_cap_usd"] == 75.0
    again = _request(server, "settings.get", {"key": cloud_jobs.CLOUD_JOBS_SETTINGS_KEY}, "get")
    assert again["result"]["value"]["monthly_cap_usd"] == 75.0


def test_invalid_cloud_jobs_document_is_rejected(server: SidecarServer) -> None:
    response = _request(
        server,
        "settings.set",
        {"key": cloud_jobs.CLOUD_JOBS_SETTINGS_KEY, "value": {"packing_mode": "bogus"}},
        "set",
    )
    assert response["error"]["data"]["code"] == "settings.invalid_value"
    assert response["error"]["data"]["details"]["key"] == cloud_jobs.CLOUD_JOBS_SETTINGS_KEY


def test_get_many_reads_a_form_in_one_round_trip(server: SidecarServer) -> None:
    response = _request(
        server,
        "settings.get_many",
        {"keys": ["theme", cloud_jobs.CLOUD_JOBS_SETTINGS_KEY]},
        "get_many",
    )
    values = response["result"]["values"]
    assert values["theme"] == "dark"
    assert values[cloud_jobs.CLOUD_JOBS_SETTINGS_KEY]["fallback_enabled"] is False


def test_set_many_writes_all_or_none(server: SidecarServer) -> None:
    document = cloud_jobs.cloud_settings_document(None)
    response = _request(
        server,
        "settings.set_many",
        {"updates": {"theme": "light", cloud_jobs.CLOUD_JOBS_SETTINGS_KEY: document}},
        "set_many",
    )
    assert response["result"]["values"]["theme"] == "light"

    bad = document | {"max_attempts": 0}
    failed = _request(
        server,
        "settings.set_many",
        {"updates": {"theme": "dark", cloud_jobs.CLOUD_JOBS_SETTINGS_KEY: bad}},
        "set_many",
    )
    assert failed["error"]["data"]["code"] == "settings.invalid_value"
    # The whole form stayed unsaved: theme kept the first save's value.
    kept = _request(server, "settings.get", {"key": "theme"}, "kept")
    assert kept["result"]["value"] == "light"


def test_unknown_settings_method_is_method_not_found(server: SidecarServer) -> None:
    response = _request(server, "settings.clear", {}, "unknown")
    assert response["error"]["data"]["code"] == "bridge.method_not_found"


@pytest.mark.parametrize("method", ["settings.set", "settings.set_many"])
def test_empty_numeric_value_is_rejected_without_persisting(server, method):
    key = cloud_jobs.CLOUD_JOBS_SETTINGS_KEY
    params = (
        {"key": key, "value": {"monthly_cap_usd": ""}}
        if method == "settings.set"
        else {"updates": {"theme": "light", key: {"monthly_cap_usd": ""}}}
    )
    response = _request(server, method, params, "invalid-number")
    assert response["error"]["data"]["code"] == "settings.invalid_value"
    values = _request(server, "settings.get_many", {"keys": ["theme", key]}, "read")["result"]["values"]
    assert values[key]["monthly_cap_usd"] == 100.0
    assert values["theme"] == "dark"
