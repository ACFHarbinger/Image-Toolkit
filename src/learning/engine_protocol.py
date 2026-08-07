"""Versioned JSON transport between constrained hosts and the local engine."""

from __future__ import annotations

import json
import sys
from typing import Any

from project import (
    AdviceRating,
    SuggestionDecision,
    configure_feedback_policy,
    configure_progress_retention,
    create_exercise_project,
    decide_attempt_review,
    project_progress_snapshot,
    record_advice_feedback,
    record_attempt_review,
)

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
    operation = request.get("operation")
    payload = request.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("engine request payload must be an object")
    if operation == "create_exercise_project":
        try:
            project = create_exercise_project(
                payload["directory"],
                title=payload["title"],
                document_asset=payload.get("document_asset", "artwork/attempt-001.kra"),
                attempt_id=payload["attempt_id"],
            )
        except KeyError as error:
            raise ValueError("project request is incomplete") from error
        result = {"project_id": project.id, "attempt_id": payload["attempt_id"]}
        return {
            "protocol_version": ENGINE_PROTOCOL_VERSION,
            "request_id": request_id,
            "ok": True,
            "result": result,
        }
    if operation == "record_attempt_review":
        try:
            review_record = record_attempt_review(
                payload["directory"],
                attempt_id=payload["attempt_id"],
                review_payload=payload["review"],
            )
        except KeyError as error:
            raise ValueError("record-review request is incomplete") from error
        return _success(request_id, {"review_id": review_record.id})
    if operation == "decide_attempt_review":
        try:
            changed = decide_attempt_review(
                payload["directory"],
                attempt_id=payload["attempt_id"],
                review_id=payload["review_id"],
                decision=SuggestionDecision(payload["decision"]),
            )
        except KeyError as error:
            raise ValueError("review-decision request is incomplete") from error
        return _success(request_id, {"changed": changed})
    if operation == "record_advice_feedback":
        try:
            changed = record_advice_feedback(
                payload["directory"],
                attempt_id=payload["attempt_id"],
                review_id=payload["review_id"],
                rating=AdviceRating(payload["rating"]),
                note=payload.get("note"),
            )
        except KeyError as error:
            raise ValueError("advice-feedback request is incomplete") from error
        return _success(request_id, {"changed": changed})
    if operation == "project_progress_snapshot":
        try:
            snapshot = project_progress_snapshot(payload["directory"])
        except KeyError as error:
            raise ValueError("progress request is incomplete") from error
        return _success(request_id, snapshot)
    if operation == "configure_progress_retention":
        try:
            changed = configure_progress_retention(
                payload["directory"],
                enabled=payload["enabled"],
                clear_existing=payload.get("clear_existing", False),
            )
        except KeyError as error:
            raise ValueError("progress-retention request is incomplete") from error
        return _success(request_id, {"changed": changed})
    if operation == "configure_feedback_policy":
        try:
            changed = configure_feedback_policy(
                payload["directory"],
                retain_revision_history=payload["retain_revision_history"],
                note_character_limit=payload["note_character_limit"],
            )
        except KeyError as error:
            raise ValueError("feedback-policy request is incomplete") from error
        return _success(request_id, {"changed": changed})
    if operation != "review_front_head":
        raise ValueError("unsupported engine operation")
    if not isinstance(payload.get("landmarks"), dict):
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


def _success(request_id: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol_version": ENGINE_PROTOCOL_VERSION,
        "request_id": request_id,
        "ok": True,
        "result": result,
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
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
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
