"""Tests for portable identity-card-aware variation review."""

from learning.variation_review import review_identity_comparison


def _landmarks(scale=1.0):
    return {
        "cranium_center": (0.5, 0.3),
        "cranium_edge": (0.5 + 0.25 * scale, 0.3),
        "axis_top": (0.5, 0.08),
        "chin": (0.5, 0.86),
        "left_eye_center": (0.36, 0.4),
        "right_eye_center": (0.64, 0.4),
        "jaw_left": (0.34, 0.65),
        "jaw_right": (0.66, 0.65),
        "mouth_left": (0.42, 0.67),
        "mouth_right": (0.58, 0.67),
        "left_ear_top": (0.22, 0.34),
        "right_ear_top": (0.78, 0.34),
        "left_ear_bottom": (0.22, 0.58),
        "right_ear_bottom": (0.78, 0.58),
    }


def _card():
    return {
        "name": "Aiko",
        "revision": 2,
        "anchors": [
            {"key": key, "value": 0.5, "description": key + " relationship"}
            for key in ("cranial_radius", "lower_face", "eye_span", "jaw_span", "mouth_span")
        ],
    }


def test_variants_report_descriptive_change_without_failure_ranking():
    review = review_identity_comparison(
        _landmarks(), _landmarks(0.9), "proportion_variant", _card(), "variation-1"
    )
    assert review.rubric_id == "anime-head-variation-proportion_variant"
    assert "identity_cranial_radius_variation_magnitude" in review.measurements
    assert review.targeted_exercise_ids == []


def test_selected_pair_review_uses_card_and_retention_dimensions():
    review = review_identity_comparison(
        _landmarks(), _landmarks(), "selected_front", _card(), "variation-2"
    )
    assert "identity_card_adherence" in review.measurements
    assert "identity_cranial_retention" in review.measurements
    assert review.evidence[0].source.value == "artist_confirmation"


def test_failed_selected_pair_offers_identity_retention_preview_guides():
    candidate = _landmarks(0.45)
    candidate["right_eye_center"] = (0.53, 0.4)
    candidate["jaw_right"] = (0.53, 0.65)
    review = review_identity_comparison(
        _landmarks(), candidate, "selected_front", _card(), "variation-3"
    )

    assert review.redlines
    assert review.suggestions[0].id == "identity-retention-guides"
    assert all(redline.layer_name.startswith("Tutor — identity") for redline in review.redlines)
