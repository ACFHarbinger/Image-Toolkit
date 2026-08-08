"""Tests for paired front/turned cranial and jaw consistency review."""

import pytest

from learning.design_review import review_cranial_jaw_pair
from learning.head_review import FrontHeadLandmarks
from learning.orientation_review import ThreeQuarterLandmarks


def _front():
    return FrontHeadLandmarks(
        (0.5, 0.35),
        0.25,
        (0.5, 0.1),
        (0.5, 0.6),
        (0.3, 0.4),
        (0.7, 0.4),
        (0.36, 0.65),
        (0.64, 0.65),
        (0.5, 0.82),
    )


def _turned():
    return ThreeQuarterLandmarks(
        (0.5, 0.35),
        0.25,
        (0.56, 0.1),
        (0.56, 0.82),
        (0.3, 0.4),
        (0.7, 0.4),
        (0.38, 0.4),
        (0.7, 0.4),
        (0.40, 0.65),
        (0.62, 0.65),
    )


def test_pair_review_returns_auditable_consistency_measurements():
    review = review_cranial_jaw_pair(_front(), _turned(), "review-1", "neutral")

    assert review.exercise_id == "anime-head-volume-jaw"
    assert review.rubric_id == "anime-head-volume-jaw-pair"
    for score_id in (
        "cranial_volume_retention",
        "lower_face_length_retention",
        "jaw_character_retention",
        "chin_alignment",
        "perspective_adjustment",
    ):
        assert 0 <= review.measurements[score_id] <= 1
    assert review.explanations


def test_pair_review_requires_identifiers():
    with pytest.raises(ValueError, match="identifiers"):
        review_cranial_jaw_pair(_front(), _turned(), "review-1", "")
