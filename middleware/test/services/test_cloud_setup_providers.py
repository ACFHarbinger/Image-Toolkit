"""Cloud Compute provider catalog (T-04 / #920): parity with the Qt providers
pane's DEFAULT_PROVIDERS and the dispatch path."""

from __future__ import annotations

import io
from typing import Any

import pytest
from middleware.src.bridge import PROTOCOL_NAME
from middleware.src.services.cloud_setup.providers import (
    is_provider,
    provider_ids,
    providers_result,
)
from middleware.src.sidecar.server import SidecarServer

EXPECTED_FIELDS = {
    "provider_id",
    "name",
    "badge_text",
    "badge_token",
    "description",
    "target_service",
    "cpu_shapes",
    "memory_tiers",
    "gpu_options",
    "cost_estimate",
    "cold_start",
    "regions",
    "config_file",
    "is_poc_target",
}


def test_catalog_matches_the_qt_pane_providers() -> None:
    result = providers_result()
    assert provider_ids() == ["gcd", "cloudflare", "oracle", "aws"]
    for provider in result["providers"]:
        assert set(provider) >= EXPECTED_FIELDS
        assert provider["regions"], provider["provider_id"]
    gcd = next(p for p in result["providers"] if p["provider_id"] == "gcd")
    assert gcd["is_poc_target"] is True
    assert gcd["target_service"] == "Cloud Run (Knative)"
    assert gcd["badge_token"] == "success"
    # Every other provider is a roadmap shape, not a PoC target.
    assert all(
        provider["is_poc_target"] is False
        for provider in result["providers"]
        if provider["provider_id"] != "gcd"
    )


def test_is_provider_accepts_only_the_catalog() -> None:
    assert is_provider("gcd") and is_provider("aws")
    assert not is_provider("bogus")


def _request(server: SidecarServer, method: str, params: dict[str, Any], request_id: str) -> dict[str, Any]:
    return server.handle_frame({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})  # type: ignore[return-value]


@pytest.fixture()
def server() -> SidecarServer:
    server = SidecarServer(stdout=io.StringIO())
    handshake = _request(
        server,
        "system.handshake",
        {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        "handshake",
    )
    assert "cloud_setup" in handshake["result"]["capabilities"]
    return server


def test_providers_dispatch_over_the_sidecar(server: SidecarServer) -> None:
    response = _request(server, "cloud_setup.providers", {}, "providers")
    ids = [provider["provider_id"] for provider in response["result"]["providers"]]
    assert ids == ["gcd", "cloudflare", "oracle", "aws"]


def test_unknown_cloud_setup_method_is_method_not_found(server: SidecarServer) -> None:
    response = _request(server, "cloud_setup.credentials", {}, "x")
    assert response["error"]["data"]["code"] == "bridge.method_not_found"


def test_profiles_settings_key_is_account_scoped() -> None:
    from middleware.src.settings.cloud_jobs import CLOUD_SETUP_PROFILES_DEFINITION
    from middleware.src.settings.keys import definition_for
    from middleware.src.settings.scopes import SettingScope

    assert CLOUD_SETUP_PROFILES_DEFINITION.key == "cloud_setup/profiles"
    assert CLOUD_SETUP_PROFILES_DEFINITION.scope is SettingScope.ACCOUNT
    assert definition_for("cloud_setup/profiles") is CLOUD_SETUP_PROFILES_DEFINITION
