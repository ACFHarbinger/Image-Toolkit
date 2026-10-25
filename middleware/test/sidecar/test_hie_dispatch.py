"""hie.* methods reach HieService through the sidecar dispatcher."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from PIL import Image

from middleware.src.bridge import PROTOCOL_NAME
from middleware.src.services.hie.service import HieService
from middleware.src.sidecar.server import SidecarServer


def _request(server: SidecarServer, method: str, params: dict[str, Any], request_id: str) -> dict[str, Any]:
    return server.handle_frame({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})  # type: ignore[return-value]


def _ready(service: HieService | None = None) -> SidecarServer:
    server = SidecarServer(stdout=io.StringIO(), hie_service=service)
    handshake = _request(
        server,
        "system.handshake",
        {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        "handshake",
    )
    assert "hie" in handshake["result"]["capabilities"]
    return server


def test_hie_open_document_dispatch() -> None:
    server = _ready()
    response = _request(
        server,
        "hie.open_document",
        {"source": "/path/to/test.png"},
        "open-1",
    )
    result = response["result"]
    assert result["success"] is True
    assert result["document_id"].startswith("doc-")
    assert result["frame_count"] == 1


def test_hie_execute_edit_dispatch(tmp_path: Path) -> None:
    server = _ready()
    opened = _request(
        server,
        "hie.open_document",
        {"source": str(tmp_path / "frame.png"), "document_id": "doc-123"},
        "open-for-edit",
    )
    assert opened["result"]["success"] is True
    response = _request(
        server,
        "hie.execute_edit",
        {
            "document_id": "doc-123",
            "operation": "crop-composition",
            "parameters": {"x": 0, "y": 0, "width": 100, "height": 100},
        },
        "edit-1",
    )
    result = response["result"]
    assert result["success"] is True
    assert result["document_id"] == "doc-123"
    assert "layer-0" not in result["modified_layers"]


def test_hie_export_document_dispatch(tmp_path: Path) -> None:
    source = tmp_path / "tiny.png"
    Image.new("RGB", (2, 2), (255, 0, 0)).save(source)
    server = _ready()
    opened = _request(
        server,
        "hie.open_document",
        {"source": str(source), "document_id": "doc-123"},
        "open-for-export",
    )
    assert opened["result"]["success"] is True
    out_file = tmp_path / "export.png"
    response = _request(
        server,
        "hie.export_document",
        {
            "document_id": "doc-123",
            "output_path": str(out_file),
            "format": "png",
            "quality": 90,
        },
        "export-1",
    )
    result = response["result"]
    assert result["success"] is True
    assert result["output_path"] == str(out_file)
    assert result["size_bytes"] == out_file.stat().st_size
    with Image.open(out_file) as decoded:
        decoded.load()
        assert decoded.size == (2, 2)


def test_hie_list_capabilities_dispatch() -> None:
    server = _ready()
    response = _request(
        server,
        "hie.list_capabilities",
        {},
        "caps-1",
    )
    result = response["result"]
    assert "open_media" in result["capabilities"]
    assert "birefnet" in result["models_available"]
