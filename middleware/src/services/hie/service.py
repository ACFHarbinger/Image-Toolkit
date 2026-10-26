"""Hybrid Image Editor (HIE) service implementation.

Canonical service home for HIE document model and render-graph pipeline
(W0-03 Phase C, #867). Unblocks Wave 8 editor #915 E-02.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from middleware.src.services._submodule_loader import ensure_submodules_registered
from middleware.src.services.base import CommandValidationError
from middleware.src.services.hie.commands import (
    HieEditCommand,
    HieEditResult,
    HieExportDocumentCommand,
    HieExportDocumentResult,
    HieListCapabilitiesCommand,
    HieListCapabilitiesResult,
    HieOpenDocumentCommand,
    HieOpenDocumentResult,
)
from middleware.src.services.hie.protocols import HieServiceProtocol

_IPC_UNAVAILABLE = "HIE IPC backend is unavailable"

# Host operation names (snake or kebab) to registered HIE policy names.
_POLICY_BY_OPERATION = {
    "crop_composition": "crop-composition",
    "crop-composition": "crop-composition",
    "global_tone": "global-tone",
    "global-tone": "global-tone",
    "brush_assistant": "brush-assistant",
    "brush-assistant": "brush-assistant",
}

# Restoration operations. inpainting is the host alias for masked_inpainting.
_RESTORATION_BY_OPERATION = {
    "deblur": "deblur",
    "inpainting": "masked_inpainting",
    "masked_inpainting": "masked_inpainting",
}


class HieService(HieServiceProtocol):
    """Canonical domain service for HIE document and pipeline operations."""

    def __init__(self, ipc_service: Any = None) -> None:
        """Initialize HieService with optional IpcService delegate."""
        self._ipc_service = ipc_service
        ensure_submodules_registered()

    def _get_ipc(self) -> Any:
        if self._ipc_service is not None:
            return self._ipc_service
        try:
            from ipc_service import IpcService

            self._ipc_service = IpcService()
            return self._ipc_service
        except (ImportError, Exception):
            return None

    def open_document(self, command: HieOpenDocumentCommand) -> HieOpenDocumentResult:
        """Open or initialize an image document session."""
        t0 = time.monotonic()
        if not command.source.strip():
            raise CommandValidationError("Document source path must not be empty", field="source")

        doc_id = command.document_id or f"doc-{uuid.uuid4().hex[:12]}"

        try:
            ipc = self._get_ipc()
            if ipc is None:
                return HieOpenDocumentResult(
                    success=False,
                    document_id=doc_id,
                    elapsed_seconds=_elapsed(t0),
                    error=_IPC_UNAVAILABLE,
                )

            res = _ipc_call(
                ipc,
                "open_media",
                {
                    "source": command.source,
                    "document_id": doc_id,
                    "metadata": command.metadata,
                },
            )
            if res.status != "ok":
                return HieOpenDocumentResult(
                    success=False,
                    document_id=doc_id,
                    elapsed_seconds=_elapsed(t0),
                    error=res.error,
                )
            payload = res.payload or {}
            return HieOpenDocumentResult(
                success=True,
                document_id=str(payload.get("document_id") or doc_id),
                frame_count=_payload_int(payload, "frame_count"),
                width=_payload_int(payload, "width"),
                height=_payload_int(payload, "height"),
                elapsed_seconds=_elapsed(t0),
            )
        except Exception as exc:
            return HieOpenDocumentResult(
                success=False,
                document_id=doc_id,
                elapsed_seconds=_elapsed(t0),
                error=str(exc),
            )

    def execute_edit(self, command: HieEditCommand) -> HieEditResult:
        """Apply an editing operation to an active document session."""
        t0 = time.monotonic()
        if not command.document_id.strip():
            raise CommandValidationError("document_id must not be empty", field="document_id")
        if not command.operation.strip():
            raise CommandValidationError("operation must not be empty", field="operation")

        try:
            ipc = self._get_ipc()
            if ipc is None:
                return HieEditResult(
                    success=False,
                    document_id=command.document_id,
                    elapsed_seconds=_elapsed(t0),
                    error=_IPC_UNAVAILABLE,
                )

            operation = command.operation.strip()
            if operation in _POLICY_BY_OPERATION:
                return self._execute_policy(ipc, command, operation, t0)
            if operation in _RESTORATION_BY_OPERATION:
                return self._execute_restoration(ipc, command, operation, t0)
            return HieEditResult(
                success=False,
                document_id=command.document_id,
                elapsed_seconds=_elapsed(t0),
                error=f"unsupported HIE operation: {operation}",
            )
        except Exception as exc:
            return HieEditResult(
                success=False,
                document_id=command.document_id,
                elapsed_seconds=_elapsed(t0),
                error=str(exc),
            )

    def _execute_policy(self, ipc: Any, command: HieEditCommand, operation: str, t0: float) -> HieEditResult:
        policy = _POLICY_BY_OPERATION[operation]
        preview = _ipc_call(
            ipc,
            "preview_policy",
            {
                "document_id": command.document_id,
                "policy": policy,
                "observation": dict(command.parameters),
            },
        )
        if preview.status != "ok":
            return _edit_failure(command, t0, preview.error)
        accepted = _ipc_call(
            ipc,
            "accept_proposal",
            {"document_id": command.document_id},
        )
        if accepted.status != "ok":
            return _edit_failure(command, t0, accepted.error)
        payload = accepted.payload or {}
        output_id = payload.get("snapshot_id") or payload.get("document_id") or command.document_id
        return HieEditResult(
            success=True,
            document_id=command.document_id,
            output_document_id=str(output_id),
            modified_layers=_layer_ids(payload),
            elapsed_seconds=_elapsed(t0),
        )

    def _execute_restoration(
        self, ipc: Any, command: HieEditCommand, operation: str, t0: float
    ) -> HieEditResult:
        submitted = _ipc_call(
            ipc,
            "submit_restoration",
            {
                "document_id": command.document_id,
                "operation": _RESTORATION_BY_OPERATION[operation],
                "backend": "pillow",
                "options": dict(command.parameters),
            },
        )
        if submitted.status != "ok":
            return _edit_failure(command, t0, submitted.error)
        payload = submitted.payload or {}
        output_id = payload.get("document_id") or command.document_id
        return HieEditResult(
            success=True,
            document_id=command.document_id,
            output_document_id=str(output_id),
            modified_layers=_layer_ids(payload),
            elapsed_seconds=_elapsed(t0),
        )

    def export_document(self, command: HieExportDocumentCommand) -> HieExportDocumentResult:
        """Export a document session to destination media file."""
        t0 = time.monotonic()
        if not command.document_id.strip():
            raise CommandValidationError("document_id must not be empty", field="document_id")
        if not command.output_path.strip():
            raise CommandValidationError("output_path must not be empty", field="output_path")

        try:
            ipc = self._get_ipc()
            if ipc is None:
                return HieExportDocumentResult(
                    success=False,
                    output_path=command.output_path,
                    elapsed_seconds=_elapsed(t0),
                    error=_IPC_UNAVAILABLE,
                )

            res = _ipc_call(
                ipc,
                "export_document",
                {
                    "document_id": command.document_id,
                    "output_path": command.output_path,
                    "format": command.format,
                    "quality": command.quality,
                },
            )
            if res.status != "ok":
                return HieExportDocumentResult(
                    success=False,
                    output_path=command.output_path,
                    elapsed_seconds=_elapsed(t0),
                    error=res.error,
                )

            payload = res.payload or {}
            document = payload.get("document") if isinstance(payload, dict) else None
            if not isinstance(document, dict):
                return HieExportDocumentResult(
                    success=False,
                    output_path=command.output_path,
                    elapsed_seconds=_elapsed(t0),
                    error="export payload has no document",
                )
            return HieExportDocumentResult(
                success=False,
                output_path=command.output_path,
                elapsed_seconds=_elapsed(t0),
                error="HIE media export is unavailable: IPC returned a document description, not rendered media",
            )
        except Exception as exc:
            return HieExportDocumentResult(
                success=False,
                output_path=command.output_path,
                elapsed_seconds=_elapsed(t0),
                error=str(exc),
            )

    def list_capabilities(
        self, command: HieListCapabilitiesCommand | None = None
    ) -> HieListCapabilitiesResult:
        """Query supported operations and available neural model adapters."""
        capabilities = (
            "open_media",
            "export_document",
            "crop_composition",
            "global_tone",
            "brush_assistant",
            "watermark_removal",
            "inpainting",
            "super_resolution",
            "deblur",
            "matting",
        )
        models = (
            "birefnet",
            "lama",
            "real_esrgan",
            "nafnet",
        )
        return HieListCapabilitiesResult(
            capabilities=capabilities,
            models_available=models,
        )


def _elapsed(t0: float) -> float:
    return round(time.monotonic() - t0, 4)


def _payload_int(payload: dict[str, Any], key: str) -> int:
    if key not in payload or payload[key] is None:
        return 0
    return int(payload[key])


def _ipc_call(ipc: Any, method: str, payload: dict[str, Any]) -> Any:
    from ipc import IpcRequest

    request = IpcRequest(
        request_id=f"req-{uuid.uuid4().hex[:8]}",
        method=method,
        payload=payload,
    )
    return ipc.handle(request)


def _edit_failure(command: HieEditCommand, t0: float, error: str | None) -> HieEditResult:
    return HieEditResult(
        success=False,
        document_id=command.document_id,
        elapsed_seconds=_elapsed(t0),
        error=error,
    )


def _layer_ids(payload: dict[str, Any]) -> tuple[str, ...]:
    """Layer ids present on the IPC payload. Never invents a layer."""
    layers = payload.get("layers")
    document = payload.get("document")
    if not isinstance(layers, list) and isinstance(document, dict):
        layers = document.get("layers")
    if not isinstance(layers, list):
        return ()
    ids: list[str] = []
    for layer in layers:
        if isinstance(layer, str) and layer.strip():
            ids.append(layer)
        elif isinstance(layer, dict):
            layer_id = layer.get("id")
            if isinstance(layer_id, str) and layer_id.strip():
                ids.append(layer_id)
    return tuple(ids)
