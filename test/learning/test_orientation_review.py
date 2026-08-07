"""Tests for specialized profile and three-quarter landmark reviews."""

from dataclasses import replace

import pytest

from learning import (
    OrientationView,
    ProfileLandmarks,
    ThreeQuarterLandmarks,
    compare_attempts,
    review_profile_head,
    review_three_quarter_head,
)


def _three_quarter():
    return ThreeQuarterLandmarks(
        cranium_center=(0.5, 0.38),
        cranium_radius=0.25,
        centerline_top=(0.575, 0.15),
        chin=(0.575, 0.82),
        eye_line_left=(0.30, 0.40),
        eye_line_right=(0.70, 0.40),
        left_contour=(0.30, 0.40),
        right_contour=(0.70, 0.40),
        jaw_left=(0.36, 0.64),
        jaw_right=(0.65, 0.63),
    )


def _profile():
    return ProfileLandmarks(
        cranium_center=(0.5, 0.38),
        cranium_radius=0.25,
        front_cranium_edge=(0.725, 0.38),
        back_cranium_edge=(0.275, 0.38),
        brow_front=(0.72, 0.35),
        muzzle_front=(0.77, 0.52),
        eye_line_back=(0.34, 0.40),
        eye_line_front=(0.72, 0.40),
        jaw_hinge=(0.33, 0.56),
        chin=(0.75, 0.76),
    )


def test_right_three_quarter_review_has_six_explainable_scores():
    review = review_three_quarter_head(
        _three_quarter(), OrientationView.RIGHT_THREE_QUARTER, "review-1"
    )
    assert review.rubric_id == "anime-head-orientation-structure"
    assert {
        "centerline_placement",
        "far_side_compression",
        "chin_alignment",
        "cross_contour_consistency",
        "jaw_attachment",
        "cranial_volume",
    } <= review.measurements.keys()
    assert all(
        0 <= review.measurements[key] <= 1
        for key in review.measurements
        if key
        in {
            "centerline_placement",
            "far_side_compression",
            "chin_alignment",
            "cross_contour_consistency",
            "jaw_attachment",
            "cranial_volume",
        }
    )


def test_profile_review_uses_profile_specific_cranial_and_jaw_evidence():
    review = review_profile_head(_profile(), OrientationView.RIGHT_PROFILE, "review-2")
    assert review.measurements["cranial_width_to_diameter_ratio"] == pytest.approx(0.9)
    assert "jaw_hinge_gap_radii" in review.measurements
    assert "far_to_near_width_ratio" not in review.measurements


def test_wrong_view_contract_is_rejected():
    with pytest.raises(ValueError, match="three-quarter view"):
        review_three_quarter_head(_three_quarter(), OrientationView.LEFT_PROFILE, "r")
    with pytest.raises(ValueError, match="profile view"):
        review_profile_head(_profile(), OrientationView.RIGHT_THREE_QUARTER, "r")


def test_mirrored_view_requires_centerline_on_the_selected_side():
    right = review_three_quarter_head(
        _three_quarter(), OrientationView.RIGHT_THREE_QUARTER, "right"
    )
    left = review_three_quarter_head(_three_quarter(), OrientationView.LEFT_THREE_QUARTER, "left")
    assert right.measurements["centerline_placement"] > left.measurements["centerline_placement"]


def test_landmarks_require_normalized_points_and_non_degenerate_profile_axis():
    invalid = replace(_profile(), chin=(1.2, 0.5))
    with pytest.raises(ValueError, match="normalized"):
        review_profile_head(invalid, OrientationView.RIGHT_PROFILE, "r")

    degenerate = replace(_profile(), muzzle_front=_profile().brow_front)
    with pytest.raises(ValueError, match="distinct"):
        review_profile_head(degenerate, OrientationView.RIGHT_PROFILE, "r")


def test_repeated_orientation_reviews_are_directionally_comparable():
    before = review_three_quarter_head(
        _three_quarter(), OrientationView.RIGHT_THREE_QUARTER, "before"
    )
    improved_landmarks = replace(_three_quarter(), chin=(0.575, 0.78))
    after = review_three_quarter_head(
        improved_landmarks, OrientationView.RIGHT_THREE_QUARTER, "after"
    )
    comparison = compare_attempts(before, after)
    assert "chin_alignment" in comparison.deltas
