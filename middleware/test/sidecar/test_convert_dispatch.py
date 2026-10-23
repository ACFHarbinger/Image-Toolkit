"""convert.convert reaches ConvertService through the sidecar dispatcher."""

from __future__ import annotations

import io
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
    assert "convert" in handshake["result"]["capabilities"]
    return server


def test_missing_input_is_a_validated_convert_result() -> None:
    server = _ready()
    response = _request(
        server,
        "convert.convert",
        {"input_path": "/no/such/image.png", "output_path": "/tmp/out.png", "quality": 95},
        "convert",
    )
    result = response["result"]
    assert result["success"] is False
    assert result["input_path"] == "/no/such/image.png"
    assert "does not exist" in result["error"]


def test_non_canonical_quality_is_rejected_before_dispatch() -> None:
    server = _ready()
    response = _request(
        server,
        "convert.convert",
        {"input_path": "/no/such/image.png", "output_path": "/tmp/out.png", "quality": 80},
        "convert",
    )
    assert response["error"]["data"]["code"] == "bridge.invalid_params"
