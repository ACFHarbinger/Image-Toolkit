from __future__ import annotations

import pathlib

import pytest

from middleware.src.bridge.catalog import catalog, contracts_dir
from middleware.src.bridge.envelope import BridgeAppError
from middleware.src.bridge.handshake import (
    COMPATIBILITY_MAX,
    PROTOCOL_NAME,
    PROTOCOL_VERSION,
    accept_handshake_result,
    build_handshake_request,
    build_handshake_result,
    build_ping_result,
    in_compatibility_range,
    parse_version,
)
from middleware.src.bridge.schema import SchemaRegistry, UnsupportedSchema

TABLE = catalog()


def test_contracts_dir_located_from_package() -> None:
    root = contracts_dir()
    assert (root / "methods.toml").is_file()
    assert root.name == "contracts"


def test_parse_version() -> None:
    assert parse_version("1.2.3") == (1, 2, 3)
    assert parse_version("2") == (2, 0, 0)
    with pytest.raises(ValueError):
        parse_version("v1.2")


def test_in_compatibility_range() -> None:
    assert in_compatibility_range("1.0.0")
    assert in_compatibility_range("0.9.9") is False
    assert in_compatibility_range("1.0.1", minimum="1.0.0", maximum="2.0.0")
    assert in_compatibility_range("2.0.1", minimum="1.0.0", maximum="2.0.0") is False


def test_handshake_request_result_roundtrip() -> None:
    request = build_handshake_request("tauri-shell", "1.0.0")
    assert request["method"] == "system.handshake"
    result = build_handshake_result()
    assert result["protocol"] == PROTOCOL_NAME
    assert result["version"] == PROTOCOL_VERSION
    assert result["compatibility"] == {"min": "1.0.0", "max": COMPATIBILITY_MAX}
    assert set(result["capabilities"]) == {
        "scan",
        "settings",
        "jobs",
        "library_admin",
        "system",
        "library",
        "convert",
        "cloud_jobs",
        "library_preview",
        "cloud_offer",
        "merge",
        "similarity",
        "extractor",
        "drive_sync",
        "media_loader",
    }
    # the built result validates against the contract schemas
    assert TABLE.validate_result("system.handshake", result) == []


def test_accept_handshake_result_enforces_range() -> None:
    result = build_handshake_result()
    response = {"jsonrpc": "2.0", "id": "handshake", "result": result}
    accepted = accept_handshake_result(response, client_version="1.0.0")
    assert accepted is result

    with pytest.raises(BridgeAppError) as exc_info:
        accept_handshake_result(response, client_version="9.9.9")
    assert exc_info.value.code == "bridge.version_mismatch"
    assert exc_info.value.details["client"] == "9.9.9"


def test_accept_handshake_result_rejects_wrong_protocol() -> None:
    result = build_handshake_result()
    result["protocol"] = "some-other-protocol"
    response = {"jsonrpc": "2.0", "id": 1, "result": result}
    with pytest.raises(BridgeAppError) as exc_info:
        accept_handshake_result(response, client_version="1.0.0")
    assert exc_info.value.code == "bridge.protocol_mismatch"


def test_ping_const_true_enforced() -> None:
    assert build_ping_result() == {"ok": True}
    assert TABLE.validate_result("system.ping", {"ok": False}) != []
    assert TABLE.validate_result("system.ping", {"ok": True, "extra": 1}) != []


def test_method_params_validated_per_methods_toml() -> None:
    assert TABLE.validate_params("jobs.submit", {"kind": "convert", "spec": {}}) == []
    assert TABLE.validate_params("jobs.submit", {"spec": {}}) != []  # missing kind
    assert TABLE.validate_params("jobs.submit", {"kind": "convert", "spec": {}, "x": 1}) != []
    assert TABLE.validate_params("jobs.list", {"limit": 501}) != []  # maximum 500
    assert TABLE.validate_params("jobs.list", {"limit": 500}) == []


def test_inline_enum_and_const_enforced_at_runtime() -> None:
    # Grok's #931 review residual: generated Python/Rust degrade inline
    # enums to str/String; the bridge enforces them here.
    bad_state = {"job_id": "j1", "state": "exploded"}
    assert TABLE.validate_params("jobs.status", {"job_id": "j1"}) == []
    payload_errors = TABLE.validate_event_payload("jobs", bad_state)
    assert payload_errors
    bridge_errors = TABLE.validate_event_payload("bridge", {"state": "maybe"})
    assert bridge_errors


def test_registry_fails_loud_on_unknown_keyword(tmp_path: pathlib.Path) -> None:
    (tmp_path / "envelope").mkdir()
    (tmp_path / "envelope" / "weird.json").write_text('{"type": "object", "minProperties": 1}', encoding="utf-8")
    registry = SchemaRegistry(tmp_path)
    with pytest.raises(UnsupportedSchema) as exc_info:
        registry.document("envelope/weird.json")
    assert "minProperties" in str(exc_info.value)


def test_catalog_unknown_method_and_channel() -> None:
    with pytest.raises(ValueError):
        TABLE.validate_params("no.such_method", {})
    with pytest.raises(ValueError):
        TABLE.validate_event_payload("no_such_channel", {})
