"""entity_recon.* reaches the service through the sidecar dispatcher
(B-06 / #911). The engine is monkeypatched — the dispatch tests load no
dataset index and touch no network."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import numpy
import pytest

from middleware.src.bridge import PROTOCOL_NAME
from middleware.src.sidecar.handlers import entity_recon as entity_handlers
from middleware.src.sidecar.server import SidecarServer


def _request(server: SidecarServer, method: str, params: dict[str, Any], request_id: str) -> dict[str, Any]:
    return server.handle_frame({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})  # type: ignore[return-value]


@pytest.fixture()
def server(monkeypatch, tmp_path: Path) -> SidecarServer:
    """Engine attached: the handler really reads the cutout via cv2, but
    the resolution is a stubbed projection (no index, no network)."""
    import cv2

    class _Engine:
        def __init__(self) -> None:
            from middleware.src.web.recon.config import ReconConfig

            self.config = ReconConfig()

    image = tmp_path / "cutout.png"
    cv2.imwrite(str(image), numpy.zeros((4, 4, 3), dtype="uint8"))

    def fake_resolve_result(engine, cutout_rgb, cutout_png, params):
        assert cutout_rgb is not None, "the handler must load the image"
        return {
            "available": True,
            "found": True,
            "name": "rin tohsaka",
            "confidence": 0.91,
            "method": "ArcFace -> Local DB",
            "origin": "local",
            "local_matches": [{"label": "rin tohsaka", "path": "/dataset/rin/001.png", "score": 0.91}],
            "web_domains": [],
            "report": {
                "query_hash": "abc123",
                "predicted_name": "rin tohsaka",
                "confidence": 0.91,
                "method": "ArcFace -> Local DB",
                "created_at": "2026-10-25T00:00:00+00:00",
                "entries": [
                    {
                        "kind": "local",
                        "label": "rin tohsaka",
                        "source": "/dataset/rin/001.png",
                        "score": 0.91,
                        "method": "ArcFace -> Local DB",
                    }
                ],
            },
            "error": None,
        }

    monkeypatch.setattr(entity_handlers, "resolve_result", fake_resolve_result)
    server = SidecarServer(stdout=io.StringIO(), recon_engine=_Engine())
    handshake = _request(
        server,
        "system.handshake",
        {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        "handshake",
    )
    assert "entity_recon" in handshake["result"]["capabilities"]
    return server


def test_describe_dispatch(server: SidecarServer) -> None:
    response = _request(server, "entity_recon.describe", {}, "d")
    result = response["result"]
    assert result["available"] is True
    assert result["config"]["search_scope"] == "local"


def test_resolve_handler_passes_rgb_and_encodes_bgr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import cv2

    bgr = numpy.zeros((2, 2, 3), dtype="uint8")
    bgr[..., 0] = 10
    bgr[..., 1] = 20
    bgr[..., 2] = 30
    path = tmp_path / "color.png"
    cv2.imwrite(str(path), bgr)
    seen: dict[str, Any] = {}

    def fake_resolve_result(engine, cutout_rgb, cutout_png, params):
        seen["rgb"] = cutout_rgb
        seen["png"] = cutout_png
        return {"available": True, "error": None}

    monkeypatch.setattr(entity_handlers, "resolve_result", fake_resolve_result)
    entity_handlers.handle_entity_recon_resolve(object(), {"image_path": str(path)})
    assert seen["rgb"][0, 0].tolist() == [30, 20, 10]
    decoded = cv2.imdecode(numpy.frombuffer(seen["png"], dtype=numpy.uint8), cv2.IMREAD_COLOR)
    assert decoded[0, 0].tolist() == [10, 20, 30]


def test_resolve_dispatch_reads_the_image_and_normalizes(server: SidecarServer, tmp_path: Path) -> None:
    response = _request(
        server,
        "entity_recon.resolve",
        {"image_path": str(tmp_path / "cutout.png")},
        "r",
    )
    result = response["result"]
    assert result["available"] is True
    assert result["error"] is None


def test_without_an_engine_every_call_stays_unavailable() -> None:
    server = SidecarServer(stdout=io.StringIO())
    _request(
        server,
        "system.handshake",
        {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        "handshake",
    )
    described = _request(server, "entity_recon.describe", {}, "d")["result"]
    assert described["available"] is False
    resolved = _request(server, "entity_recon.resolve", {"image_path": "/x.png"}, "r")["result"]
    assert resolved["available"] is False


def test_unknown_entity_recon_method_is_method_not_found(server: SidecarServer) -> None:
    response = _request(server, "entity_recon.reindex", {}, "x")
    assert response["error"]["data"]["code"] == "bridge.method_not_found"
