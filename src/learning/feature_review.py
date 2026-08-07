"""Deterministic reviews for artist-confirmed nose, mouth, and ear landmarks."""

from __future__ import annotations

import math

from .model import Evidence, EvidenceSource, Review


def review_feature_study(landmarks, feature, view, review_id):
    _validate_identity(feature, view, review_id)
    _validate_points(landmarks)
    if feature == "nose":
        scores, raw = _review_nose(landmarks, view)
    elif feature == "mouth":
        scores, raw = _review_mouth(landmarks, view)
    elif view == "front":
        scores, raw = _review_front_ears(landmarks)
    else:
        scores, raw = _review_turned_ear(landmarks)
    return _review(review_id, feature, scores, raw)


def review_feature_set(front, turned, review_id):
    if not review_id.strip():
        raise ValueError("review id must not be empty")
    if set(front) != {"nose", "mouth", "ear"} or set(turned) != {"nose", "mouth", "ear"}:
        raise ValueError(
            "combined feature review requires all three feature families in both views"
        )
    for landmarks in (*front.values(), *turned.values()):
        _validate_points(landmarks)
    front_nose = _span(front["nose"], "base_left", "base_right")
    turned_nose = _span(turned["nose"], "base_left", "base_right")
    front_mouth = _span(front["mouth"], "corner_left", "corner_right")
    turned_mouth = _span(turned["mouth"], "corner_left", "corner_right")
    front_opening = _span(front["mouth"], "upper_peak", "lower_peak") / max(front_mouth, 1e-9)
    turned_opening = _span(turned["mouth"], "upper_peak", "lower_peak") / max(turned_mouth, 1e-9)
    front_ear_height = (
        _span(front["ear"], "left_top", "left_bottom")
        + _span(front["ear"], "right_top", "right_bottom")
    ) / 2
    turned_ear_height = _span(turned["ear"], "near_top", "near_bottom")
    scores = {
        "nose_design_retention": _similarity(turned_nose / max(front_nose, 1e-9), 0.78, 0.35),
        "mouth_design_retention": _similarity(turned_mouth / max(front_mouth, 1e-9), 0.78, 0.35),
        "ear_design_retention": _similarity(
            turned_ear_height / max(front_ear_height, 1e-9), 1.0, 0.30
        ),
        "feature_expression_consistency": _similarity(
            turned_opening / max(front_opening, 1e-9), 1.0, 0.30
        ),
    }
    raw = {
        "turned_to_front_nose_width_ratio": turned_nose / max(front_nose, 1e-9),
        "turned_to_front_mouth_width_ratio": turned_mouth / max(front_mouth, 1e-9),
        "turned_to_front_ear_height_ratio": turned_ear_height / max(front_ear_height, 1e-9),
        "turned_to_front_mouth_opening_ratio": turned_opening / max(front_opening, 1e-9),
    }
    return _review(review_id, "combined", scores, raw, rubric="anime-head-features-paired")


def _review_nose(points, view):
    required = {
        "axis_top",
        "chin",
        "bridge_top",
        "tip",
        "base_left",
        "base_right",
        "nostril_left",
        "nostril_right",
        "muzzle_left",
        "muzzle_right",
    }
    _require(points, required)
    axis_x = _axis_x(points, points["tip"][1])
    span = _span(points, "base_left", "base_right")
    left = abs(axis_x - points["base_left"][0])
    right = abs(points["base_right"][0] - axis_x)
    target = 1.0 if view == "front" else 0.68
    scores = {
        "nose_axis_alignment": _upper(abs(points["tip"][0] - axis_x) / max(span, 1e-9), 0.15),
        "nose_base_level": _upper(
            abs(points["base_left"][1] - points["base_right"][1]) / max(span, 1e-9), 0.12
        ),
        "nose_perspective_compression": _similarity(right / max(left, 1e-9), target, 0.35),
        "muzzle_support": _similarity(
            _span(points, "muzzle_left", "muzzle_right") / max(span, 1e-9), 1.8, 0.8
        ),
    }
    return scores, {
        "nose_base_span": span,
        "nose_right_to_left_half_ratio": right / max(left, 1e-9),
    }


def _review_mouth(points, view):
    required = {
        "axis_top",
        "chin",
        "nose_base",
        "mouth_center",
        "corner_left",
        "corner_right",
        "upper_peak",
        "lower_peak",
        "muzzle_left",
        "muzzle_right",
    }
    _require(points, required)
    axis_x = _axis_x(points, points["mouth_center"][1])
    width = _span(points, "corner_left", "corner_right")
    left = abs(axis_x - points["corner_left"][0])
    right = abs(points["corner_right"][0] - axis_x)
    target = 1.0 if view == "front" else 0.72
    scores = {
        "mouth_axis_alignment": _upper(
            abs(points["mouth_center"][0] - axis_x) / max(width, 1e-9), 0.12
        ),
        "mouth_corner_coherence": _upper(
            abs(points["corner_left"][1] - points["corner_right"][1]) / max(width, 1e-9), 0.18
        ),
        "mouth_perspective_wrap": _similarity(right / max(left, 1e-9), target, 0.35),
        "mouth_within_muzzle": _upper(
            width / max(_span(points, "muzzle_left", "muzzle_right"), 1e-9), 0.85
        ),
    }
    return scores, {"mouth_width": width, "mouth_right_to_left_half_ratio": right / max(left, 1e-9)}


