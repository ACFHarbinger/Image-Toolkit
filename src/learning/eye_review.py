"""Deterministic review of artist-confirmed eye construction landmarks."""

from __future__ import annotations

import math
from dataclasses import dataclass, fields

from .model import Evidence, EvidenceSource, Review

Point = tuple[float, float]


@dataclass(frozen=True, slots=True)
class EyePairLandmarks:
    centerline_top: Point
    chin: Point
    eye_line_left: Point
    eye_line_right: Point
    left_inner: Point
    left_outer: Point
    right_inner: Point
    right_outer: Point
    left_upper_peak: Point
    left_lower_peak: Point
    right_upper_peak: Point
    right_lower_peak: Point
    left_iris_top: Point
    left_iris_bottom: Point
    right_iris_top: Point
    right_iris_bottom: Point

    def validate(self) -> None:
        for field in fields(self):
            point = getattr(self, field.name)
            if len(point) != 2 or any(
                not math.isfinite(value) or not 0 <= value <= 1 for value in point
            ):
                raise ValueError("eye landmarks must use finite normalized coordinates")
        if (
            self.centerline_top[1] == self.chin[1]
            or self.eye_line_left[0] == self.eye_line_right[0]
        ):
            raise ValueError("eye construction axes need distinct endpoints")
        if self.left_inner == self.left_outer or self.right_inner == self.right_outer:
            raise ValueError("each eye needs distinct inner and outer corners")


def review_eye_pair(landmarks: EyePairLandmarks, view: str, stage: str, review_id: str) -> Review:
    landmarks.validate()
    if view not in {"front", "right_three_quarter"}:
        raise ValueError("eye review supports front or right three-quarter views")
    if stage not in {"structure", "style_expression"}:
        raise ValueError("eye review stage is invalid")
    if not review_id.strip():
        raise ValueError("review id must not be empty")

    left_width = math.dist(landmarks.left_inner, landmarks.left_outer)
    right_width = math.dist(landmarks.right_inner, landmarks.right_outer)
    mean_width = max((left_width + right_width) / 2, 1e-9)
    eye_line_consistency = _upper_bound(
        (
            abs(landmarks.left_inner[1] - _line_y(landmarks, landmarks.left_inner[0]))
            + abs(landmarks.right_inner[1] - _line_y(landmarks, landmarks.right_inner[0]))
        )
        / (2 * mean_width),
        0.12,
    )
    axis_x = _axis_x_at(landmarks, _mean_y(landmarks.left_inner, landmarks.right_inner))
    left_gap = abs(axis_x - landmarks.left_inner[0])
    right_gap = abs(landmarks.right_inner[0] - axis_x)
    spacing_balance = _similarity(right_gap / max(left_gap, 1e-9), 1.0, 0.28)
    target_ratio = 1.0 if view == "front" else 0.72
    projected_scale = _similarity(right_width / max(left_width, 1e-9), target_ratio, 0.30)
    left_opening = math.dist(landmarks.left_upper_peak, landmarks.left_lower_peak)
    right_opening = math.dist(landmarks.right_upper_peak, landmarks.right_lower_peak)
    eyelid_rhythm = _similarity(
        (right_opening / max(right_width, 1e-9)) / max(left_opening / max(left_width, 1e-9), 1e-9),
        1.0,
        0.30,
    )
    left_iris = math.dist(landmarks.left_iris_top, landmarks.left_iris_bottom)
    right_iris = math.dist(landmarks.right_iris_top, landmarks.right_iris_bottom)
    expression_consistency = _similarity(
        (right_iris / max(right_opening, 1e-9)) / max(left_iris / max(left_opening, 1e-9), 1e-9),
        1.0,
        0.30,
    )
    scores = {
        "eye_line_consistency": eye_line_consistency,
        "eye_spacing_balance": spacing_balance,
        "eye_projected_scale": projected_scale,
        "eyelid_rhythm_consistency": eyelid_rhythm,
        "expression_consistency": expression_consistency,
    }
    principles = {
        "eye_line_consistency": "Keep inner corners attached to the head's eye-line cross-contour.",
        "eye_spacing_balance": "Organize front spacing from the facial axis, not the page edges.",
        "eye_projected_scale": (
            "Preserve paired scale in front view."
            if view == "front"
            else "Compress the image-right far eye through perspective without redesigning it."
        ),
        "eyelid_rhythm_consistency": "Carry the chosen lid opening and rhythm across the pair.",
        "expression_consistency": "Keep iris exposure consistent with the named expression.",
    }
    applicable = list(scores) if stage == "style_expression" else list(scores)[:3]
    failed = [key for key in applicable if scores[key] < 0.70]
    explanations = [principles[key] for key in failed] or [
        "The confirmed eye landmarks satisfy the provisional structure"
        + (" and style/expression" if stage == "style_expression" else "")
        + " checks. Repeat without tracing to test control."
    ]
    return Review(
        id=review_id,
        exercise_id="anime-head-eyes",
        exercise_version="1.0.0",
        method_id="anime-head-construction-v1",
        rubric_id=f"anime-head-eyes-{stage}",
        rubric_version="1.0.0",
        evidence=[
            Evidence(
                (0.0, 0.0, 1.0, 1.0),
                EvidenceSource.GEOMETRY,
                1.0,
                f"{key.replace('_', ' ')} scored {scores[key]:.2f} from confirmed landmarks.",
            )
            for key in failed
        ],
        explanations=explanations,
        measurements={key: scores[key] for key in applicable}
        | {
            "left_eye_width": left_width,
            "right_eye_width": right_width,
            "right_to_left_width_ratio": right_width / max(left_width, 1e-9),
            "left_opening_ratio": left_opening / max(left_width, 1e-9),
            "right_opening_ratio": right_opening / max(right_width, 1e-9),
        },
        targeted_exercise_ids=["anime-head-eyes"] if failed else [],
    )


def _line_y(landmarks, x):
    left, right = landmarks.eye_line_left, landmarks.eye_line_right
    return left[1] + (right[1] - left[1]) * (x - left[0]) / (right[0] - left[0])


def _axis_x_at(landmarks, y):
    top, bottom = landmarks.centerline_top, landmarks.chin
    return top[0] + (bottom[0] - top[0]) * (y - top[1]) / (bottom[1] - top[1])


def _mean_y(left, right):
    return (left[1] + right[1]) / 2


def _similarity(value, target, tolerance):
    if not math.isfinite(value):
        raise ValueError("eye measurements must be finite")
    return max(0.0, min(1.0, 1.0 - abs(value - target) / tolerance))


def _upper_bound(value, limit):
    if not math.isfinite(value):
        raise ValueError("eye measurements must be finite")
    return 1.0 if value <= limit else max(0.0, 1.0 - (value - limit) / limit)
