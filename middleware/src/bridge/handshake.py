"""Version handshake for the bridge (W0-11, #875; Codex R6).

The UI and the sidecar ship as one tested version pair, confirmed at
startup by ``system.handshake``: the client presents its protocol and
itself; the sidecar answers with its protocol version, a compatibility
range and the capabilities routed in ``methods.toml``. Remote clients
negotiate within that range.
"""

from __future__ import annotations

import re
from typing import Any

from .catalog import Catalog, catalog
from .envelope import BridgeAppError, build_request, decode_response

PROTOCOL_NAME = "image-toolkit-bridge"
PROTOCOL_VERSION = "1.0.0"
COMPATIBILITY_MIN = "1.0.0"
COMPATIBILITY_MAX = "1.0.0"

_VERSION_RE = re.compile(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?$")


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse a dotted numeric version; raises ValueError on anything else."""
    match = _VERSION_RE.match(version)
    if match is None:
        raise ValueError(f"version {version!r} is not dotted numeric")
    parts = [int(group) if group else 0 for group in match.groups()]
    return (parts[0], parts[1], parts[2])


def in_compatibility_range(
    version: str,
    *,
    minimum: str = COMPATIBILITY_MIN,
    maximum: str = COMPATIBILITY_MAX,
) -> bool:
    parsed = parse_version(version)
    return parse_version(minimum) <= parsed <= parse_version(maximum)


def build_handshake_request(
    client_name: str,
    client_version: str,
    *,
    request_id: str | int | None = "handshake",
    table: Catalog | None = None,
) -> dict[str, Any]:
    """Build the ``system.handshake`` request a client sends at attach."""
    return build_request(
        "system.handshake",
        request_id=request_id,
        params={"protocol": PROTOCOL_NAME, "client": {"name": client_name, "version": client_version}},
        table=table,
    )


def build_handshake_result(
    *,
    version: str = PROTOCOL_VERSION,
    compatibility: dict[str, str] | None = None,
    table: Catalog | None = None,
) -> dict[str, Any]:
    """Build the validated ``system.handshake`` result the sidecar returns."""
    table = table or catalog()
    compatibility = compatibility or {"min": COMPATIBILITY_MIN, "max": COMPATIBILITY_MAX}
    result: dict[str, Any] = {
        "protocol": PROTOCOL_NAME,
        "version": version,
        "compatibility": compatibility,
        "capabilities": list(table.capabilities()),
    }
    errors = table.validate_result("system.handshake", result)
    if errors:
        raise BridgeAppError(
            "bridge.invalid_request",
            details={"errors": [str(error) for error in errors]},
        )
    return result


def accept_handshake_result(
    frame: Any,
    *,
    client_version: str,
    table: Catalog | None = None,
) -> dict[str, Any]:
    """Validate a handshake response and enforce the compatibility range."""
    table = table or catalog()
    response = decode_response(frame, table=table)
    result = response.get("result")
    if result is None:
        raise BridgeAppError(
            "bridge.invalid_request",
            details={"reason": "handshake failed", "error": response.get("error", {}).get("data", {})},
        )
    errors = table.validate_result("system.handshake", result)
    if errors:
        raise BridgeAppError(
            "bridge.invalid_request",
            details={"errors": [str(error) for error in errors]},
        )
    if result["protocol"] != PROTOCOL_NAME:
        raise BridgeAppError(
            "bridge.protocol_mismatch",
            retryable=False,
            details={"expected": PROTOCOL_NAME, "got": result["protocol"]},
        )
    compat = result["compatibility"]
    if not in_compatibility_range(client_version, minimum=compat["min"], maximum=compat["max"]):
        raise BridgeAppError(
            "bridge.version_mismatch",
            retryable=False,
            details={
                "client": client_version,
                "min": compat["min"],
                "max": compat["max"],
            },
        )
    return result


def build_ping_request(*, request_id: str | int | None = "ping", table: Catalog | None = None) -> dict[str, Any]:
    """Build the ``system.ping`` liveness request (session-owned)."""
    return build_request("system.ping", request_id=request_id, params={}, table=table)


def build_ping_result(*, table: Catalog | None = None) -> dict[str, Any]:
    """Build the validated ``system.ping`` result (``ok: true`` const)."""
    table = table or catalog()
    result = {"ok": True}
    errors = table.validate_result("system.ping", result)
    if errors:
        raise BridgeAppError(
            "bridge.invalid_request",
            details={"errors": [str(error) for error in errors]},
        )
    return result
