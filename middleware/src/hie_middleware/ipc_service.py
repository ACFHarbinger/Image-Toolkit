"""Small in-memory IPC service for frontend integration tests and hosts."""

from __future__ import annotations

import uuid
from typing import Any

from .document import Document, FrameSequence
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
        if not isinstance(source, str) or not source.strip():
            raise ValueError("open_media requires a non-empty source")
        document_id = payload.get("document_id") or f"doc-{uuid.uuid4().hex[:12]}"
        document = Document(document_id, FrameSequence.still(source))
        self._documents[document_id] = document
        return {"document_id": document_id, "snapshot_id": document.snapshot_id()}

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
