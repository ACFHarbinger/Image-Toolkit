"""Deterministic review of artist-confirmed front-view head landmarks."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .model import Evidence, EvidenceSource, Redline, Review, Suggestion

Point = tuple[float, float]

METHOD_ID = "anime-head-construction-v1"
EXERCISE_ID = "anime-head-front-construction"
EXERCISE_VERSION = "1.0.0"
RUBRIC_ID = "anime-head-front-structure"
RUBRIC_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class FrontHeadLandmarks:
    """Artist-placed normalized landmarks; no pixel analysis is implied."""

    cranium_center: Point
    cranium_radius: float
    centerline_top: Point
    centerline_bottom: Point
    eye_line_left: Point
    eye_line_right: Point
    jaw_left: Point
    jaw_right: Point
    chin: Point

    def validate(self) -> None:
        for point in (
            self.cranium_center,
            self.centerline_top,
            self.centerline_bottom,
            self.eye_line_left,
            self.eye_line_right,
            self.jaw_left,
            self.jaw_right,
            self.chin,
        ):
            if len(point) != 2 or any(
                not math.isfinite(value) or not 0 <= value <= 1 for value in point
            ):
                raise ValueError("head landmarks must use finite normalized coordinates")
        if not math.isfinite(self.cranium_radius) or not 0 < self.cranium_radius <= 1:
            raise ValueError("cranium radius must be between zero and one")
        if self.centerline_top == self.centerline_bottom:
            raise ValueError("centerline needs two distinct landmarks")
        if self.eye_line_left == self.eye_line_right:
            raise ValueError("eye-line needs two distinct landmarks")


@dataclass(frozen=True, slots=True)
class FrontHeadReviewThresholds:
    """Provisional teaching tolerances to calibrate with beginner studies."""

    centerline_degrees: float = 5.0
    eye_line_degrees: float = 5.0
    chin_offset_radii: float = 0.08
    jaw_asymmetry_radii: float = 0.12


def review_front_head(
    landmarks: FrontHeadLandmarks,
    review_id: str,
    thresholds: FrontHeadReviewThresholds | None = None,
) -> Review:
    """Return auditable measurements and feedback without inspecting artwork."""
    landmarks.validate()
    if not review_id.strip():
        raise ValueError("review id must not be empty")
    thresholds = thresholds or FrontHeadReviewThresholds()
    _validate_thresholds(thresholds)

    cx, _ = landmarks.cranium_center
    centerline_degrees = _vertical_deviation(landmarks.centerline_top, landmarks.centerline_bottom)
    eye_line_degrees = _horizontal_deviation(landmarks.eye_line_left, landmarks.eye_line_right)
    chin_offset = abs(landmarks.chin[0] - cx) / landmarks.cranium_radius
    left_width = cx - landmarks.jaw_left[0]
    right_width = landmarks.jaw_right[0] - cx
    jaw_asymmetry = abs(left_width - right_width) / landmarks.cranium_radius

    measurements = {
        "centerline_deviation_degrees": centerline_degrees,
        "eye_line_deviation_degrees": eye_line_degrees,
        "chin_offset_cranium_radii": chin_offset,
        "jaw_asymmetry_cranium_radii": jaw_asymmetry,
        "head_axis_consistency": _score(centerline_degrees, thresholds.centerline_degrees),
        "eye_line_consistency": _score(eye_line_degrees, thresholds.eye_line_degrees),
        "chin_centering": _score(chin_offset, thresholds.chin_offset_radii),
        "jaw_symmetry": _score(jaw_asymmetry, thresholds.jaw_asymmetry_radii),
    }
    evidence: list[Evidence] = []
    explanations: list[str] = []
    redlines: list[Redline] = []

    _add_axis_feedback(
        evidence,
        explanations,
        redlines,
        measurement=centerline_degrees,
        limit=thresholds.centerline_degrees,
        region=_bounds(landmarks.centerline_top, landmarks.centerline_bottom),
        observation=f"Centerline deviates {centerline_degrees:.1f}° from vertical.",
        explanation=(
            "For this front-view exercise, align the centerline vertically through the cranial "
            "center and chin. A deliberate tilt belongs in a later tilted-head exercise."
        ),
        geometry=[
            (cx, landmarks.centerline_top[1]),
            (cx, landmarks.centerline_bottom[1]),
        ],
    )
    eye_y = (landmarks.eye_line_left[1] + landmarks.eye_line_right[1]) / 2
    _add_axis_feedback(
        evidence,
        explanations,
        redlines,
        measurement=eye_line_degrees,
        limit=thresholds.eye_line_degrees,
        region=_bounds(landmarks.eye_line_left, landmarks.eye_line_right),
        observation=f"Eye-line deviates {eye_line_degrees:.1f}° from horizontal.",
        explanation=(
            "Keep the eye-line level and perpendicular to the centerline in a straight-on view; "
            "use it as a placement guide rather than drawing finished eyes yet."
        ),
        geometry=[
            (landmarks.eye_line_left[0], eye_y),
            (landmarks.eye_line_right[0], eye_y),
        ],
    )
    if chin_offset > thresholds.chin_offset_radii:
        explanation = (
            "Move the chin back under the cranial centerline before adding features; otherwise "
            "the face reads as skewed even when individual features are symmetric."
        )
        evidence.append(
            Evidence(
                _point_region(landmarks.chin),
                EvidenceSource.GEOMETRY,
                1.0,
                f"Chin is offset by {chin_offset:.2f} cranial radii.",
            )
        )
        explanations.append(explanation)
        redlines.append(
            Redline("Tutor — centered chin", [landmarks.chin, (cx, landmarks.chin[1])], explanation)
        )
    if jaw_asymmetry > thresholds.jaw_asymmetry_radii:
        explanation = (
            "Compare the large left and right jaw widths before refining the contour. Match the "
            "structural taper first; intentional asymmetry can be introduced afterward."
        )
        evidence.append(
            Evidence(
                _bounds(landmarks.jaw_left, landmarks.jaw_right),
                EvidenceSource.GEOMETRY,
                1.0,
                f"Jaw widths differ by {jaw_asymmetry:.2f} cranial radii.",
            )
        )
        explanations.append(explanation)
        mirror_x = 2 * cx - landmarks.jaw_left[0]
        redlines.append(
            Redline(
                "Tutor — mirrored jaw guide",
                [landmarks.jaw_left, (mirror_x, landmarks.jaw_right[1])],
                explanation,
            )
        )

    needs_practice = bool(redlines)
    suggestions = []
    if redlines:
        suggestions.append(
            Suggestion(
                "front-head-guides", "Preview corrected construction guides", "Tutor — Preview"
            )
        )
    if not explanations:
        explanations.append(
            "The manually placed landmarks meet this exercise's provisional structural tolerances. "
            "Repeat once without tracing to check whether the construction is becoming reliable."
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
        redlines=redlines,
        suggestions=suggestions,
        measurements=measurements,
        targeted_exercise_ids=["anime-head-front-axis-practice"] if needs_practice else [],
    )


def _validate_thresholds(thresholds: FrontHeadReviewThresholds) -> None:
    if any(
        value <= 0 or not math.isfinite(value)
        for value in (
            thresholds.centerline_degrees,
            thresholds.eye_line_degrees,
            thresholds.chin_offset_radii,
            thresholds.jaw_asymmetry_radii,
        )
    ):
        raise ValueError("review thresholds must be finite and positive")


def _vertical_deviation(start: Point, end: Point) -> float:
    dx = abs(end[0] - start[0])
    dy = abs(end[1] - start[1])
    return math.degrees(math.atan2(dx, dy))


def _horizontal_deviation(start: Point, end: Point) -> float:
    dx = abs(end[0] - start[0])
    dy = abs(end[1] - start[1])
    return math.degrees(math.atan2(dy, dx))


def _score(measurement: float, limit: float) -> float:
    if math.isclose(measurement, 0.0, abs_tol=1e-12):
        return 1.0
    return max(0.0, min(1.0, 1.0 - measurement / (limit * 2)))


def _bounds(
    first: Point, second: Point, padding: float = 0.02
) -> tuple[float, float, float, float]:
    return (
        max(0.0, min(first[0], second[0]) - padding),
        max(0.0, min(first[1], second[1]) - padding),
        min(1.0, max(first[0], second[0]) + padding),
        min(1.0, max(first[1], second[1]) + padding),
    )


def _point_region(point: Point, padding: float = 0.03) -> tuple[float, float, float, float]:
    return (
        max(0.0, point[0] - padding),
        max(0.0, point[1] - padding),
        min(1.0, point[0] + padding),
        min(1.0, point[1] + padding),
    )


def _add_axis_feedback(
    evidence: list[Evidence],
    explanations: list[str],
    redlines: list[Redline],
    *,
    measurement: float,
    limit: float,
    region: tuple[float, float, float, float],
    observation: str,
    explanation: str,
    geometry: list[Point],
) -> None:
    if measurement <= limit:
        return
    evidence.append(Evidence(region, EvidenceSource.GEOMETRY, 1.0, observation))
    explanations.append(explanation)
    redlines.append(Redline("Tutor — construction axis", geometry, explanation))
