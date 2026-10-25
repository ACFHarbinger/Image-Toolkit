"""Unit tests for the Hybrid Image Editor (HIE) service (W0-03 Phase C, #867)."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from middleware.src.services.base import CommandValidationError
from middleware.src.services.hie import (
    HieEditCommand,
    HieExportDocumentCommand,
    HieListCapabilitiesResult,
    HieOpenDocumentCommand,
    HieOpenDocumentResult,
    HieService,
    HieServiceProtocol,
)
from middleware.src.services.hie.service import _IPC_UNAVAILABLE
from PIL import Image


def _png(path: Path, size: tuple[int, int] = (4, 3), color: tuple[int, int, int] = (10, 20, 30)) -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def _open(service: HieService, source: str, document_id: str = "doc-1"):
    return service.open_document(HieOpenDocumentCommand(source=source, document_id=document_id))


def test_hie_protocol_conformance() -> None:
    service = HieService()
    assert isinstance(service, HieServiceProtocol)


def test_hie_command_immutability() -> None:
    cmd = HieOpenDocumentCommand(source="/sample.png")
    with pytest.raises(dataclasses.FrozenInstanceError):
        cmd.source = "/other.png"  # type: ignore[misc]

    res = HieOpenDocumentResult(success=True, document_id="doc-1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        res.success = False  # type: ignore[misc]


def test_hie_open_document_validation() -> None:
    service = HieService()
    with pytest.raises(CommandValidationError):
        service.open_document(HieOpenDocumentCommand(source=""))


def test_hie_open_document_execution() -> None:
    service = HieService()
    result = service.open_document(HieOpenDocumentCommand(source="/sample.png", document_id="doc-42"))
    assert result.success is True
    assert result.document_id == "doc-42"
    assert result.frame_count >= 1
    assert result.width == 0
    assert result.height == 0
    assert result.elapsed_seconds >= 0.0


def test_hie_open_document_with_mock_ipc() -> None:
    mock_ipc = MagicMock()
    mock_ipc.handle.return_value = MagicMock(
        status="ok",
        payload={"width": 800, "height": 600, "frame_count": 3, "document_id": "doc-mock"},
        error=None,
    )
    service = HieService(ipc_service=mock_ipc)
    result = service.open_document(HieOpenDocumentCommand(source="/sample.png"))
    assert result.success is True
    assert result.document_id == "doc-mock"
    assert result.width == 800
    assert result.height == 600
    assert result.frame_count == 3


def test_hie_open_unavailable_ipc() -> None:
    service = HieService()
    service._get_ipc = lambda: None  # type: ignore[method-assign]
    result = service.open_document(HieOpenDocumentCommand(source="/sample.png", document_id="doc-42"))
    assert result.success is False
    assert result.error == _IPC_UNAVAILABLE
    assert result.width == 0
    assert result.height == 0


def test_hie_edit_validation() -> None:
    service = HieService()
    with pytest.raises(CommandValidationError):
        service.execute_edit(HieEditCommand(document_id="", operation="tone"))
    with pytest.raises(CommandValidationError):
        service.execute_edit(HieEditCommand(document_id="doc-1", operation=""))


def test_hie_edit_unopened_document_fails() -> None:
    service = HieService()
    result = service.execute_edit(
        HieEditCommand(document_id="never-opened", operation="crop-composition", parameters={"x": 10})
    )
    assert result.success is False
    assert result.output_document_id is None
    assert result.modified_layers == ()
    assert result.error is not None
    assert "not open" in result.error


def test_hie_edit_unsupported_operation_fails() -> None:
    service = HieService()
    for operation in ("brush-assistant_accept", "crop"):
        result = service.execute_edit(HieEditCommand(document_id="doc-1", operation=operation))
        assert result.success is False
        assert result.error == f"unsupported HIE operation: {operation}"


def test_hie_edit_unavailable_ipc() -> None:
    service = HieService()
    service._get_ipc = lambda: None  # type: ignore[method-assign]
    result = service.execute_edit(HieEditCommand(document_id="doc-1", operation="crop-composition"))
    assert result.success is False
    assert result.error == _IPC_UNAVAILABLE


def test_hie_policy_preview_then_accept() -> None:
    service = HieService()
    opened = _open(service, "/sample.png")
    assert opened.success is True

    preview = service.execute_edit(
        HieEditCommand(document_id="doc-1", operation="crop_composition", parameters={"x": 10})
    )
    assert preview.success is True
    assert preview.document_id == "doc-1"
    assert preview.output_document_id == "doc-1"
    assert preview.modified_layers == ()
    assert "layer-0" not in preview.modified_layers

    accepted = service.execute_edit(HieEditCommand(document_id="doc-1", operation="accept"))
    assert accepted.success is True
    assert accepted.document_id == "doc-1"
    assert accepted.modified_layers == ()
    assert accepted.output_document_id not in (None, "doc-1")

    again = service.execute_edit(HieEditCommand(document_id="doc-1", operation="accept"))
    assert again.success is False
    assert again.error is not None
    assert "pending" in again.error


def test_hie_deblur_submits_restoration(tmp_path: Path) -> None:
    source = _png(tmp_path / "soft.png")
    service = HieService()
    assert _open(service, str(source)).success is True
    result = service.execute_edit(
        HieEditCommand(
            document_id="doc-1",
            operation="deblur",
            parameters={"output_ref": str(tmp_path / "soft.deblur.png")},
        )
    )
    assert result.success is True
    assert result.modified_layers == ()
    assert result.output_document_id == "doc-1"


def test_hie_inpainting_alias_reaches_restoration() -> None:
    service = HieService()
    assert _open(service, "/sample.png").success is True
    result = service.execute_edit(HieEditCommand(document_id="doc-1", operation="inpainting"))
    assert result.success is False
    assert result.error is not None
    assert "mask_ref" in result.error


def test_hie_export_validation() -> None:
    service = HieService()
    with pytest.raises(CommandValidationError):
        service.export_document(HieExportDocumentCommand(document_id="", output_path="/out.png"))
    with pytest.raises(CommandValidationError):
        service.export_document(HieExportDocumentCommand(document_id="doc-1", output_path=""))


def test_hie_export_execution(tmp_path: Path) -> None:
    source = _png(tmp_path / "src.png", (4, 3), (10, 20, 30))
    out = tmp_path / "nested" / "exported.png"
    old = b"old-bytes"
    out.parent.mkdir()
    out.write_bytes(old)
    service = HieService()
    assert _open(service, str(source)).success is True

    result = service.export_document(
        HieExportDocumentCommand(document_id="doc-1", output_path=str(out), format="png", quality=95)
    )
    assert result.success is True
    assert result.output_path == str(out)
    assert result.size_bytes == out.stat().st_size
    assert result.size_bytes != len(old)
    assert out.read_bytes() != old
    with Image.open(out) as decoded:
        decoded.load()
        assert decoded.size == (4, 3)


def test_hie_export_keeps_destination_when_source_is_not_an_image(tmp_path: Path) -> None:
    source = tmp_path / "notes.png"
    source.write_bytes(b"not-an-image")
    out = tmp_path / "dest.png"
    out.write_bytes(b"old-bytes")
    service = HieService()
    assert _open(service, str(source)).success is True

    result = service.export_document(HieExportDocumentCommand(document_id="doc-1", output_path=str(out)))
    assert result.success is False
    assert out.read_bytes() == b"old-bytes"
    assert not list(tmp_path.glob(".dest.png.*"))


def test_hie_export_unopened_writes_nothing(tmp_path: Path) -> None:
    out = tmp_path / "missing" / "export.png"
    service = HieService()
    result = service.export_document(HieExportDocumentCommand(document_id="missing", output_path=str(out)))
    assert result.success is False
    assert result.error is not None
    assert "not open" in result.error
    assert not out.exists()
    assert not out.parent.exists()


def test_hie_export_unavailable_ipc_writes_nothing(tmp_path: Path) -> None:
    out = tmp_path / "export.png"
    service = HieService()
    service._get_ipc = lambda: None  # type: ignore[method-assign]
    result = service.export_document(HieExportDocumentCommand(document_id="doc-1", output_path=str(out)))
    assert result.success is False
    assert result.error == _IPC_UNAVAILABLE
    assert not out.exists()


def test_hie_list_capabilities() -> None:
    service = HieService()
    result = service.list_capabilities()
    assert isinstance(result, HieListCapabilitiesResult)
    assert "open_media" in result.capabilities
    assert "crop_composition" in result.capabilities
    assert "birefnet" in result.models_available
