from __future__ import annotations

import pytest

from middleware.src.bridge.catalog import catalog
from middleware.src.bridge.envelope import (
    BridgeAppError,
    FrameValidationError,
    build_request,
    build_response,
    decode_app_error,
    decode_request,
    decode_response,
    from_exception,
)
from middleware.src.errors import PipelineError

TABLE = catalog()


def test_build_request_roundtrip() -> None:
    frame = build_request("system.ping", request_id=7, params={})
    decode_request(frame)
    assert frame == {"jsonrpc": "2.0", "id": 7, "method": "system.ping", "params": {}}


def test_build_request_enforces_jsonrpc_const() -> None:
    frame = {"jsonrpc": "1.0", "id": 1, "method": "system.ping"}
    with pytest.raises(FrameValidationError) as exc_info:
        decode_request(frame)
    assert exc_info.value.app_error.code == "bridge.invalid_request"
    assert any("must be '2.0'" in e for e in exc_info.value.app_error.details["errors"])


def test_decode_request_rejects_unknown_and_missing_fields() -> None:
    with pytest.raises(FrameValidationError):
        decode_request({"jsonrpc": "2.0", "id": 1, "method": "no-such-method!"})
    with pytest.raises(FrameValidationError):
        decode_request({"jsonrpc": "2.0", "method": "system.ping"})
    with pytest.raises(FrameValidationError):
        decode_request({"jsonrpc": "2.0", "id": 1, "method": "system.ping", "extra": 1})


def test_decode_request_rejects_params_array() -> None:
    with pytest.raises(FrameValidationError):
        decode_request({"jsonrpc": "2.0", "id": 1, "method": "system.ping", "params": []})


def test_response_is_result_xor_error() -> None:
    decode_response({"jsonrpc": "2.0", "id": 1, "result": {"ok": True}})
    decode_response(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {
                "code": -32000,
                "message": "bridge.errors.internal",
                "data": {"code": "app.internal", "retryable": False, "message_key": "bridge.errors.internal"},
            },
        }
    )
    with pytest.raises(FrameValidationError):
        decode_response({"jsonrpc": "2.0", "id": 1})
    with pytest.raises(FrameValidationError):
        decode_response({"jsonrpc": "2.0", "id": 1, "result": {}, "error": {"code": 1, "message": "m", "data": {}}})


def test_build_response_error_wraps_app_envelope_in_rpc_error() -> None:
    error = BridgeAppError("jobs.not_found", details={"job_id": "j1"})
    frame = build_response("req-1", error=error)
    assert frame["error"]["code"] == -32000
    decode_response(frame)
    decoded = decode_app_error(frame)
    assert decoded.code == "jobs.not_found"
    assert decoded.retryable is False
    assert decoded.message_key == "bridge.errors.not_found"
    assert decoded.details == {"job_id": "j1"}


def test_build_response_result_is_valid() -> None:
    frame = build_response("req-1", result={"ok": True})
    assert frame == {"jsonrpc": "2.0", "id": "req-1", "result": {"ok": True}}
    decode_response(frame)


def test_build_response_rejects_both_and_neither() -> None:
    error = BridgeAppError("jobs.not_found")
    with pytest.raises(ValueError):
        build_response(1, result={"ok": True}, error=error)


def test_app_error_envelope_shape() -> None:
    error = BridgeAppError("jobs.submit.rejected", retryable=True, details={"k": "v"})
    envelope = error.envelope()
    assert envelope == {
        "code": "jobs.submit.rejected",
        "retryable": True,
        "message_key": "bridge.errors.rejected",
        "details": {"k": "v"},
    }
    errors = TABLE.validate_error_envelope(envelope)
    assert errors == []


def test_app_error_rejects_invalid_code_shape() -> None:
    # codes are dotted lowercase: a bare word violates the contract pattern
    error = BridgeAppError("internal")
    errors = TABLE.validate_error_envelope(error.envelope())
    assert errors


def test_decode_app_error_enforces_dotted_code() -> None:
    # the response envelope itself validates error.data against error.json,
    # so a malformed app code fails at decode_response already
    frame = {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {
            "code": -32000,
            "message": "m",
            "data": {"code": "not-dotted!", "retryable": False, "message_key": "m"},
        },
    }
    with pytest.raises(FrameValidationError):
        decode_response(frame)


def test_from_exception_maps_without_traceback() -> None:
    # caller-input errors echo the reason (the caller's own input); internal
    # failures leak nothing but the exception class name
    app_error = from_exception(ValueError("boom at secret/path"))
    assert app_error.code == "bridge.invalid_params"
    assert app_error.retryable is True
    assert app_error.details == {"reason": "boom at secret/path"}

    app_error = from_exception(PipelineError("detailed traceback at /home/user/x"))
    assert app_error.code == "app.internal"
    assert app_error.details == {"reason": "PipelineError"}
    assert "traceback" not in str(app_error.details)
    assert "/home" not in str(app_error.details)


def test_from_exception_passes_bridge_app_error_through() -> None:
    original = BridgeAppError("jobs.not_found", retryable=False)
    assert from_exception(original) is original
