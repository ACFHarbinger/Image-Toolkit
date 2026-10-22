from __future__ import annotations

import importlib.util
import json
import sys
from typing import Any

import pytest

from middleware.src.bridge.catalog import catalog, contracts_dir
from middleware.src.bridge.envelope import build_response

TABLE = catalog()


def _load_generated() -> Any:
    path = contracts_dir() / "generated" / "python" / "contracts_generated.py"
    spec = importlib.util.spec_from_file_location("contracts_generated_consistency", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_validated_frames_fit_generated_dataclasses() -> None:
    generated = _load_generated()
    result = build_response(1, result={"ok": True})
    ping = generated.PingResult(ok=result["result"]["ok"])
    assert ping.ok is True

    frame = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "protocol": "image-toolkit-bridge",
            "version": "1.0.0",
            "compatibility": {"min": "1.0.0", "max": "1.0.0"},
            "capabilities": ["system", "jobs"],
        },
    }
    assert TABLE.validate_result("system.handshake", frame["result"]) == []
    handshake = generated.HandshakeResult(
        protocol=frame["result"]["protocol"],
        version=frame["result"]["version"],
        compatibility=generated.Compatibility(**frame["result"]["compatibility"]),
        capabilities=frame["result"]["capabilities"],
    )
    assert handshake.compatibility.min == "1.0.0"


@pytest.mark.parametrize(
    "frame",
    [
        {"jsonrpc": "2.0", "id": 1, "method": "system.ping", "params": {}},
        {"jsonrpc": "2.0", "id": None, "method": "jobs.status", "params": {"job_id": "j1"}},
        {
            "jsonrpc": "2.0",
            "id": "x",
            "method": "system.handshake",
            "params": {"protocol": "p", "client": {"name": "n", "version": "1"}},
        },
    ],
)
def test_request_validator_agrees_with_jsonschema(frame: dict[str, Any]) -> None:
    jsonschema = pytest.importorskip("jsonschema", reason="optional deep validation cross-check")
    schemas = contracts_dir() / "schemas"
    schema = json.loads((schemas / "envelope" / "request.json").read_text(encoding="utf-8"))
    jsonschema.validate(frame, schema)
    assert TABLE.validate_request_envelope(frame) == []


@pytest.mark.parametrize(
    "frame",
    [
        {"jsonrpc": "1.0", "id": 1, "method": "system.ping"},
        {"jsonrpc": "2.0", "id": 1},
        {"jsonrpc": "2.0", "id": True, "method": "system.ping"},
        {"jsonrpc": "2.0", "id": 1, "method": "system.ping", "params": []},
    ],
)
def test_request_validator_rejects_what_jsonschema_rejects(frame: dict[str, Any]) -> None:
    jsonschema = pytest.importorskip("jsonschema", reason="optional deep validation cross-check")
    schemas = contracts_dir() / "schemas"
    schema = json.loads((schemas / "envelope" / "request.json").read_text(encoding="utf-8"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(frame, schema)
    assert TABLE.validate_request_envelope(frame) != []
