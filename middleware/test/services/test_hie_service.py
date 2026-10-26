"""Unit tests for the Hybrid Image Editor (HIE) service (W0-03 Phase C, #867)."""

from __future__ import annotations

import dataclasses
import json
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
    assert result.elapsed_seconds >= 0.0


def test_hie_open_document_with_mock_ipc() -> None:
    mock_ipc = MagicMock()
    mock_ipc.handle.return_value = MagicMock(
        status="ok",
        payload={"width": 800, "height": 600, "frame_count": 3},
        error=None,
    )
    service = HieService(ipc_service=mock_ipc)
    result = service.open_document(HieOpenDocumentCommand(source="/sample.png"))
    assert result.success is True
    assert result.width == 800
    assert result.height == 600
    assert result.frame_count == 3


def test_hie_ipc_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(HieService, "_get_ipc", lambda self: None)
    service = HieService()
    opened = service.open_document(HieOpenDocumentCommand(source="/sample.png"))
    edited = service.execute_edit(
        HieEditCommand(document_id="doc-1", operation="crop_composition")
    )
    out = tmp_path / "exported.json"
    exported = service.export_document(
        HieExportDocumentCommand(document_id="doc-1", output_path=str(out))
    )
    assert opened.success is False
    assert edited.success is False
    assert exported.success is False
    assert opened.error and "unavailable" in opened.error
    assert edited.error and "unavailable" in edited.error
    assert exported.error and "unavailable" in exported.error
    assert not out.exists()


def test_hie_ipc_error_status(tmp_path: Path) -> None:
    mock_ipc = MagicMock()
    mock_ipc.handle.return_value = MagicMock(
        status="error",
        payload={},
        error="backend rejected the request",
    )
    service = HieService(ipc_service=mock_ipc)
    opened = service.open_document(HieOpenDocumentCommand(source="/sample.png"))
    edited = service.execute_edit(
        HieEditCommand(document_id="doc-1", operation="deblur")
    )
    out = tmp_path / "exported.json"
    exported = service.export_document(
        HieExportDocumentCommand(document_id="doc-1", output_path=str(out))
    )
    assert opened.success is False
    assert edited.success is False
    assert exported.success is False
    assert opened.error == "backend rejected the request"
    assert edited.error == "backend rejected the request"
    assert exported.error == "backend rejected the request"
    assert not out.exists()


def test_hie_edit_validation() -> None:
    service = HieService()
    with pytest.raises(CommandValidationError):
        service.execute_edit(HieEditCommand(document_id="", operation="tone"))
    with pytest.raises(CommandValidationError):
        service.execute_edit(HieEditCommand(document_id="doc-1", operation=""))


def test_hie_edit_requires_open_document() -> None:
    service = HieService()
    result = service.execute_edit(
        HieEditCommand(document_id="doc-missing", operation="crop_composition", parameters={"x": 10})
    )
    assert result.success is False
    assert result.error and "not open" in result.error


def test_hie_edit_crop_composition() -> None:
    service = HieService()
    opened = service.open_document(
        HieOpenDocumentCommand(source="/sample.png", document_id="doc-1")
    )
    assert opened.success is True
    result = service.execute_edit(
        HieEditCommand(document_id="doc-1", operation="crop_composition", parameters={"x": 10})
    )
    assert result.success is True
    assert result.document_id == "doc-1"
    assert result.output_document_id is not None
    assert "-op-" not in result.output_document_id
    assert result.modified_layers != ("layer-0",)


def test_hie_export_validation() -> None:
    service = HieService()
    with pytest.raises(CommandValidationError):
        service.export_document(HieExportDocumentCommand(document_id="", output_path="/out.png"))
    with pytest.raises(CommandValidationError):
        service.export_document(HieExportDocumentCommand(document_id="doc-1", output_path=""))


def test_hie_export_execution(tmp_path: Path) -> None:
    out = tmp_path / "exported.png"
    service = HieService()
    open_res = service.open_document(HieOpenDocumentCommand(source="/sample.png", document_id="doc-1"))
    assert open_res.success is True

    result = service.export_document(HieExportDocumentCommand(document_id="doc-1", output_path=str(out)))
    assert result.success is True
    assert result.output_path == str(out)
    assert out.is_file()
    raw = out.read_bytes()
    assert raw != b""
    assert result.size_bytes == out.stat().st_size == len(raw)
    document = json.loads(raw)
    assert document["document_id"] == "doc-1"


def test_hie_list_capabilities() -> None:
    service = HieService()
    result = service.list_capabilities()
    assert isinstance(result, HieListCapabilitiesResult)
    assert "open_media" in result.capabilities
    assert "crop_composition" in result.capabilities
    assert "birefnet" in result.models_available
