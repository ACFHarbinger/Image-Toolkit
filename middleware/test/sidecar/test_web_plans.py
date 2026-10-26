from __future__ import annotations

import io

from middleware.src.bridge import PROTOCOL_NAME
from middleware.src.sidecar.server import SidecarServer


def _call(server: SidecarServer, method: str, params: dict) -> dict:
    return server.handle_frame({"jsonrpc": "2.0", "id": method, "method": method, "params": params})


def test_web_plans_do_not_submit_or_download(tmp_path) -> None:
    server = SidecarServer(stdout=io.StringIO())
    server.handle_frame(
        {
            "jsonrpc": "2.0",
            "id": "handshake",
            "method": "system.handshake",
            "params": {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        }
    )
    planned = _call(server, "drive_sync.plan", {"provider": "dropbox", "paths": ["a.png"]})
    assert planned["result"]["submitted"] is False
    assert planned["result"]["count"] == 1
    loaded = _call(server, "media_loader.plan", {"url": "https://example.com/a.png", "destination": str(tmp_path)})
    assert loaded["result"]["downloaded"] is False
    assert loaded["result"]["accepted"] is True
    assert list(tmp_path.iterdir()) == []
