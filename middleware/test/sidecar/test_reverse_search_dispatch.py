"""reverse_search.* reaches the service through the sidecar dispatcher
(B-05 / #910). The manager factory is monkeypatched onto a fake — the
dispatch tests make no live calls."""

from __future__ import annotations

import io
from typing import Any

import pytest

from middleware.src.bridge import PROTOCOL_NAME
from middleware.src.sidecar.handlers import reverse_search as handlers
from middleware.src.sidecar.server import SidecarServer


def _request(server: SidecarServer, method: str, params: dict[str, Any], request_id: str) -> dict[str, Any]:
    return server.handle_frame({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})  # type: ignore[return-value]


@pytest.fixture()
def server(monkeypatch) -> SidecarServer:
    class _FakeManager:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def perform_reverse_search(self, image_path, engine_type, roi=None, **kwargs):
            self.calls.append({"image_path": image_path, "engine_type": engine_type, "roi": roi, **kwargs})
            return [
                {"url": "https://example.com/a", "engine": engine_type, "score": "0.9000", "resolution": "800x600", "title": "hit"},
            ]

    fake = _FakeManager()
    monkeypatch.setattr(handlers, "reverse_search_manager", lambda: fake)
    server = SidecarServer(stdout=io.StringIO())
    handshake = _request(
        server,
        "system.handshake",
        {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        "handshake",
    )
    assert "reverse_search" in handshake["result"]["capabilities"]
    return server


def test_engines_lists_the_catalog(server: SidecarServer) -> None:
    response = _request(server, "reverse_search.engines", {}, "engines")
    ids = [engine["id"] for engine in response["result"]["engines"]]
    assert "google" in ids and "tineye" in ids


def test_search_dispatches_onto_the_manager(server: SidecarServer) -> None:
    response = _request(
        server,
        "reverse_search.search",
        {"engine": "tineye", "image_path": "/pics/q.png", "limit": 5},
        "search",
    )
    result = response["result"]
    assert result["ok"] is True
    assert result["results"][0]["url"] == "https://example.com/a"
    assert result["results"][0]["score"] == 0.9


def test_unknown_engine_is_rejected_by_the_schema_before_dispatch(server: SidecarServer) -> None:
    response = _request(
        server,
        "reverse_search.search",
        {"engine": "bogus", "image_path": "/pics/q.png"},
        "bad",
    )
    assert response["error"]["data"]["code"] == "bridge.invalid_params"


def test_unknown_reverse_search_method_is_method_not_found(server: SidecarServer) -> None:
    response = _request(server, "reverse_search.clear", {}, "x")
    assert response["error"]["data"]["code"] == "bridge.method_not_found"
