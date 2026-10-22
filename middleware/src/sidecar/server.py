"""JSON-RPC/stdio server loop for the sidecar.

One frame in, one frame out: ``bridge.framing`` owns the wire format,
``bridge.envelope`` owns request/response validation and the no-traceback
error mapping, ``bridge.handshake`` owns the startup version negotiation.
stdout carries only framed protocol messages; every diagnostic line goes
to stderr redacted (code + message_key + safe detail fields, never
exception text or a traceback).
"""

from __future__ import annotations

import json
from typing import Any, Callable, TextIO

from middleware.src.bridge import (
    COMPATIBILITY_MAX,
    COMPATIBILITY_MIN,
    PROTOCOL_NAME,
    BridgeAppError,
    Catalog,
    FrameValidationError,
    build_handshake_result,
    build_ping_result,
    build_response,
    catalog,
    decode_request,
    from_exception,
    in_compatibility_range,
    iter_frames,
    job_event,
    write_frame,
)

from .jobs import JobRegistry

# Detail keys safe to echo to stderr: no params, no exception text.
_SAFE_DETAIL_KEYS = ("reason", "method", "job_id", "channel", "expected", "got", "client", "min", "max")


def _safe_id(frame: Any) -> str | int | None:
    if isinstance(frame, dict):
        request_id = frame.get("id")
        if isinstance(request_id, (str, int)) and not isinstance(request_id, bool):
            return request_id
    return None


class SidecarServer:
    """Handshake-gated dispatcher for the methods routed in ``catalog()``."""

    def __init__(self, table: Catalog | None = None) -> None:
        self._table = table or catalog()
        self._ready = False
        self._seq: dict[str, int] = {}  # per-channel event sequence
        self._out: TextIO | None = None
        self._err: TextIO | None = None
        self.jobs = JobRegistry(self._emit_job_event)
        self._handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
            "system.handshake": self._handshake,
            "system.ping": self._ping,
            "jobs.submit": self.jobs.submit,
            "jobs.cancel": self.jobs.cancel,
            "jobs.status": self.jobs.status,
            "jobs.list": self.jobs.list,
        }

    def serve(self, instream: TextIO, outstream: TextIO, errstream: TextIO) -> int:
        """Frame loop until stdin EOF. Returns the process exit code."""
        self._out = outstream
        self._err = errstream
        frames = iter_frames(instream)
        while True:
            try:
                frame = next(frames)
            except StopIteration:
                return 0
            except BridgeAppError as exc:  # framing raised: the line was not JSON
                self._diagnose(exc)
                self._send_error(None, exc)
                frames = iter_frames(instream)  # resume after the bad line
                continue
            try:
                self._handle(frame)
            except Exception as exc:  # a dispatch bug must not kill the loop
                error = from_exception(exc)
                self._diagnose(error)
                self._send_error(_safe_id(frame), error)

    def _handle(self, frame: Any) -> None:
        try:
            request = decode_request(frame, table=self._table)
        except FrameValidationError as exc:
            self._send_error(_safe_id(frame), exc.app_error)
            return
        method = request["method"]
        request_id = request["id"]
        if not self._ready and method != "system.handshake":
            self._send_error(
                request_id,
                BridgeAppError(
                    "bridge.invalid_request",
                    details={"reason": "handshake_required", "method": method},
                ),
            )
            return
        if method not in self._table.methods:
            self._send_error(
                request_id,
                BridgeAppError("bridge.method_not_found", details={"method": method}),
            )
            return
        params = request.get("params") or {}
        errors = self._table.validate_params(method, params)
        if errors:
            self._send_error(
                request_id,
                BridgeAppError(
                    "bridge.invalid_params",
                    retryable=True,  # caller can fix the input (see from_exception)
                    details={"errors": [str(error) for error in errors]},
                ),
            )
            return
        try:
            result = self._handlers[method](params)
        except Exception as exc:
            error = from_exception(exc)
            self._diagnose(error)
            self._send_error(request_id, error)
            return
        if self._table.validate_result(method, result):
            # Our own result broke the contract — opaque internal error on the
            # wire; the method name goes to stderr only.
            error = BridgeAppError("app.internal", details={"reason": "result_schema", "method": method})
            self._diagnose(error)
            self._send_error(request_id, error)
            return
        self._send(build_response(request_id, result=result, table=self._table))

    def _handshake(self, params: dict[str, Any]) -> dict[str, Any]:
        if params["protocol"] != PROTOCOL_NAME:
            raise BridgeAppError(
                "bridge.protocol_mismatch",
                details={"expected": PROTOCOL_NAME, "got": params["protocol"]},
            )
        version = params["client"]["version"]
        if not in_compatibility_range(version):  # malformed version -> ValueError -> invalid_params
            raise BridgeAppError(
                "bridge.version_mismatch",
                details={"client": version, "min": COMPATIBILITY_MIN, "max": COMPATIBILITY_MAX},
            )
        self._ready = True
        return build_handshake_result(table=self._table)

    def _ping(self, _params: dict[str, Any]) -> dict[str, Any]:
        return build_ping_result(table=self._table)

    def _emit_job_event(self, job_id: str, state: str) -> None:
        seq = self._seq.get("jobs", 0) + 1
        self._seq["jobs"] = seq
        self._send(job_event(job_id, state, seq, table=self._table))

    def _send(self, frame: dict[str, Any]) -> None:
        assert self._out is not None
        write_frame(self._out, frame)

    def _send_error(self, request_id: str | int | None, error: BridgeAppError) -> None:
        self._send(build_response(request_id, error=error, table=self._table))

    def _diagnose(self, error: BridgeAppError) -> None:
        """One redacted stderr line: code + message_key + safe details only."""
        assert self._err is not None
        safe = {
            key: error.details[key]
            for key in _SAFE_DETAIL_KEYS
            if error.details and key in error.details
        }
        detail = " " + json.dumps(safe, separators=(",", ":")) if safe else ""
        self._err.write(f"sidecar: {error.code} {error.message_key}{detail}\n")
        self._err.flush()
