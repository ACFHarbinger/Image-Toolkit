"""Paired consistency review for a front jaw design and its turned reconstruction."""

from __future__ import annotations

import math

from .head_review import FrontHeadLandmarks
from .model import Evidence, EvidenceSource, Review
from .orientation_review import ThreeQuarterLandmarks


def review_cranial_jaw_pair(
    front: FrontHeadLandmarks,
    turned: ThreeQuarterLandmarks,
    review_id: str,
    variant_id: str,
) -> Review:
    front.validate()
    turned.validate()
    if not review_id.strip() or not variant_id.strip():
        raise ValueError("pair review and variant identifiers must not be empty")
    radius_ratio = turned.cranium_radius / front.cranium_radius
    cranial_volume_retention = _similarity(radius_ratio, 1.0, 0.25)
    front_eye_y = (front.eye_line_left[1] + front.eye_line_right[1]) / 2
    turned_eye_y = (turned.eye_line_left[1] + turned.eye_line_right[1]) / 2
    front_length = abs(front.chin[1] - front_eye_y) / front.cranium_radius
    turned_length = abs(turned.chin[1] - turned_eye_y) / turned.cranium_radius
    lower_face_length_retention = _similarity(turned_length / max(front_length, 1e-9), 1.0, 0.30)
    front_jaw = abs(front.jaw_right[0] - front.jaw_left[0]) / front.cranium_radius
    turned_jaw = abs(turned.jaw_right[0] - turned.jaw_left[0]) / turned.cranium_radius
    jaw_character_retention = _similarity(turned_jaw / max(front_jaw, 1e-9), 0.78, 0.35)
    chin_alignment = _upper_bound(
        abs(turned.chin[0] - turned.centerline_top[0]) / turned.cranium_radius, 0.20
    )
    axis_x = (turned.centerline_top[0] + turned.chin[0]) / 2
    far_width = abs(axis_x - turned.left_contour[0])
    near_width = abs(turned.right_contour[0] - axis_x)
    perspective_adjustment = _upper_bound(far_width / max(near_width, 1e-9), 0.72)
    scores = {
        "cranial_volume_retention": cranial_volume_retention,
        "lower_face_length_retention": lower_face_length_retention,
        "jaw_character_retention": jaw_character_retention,
        "chin_alignment": chin_alignment,
        "perspective_adjustment": perspective_adjustment,
    }
    principles = {
        "cranial_volume_retention": "Keep the same intended cranial mass when rotating the design.",
        "lower_face_length_retention": "Preserve the chosen lower-face length through the turn.",
        "jaw_character_retention": "Carry the variant's jaw width and taper into perspective.",
        "chin_alignment": "Keep the turned chin on the continued facial axis.",
        "perspective_adjustment": "Compress the far side without redesigning the character.",
    }
    failed = [key for key, value in scores.items() if value < 0.70]
    explanations = [principles[key] for key in failed] or [
        "The selected front and three-quarter constructions retain the provisional design "
        "relationships. Repeat the pair without tracing to test consistency."
    ]
    evidence = [
        Evidence(
            (0.0, 0.0, 1.0, 1.0),
            EvidenceSource.GEOMETRY,
            1.0,
            f"{key.replace('_', ' ')} scored {scores[key]:.2f} across confirmed landmarks.",
        )
        for key in failed
    ]
    return Review(
        id=review_id,
        exercise_id="anime-head-volume-jaw",
        exercise_version="1.0.0",
        method_id="anime-head-construction-v1",
        rubric_id="anime-head-volume-jaw-pair",
        rubric_version="1.0.0",
        evidence=evidence,
        explanations=explanations,
        measurements=scores
        | {
            "cranial_radius_ratio": radius_ratio,
            "lower_face_length_ratio": turned_length / max(front_length, 1e-9),
            "jaw_span_ratio": turned_jaw / max(front_jaw, 1e-9),
        },
        targeted_exercise_ids=["anime-head-volume-jaw"] if failed else [],
    )


def _similarity(value, target, tolerance):
    if not math.isfinite(value):
        raise ValueError("pair measurements must be finite")
    return max(0.0, min(1.0, 1.0 - abs(value - target) / tolerance))


def _upper_bound(value, limit):
    if not math.isfinite(value):
        raise ValueError("pair measurements must be finite")
    return 1.0 if value <= limit else max(0.0, 1.0 - (value - limit) / limit)
