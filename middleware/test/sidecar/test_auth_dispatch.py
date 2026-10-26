"""auth.status is dispatched without opening a store (#918)."""

from __future__ import annotations

import io
import json
from typing import Any

from middleware.src.bridge import PROTOCOL_NAME
from middleware.src.sidecar.server import SidecarServer


def _request(server: SidecarServer, method: str, params: dict[str, Any], request_id: str) -> dict[str, Any]:
    return server.handle_frame({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})  # type: ignore[return-value]


def _ready() -> SidecarServer:
    server = SidecarServer(stdout=io.StringIO())
    handshake = _request(
        server,
        "system.handshake",
        {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        "handshake",
    )
    assert "auth" in handshake["result"]["capabilities"]
    return server


def test_status_returns_the_locked_session() -> None:
    server = _ready()
    response = _request(server, "auth.status", {"account": "  keeper  "}, "auth")
    assert response["result"] == {
        "unlocked": False,
        "account": "keeper",
        "reason": "unlock stays on the C++ session",
    }


def test_blank_account_is_invalid_and_does_not_echo() -> None:
    server = _ready()
    secret = "not-a-password"
    response = _request(server, "auth.status", {"account": f"  {secret}  "}, "blank")
    assert response["result"]["account"] == secret
    blank = _request(server, "auth.status", {"account": "   "}, "blank-account")
    assert blank["error"]["data"]["code"] == "bridge.invalid_params"
    assert blank["error"]["data"]["details"]["reason"] == "ValueError"
    assert secret not in json.dumps(blank)
    missing = _request(server, "auth.status", {}, "missing")
    assert missing["error"]["data"]["code"] == "bridge.invalid_params"
