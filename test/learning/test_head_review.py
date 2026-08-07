"""Deterministic fixtures for the front-view construction review."""

import pytest

from learning import FrontHeadLandmarks, review_front_head


def _landmarks(**changes):
    values = {
        "cranium_center": (0.5, 0.4),
        "cranium_radius": 0.25,
        "centerline_top": (0.5, 0.15),
        "centerline_bottom": (0.5, 0.85),
        "eye_line_left": (0.3, 0.4),
        "eye_line_right": (0.7, 0.4),
        "jaw_left": (0.34, 0.65),
        "jaw_right": (0.66, 0.65),
        "chin": (0.5, 0.85),
    }
    return FrontHeadLandmarks(**(values | changes))


def test_balanced_fixture_produces_no_corrective_redlines():
    review = review_front_head(_landmarks(), "review-balanced")
    assert review.evidence == []
    assert review.redlines == []
    assert review.suggestions == []
    assert review.targeted_exercise_ids == []
    assert all(
        score == 1
        for name, score in review.measurements.items()
        if "consistency" in name or name in {"chin_centering", "jaw_symmetry"}
    )
    assert "provisional" in review.explanations[0]


def test_flawed_fixture_returns_auditable_feedback_and_preview():
    review = review_front_head(
        _landmarks(
            centerline_bottom=(0.62, 0.85),
            eye_line_right=(0.7, 0.5),
            jaw_right=(0.75, 0.65),
            chin=(0.6, 0.85),
        ),
        "review-flawed",
    )
    assert len(review.evidence) == 4
    assert len(review.redlines) == 4
    assert review.suggestions[0].accepted is None
    assert review.suggestions[0].preview_layer_name == "Tutor — Preview"
    assert review.targeted_exercise_ids == ["anime-head-front-axis-practice"]
    assert review.measurements["centerline_deviation_degrees"] > 5
    assert all(item.source.value == "geometry" and item.confidence == 1 for item in review.evidence)


@pytest.mark.parametrize(
    "changes",
    [
        {"cranium_radius": 0},
        {"chin": (1.1, 0.8)},
        {"eye_line_right": (0.3, 0.4)},
    ],
)
def test_invalid_manual_landmarks_are_rejected(changes):
    with pytest.raises(ValueError):
        review_front_head(_landmarks(**changes), "review-invalid")
