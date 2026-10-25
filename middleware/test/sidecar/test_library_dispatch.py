"""library.* reaches the store projection through the sidecar dispatcher
(L-02 / #896). The store is injected; the default sidecar stays
unavailable and never opens library.db (Gate B closed)."""

from __future__ import annotations

import io
from typing import Any

from middleware.src.bridge import PROTOCOL_NAME
from middleware.src.sidecar.server import SidecarServer


class _FakeStore:
    """Minimal UnifiedImageDatabase surface for dispatch tests."""

    def search_files(self, **query_params: Any) -> list[dict[str, Any]]:
        return [
            {
                "id": 1,
                "file_path": "/pics/a.png",
                "filename": "a.png",
                "group_name": query_params.get("group_name"),
                "tags": ["night"],
                "date_added": "2026-10-25T00:00:00+00:00",
            }
        ]

    def get_all_tags(self, limit: int = 10000) -> list[str]:
        return ["night"]

    def get_all_groups(self, limit: int = 10000) -> list[str]:
        return ["Trips"]

    def get_all_subgroups_detailed(self, limit: int = 10000) -> list[tuple[str, str]]:
        return [("Beach", "Trips")]


def _request(server: SidecarServer, method: str, params: dict[str, Any], request_id: str) -> dict[str, Any]:
    return server.handle_frame({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})  # type: ignore[return-value]


def _ready(library_store: Any) -> SidecarServer:
    server = SidecarServer(stdout=io.StringIO(), library_store=library_store)
    handshake = _request(
        server,
        "system.handshake",
        {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        "handshake",
    )
    assert "library" in handshake["result"]["capabilities"]
    return server


def test_without_a_store_every_call_is_unavailable() -> None:
    server = _ready(None)
    assert _request(server, "library.list_images", {}, "a")["result"] == {
        "available": False,
        "images": [],
    }
    assert _request(server, "library.list_tags", {}, "b")["result"] == {
        "available": False,
        "tags": [],
    }
    assert _request(server, "library.list_groups", {}, "c")["result"] == {
        "available": False,
        "groups": [],
    }


def test_list_images_dispatches_filters_onto_the_store() -> None:
    server = _ready(_FakeStore())
    response = _request(server, "library.list_images", {"group_name": "Trips", "tags": ["night"]}, "a")
    result = response["result"]
    assert result["available"] is True
    assert result["images"][0]["file_path"] == "/pics/a.png"
    assert result["images"][0]["group_name"] == "Trips"


def test_tags_and_groups_dispatch() -> None:
    server = _ready(_FakeStore())
    tags = _request(server, "library.list_tags", {}, "t")["result"]
    assert tags == {"available": True, "tags": ["night"]}
    groups = _request(server, "library.list_groups", {}, "g")["result"]
    assert groups == {"available": True, "groups": [{"name": "Trips", "subgroups": ["Beach"]}]}


def test_unknown_library_method_is_method_not_found() -> None:
    server = _ready(None)
    response = _request(server, "library.reindex", {}, "x")
    assert response["error"]["data"]["code"] == "bridge.method_not_found"
