"""Intent-aware comparison review for controlled asymmetry studies."""

from __future__ import annotations

import math

from .model import Evidence, EvidenceSource, Review

REQUIRED_KEYS = {
    "cranium_center",
    "cranium_edge",
    "axis_top",
    "chin",
    "left_eye_center",
    "right_eye_center",
    "jaw_left",
    "jaw_right",
    "mouth_left",
    "mouth_right",
    "left_ear_top",
    "right_ear_top",
    "left_ear_bottom",
    "right_ear_bottom",
}
REQUIRED_INTENT_STAGES = {"design", "expression", "transferred"}


def review_asymmetry_comparison(control, candidate, stage, intent, review_id):
    _validate_points(control)
    _validate_points(candidate)
    if stage not in {"corrected_drift", "design", "expression", "turned_control", "transferred"}:
        raise ValueError("controlled-asymmetry comparison stage is invalid")
    if not review_id.strip():
        raise ValueError("review id must not be empty")
    _validate_intent(stage, intent)
    control_metrics = _relationships(control)
    candidate_metrics = _relationships(candidate)
    turned = stage in {"turned_control", "transferred"}
    projected_target = 0.78 if turned else 1.0
    scores = {
        "asymmetry_cranial_retention": _similarity(
            candidate_metrics["radius"] / control_metrics["radius"], 1.0, 0.20
        ),
        "asymmetry_lower_face_retention": _similarity(
            candidate_metrics["lower_face"] / control_metrics["lower_face"], 1.0, 0.25
        ),
        "asymmetry_eye_span_retention": _similarity(
            candidate_metrics["eye_span"] / control_metrics["eye_span"], projected_target, 0.35
        ),
        "asymmetry_jaw_span_retention": _similarity(
            candidate_metrics["jaw_span"] / control_metrics["jaw_span"], projected_target, 0.35
        ),
        "asymmetry_mouth_span_retention": _similarity(
            candidate_metrics["mouth_span"] / control_metrics["mouth_span"],
            projected_target,
            0.35,
        ),
        "asymmetry_ear_height_retention": _similarity(
            candidate_metrics["ear_height"] / control_metrics["ear_height"], 1.0, 0.30
        ),
    }
    if stage in REQUIRED_INTENT_STAGES:
        scores["asymmetry_side_consistency"] = _side_score(control, candidate, intent["side"])
        scores["asymmetry_strength_control"] = _strength_score(
            control, candidate, intent["strength"]
        )
    failed = [key for key, score in scores.items() if score < 0.70]
    label = _intent_label(intent) if intent else "No intent label required for this control stage."
    explanations = [
        "Preserve stable head relationships while isolating the named asymmetry "
        "or perspective change."
        for _ in failed
    ] or ["The comparison preserves the provisional stable relationships. " + label]
    raw = {
        f"candidate_to_control_{key}_ratio": candidate_metrics[key] / control_metrics[key]
        for key in ("radius", "lower_face", "eye_span", "jaw_span", "mouth_span", "ear_height")
    }
    return Review(
        id=review_id,
        exercise_id="anime-head-asymmetry",
        exercise_version="1.0.0",
        method_id="anime-head-construction-v1",
        rubric_id=f"anime-head-asymmetry-{stage}",
        rubric_version="1.0.0",
        evidence=[
            Evidence((0, 0, 1, 1), EvidenceSource.ARTIST_CONFIRMATION, 1.0, label),
            *[Evidence((0, 0, 1, 1), EvidenceSource.GEOMETRY, 1.0, key) for key in failed],
        ],
        explanations=explanations,
        measurements=scores | raw,
        targeted_exercise_ids=["anime-head-asymmetry"] if failed else [],
    )


def _relationships(points):
    radius = math.dist(points["cranium_center"], points["cranium_edge"])
    if radius <= 0:
        raise ValueError("cranial center and edge must be distinct")
    return {
        "radius": radius,
        "lower_face": math.dist(points["cranium_center"], points["chin"]) / radius,
        "eye_span": math.dist(points["left_eye_center"], points["right_eye_center"]) / radius,
        "jaw_span": math.dist(points["jaw_left"], points["jaw_right"]) / radius,
        "mouth_span": math.dist(points["mouth_left"], points["mouth_right"]) / radius,
        "ear_height": (
            math.dist(points["left_ear_top"], points["left_ear_bottom"])
            + math.dist(points["right_ear_top"], points["right_ear_bottom"])
        )
        / (2 * radius),
    }


def _side_score(control, candidate, side):
    left = sum(
        math.dist(control[key], candidate[key])
        for key in ("left_eye_center", "jaw_left", "mouth_left", "left_ear_top")
    )
    right = sum(
        math.dist(control[key], candidate[key])
        for key in ("right_eye_center", "jaw_right", "mouth_right", "right_ear_top")
    )
    if side == "bilateral":
        return _similarity(right / max(left, 1e-9), 1.0, 0.60)
    if side == "character_left":
        return _upper(right / max(left, 1e-9), 0.75)
    return _upper(left / max(right, 1e-9), 0.75)


def _strength_score(control, candidate, strength):
    mean_delta = sum(math.dist(control[key], candidate[key]) for key in REQUIRED_KEYS) / len(
        REQUIRED_KEYS
    )
    target = {"subtle": 0.015, "medium": 0.04, "exaggerated": 0.08}[strength]
    return _similarity(mean_delta, target, target + 0.02)


def _validate_points(points):
    if not isinstance(points, dict) or set(points) != REQUIRED_KEYS:
        raise ValueError("controlled-asymmetry landmarks do not match the comparison contract")
    for point in points.values():
        if (
            not isinstance(point, (list, tuple))
            or len(point) != 2
            or any(
                not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0 <= value <= 1
                for value in point
            )
        ):
            raise ValueError("controlled-asymmetry landmarks must be normalized")


def _validate_intent(stage, intent):
    if stage not in REQUIRED_INTENT_STAGES:
        if intent is not None and not isinstance(intent, dict):
            raise ValueError("optional intent must be an object")
        return
    if not isinstance(intent, dict) or set(intent) != {"cause", "side", "strength", "purpose"}:
        raise ValueError("intent cause, side, strength, and purpose are required")
    if intent["cause"] not in {"anatomical_design", "expression"}:
        raise ValueError("intent cause is invalid")
    if intent["side"] not in {"character_left", "character_right", "bilateral"}:
        raise ValueError("intent side is invalid")
    if intent["strength"] not in {"subtle", "medium", "exaggerated"}:
        raise ValueError("intent strength is invalid")
    if not isinstance(intent["purpose"], str) or not intent["purpose"].strip():
        raise ValueError("intent purpose is required")


def _intent_label(intent):
    if not intent:
        return "No optional intent label supplied."
    return (
        f"Artist intent: {intent['cause']}; {intent['side']}; {intent['strength']}; "
        f"purpose: {intent['purpose'].strip()}"
    )


def _similarity(value, target, tolerance):
    return max(0.0, min(1.0, 1.0 - abs(value - target) / tolerance))


def _upper(value, limit):
    return 1.0 if value <= limit else max(0.0, 1.0 - (value - limit) / limit)