def _review_front_ears(points):
    required = {"eye_line_left", "eye_line_right"} | {
        f"{side}_{part}"
        for side in ("left", "right")
        for part in ("top", "bottom", "outer", "inner", "attach_top", "attach_bottom")
    }
    _require(points, required)
    left_height = _span(points, "left_top", "left_bottom")
    right_height = _span(points, "right_top", "right_bottom")
    left_depth = _span(points, "left_outer", "left_inner")
    right_depth = _span(points, "right_outer", "right_inner")
    scores = {
        "ear_height_balance": _similarity(right_height / max(left_height, 1e-9), 1.0, 0.25),
        "ear_attachment_balance": _similarity(
            _span(points, "right_attach_top", "right_attach_bottom")
            / max(_span(points, "left_attach_top", "left_attach_bottom"), 1e-9),
            1.0,
            0.25,
        ),
        "ear_bowl_balance": _similarity(right_depth / max(left_depth, 1e-9), 1.0, 0.30),
        "ear_level_balance": _upper(
            (
                abs(points["left_top"][1] - points["right_top"][1])
                + abs(points["left_bottom"][1] - points["right_bottom"][1])
            )
            / max(left_height + right_height, 1e-9),
            0.12,
        ),
    }
    return scores, {"left_ear_height": left_height, "right_ear_height": right_height}


def _review_turned_ear(points):
    required = {
        "side_plane_top",
        "side_plane_bottom",
        "near_top",
        "near_bottom",
        "near_outer",
        "near_inner",
        "near_attach_top",
        "near_attach_bottom",
        "skull_edge",
        "far_evidence",
    }
    _require(points, required)
    height = _span(points, "near_top", "near_bottom")
    attachment = _span(points, "near_attach_top", "near_attach_bottom")
    depth = _span(points, "near_outer", "near_inner")
    scores = {
        "near_ear_attachment": _similarity(attachment / max(height, 1e-9), 0.75, 0.35),
        "near_ear_bowl": _similarity(depth / max(height, 1e-9), 0.45, 0.30),
        "ear_side_plane_alignment": _upper(
            abs(points["near_attach_top"][0] - points["side_plane_top"][0]) / max(height, 1e-9),
            0.35,
        ),
        "far_ear_occlusion_evidence": _upper(
            abs(points["far_evidence"][0] - points["skull_edge"][0]) / max(height, 1e-9), 0.45
        ),
    }
    return scores, {"near_ear_height": height, "near_ear_attachment_span": attachment}


def _review(review_id, feature, scores, raw, rubric=None):
    failed = [key for key, score in scores.items() if score < 0.70]
    explanations = [_principle(key) for key in failed] or [
        "The confirmed landmarks meet the provisional feature-construction checks."
    ]
    return Review(
        id=review_id,
        exercise_id="anime-head-features",
        exercise_version="1.0.0",
        method_id="anime-head-construction-v1",
        rubric_id=rubric or f"anime-head-features-{feature}",
        rubric_version="1.0.0",
        evidence=[Evidence((0, 0, 1, 1), EvidenceSource.GEOMETRY, 1.0, key) for key in failed],
        explanations=explanations,
        measurements=scores | raw,
        targeted_exercise_ids=["anime-head-features"] if failed else [],
    )


def _principle(key):
    return {
        "feature_expression_consistency": (
            "Preserve the chosen mouth opening and expression through the turn."
        ),
        "ear_height_balance": "Compare both front ears independently before accepting asymmetry.",
        "far_ear_occlusion_evidence": (
            "Treat the far ear as optional occlusion evidence, not required symmetry."
        ),
    }.get(key, "Correct the confirmed feature relationship before simplifying its anime symbol.")


def _validate_identity(feature, view, review_id):
    if feature not in {"nose", "mouth", "ear"} or view not in {"front", "right_three_quarter"}:
        raise ValueError("feature review identity is invalid")
    if not review_id.strip():
        raise ValueError("review id must not be empty")


def _validate_points(points):
    if not isinstance(points, dict) or not points:
        raise ValueError("feature landmarks must be a non-empty object")
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
            raise ValueError("feature landmarks must use finite normalized points")


def _require(points, keys):
    if set(points) != keys:
        raise ValueError("feature landmark fields do not match the selected workflow")


def _span(points, first, second):
    return math.dist(points[first], points[second])


def _axis_x(points, y):
    top, bottom = points["axis_top"], points["chin"]
    if top[1] == bottom[1]:
        raise ValueError("facial axis needs vertical extent")
    return top[0] + (bottom[0] - top[0]) * (y - top[1]) / (bottom[1] - top[1])


def _similarity(value, target, tolerance):
    return max(0.0, min(1.0, 1.0 - abs(value - target) / tolerance))


def _upper(value, limit):
    return 1.0 if value <= limit else max(0.0, 1.0 - (value - limit) / limit)
