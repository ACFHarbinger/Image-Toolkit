"""Shared conformance scenarios against the LIVE sidecar (W0-12, #876).

Scenario fixtures live in
``frontend/src/hostclient/__tests__/fixtures/conformance.json`` and are
consumed by both this suite (real sidecar subprocess) and the TS suite
(``conformance.test.ts`` over a loopback responder). Keep the DSL in sync
with that file's ``description``.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from .client import FIXTURES, SidecarClient

_SCENARIOS = json.loads((FIXTURES / "conformance.json").read_text(encoding="utf-8"))
_TEMPLATE = re.compile(r"\$\{([a-z_]+)\}")


def _substitute(value: Any, captures: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return _TEMPLATE.sub(lambda match: str(captures[match.group(1)]), value)
    if isinstance(value, list):
        return [_substitute(item, captures) for item in value]
    if isinstance(value, dict):
        return {key: _substitute(item, captures) for key, item in value.items()}
    return value


def _assert_subset(expected: Any, actual: Any, path: str = "$") -> None:
    if expected == "*":
        assert actual is not None, f"{path}: expected a value"
    elif isinstance(expected, dict):
        assert isinstance(actual, dict), f"{path}: expected object, got {actual!r}"
        for key, sub in expected.items():
            assert key in actual, f"{path}.{key}: missing"
            _assert_subset(sub, actual[key], f"{path}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), f"{path}: {actual!r}"
        for index, sub in enumerate(expected):
            _assert_subset(sub, actual[index], f"{path}[{index}]")
    else:
        assert actual == expected, f"{path}: expected {expected!r}, got {actual!r}"


def _expectation(response: dict[str, Any], expect: dict[str, Any]) -> Any:
    """Assert one response against an expect block; return its result."""
    if "error" in expect:
        assert "error" in response, f"expected error, got {response!r}"
        _assert_subset(expect["error"], response["error"]["data"])
        return None
    assert "result" in response, f"expected result, got {response!r}"
    if "result" in expect:
        _assert_subset(expect["result"], response["result"])
    return response["result"]


def _run_scenario(scenario: dict[str, Any]) -> None:
    client = SidecarClient()
    try:
        attach = scenario.get("attach", {})
        identity = attach.get("client", _SCENARIOS["client"])
        response = client.handshake(version=identity["version"], protocol=_SCENARIOS["protocol"])
        _expectation(response, attach.get("expect", {"result": "*"}))
        if "error" in attach.get("expect", {}):
            return  # failed attach: no steps follow
        captures: dict[str, Any] = {}
        for index, step in enumerate(scenario["steps"]):
            params = _substitute(step.get("params", {}), captures)
            client.send({"jsonrpc": "2.0", "id": f"step-{index}", "method": step["method"], "params": params})
            result = _expectation(client.read_response(), _substitute(step["expect"], captures))
            for name, source in step.get("capture", {}).items():
                assert source.startswith("result.")
                captures[name] = result[source[len("result.") :]]
    finally:
        client.kill()


@pytest.mark.parametrize("scenario", _SCENARIOS["scenarios"], ids=[s["name"] for s in _SCENARIOS["scenarios"]])
def test_conformance(scenario: dict[str, Any]) -> None:
    _run_scenario(scenario)
