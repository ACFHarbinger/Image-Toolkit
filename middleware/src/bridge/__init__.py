"""Shared bridge package (W0-11, #875): framing, envelopes, handshake, cancel.

One small package over ``contracts/`` (W0-10, #874): the runtime
enforcement point for the wire frames. Consumers: #876 (HostClient
routing), #877 (supervisor restart events), #878 (EventHub — its
``transport.ts`` seam receives the decoded frames this package validates).
"""

from __future__ import annotations

from .cancel import Cancelled, CancelRegistry, CancelToken
from .catalog import Catalog, ContractsNotFound, catalog, contracts_dir
from .envelope import (
    RPC_APP_ERROR,
    RPC_INVALID_PARAMS,
    RPC_INVALID_REQUEST,
    RPC_METHOD_NOT_FOUND,
    RPC_PARSE_ERROR,
    BridgeAppError,
    FrameValidationError,
    build_request,
    build_response,
    decode_app_error,
    decode_request,
    decode_response,
    from_exception,
)
from .events import bridge_state_event, build_event, job_event, validate_event
from .framing import encode_frame, iter_frames, write_frame
from .handshake import (
    COMPATIBILITY_MAX,
    COMPATIBILITY_MIN,
    PROTOCOL_NAME,
    PROTOCOL_VERSION,
    accept_handshake_result,
    build_handshake_request,
    build_handshake_result,
    build_ping_request,
    build_ping_result,
    in_compatibility_range,
    parse_version,
)
from .schema import SchemaError, SchemaRegistry, UnsupportedSchema

__all__ = [
    "BridgeAppError",
    "Cancelled",
    "CancelRegistry",
    "CancelToken",
    "Catalog",
    "COMPATIBILITY_MAX",
    "COMPATIBILITY_MIN",
    "ContractsNotFound",
    "FrameValidationError",
    "PROTOCOL_NAME",
    "PROTOCOL_VERSION",
    "RPC_APP_ERROR",
    "RPC_INVALID_PARAMS",
    "RPC_INVALID_REQUEST",
    "RPC_METHOD_NOT_FOUND",
    "RPC_PARSE_ERROR",
    "SchemaError",
    "SchemaRegistry",
    "UnsupportedSchema",
    "accept_handshake_result",
    "bridge_state_event",
    "build_event",
    "build_handshake_request",
    "build_handshake_result",
    "build_ping_request",
    "build_ping_result",
    "build_request",
    "build_response",
    "catalog",
    "contracts_dir",
    "decode_app_error",
    "decode_request",
    "decode_response",
    "encode_frame",
    "from_exception",
    "in_compatibility_range",
    "iter_frames",
    "job_event",
    "parse_version",
    "validate_event",
    "write_frame",
]
