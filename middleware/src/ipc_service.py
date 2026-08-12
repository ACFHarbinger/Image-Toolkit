"""Small in-memory IPC service for frontend integration tests and hosts."""

from __future__ import annotations

import uuid
from typing import Any

from .document import Document, Frame, FrameSequence
from .ipc import IpcRequest, IpcResponse


class IpcService:
    """Handle initial media/document commands without filesystem policy."""

    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}

    def handle(self, request: IpcRequest) -> IpcResponse:
        try:
            handler = {
                "open_media": self._open_media,
                "export_document": self._export_document,
                "notify": self._notify,
            }[request.method]
            return IpcResponse(request.request_id, "ok", handler(request.payload))
        except (KeyError, TypeError, ValueError) as exc:
            return IpcResponse(request.request_id, "error", error=str(exc))

    def _open_media(self, payload: dict[str, Any]) -> dict[str, Any]:
        source = payload.get("source")
        sequence = self._sequence_from_payload(source, payload)
        document_id = payload.get("document_id") or f"doc-{uuid.uuid4().hex[:12]}"
        document = Document(document_id, sequence)
        self._documents[document_id] = document
        return {
            "document_id": document_id,
            "snapshot_id": document.snapshot_id(),
            "frame_count": len(sequence.frames),
            "fps": sequence.fps,
        }

    @staticmethod
    def _sequence_from_payload(source: Any, payload: dict[str, Any]) -> FrameSequence:
        frames = payload.get("frames")
        if frames is None:
            if not isinstance(source, str) or not source.strip():
                raise ValueError("open_media requires a non-empty source or frames list")
            return FrameSequence.still(source)
        if not isinstance(frames, list) or not frames:
            raise ValueError("open_media frames must be a non-empty list")
        parsed: list[Frame] = []
        for index, value in enumerate(frames):
            if isinstance(value, str):
                frame_source, duration_ms, metadata = value, 0, {}
            elif isinstance(value, dict):
                frame_source = value.get("source")
                duration_ms = value.get("duration_ms", 0)
                metadata = value.get("metadata", {})
            else:
                raise ValueError(f"frame {index} must be a source string or object")
            if not isinstance(frame_source, str) or not frame_source.strip():
                raise ValueError(f"frame {index} requires a non-empty source")
            if not isinstance(duration_ms, int) or duration_ms < 0:
                raise ValueError(f"frame {index} duration_ms must be a non-negative integer")
            if not isinstance(metadata, dict):
                raise ValueError(f"frame {index} metadata must be an object")
            parsed.append(Frame(frame_source, duration_ms, metadata))
        fps = payload.get("fps", 0.0)
        if not isinstance(fps, (int, float)) or isinstance(fps, bool) or fps < 0:
            raise ValueError("open_media fps must be a non-negative number")
        return FrameSequence(tuple(parsed), float(fps))

    def _export_document(self, payload: dict[str, Any]) -> dict[str, Any]:
        document_id = payload.get("document_id")
        if document_id not in self._documents:
            raise ValueError(f"document is not open: {document_id!r}")
        document = self._documents[document_id]
        return {"document_id": document_id, "document": document.to_dict()}

    @staticmethod
    def _notify(payload: dict[str, Any]) -> dict[str, Any]:
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("notify requires a non-empty message")
        return {"acknowledged": True}
