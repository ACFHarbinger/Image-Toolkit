"""Sidecar handlers for the Hybrid Image Editor capability (E-02 / #915)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.hie.commands import (
    HieEditCommand,
    HieExportDocumentCommand,
    HieListCapabilitiesCommand,
    HieOpenDocumentCommand,
)
from middleware.src.services.hie.service import HieService


def handle_open_document(service: HieService | None, params: dict[str, Any]) -> dict[str, Any]:
    """Dispatch hie.open_document onto HieService."""
    svc = service or HieService()
    cmd = HieOpenDocumentCommand(
        source=str(params["source"]),
        document_id=params.get("document_id"),
        metadata=params.get("metadata") or {},
    )
    res = svc.open_document(cmd)
    return {
        "success": res.success,
        "document_id": res.document_id,
        "frame_count": res.frame_count,
        "width": res.width,
        "height": res.height,
        "elapsed_seconds": res.elapsed_seconds,
        "error": res.error,
    }


def handle_execute_edit(service: HieService | None, params: dict[str, Any]) -> dict[str, Any]:
    """Dispatch hie.execute_edit onto HieService."""
    svc = service or HieService()
    cmd = HieEditCommand(
        document_id=str(params["document_id"]),
        operation=str(params["operation"]),
        parameters=params.get("parameters") or {},
    )
    res = svc.execute_edit(cmd)
    return {
        "success": res.success,
        "document_id": res.document_id,
        "output_document_id": res.output_document_id,
        "modified_layers": list(res.modified_layers),
        "elapsed_seconds": res.elapsed_seconds,
        "error": res.error,
    }


def handle_export_document(service: HieService | None, params: dict[str, Any]) -> dict[str, Any]:
    """Dispatch hie.export_document onto HieService."""
    svc = service or HieService()
    fmt = params.get("format") or "png"
    quality = params.get("quality") if params.get("quality") is not None else 95
    cmd = HieExportDocumentCommand(
        document_id=str(params["document_id"]),
        output_path=str(params["output_path"]),
        format=fmt,
        quality=quality,
    )
    res = svc.export_document(cmd)
    return {
        "success": res.success,
        "output_path": res.output_path,
        "size_bytes": res.size_bytes,
        "elapsed_seconds": res.elapsed_seconds,
        "error": res.error,
    }


def handle_list_capabilities(
    service: HieService | None, _params: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Dispatch hie.list_capabilities onto HieService."""
    svc = service or HieService()
    res = svc.list_capabilities(HieListCapabilitiesCommand())
    return {
        "capabilities": list(res.capabilities),
        "models_available": list(res.models_available),
        "error": res.error,
    }


def handle_render_viewport(
    service: HieService | None, params: dict[str, Any]
) -> dict[str, Any]:
    """Dispatch hie.render_viewport onto HieService."""
    svc = service or HieService()
    return svc.render_viewport(
        document_id=str(params["document_id"]),
        zoom=params.get("zoom"),
        pan_x=params.get("pan_x"),
        pan_y=params.get("pan_y"),
        viewport_width=params.get("viewport_width"),
        viewport_height=params.get("viewport_height"),
    )

