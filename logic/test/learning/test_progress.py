"""Tests for local, non-ranking learning progress summaries."""

from __future__ import annotations

from dataclasses import replace

import pytest

from learning import ArtistFeedback, Review, summarize_progress


def _review(identifier: str, score: float, **changes: str) -> Review:
    values = {
        "id": identifier,
        "exercise_id": "anime-head-front-construction",
        "exercise_version": "1.0.0",
        "method_id": "anime-head-construction-v1",
        "rubric_id": "anime-head-front-structure",
        "rubric_version": "1.0.0",
    }
    values.update(changes)
    return Review(
        **values,
        evidence=[],
        explanations=[],
        measurements={"head_axis_consistency": score},
    )


def test_progress_reports_retries_direction_and_feedback_counts() -> None:
    reviews = [_review("r1", 0.3), _review("r2", 0.6), _review("r3", 0.6)]
    feedback = [
        ArtistFeedback("r1", helpful=True),
        ArtistFeedback("r2", helpful=False, note="The example did not explain the axis."),
    ]

    summary = summarize_progress(reviews, feedback)

    assert summary.attempt_count == 3
    assert summary.retry_count == 2
    assert summary.comparisons[0].improved == ("head_axis_consistency",)
    assert summary.comparisons[1].unchanged == ("head_axis_consistency",)
    assert summary.feedback.helpful == 1
    assert summary.feedback.unhelpful == 1
    assert summary.feedback.unrated == 1


def test_incompatible_pairs_are_disclosed_instead_of_compared() -> None:
    first = _review("r1", 0.3)
    incompatible = replace(_review("r2", 0.7), rubric_version="2.0.0")

    summary = summarize_progress([first, incompatible], [])

    assert summary.comparisons == ()
    assert summary.incompatible_pair_count == 1


def test_feedback_supports_incorrect_not_applicable_and_unrated() -> None:
    reviews = [_review("r1", 0.3), _review("r2", 0.4), _review("r3", 0.5)]
    summary = summarize_progress(
        reviews,
        [ArtistFeedback("r1", incorrect=True), ArtistFeedback("r2", not_applicable=True)],
    )

    assert summary.feedback.incorrect == 1
    assert summary.feedback.not_applicable == 1
    assert summary.feedback.unrated == 1


@pytest.mark.parametrize(
    "feedback, message",
    [
        (ArtistFeedback("missing", helpful=True), "unknown review"),
        (ArtistFeedback("r1", helpful=True, incorrect=True), "mutually exclusive"),
        (ArtistFeedback("r1", note=" "), "absent or non-empty"),
    ],
)
def test_invalid_feedback_is_rejected(feedback: ArtistFeedback, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        summarize_progress([_review("r1", 0.3)], [feedback])


def test_duplicate_review_and_feedback_ids_are_rejected() -> None:
    review = _review("r1", 0.3)
    with pytest.raises(ValueError, match="review identifiers"):
        summarize_progress([review, review], [])
    with pytest.raises(ValueError, match="one feedback report"):
        summarize_progress(
            [review],
            [ArtistFeedback("r1", helpful=True), ArtistFeedback("r1", helpful=False)],
        )
