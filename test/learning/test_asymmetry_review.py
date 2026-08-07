"""Tests for intent-aware controlled-asymmetry comparisons."""

import pytest

from learning.asymmetry_review import review_asymmetry_comparison


def _landmarks(offset=0.0):
    return {
        "cranium_center": (0.5, 0.3),
        "cranium_edge": (0.75, 0.3),
        "axis_top": (0.5, 0.08),
        "chin": (0.5, 0.86),
        "left_eye_center": (0.36, 0.4 + offset),
        "right_eye_center": (0.64, 0.4),
        "jaw_left": (0.34, 0.65),
        "jaw_right": (0.66, 0.65),
        "mouth_left": (0.42, 0.67 + offset),
        "mouth_right": (0.58, 0.67),
        "left_ear_top": (0.22, 0.34 + offset),
        "right_ear_top": (0.78, 0.34),
        "left_ear_bottom": (0.22, 0.58),
        "right_ear_bottom": (0.78, 0.58),
    }


def _intent():
    return {
        "cause": "expression",
        "side": "character_left",
        "strength": "subtle",
        "purpose": "a restrained skeptical expression",
    }


def test_required_intent_is_auditable_artist_confirmation():
    review = review_asymmetry_comparison(
        _landmarks(), _landmarks(0.015), "expression", _intent(), "review-1"
    )
    assert review.rubric_id == "anime-head-asymmetry-expression"
    assert review.evidence[0].source.value == "artist_confirmation"
    assert "skeptical" in review.evidence[0].observation
    assert "asymmetry_side_consistency" in review.measurements


def test_control_stage_allows_missing_intent():
    review = review_asymmetry_comparison(
        _landmarks(), _landmarks(), "corrected_drift", None, "review-2"
    )
    assert "asymmetry_side_consistency" not in review.measurements


def test_authored_stage_rejects_missing_intent_fields():
    with pytest.raises(ValueError, match="required"):
        review_asymmetry_comparison(_landmarks(), _landmarks(), "design", None, "review-3")


def test_failed_comparison_emits_control_relative_preview_guides():
    candidate = _landmarks(0.08)
    candidate["cranium_edge"] = (0.95, 0.3)
    candidate["mouth_right"] = (0.9, 0.67)
    review = review_asymmetry_comparison(
        _landmarks(), candidate, "expression", _intent(), "review-4"
    )
    assert review.redlines
    assert review.suggestions[0].id == "asymmetry-comparison-guides"
    assert all(redline.explanation for redline in review.redlines)
