"""Deterministic, artist-confirmed review for turned anime head constructions."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from .model import Evidence, EvidenceSource, Review

Point = tuple[float, float]
EXERCISE_ID = "anime-head-orientation"
EXERCISE_VERSION = "1.0.0"
METHOD_ID = "anime-head-construction-v1"
RUBRIC_ID = "anime-head-orientation-structure"
RUBRIC_VERSION = "1.0.0"


class OrientationView(StrEnum):
    LEFT_THREE_QUARTER = "left_three_quarter"
    RIGHT_THREE_QUARTER = "right_three_quarter"
    LEFT_PROFILE = "left_profile"
    RIGHT_PROFILE = "right_profile"


@dataclass(frozen=True, slots=True)
class ThreeQuarterLandmarks:
    cranium_center: Point
    cranium_radius: float
    centerline_top: Point
    chin: Point
    eye_line_left: Point
    eye_line_right: Point
    left_contour: Point
    right_contour: Point
    jaw_left: Point
    jaw_right: Point

    def validate(self) -> None:
        _validate_points(self, exclude={"cranium_radius"})
        _validate_radius(self.cranium_radius)
        if self.eye_line_left == self.eye_line_right:
            raise ValueError("eye-line endpoints must be distinct")


@dataclass(frozen=True, slots=True)
class ProfileLandmarks:
    cranium_center: Point
    cranium_radius: float
    front_cranium_edge: Point
    back_cranium_edge: Point
    brow_front: Point
    muzzle_front: Point
    eye_line_back: Point
    eye_line_front: Point
    jaw_hinge: Point
    chin: Point

    def validate(self) -> None:
        _validate_points(self, exclude={"cranium_radius"})
        _validate_radius(self.cranium_radius)
        if self.front_cranium_edge == self.back_cranium_edge:
            raise ValueError("front and back cranial edges must be distinct")


def review_three_quarter_head(
    landmarks: ThreeQuarterLandmarks, view: OrientationView, review_id: str
) -> Review:
    """Measure one selected three-quarter construction without pixel inference."""
    if view not in {
        OrientationView.LEFT_THREE_QUARTER,
        OrientationView.RIGHT_THREE_QUARTER,
    }:
        raise ValueError("three-quarter review requires a three-quarter view")
    landmarks.validate()
    _validate_review_id(review_id)
    cx = landmarks.cranium_center[0]
    axis_x = (landmarks.centerline_top[0] + landmarks.chin[0]) / 2
    expected_sign = -1 if view is OrientationView.LEFT_THREE_QUARTER else 1
    signed_axis = expected_sign * (axis_x - cx) / landmarks.cranium_radius
    centerline_placement = _target_score(signed_axis, target=0.30, tolerance=0.30)

    left_width = abs(axis_x - landmarks.left_contour[0])
    right_width = abs(landmarks.right_contour[0] - axis_x)
    far_width = right_width if expected_sign < 0 else left_width
    near_width = left_width if expected_sign < 0 else right_width
    compression_ratio = far_width / max(near_width, 1e-9)
    far_side_compression = _upper_bound_score(compression_ratio, 0.72)

    chin_offset = abs(landmarks.chin[0] - landmarks.centerline_top[0]) / landmarks.cranium_radius
    chin_alignment = _upper_bound_score(chin_offset, 0.20)
    eye_deviation = _horizontal_deviation(landmarks.eye_line_left, landmarks.eye_line_right)
    cross_contour_consistency = _upper_bound_score(eye_deviation, 8.0)

    near_jaw = landmarks.jaw_left if expected_sign < 0 else landmarks.jaw_right
    far_jaw = landmarks.jaw_right if expected_sign < 0 else landmarks.jaw_left
    jaw_span = abs(near_jaw[0] - far_jaw[0]) / landmarks.cranium_radius
    jaw_attachment = _target_score(jaw_span, target=0.85, tolerance=0.55)
    cranial_volume = _target_score(
        abs(landmarks.right_contour[0] - landmarks.left_contour[0])
        / (2 * landmarks.cranium_radius),
        target=1.0,
        tolerance=0.25,
    )
    scores = {
        "centerline_placement": centerline_placement,
        "far_side_compression": far_side_compression,
        "chin_alignment": chin_alignment,
        "cross_contour_consistency": cross_contour_consistency,
        "jaw_attachment": jaw_attachment,
        "cranial_volume": cranial_volume,
    }
    raw = {
        "centerline_signed_offset_radii": signed_axis,
        "far_to_near_width_ratio": compression_ratio,
        "chin_axis_offset_radii": chin_offset,
        "eye_line_deviation_degrees": eye_deviation,
        "jaw_span_radii": jaw_span,
    }
    return _review(review_id, view, scores, raw)


def review_profile_head(
    landmarks: ProfileLandmarks, view: OrientationView, review_id: str
) -> Review:
    """Measure one selected profile construction without inventing a far side."""
    if view not in {OrientationView.LEFT_PROFILE, OrientationView.RIGHT_PROFILE}:
        raise ValueError("profile review requires a profile view")
    landmarks.validate()
    _validate_review_id(review_id)
    direction = -1 if view is OrientationView.LEFT_PROFILE else 1
    cx = landmarks.cranium_center[0]
    front_offset = direction * (landmarks.front_cranium_edge[0] - cx) / landmarks.cranium_radius
    centerline_placement = _target_score(front_offset, target=0.90, tolerance=0.35)
    cranial_span = abs(landmarks.front_cranium_edge[0] - landmarks.back_cranium_edge[0])
    cranial_ratio = cranial_span / (2 * landmarks.cranium_radius)
    cranial_volume = _target_score(cranial_ratio, target=1.0, tolerance=0.25)
    eye_deviation = _horizontal_deviation(landmarks.eye_line_back, landmarks.eye_line_front)
    cross_contour_consistency = _upper_bound_score(eye_deviation, 8.0)
    chin_offset = (
        _point_line_distance(landmarks.chin, landmarks.brow_front, landmarks.muzzle_front)
        / landmarks.cranium_radius
    )
    chin_alignment = _upper_bound_score(chin_offset, 0.25)
    jaw_gap = math.dist(landmarks.jaw_hinge, landmarks.back_cranium_edge) / landmarks.cranium_radius
    jaw_attachment = _upper_bound_score(jaw_gap, 0.75)
    face_depth = abs(landmarks.muzzle_front[0] - landmarks.brow_front[0]) / landmarks.cranium_radius
    far_side_compression = _target_score(face_depth, target=0.20, tolerance=0.25)
    scores = {
        "centerline_placement": centerline_placement,
        "far_side_compression": far_side_compression,
        "chin_alignment": chin_alignment,
        "cross_contour_consistency": cross_contour_consistency,
        "jaw_attachment": jaw_attachment,
        "cranial_volume": cranial_volume,
    }
    raw = {
        "front_edge_offset_radii": front_offset,
        "cranial_width_to_diameter_ratio": cranial_ratio,
        "eye_line_deviation_degrees": eye_deviation,
        "chin_profile_axis_offset_radii": chin_offset,
        "jaw_hinge_gap_radii": jaw_gap,
        "brow_muzzle_depth_radii": face_depth,
    }
    return _review(review_id, view, scores, raw)


def _review(review_id, view, scores, raw):
    explanations = []
    evidence = []
    principles = {
        "centerline_placement": (
            "Place the facial axis to describe the selected turn before adding features."
        ),
        "far_side_compression": (
            "Use view-specific depth evidence; compress the far side only when it is visible."
        ),
        "chin_alignment": (
            "Carry the facial axis through the lower face so the chin belongs to the same "
            "orientation."
        ),
        "cross_contour_consistency": (
            "Make the eye-line and facial axis wrap around one coherent cranial volume."
        ),
        "jaw_attachment": (
            "Attach the jaw beneath the cranial mass instead of pasting a flat mask onto it."
        ),
        "cranial_volume": (
            "Preserve the back and upper cranial mass while turning or attaching the face."
        ),
    }
    for dimension, score in scores.items():
        if score < 0.70:
            explanation = principles[dimension]
            explanations.append(explanation)
            evidence.append(
                Evidence(
                    (0.0, 0.0, 1.0, 1.0),
                    EvidenceSource.GEOMETRY,
                    1.0,
                    f"{dimension.replace('_', ' ')} scored {score:.2f} from confirmed landmarks.",
                )
            )
    if not explanations:
        explanations.append(
            "The confirmed landmarks meet the provisional orientation tolerances. Repeat the "
            "selected view without tracing to test consistency."
        )
    return Review(
        id=review_id,
        exercise_id=EXERCISE_ID,
        exercise_version=EXERCISE_VERSION,
        method_id=METHOD_ID,
        rubric_id=RUBRIC_ID,
        rubric_version=RUBRIC_VERSION,
        evidence=evidence,
        explanations=explanations,
        measurements=scores | raw,
        targeted_exercise_ids=["anime-head-perspective-practice"] if evidence else [],
    )


def _validate_points(value, *, exclude):
    for name in value.__dataclass_fields__:
        if name in exclude:
            continue
        point = getattr(value, name)
        if len(point) != 2 or any(not math.isfinite(item) or not 0 <= item <= 1 for item in point):
            raise ValueError("orientation landmarks must use finite normalized coordinates")


def _validate_radius(radius):
    if not math.isfinite(radius) or not 0 < radius <= 1:
        raise ValueError("cranium radius must be between zero and one")


def _validate_review_id(review_id):
    if not review_id.strip():
        raise ValueError("review id must not be empty")


def _target_score(value, *, target, tolerance):
    return max(0.0, min(1.0, 1.0 - abs(value - target) / tolerance))


def _upper_bound_score(value, limit):
    if value <= limit:
        return 1.0
    return max(0.0, 1.0 - (value - limit) / max(limit, 1e-9))


def _horizontal_deviation(start, end):
    return math.degrees(math.atan2(abs(end[1] - start[1]), abs(end[0] - start[0])))


def _point_line_distance(point, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length <= 1e-12:
        raise ValueError("profile facial axis needs two distinct landmarks")
    return abs(dy * point[0] - dx * point[1] + end[0] * start[1] - end[1] * start[0]) / length
