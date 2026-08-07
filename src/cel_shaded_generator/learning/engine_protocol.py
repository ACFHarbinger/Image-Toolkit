"""Versioned JSON transport between constrained hosts and the local engine."""

from __future__ import annotations

import json
import sys
from typing import Any

from .head_review import FrontHeadLandmarks, review_front_head

ENGINE_PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 1024 * 1024


def handle_request(request: dict[str, Any]) -> dict[str, Any]:
    """Handle one side-effect-free engine request."""
    if request.get("protocol_version") != ENGINE_PROTOCOL_VERSION:
        raise ValueError("unsupported engine protocol version")
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("request_id must be a non-empty string")
    if request.get("operation") != "review_front_head":
        raise ValueError("unsupported engine operation")
    payload = request.get("payload")
    if not isinstance(payload, dict) or not isinstance(payload.get("landmarks"), dict):
        raise ValueError("review request must contain landmark data")
    try:
        landmarks = FrontHeadLandmarks(**payload["landmarks"])
    except TypeError as error:
        raise ValueError("review request has invalid landmark fields") from error
    review = review_front_head(landmarks, request_id)
    return {
        "protocol_version": ENGINE_PROTOCOL_VERSION,
        "request_id": request_id,
        "ok": True,
        "result": review.to_dict(),
    }


def main() -> int:
    """Read one bounded JSON request from stdin and emit one JSON response."""
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        return _write_error(None, "request_too_large", "engine request exceeds 1 MiB")
    try:
        request = json.loads(raw)
        if not isinstance(request, dict):
            raise ValueError("engine request root must be an object")
        response = handle_request(request)
    except (UnicodeError, json.JSONDecodeError, ValueError) as error:
        request_id = (
            request.get("request_id") if isinstance(locals().get("request"), dict) else None
        )
        return _write_error(request_id, "invalid_request", str(error))
    sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
    return 0


def _write_error(request_id: Any, code: str, message: str) -> int:
    response = {
        "protocol_version": ENGINE_PROTOCOL_VERSION,
        "request_id": request_id if isinstance(request_id, str) else None,
        "ok": False,
        "error": {"code": code, "message": message},
    }
    sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
    return 2


if __name__ == "__main__":  # pragma: no cover - exercised through the installed script
    raise SystemExit(main())
