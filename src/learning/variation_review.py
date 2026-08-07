"""Identity-card-aware comparison for character variation and reconstruction."""

from __future__ import annotations

import math

from .asymmetry_review import REQUIRED_KEYS
from .model import Evidence, EvidenceSource, Review

VARIANT_STAGES = {"proportion_variant", "feature_variant", "age_style_variant"}
SELECTED_STAGES = {"selected_front", "selected_turned"}


def review_identity_comparison(baseline, candidate, stage, identity_card, review_id):
    _validate_points(baseline)
    _validate_points(candidate)
    if stage not in VARIANT_STAGES | SELECTED_STAGES:
        raise ValueError("identity-comparison stage is invalid")
    if not review_id.strip():
        raise ValueError("review id must not be empty")
    _validate_card(identity_card)
    base = _relationships(baseline)
    current = _relationships(candidate)
    ratios = {key: current[key] / max(base[key], 1e-9) for key in base}
    if stage in VARIANT_STAGES:
        scores = {
            f"identity_{key}_variation_magnitude": min(1.0, abs(ratio - 1.0))
            for key, ratio in ratios.items()
        }
        failed = []
        explanation = (
            "Variation deltas are descriptive rather than failures; confirm that they match "
            "the declared design axis."
        )
    else:
        projection = 0.78 if stage == "selected_turned" else 1.0
        scores = {
            "identity_cranial_retention": _similarity(ratios["cranial_radius"], 1.0, 0.20),
            "identity_lower_face_retention": _similarity(ratios["lower_face"], 1.0, 0.25),
            "identity_eye_span_retention": _similarity(ratios["eye_span"], projection, 0.35),
            "identity_jaw_span_retention": _similarity(ratios["jaw_span"], projection, 0.35),
            "identity_mouth_span_retention": _similarity(ratios["mouth_span"], projection, 0.35),
            "identity_ear_height_retention": _similarity(ratios["ear_height"], 1.0, 0.30),
        }
        failed = [key for key, value in scores.items() if value < 0.70]
        explanation = (
            "Preserve the selected identity-anchor system while allowing projection and mild "
            "expression to change the image."
        )
    adherence = [
        _similarity(current[anchor["key"]], anchor["value"], 0.25)
        for anchor in identity_card["anchors"]
        if anchor["key"] in current
    ]
    if adherence:
        scores["identity_card_adherence"] = sum(adherence) / len(adherence)
        if stage in SELECTED_STAGES and scores["identity_card_adherence"] < 0.70:
            failed.append("identity_card_adherence")
    raw = {f"candidate_to_baseline_{key}_ratio": ratio for key, ratio in ratios.items()}
    return Review(
        id=review_id,
        exercise_id="anime-head-variation",
        exercise_version="1.0.0",
        method_id="anime-head-construction-v1",
        rubric_id=f"anime-head-variation-{stage}",
        rubric_version="1.0.0",
        evidence=[
            Evidence(
                (0, 0, 1, 1),
                EvidenceSource.ARTIST_CONFIRMATION,
                1.0,
                f"Identity card {identity_card['name']} revision {identity_card['revision']}.",
            ),
            *[Evidence((0, 0, 1, 1), EvidenceSource.GEOMETRY, 1.0, key) for key in failed],
        ],
        explanations=[explanation],
        measurements=scores | raw,
        targeted_exercise_ids=["anime-head-variation"] if failed else [],
    )


def _relationships(points):
    radius = math.dist(points["cranium_center"], points["cranium_edge"])
    if radius <= 0:
        raise ValueError("cranial center and edge must be distinct")
    return {
        "cranial_radius": radius,
        "lower_face": min(1.0, math.dist(points["cranium_center"], points["chin"]) / radius / 3),
        "eye_span": min(
            1.0, math.dist(points["left_eye_center"], points["right_eye_center"]) / radius / 3
        ),
        "jaw_span": min(1.0, math.dist(points["jaw_left"], points["jaw_right"]) / radius / 3),
        "mouth_span": min(1.0, math.dist(points["mouth_left"], points["mouth_right"]) / radius / 2),
        "ear_height": (
            math.dist(points["left_ear_top"], points["left_ear_bottom"])
            + math.dist(points["right_ear_top"], points["right_ear_bottom"])
        )
        / (4 * radius),
    }


def _validate_points(points):
    if not isinstance(points, dict) or set(points) != REQUIRED_KEYS:
        raise ValueError("identity landmarks do not match the comparison contract")
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
            raise ValueError("identity landmarks must be normalized")


def _validate_card(card):
    if not isinstance(card, dict) or not isinstance(card.get("name"), str):
        raise ValueError("portable identity card is required")
    anchors = card.get("anchors")
    if not isinstance(anchors, list) or not 5 <= len(anchors) <= 8:
        raise ValueError("identity card requires five to eight anchors")
    for anchor in anchors:
        if (
            not isinstance(anchor, dict)
            or set(anchor) != {"key", "value", "description"}
            or not isinstance(anchor["value"], (int, float))
            or not 0 <= anchor["value"] <= 1
            or not str(anchor["key"]).strip()
            or not str(anchor["description"]).strip()
        ):
            raise ValueError("identity-card anchor is invalid")


def _similarity(value, target, tolerance):
    return max(0.0, min(1.0, 1.0 - abs(value - target) / tolerance))
