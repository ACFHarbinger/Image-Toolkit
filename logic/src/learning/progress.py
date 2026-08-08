"""Private progress summaries derived from locally retained review records."""

from __future__ import annotations

from dataclasses import dataclass

from .curriculum import AttemptComparison, compare_attempts
from .model import ArtistFeedback, Review


@dataclass(frozen=True, slots=True)
class FeedbackSummary:
    """Counts artist judgments without inventing an opaque quality score."""

    helpful: int = 0
    unhelpful: int = 0
    incorrect: int = 0
    not_applicable: int = 0
    unrated: int = 0


@dataclass(frozen=True, slots=True)
class ProgressSummary:
    """A local, non-ranking view of retries and comparable changes."""

    attempt_count: int
    retry_count: int
    comparisons: tuple[AttemptComparison, ...]
    incompatible_pair_count: int
    feedback: FeedbackSummary


def summarize_progress(reviews: list[Review], feedback: list[ArtistFeedback]) -> ProgressSummary:
    """Summarize ordered attempts; incompatible adjacent pairs remain visible."""
    review_ids = [review.id for review in reviews]
    if len(review_ids) != len(set(review_ids)):
        raise ValueError("review identifiers must be unique")
    known_ids = set(review_ids)
    feedback_by_review: dict[str, ArtistFeedback] = {}
    for item in feedback:
        _validate_feedback(item)
        if item.review_id not in known_ids:
            raise ValueError("feedback references an unknown review")
        if item.review_id in feedback_by_review:
            raise ValueError("only one feedback report is allowed per review")
        feedback_by_review[item.review_id] = item

    comparisons: list[AttemptComparison] = []
    incompatible = 0
    for before, after in zip(reviews, reviews[1:], strict=False):
        try:
            comparisons.append(compare_attempts(before, after))
        except ValueError:
            incompatible += 1

    return ProgressSummary(
        attempt_count=len(reviews),
        retry_count=max(0, len(reviews) - 1),
        comparisons=tuple(comparisons),
        incompatible_pair_count=incompatible,
        feedback=_summarize_feedback(reviews, feedback_by_review),
    )


def _validate_feedback(feedback: ArtistFeedback) -> None:
    if not feedback.review_id.strip():
        raise ValueError("feedback review id must not be empty")
    classifications = sum(
        (
            feedback.helpful is not None,
            feedback.incorrect,
            feedback.not_applicable,
        )
    )
    if classifications > 1:
        raise ValueError("feedback classifications are mutually exclusive")
    if feedback.note is not None and not feedback.note.strip():
        raise ValueError("feedback note must be absent or non-empty")


def _summarize_feedback(
    reviews: list[Review], feedback_by_review: dict[str, ArtistFeedback]
) -> FeedbackSummary:
    counts = {key: 0 for key in FeedbackSummary.__dataclass_fields__}
    for review in reviews:
        item = feedback_by_review.get(review.id)
        if item is None or (
            item.helpful is None and not item.incorrect and not item.not_applicable
        ):
            counts["unrated"] += 1
        elif item.incorrect:
            counts["incorrect"] += 1
        elif item.not_applicable:
            counts["not_applicable"] += 1
        elif item.helpful:
            counts["helpful"] += 1
        else:
            counts["unhelpful"] += 1
    return FeedbackSummary(**counts)
