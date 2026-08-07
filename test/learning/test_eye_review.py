"""Tests for auditable eye-structure and style/expression review."""

import pytest

from learning.eye_review import EyePairLandmarks, review_eye_pair


def _landmarks():
    return EyePairLandmarks(
        (0.5, 0.1),
        (0.5, 0.9),
        (0.15, 0.4),
        (0.85, 0.4),
        (0.42, 0.4),
        (0.20, 0.4),
        (0.58, 0.4),
        (0.80, 0.4),
        (0.31, 0.34),
        (0.31, 0.46),
        (0.69, 0.34),
        (0.69, 0.46),
        (0.31, 0.35),
        (0.31, 0.45),
        (0.69, 0.35),
        (0.69, 0.45),
    )


def test_structure_review_excludes_style_only_dimensions():
    review = review_eye_pair(_landmarks(), "front", "structure", "review-1")
    assert review.rubric_id == "anime-head-eyes-structure"
    assert "eye_spacing_balance" in review.measurements
    assert "expression_consistency" not in review.measurements
    assert review.explanations


def test_style_review_includes_lid_and_expression_dimensions():
    review = review_eye_pair(_landmarks(), "right_three_quarter", "style_expression", "review-2")
    assert review.rubric_id == "anime-head-eyes-style_expression"
    assert "eyelid_rhythm_consistency" in review.measurements
    assert "expression_consistency" in review.measurements
    assert all(
        0 <= review.measurements[key] <= 1
        for key in (
            "eye_line_consistency",
            "eye_spacing_balance",
            "eye_projected_scale",
            "eyelid_rhythm_consistency",
            "expression_consistency",
        )
    )


def test_eye_review_rejects_unknown_view_or_stage():
    with pytest.raises(ValueError, match="front or right"):
        review_eye_pair(_landmarks(), "profile", "structure", "review-3")
    with pytest.raises(ValueError, match="stage"):
        review_eye_pair(_landmarks(), "front", "polish", "review-4")
