"""Small in-memory IPC service for frontend integration tests and hosts."""

from __future__ import annotations

import uuid
from typing import Any

from document import Document, Frame, FrameSequence
from ipc import IpcRequest, IpcResponse
from pipeline import PipelineSession, build_default_pipeline


class IpcService:
    """Handle media, proposal, and restoration commands for editor hosts."""

    def __init__(self) -> None:
        self._sessions: dict[str, PipelineSession] = {}
        self._pending_proposals: dict[str, Any] = {}

    def handle(self, request: IpcRequest) -> IpcResponse:
        try:
            handler = {
                "open_media": self._open_media,
                "export_document": self._export_document,
                "notify": self._notify,
                "list_capabilities": self._list_capabilities,
                "preview_policy": self._preview_policy,
                "accept_proposal": self._accept_proposal,
                "submit_restoration": self._submit_restoration,
            }[request.method]
            return IpcResponse(request.request_id, "ok", handler(request.payload))
        except (KeyError, TypeError, ValueError) as exc:
            return IpcResponse(request.request_id, "error", error=str(exc))

    def _open_media(self, payload: dict[str, Any]) -> dict[str, Any]:
        source = payload.get("source")
        sequence = self._sequence_from_payload(source, payload)
        document_id = payload.get("document_id") or f"doc-{uuid.uuid4().hex[:12]}"
        metadata = dict(payload.get("metadata") or {})
        if isinstance(source, str) and source.strip() and "source" not in metadata:
            metadata["source"] = source
        document = Document(document_id, sequence, metadata=metadata)
        self._sessions[document_id] = PipelineSession(
            document, pipeline=build_default_pipeline()
        )
        self._pending_proposals.pop(document_id, None)
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
        session = self._require_session(document_id)
        return {"document_id": document_id, "document": session.document.to_dict()}

    def _list_capabilities(self, payload: dict[str, Any]) -> dict[str, Any]:
        document_id = payload.get("document_id")
        if document_id:
            session = self._require_session(document_id)
            pipeline_caps = session.pipeline.capabilities()
            restoration_caps = session.restoration.capabilities()
        else:
            pipeline_caps = build_default_pipeline().capabilities()
            from pipeline import RestorationPipeline

            restoration_caps = RestorationPipeline().capabilities()
        return {
            "models": pipeline_caps.get("models", []),
            "policies": pipeline_caps.get("policies", []),
            "restoration": restoration_caps,
        }

    def _preview_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        document_id = payload.get("document_id")
        policy = payload.get("policy")
        if not isinstance(policy, str) or not policy.strip():
            raise ValueError("preview_policy requires a non-empty policy name")
        session = self._require_session(document_id)
        observation = dict(payload.get("observation") or {"source": "ipc"})
        proposal = session.preview_policy(policy, observation)
        self._pending_proposals[document_id] = proposal
        action = getattr(proposal.proposal, "action", None) or policy
        return {
            "document_id": document_id,
            "policy": policy,
            "action": action,
            "pending": True,
        }

    def _accept_proposal(self, payload: dict[str, Any]) -> dict[str, Any]:
        document_id = payload.get("document_id")
        session = self._require_session(document_id)
        proposal = self._pending_proposals.pop(document_id, None)
        if proposal is None:
            raise ValueError(f"no pending proposal for document: {document_id!r}")
        record = session.accept(proposal)
        return {
            "document_id": document_id,
            "accepted": True,
            "snapshot_id": session.document.snapshot_id(),
            "record": record.to_dict(),
        }

    def _submit_restoration(self, payload: dict[str, Any]) -> dict[str, Any]:
        document_id = payload.get("document_id")
        session = self._require_session(document_id)
        operation = payload.get("operation")
        backend = payload.get("backend", "pillow")
        if not isinstance(operation, str) or not operation.strip():
            raise ValueError("submit_restoration requires an operation")
        if not isinstance(backend, str) or not backend.strip():
            raise ValueError("submit_restoration requires a backend")
        input_ref = payload.get("input_ref") or session.document.metadata.get("source")
        if not isinstance(input_ref, str) or not input_ref.strip():
            raise ValueError("submit_restoration requires input_ref or open media with source")
        options = dict(payload.get("options") or {})
        handle = session.submit_restoration(
            operation, input_ref, backend=backend, options=options
        )
        return {
            "document_id": document_id,
            "job_id": handle.job_id,
            "operation": operation,
            "backend": backend,
        }

    def _require_session(self, document_id: Any) -> PipelineSession:
        if document_id not in self._sessions:
            raise ValueError(f"document is not open: {document_id!r}")
        return self._sessions[document_id]

    @staticmethod
    def _notify(payload: dict[str, Any]) -> dict[str, Any]:
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("notify requires a non-empty message")
        return {"acknowledged": True}
