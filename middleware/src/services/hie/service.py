"""Hybrid Image Editor (HIE) service implementation.

Canonical service home for HIE document model and render-graph pipeline
(W0-03 Phase C, #867). Unblocks Wave 8 editor #915 E-02.
"""

from __future__ import annotations

import io
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from PIL import Image

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

_PILLOW_FORMATS = {
    "png": "PNG",
    "jpeg": "JPEG",
    "jpg": "JPEG",
    "webp": "WEBP",
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
            if operation == "accept":
                return self._execute_accept(ipc, command, t0)
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
        """Preview a registered policy. Acceptance is a separate ``accept`` call."""
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
        return _edit_success(command, t0, preview.payload or {})

    def _execute_accept(self, ipc: Any, command: HieEditCommand, t0: float) -> HieEditResult:
        """Accept the pending proposal. IPC errors when nothing is pending."""
        accepted = _ipc_call(
            ipc,
            "accept_proposal",
            {"document_id": command.document_id},
        )
        if accepted.status != "ok":
            return _edit_failure(command, t0, accepted.error)
        return _edit_success(command, t0, accepted.payload or {})

    def _execute_restoration(self, ipc: Any, command: HieEditCommand, operation: str, t0: float) -> HieEditResult:
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
        return _edit_success(command, t0, submitted.payload or {})

    def export_document(self, command: HieExportDocumentCommand) -> HieExportDocumentResult:
        """Export a document session to a real encoded image file."""
        t0 = time.monotonic()
        if not command.document_id.strip():
            raise CommandValidationError("document_id must not be empty", field="document_id")
        if not command.output_path.strip():
            raise CommandValidationError("output_path must not be empty", field="output_path")

        try:
            ipc = self._get_ipc()
            if ipc is None:
                return _export_failure(command, t0, _IPC_UNAVAILABLE)

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
                return _export_failure(command, t0, res.error)

            payload = res.payload or {}
            document = payload.get("document") if isinstance(payload, dict) else None
            if not isinstance(document, dict):
                return _export_failure(command, t0, "export payload has no document")

            source = _document_source(document)
            if source is None:
                return _export_failure(command, t0, "export document has no source image")

            encoded = _encode_source_image(source, command.format, command.quality)
            size = _commit_encoded_image(Path(command.output_path), encoded)
            return HieExportDocumentResult(
                success=True,
                output_path=command.output_path,
                size_bytes=size,
                elapsed_seconds=_elapsed(t0),
            )
        except Exception as exc:
            return _export_failure(command, t0, str(exc))

    def list_capabilities(self, command: HieListCapabilitiesCommand | None = None) -> HieListCapabilitiesResult:
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


def _edit_success(command: HieEditCommand, t0: float, payload: dict[str, Any]) -> HieEditResult:
    output_id = payload.get("snapshot_id") or payload.get("document_id") or command.document_id
    return HieEditResult(
        success=True,
        document_id=command.document_id,
        output_document_id=str(output_id),
        modified_layers=_layer_ids(payload),
        elapsed_seconds=_elapsed(t0),
    )


def _export_failure(command: HieExportDocumentCommand, t0: float, error: str | None) -> HieExportDocumentResult:
    return HieExportDocumentResult(
        success=False,
        output_path=command.output_path,
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


def _nonempty_str(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    return None


def _document_source(document: dict[str, Any]) -> str | None:
    """Source path from document metadata, else the first frame source."""
    metadata = document.get("metadata")
    if isinstance(metadata, dict):
        source = _nonempty_str(metadata.get("source"))
        if source is not None:
            return source
    sequence = document.get("sequence")
    if not isinstance(sequence, dict):
        return None
    frames = sequence.get("frames")
    if not isinstance(frames, list) or not frames:
        return None
    first = frames[0]
    if isinstance(first, str):
        return _nonempty_str(first)
    if isinstance(first, dict):
        return _nonempty_str(first.get("source"))
    return None


def _pillow_format(image_format: str) -> str:
    normalized = (image_format or "").strip().lower()
    return _PILLOW_FORMATS.get(normalized, "PNG")


def _prepare_image(image: Image.Image, pillow_format: str) -> Image.Image:
    if pillow_format != "JPEG":
        return image
    if image.mode in {"RGB", "L"}:
        return image
    return image.convert("RGB")


def _assert_decodable(source: Any) -> None:
    with Image.open(source) as decoded:
        decoded.load()
        if decoded.width <= 0 or decoded.height <= 0:
            raise ValueError("export encode is not a decodable image")


def _encode_source_image(source: str, image_format: str, quality: int) -> bytes:
    path = Path(source)
    if not path.is_file():
        raise ValueError(f"export source is not a readable image: {source}")
    pillow_format = _pillow_format(image_format)
    try:
        with Image.open(path) as image:
            image.load()
            if image.width <= 0 or image.height <= 0:
                raise ValueError("export source has no positive dimensions")
            working = _prepare_image(image, pillow_format)
            buffer = io.BytesIO()
            save_kwargs: dict[str, Any] = {}
            if pillow_format in {"JPEG", "WEBP"}:
                save_kwargs["quality"] = int(quality)
            working.save(buffer, format=pillow_format, **save_kwargs)
            encoded = buffer.getvalue()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"export source is not a readable image: {source}") from exc
    if not encoded:
        raise ValueError("export encode produced an empty image")
    _assert_decodable(io.BytesIO(encoded))
    return encoded


def _commit_encoded_image(output_path: Path, encoded: bytes) -> int:
    """Write via a sibling temp file and replace only after the image decodes."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{output_path.name}.", dir=output_path.parent)
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        tmp_path.write_bytes(encoded)
        size = tmp_path.stat().st_size
        if size <= 0:
            raise ValueError("export encode produced an empty image")
        _assert_decodable(tmp_path)
        os.replace(tmp_path, output_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return output_path.stat().st_size
