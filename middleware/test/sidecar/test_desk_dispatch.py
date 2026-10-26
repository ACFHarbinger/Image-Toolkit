"""logs.read and metadata.describe dispatch without opening a database (#919)."""

from __future__ import annotations

import io
from typing import Any

from middleware.src.bridge import PROTOCOL_NAME
from middleware.src.sidecar.server import SidecarServer


def _request(server: SidecarServer, method: str, params: dict[str, Any], request_id: str) -> dict[str, Any]:
    return server.handle_frame({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})  # type: ignore[return-value]


def test_desk_methods_dispatch(tmp_path) -> None:
    log = tmp_path / "app.log"
    log_payload = b"one\nERROR two\nthree\n"
    log.write_bytes(log_payload)
    note = tmp_path / "note.txt"
    note_payload = b"abc"
    note.write_bytes(note_payload)
    server = SidecarServer(stdout=io.StringIO())
    handshake = _request(
        server,
        "system.handshake",
        {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        "handshake",
    )
    assert "desk" in handshake["result"]["capabilities"]

    logs = _request(server, "logs.read", {"path": str(log), "limit": 2}, "logs")
    assert logs["result"]["lines"] == ["ERROR two", "three"]
    assert logs["result"]["error_count"] == 1
    assert logs["result"]["reason"] == "log is not followed"
    assert logs["result"]["found"] is True

    meta = _request(server, "metadata.describe", {"path": str(note)}, "meta")
    assert meta["result"]["found"] is True
    assert meta["result"]["name"] == "note.txt"
    assert meta["result"]["size"] == 3
    assert meta["result"]["suffix"] == ".txt"
    assert meta["result"]["reason"] == "metadata is not edited"
    assert log.read_bytes() == log_payload
    assert note.read_bytes() == note_payload
