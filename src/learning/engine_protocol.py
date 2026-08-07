"""Versioned JSON transport between constrained hosts and the local engine."""

from __future__ import annotations

import json
import sys
from typing import Any

from project import (
    AdviceRating,
    SuggestionDecision,
    attach_correspondence_set,
    attach_style_bible,
    configure_capstone_policy,
    configure_feedback_policy,
    configure_identity_card_policy,
    configure_progress_retention,
    configure_study_consent,
    create_exercise_project,
    decide_attempt_review,
    detach_correspondence_set,
    detach_style_bible,
    import_compatible_capstone_review,
    import_reference_asset,
    project_correspondence_set_payload,
    project_progress_snapshot,
    project_style_bible_payload,
    propagate_project_correspondence,
    record_advice_feedback,
    record_attempt_review,
    record_study_session,
    revise_capstone_decision_rationale,
    set_attempt_completion,
    upsert_identity_card,
    upsert_project_correspondence_set,
    upsert_project_style_bible,
)

from .asymmetry_review import review_asymmetry_comparison
from .curriculum import build_curriculum_v1, next_primary_exercise
from .design_review import review_cranial_jaw_pair
from .eye_review import EyePairLandmarks, review_eye_pair
from .feature_review import review_feature_set, review_feature_study
from .head_review import FrontHeadLandmarks, review_front_head
from .orientation_review import (
    OrientationView,
    ProfileLandmarks,
    ThreeQuarterLandmarks,
    review_profile_head,
    review_three_quarter_head,
)
from .value_review import review_value_masks
from .variation_review import review_identity_comparison

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
                exercise_id=payload.get("exercise_id", "anime-head-front-construction"),
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
                rationale=payload.get("rationale"),
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
    if operation == "revise_capstone_decision_rationale":
        try:
            changed = revise_capstone_decision_rationale(
                payload["directory"],
                attempt_id=payload["attempt_id"],
                review_id=payload["review_id"],
                rationale=payload["rationale"],
            )
        except KeyError as error:
            raise ValueError("rationale-revision request is incomplete") from error
        return _success(request_id, {"changed": changed})
    if operation == "import_compatible_capstone_review":
        try:
            imported = import_compatible_capstone_review(
                payload["directory"],
                target_attempt_id=payload["target_attempt_id"],
                source_attempt_id=payload["source_attempt_id"],
                source_review_id=payload["source_review_id"],
                decision=SuggestionDecision(payload["decision"]),
                rationale=payload["rationale"],
            )
        except KeyError as error:
            raise ValueError("capstone-import request is incomplete") from error
        return _success(request_id, {"review_id": imported.id})
    if operation == "configure_capstone_policy":
        try:
            changed = configure_capstone_policy(
                payload["directory"],
                retain_rationale_history=payload["retain_rationale_history"],
            )
        except KeyError as error:
            raise ValueError("capstone-policy request is incomplete") from error
        return _success(request_id, {"changed": changed})
    if operation == "project_progress_snapshot":
        try:
            snapshot = project_progress_snapshot(payload["directory"])
        except KeyError as error:
            raise ValueError("progress request is incomplete") from error
        completed_ids = {
            exercise["exercise_id"]
            for exercise in snapshot["exercises"]
            if any(attempt["completed_at"] is not None for attempt in exercise["attempts"])
        }
        snapshot["recommended_exercise_id"] = next_primary_exercise(
            build_curriculum_v1(), completed_ids
        )
        return _success(request_id, snapshot)
    if operation in {"attach_style_bible", "detach_style_bible"}:
        try:
            function = (
                attach_style_bible if operation == "attach_style_bible" else detach_style_bible
            )
            changed = function(payload["directory"], asset_path=payload["asset_path"])
        except KeyError as error:
            raise ValueError("style-bible binding request is incomplete") from error
        return _success(request_id, {"changed": changed})
    if operation == "upsert_project_style_bible":
        try:
            asset_path = upsert_project_style_bible(
                payload["directory"], payload=payload["style_bible"]
            )
        except KeyError as error:
            raise ValueError("style-bible authoring request is incomplete") from error
        return _success(request_id, {"asset_path": asset_path})
    if operation == "import_reference_asset":
        try:
            asset_path = import_reference_asset(
                payload["directory"], source_path=payload["source_path"]
            )
        except KeyError as error:
            raise ValueError("reference-import request is incomplete") from error
        return _success(request_id, {"asset_path": asset_path})
    if operation == "project_style_bible_payload":
        try:
            bible = project_style_bible_payload(
                payload["directory"], asset_path=payload["asset_path"]
            )
        except KeyError as error:
            raise ValueError("style-bible read request is incomplete") from error
        return _success(request_id, bible)
    if operation in {"attach_correspondence_set", "detach_correspondence_set"}:
        try:
            function = (
                attach_correspondence_set
                if operation == "attach_correspondence_set"
                else detach_correspondence_set
            )
            changed = function(payload["directory"], asset_path=payload["asset_path"])
        except KeyError as error:
            raise ValueError("correspondence-set binding request is incomplete") from error
        return _success(request_id, {"changed": changed})
    if operation == "upsert_project_correspondence_set":
        try:
            asset_path = upsert_project_correspondence_set(
                payload["directory"], payload=payload["correspondence_set"]
            )
        except KeyError as error:
            raise ValueError("correspondence-set authoring request is incomplete") from error
        return _success(request_id, {"asset_path": asset_path})
    if operation == "project_correspondence_set_payload":
        try:
            correspondence_set = project_correspondence_set_payload(
                payload["directory"], asset_path=payload["asset_path"]
            )
        except KeyError as error:
            raise ValueError("correspondence-set read request is incomplete") from error
        return _success(request_id, correspondence_set)
    if operation == "propagate_project_correspondence":
        try:
            propagated = propagate_project_correspondence(
                payload["directory"],
                asset_path=payload["asset_path"],
                source_id=payload["source_id"],
                target_region_ids=payload["target_region_ids"],
            )
        except KeyError as error:
            raise ValueError("correspondence-propagation request is incomplete") from error
        return _success(request_id, propagated)
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
    if operation == "configure_study_consent":
        try:
            changed = configure_study_consent(
                payload["directory"],
                opted_in=payload["opted_in"],
                clear_existing=payload.get("clear_existing", False),
            )
        except KeyError as error:
            raise ValueError("study-consent request is incomplete") from error
        return _success(request_id, {"changed": changed})
    if operation == "record_study_session":
        try:
            session = record_study_session(
                payload["directory"],
                baseline_attempt_id=payload["baseline_attempt_id"],
                remedial_exercise_id=payload.get("remedial_exercise_id"),
                redraw_attempt_id=payload.get("redraw_attempt_id"),
                explanation_rating=(
                    AdviceRating(payload["explanation_rating"])
                    if payload.get("explanation_rating") is not None
                    else None
                ),
                completed=payload.get("completed", False),
            )
        except KeyError as error:
            raise ValueError("study-session request is incomplete") from error
        return _success(request_id, {"session_id": session.id})
    if operation == "upsert_identity_card":
        try:
            changed = upsert_identity_card(
                payload["directory"], name=payload["name"], anchors=payload["anchors"]
            )
        except KeyError as error:
            raise ValueError("identity-card request is incomplete") from error
        return _success(request_id, {"changed": changed})
    if operation == "configure_identity_card_policy":
        try:
            changed = configure_identity_card_policy(
                payload["directory"],
                retain_revision_history=payload["retain_revision_history"],
            )
        except KeyError as error:
            raise ValueError("identity-card policy request is incomplete") from error
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
    if operation == "set_attempt_completion":
        try:
            changed = set_attempt_completion(
                payload["directory"],
                attempt_id=payload["attempt_id"],
                completed=payload["completed"],
            )
        except KeyError as error:
            raise ValueError("attempt-completion request is incomplete") from error
        return _success(request_id, {"changed": changed})
    if operation == "review_orientation_head":
        try:
            view = OrientationView(payload["view"])
            raw_landmarks = payload["landmarks"]
        except KeyError as error:
            raise ValueError("orientation review request is incomplete") from error
        if not isinstance(raw_landmarks, dict):
            raise ValueError("orientation review landmarks must be an object")
        try:
            if view in {OrientationView.LEFT_PROFILE, OrientationView.RIGHT_PROFILE}:
                review = review_profile_head(ProfileLandmarks(**raw_landmarks), view, request_id)
            elif view in {
                OrientationView.LEFT_THREE_QUARTER,
                OrientationView.RIGHT_THREE_QUARTER,
            }:
                review = review_three_quarter_head(
                    ThreeQuarterLandmarks(**raw_landmarks), view, request_id
                )
            else:
                raise ValueError("front orientation uses the front review operation")
        except TypeError as error:
            raise ValueError("orientation review has invalid landmark fields") from error
        return _success(request_id, review.to_dict())
    if operation == "review_cranial_jaw_pair":
        try:
            front = FrontHeadLandmarks(**payload["front_landmarks"])
            turned = ThreeQuarterLandmarks(**payload["turned_landmarks"])
            review = review_cranial_jaw_pair(front, turned, request_id, payload["variant_id"])
        except KeyError as error:
            raise ValueError("cranial/jaw pair review is incomplete") from error
        except TypeError as error:
            raise ValueError("cranial/jaw pair review has invalid landmarks") from error
        return _success(request_id, review.to_dict())
    if operation == "review_eye_pair":
        try:
            eye_landmarks = EyePairLandmarks(**payload["landmarks"])
            review = review_eye_pair(eye_landmarks, payload["view"], payload["stage"], request_id)
        except KeyError as error:
            raise ValueError("eye review request is incomplete") from error
        except TypeError as error:
            raise ValueError("eye review has invalid landmarks") from error
        return _success(request_id, review.to_dict())
    if operation == "review_feature_study":
        try:
            review = review_feature_study(
                payload["landmarks"], payload["feature"], payload["view"], request_id
            )
        except KeyError as error:
            raise ValueError("feature review request is incomplete") from error
        return _success(request_id, review.to_dict())
    if operation == "review_feature_set":
        try:
            review = review_feature_set(payload["front"], payload["turned"], request_id)
        except KeyError as error:
            raise ValueError("combined feature review request is incomplete") from error
        return _success(request_id, review.to_dict())
    if operation == "review_asymmetry_comparison":
        try:
            review = review_asymmetry_comparison(
                payload["control"],
                payload["candidate"],
                payload["stage"],
                payload.get("intent"),
                request_id,
            )
        except KeyError as error:
            raise ValueError("controlled-asymmetry review request is incomplete") from error
        return _success(request_id, review.to_dict())
    if operation == "review_identity_comparison":
        try:
            review = review_identity_comparison(
                payload["baseline"],
                payload["candidate"],
                payload["stage"],
                payload["identity_card"],
                request_id,
            )
        except KeyError as error:
            raise ValueError("identity-comparison request is incomplete") from error
        return _success(request_id, review.to_dict())
    if operation == "review_value_masks":
        try:
            review = review_value_masks(
                payload["front_form_mask"],
                payload["front_cast_mask"],
                payload["turned_form_mask"],
                payload["turned_cast_mask"],
                payload["width"],
                payload["height"],
                payload["light_direction"],
                payload["boundary_hardness"],
                request_id,
                payload.get("third_value_mask"),
            )
        except KeyError as error:
            raise ValueError("value-mask review request is incomplete") from error
        return _success(request_id, review.to_dict())
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
