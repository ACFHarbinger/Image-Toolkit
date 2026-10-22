"""Request/response/error envelopes for the bridge (W0-11, #875).

Wire shapes come from ``contracts/schemas/envelope/``; this module is the
runtime enforcement point: ``jsonrpc: "2.0"`` and ``ok: true`` consts, the
result/error XOR, enum members and dotted-lowercase codes are all asserted
here because the generated types are typing-only (and the generated Rust
degrades consts to scalars — README §degradations).

Application errors ride the JSON-RPC error object's ``data`` field as
``{code, retryable, message_key, details}``. No traceback ever reaches the
wire: exceptions are mapped to a static ``message_key``; ``details`` may
carry structured context the contract allows.

Error codes are part of the contract (add, never rename). The registry:
  bridge.invalid_request    — malformed frame (RPC -32600)
  bridge.method_not_found   — method absent from methods.toml (RPC -32601)
  bridge.invalid_params     — params fail the method's schema (RPC -32602)
  bridge.parse_error        — a line is not JSON (RPC -32700)
  bridge.invalid_event      — an event frame violates the envelope/payload schema
  bridge.unknown_channel    — a channel absent from methods.toml
  bridge.protocol_mismatch  — handshake answers a different protocol name
  bridge.version_mismatch   — client version outside the compatibility range
  app.internal              — unexpected service failure (RPC -32000)
Service-owned codes (e.g. jobs.not_found) come from methods.toml's
``errors`` column and are raised by services as ``BridgeAppError``.
"""

from __future__ import annotations

from typing import Any

from middleware.src.errors import ImageToolkitError

from .catalog import Catalog, catalog

# JSON-RPC 2.0 reserved error codes.
RPC_PARSE_ERROR = -32700
RPC_INVALID_REQUEST = -32600
RPC_METHOD_NOT_FOUND = -32601
RPC_INVALID_PARAMS = -32602
RPC_APP_ERROR = -32000

_APP_RPC_CODE = {
    "bridge.invalid_request": RPC_INVALID_REQUEST,
    "bridge.method_not_found": RPC_METHOD_NOT_FOUND,
    "bridge.invalid_params": RPC_INVALID_PARAMS,
    "bridge.parse_error": RPC_PARSE_ERROR,
}


class BridgeAppError(Exception):
    """An application error with a wire-ready envelope.

    Services raise this (or plain exceptions mapped by ``from_exception``)
    instead of letting tracebacks cross the bridge.
    """

    def __init__(
        self,
        code: str,
        *,
        retryable: bool = False,
        message_key: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.message_key = message_key or f"bridge.errors.{code.rsplit('.', 1)[-1]}"
        self.details = details

    def envelope(self) -> dict[str, Any]:
        error: dict[str, Any] = {
            "code": self.code,
            "retryable": self.retryable,
            "message_key": self.message_key,
        }
        if self.details:
            error["details"] = self.details
        return error


class FrameValidationError(Exception):
    """A frame violates the envelope contract; carries the wire-ready error."""

    def __init__(self, app_error: BridgeAppError) -> None:
        super().__init__(app_error.code)
        self.app_error = app_error


def _app_error_from_schema_errors(
    code: str,
    errors: list[Any],
    *,
    retryable: bool = False,
) -> BridgeAppError:
    details = {"errors": [str(error) for error in errors]}
    return BridgeAppError(code, retryable=retryable, details=details)


def build_request(
    method: str,
    *,
    request_id: str | int | None,
    params: dict[str, Any] | None = None,
    table: Catalog | None = None,
) -> dict[str, Any]:
    """Build and validate a request frame against the envelope schema."""
    table = table or catalog()
    frame: dict[str, Any] = {
        "jsonrpc": table.jsonrpc_version,
        "id": request_id,
        "method": method,
    }
    if params is not None:
        frame["params"] = params
    errors = table.validate_request_envelope(frame)
    if errors:
        raise FrameValidationError(_app_error_from_schema_errors("bridge.invalid_request", errors))
    return frame


def build_response(
    request_id: str | int | None,
    *,
    result: Any = None,
    error: BridgeAppError | None = None,
    table: Catalog | None = None,
) -> dict[str, Any]:
    """Build exactly one of a result or error response (schema XOR enforced)."""
    table = table or catalog()
    if error is not None and result is not None:
        raise ValueError("a response carries exactly one of result or error")
    frame: dict[str, Any]
    if error is not None:
        frame = {
            "jsonrpc": table.jsonrpc_version,
            "id": request_id,
            "error": {
                "code": _APP_RPC_CODE.get(error.code, RPC_APP_ERROR),
                "message": error.message_key,
                "data": error.envelope(),
            },
        }
    else:
        frame = {"jsonrpc": table.jsonrpc_version, "id": request_id, "result": result}
    errors = table.validate_response_envelope(frame)
    if errors:
        # Our own construction failed the contract — never ship it unmapped.
        raise FrameValidationError(_app_error_from_schema_errors("bridge.invalid_request", errors))
    return frame


def decode_request(frame: Any, *, table: Catalog | None = None) -> dict[str, Any]:
    """Validate an inbound request frame; return it unchanged when valid."""
    table = table or catalog()
    if not isinstance(frame, dict):
        raise FrameValidationError(
            BridgeAppError("bridge.invalid_request", details={"errors": ["frame is not an object"]})
        )
    errors = table.validate_request_envelope(frame)
    if errors:
        raise FrameValidationError(_app_error_from_schema_errors("bridge.invalid_request", errors))
    return frame


def decode_response(frame: Any, *, table: Catalog | None = None) -> dict[str, Any]:
    """Validate an inbound response; return it unchanged when valid."""
    table = table or catalog()
    if not isinstance(frame, dict):
        raise FrameValidationError(
            BridgeAppError("bridge.invalid_request", details={"errors": ["frame is not an object"]})
        )
    errors = table.validate_response_envelope(frame)
    if errors:
        raise FrameValidationError(_app_error_from_schema_errors("bridge.invalid_request", errors))
    return frame


def decode_app_error(frame: dict[str, Any], *, table: Catalog | None = None) -> BridgeAppError:
    """Extract the application error envelope from a validated error response."""
    table = table or catalog()
    data = frame["error"]["data"]
    errors = table.validate_error_envelope(data)
    if errors:
        raise FrameValidationError(_app_error_from_schema_errors("bridge.invalid_request", errors))
    return BridgeAppError(
        data["code"],
        retryable=data["retryable"],
        message_key=data["message_key"],
        details=data.get("details"),
    )


def from_exception(exc: Exception) -> BridgeAppError:
    """Map any exception to a wire-ready app error; no traceback leaks.

    Service errors raised as ``BridgeAppError`` keep their envelope;
    ``ValueError``/validation failures map to invalid params (retryable,
    caller can fix the input); messages are opaque and expose only the
    exception class so service validation cannot echo credentials. Everything
    else is an opaque internal
    failure with the exception class name only.
    """
    if isinstance(exc, BridgeAppError):
        return exc
    if isinstance(exc, FrameValidationError):
        return exc.app_error
    if isinstance(exc, (ValueError, TypeError)):
        return BridgeAppError(
            "bridge.invalid_params",
            retryable=True,
            details={"reason": type(exc).__name__},
        )
    if isinstance(exc, ImageToolkitError):
        return BridgeAppError("app.internal", details={"reason": type(exc).__name__})
    return BridgeAppError("app.internal", details={"reason": type(exc).__name__})
