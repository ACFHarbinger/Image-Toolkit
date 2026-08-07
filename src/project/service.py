"""Application services for portable learning projects."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from .model import (
    AdviceFeedback,
    AdviceRating,
    Attempt,
    ExerciseProgress,
    FeedbackPolicy,
    Project,
    ProjectProgress,
    ReviewRecord,
    SuggestionDecision,
)
from .storage import MANIFEST_NAME, load_project, save_project

FRONT_HEAD_EXERCISE_ID = "anime-head-front-construction"


def create_exercise_project(
    directory: str | Path,
    *,
    title: str,
    document_asset: str = "artwork/attempt-001.kra",
    attempt_id: str,
    exercise_id: str = FRONT_HEAD_EXERCISE_ID,
) -> Project:
    """Create one manifest in an existing empty project directory."""
    root = Path(directory).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("project directory must already exist")
    if any(root.iterdir()):
        expected_document = root / document_asset
        existing = set(root.iterdir())
        if existing != {expected_document.parent} or not expected_document.is_file():
            raise ValueError("project directory must be empty except for its new exercise document")
    if (root / MANIFEST_NAME).exists():
        raise FileExistsError("project manifest already exists")
    if not exercise_id.strip():
        raise ValueError("exercise id must not be empty")
    project = Project(
        title=title,
        document_asset=document_asset,
        progress=ProjectProgress(
            [ExerciseProgress(exercise_id, [Attempt(exercise_id, id=attempt_id)])]
        ),
    )
    save_project(root, project)
    return project


def record_attempt_review(
    directory: str | Path, *, attempt_id: str, review_payload: dict
) -> ReviewRecord:
    """Append one privacy-safe review to a known attempt and save atomically."""
    root = Path(directory)
    project = load_project(root)
    attempt = _find_attempt(project, attempt_id)
    review = ReviewRecord.from_review_payload(review_payload)
    attempt.reviews.append(review)
    save_project(root, project)
    return review


def decide_attempt_review(
    directory: str | Path,
    *,
    attempt_id: str,
    review_id: str,
    decision: SuggestionDecision,
) -> bool:
    """Persist one final decision with recovery history."""
    root = Path(directory)
    project = load_project(root)
    attempt = _find_attempt(project, attempt_id)
    matching = [review for review in attempt.reviews if review.id == review_id]
    if len(matching) != 1:
        raise ValueError("review does not uniquely identify a persisted attempt review")
    changed = matching[0].decide(decision)
    if changed:
        save_project(root, project)
    return changed


def record_advice_feedback(
    directory: str | Path,
    *,
    attempt_id: str,
    review_id: str,
    rating: AdviceRating,
    note: str | None = None,
) -> bool:
    """Persist one structured advice rating and optional local note."""
    root = Path(directory)
    project = load_project(root)
    attempt = _find_attempt(project, attempt_id)
    matching = [review for review in attempt.reviews if review.id == review_id]
    if len(matching) != 1:
        raise ValueError("review does not uniquely identify a persisted attempt review")
    changed = matching[0].report_feedback(AdviceFeedback(rating, note), project.feedback_policy)
    if changed:
        save_project(root, project)
    return changed


def project_progress_snapshot(directory: str | Path) -> dict:
    """Return privacy-safe project progress for constrained local hosts."""
    project = load_project(Path(directory))
    return {
        "retain_learning_progress": project.consent.retain_learning_progress,
        "feedback_policy": {
            "retain_revision_history": project.feedback_policy.retain_revision_history,
            "note_character_limit": project.feedback_policy.note_character_limit,
        },
        "exercises": [
            {
                "exercise_id": exercise.exercise_id,
                "attempts": [
                    {
                        "attempt_id": attempt.id,
                        "completed_at": attempt.completed_at,
                        "reviews": [
                            {
                                "review_id": review.id,
                                "exercise_version": review.exercise_version,
                                "method_id": review.method_id,
                                "rubric_id": review.rubric_id,
                                "rubric_version": review.rubric_version,
                                "measurements": dict(review.measurements),
                                "artist_feedback": (
                                    {
                                        "rating": review.artist_feedback.rating.value,
                                        "note": review.artist_feedback.note,
                                        "revision": review.artist_feedback.revision,
                                    }
                                    if review.artist_feedback is not None
                                    else None
                                ),
                            }
                            for review in attempt.reviews
                        ],
                    }
                    for attempt in exercise.attempts
                ],
            }
            for exercise in project.progress.exercises
        ],
    }


def configure_progress_retention(
    directory: str | Path, *, enabled: bool, clear_existing: bool = False
) -> bool:
    """Change project retention, requiring an explicit purge when disabling."""
    if not isinstance(enabled, bool) or not isinstance(clear_existing, bool):
        raise ValueError("progress-retention options must be boolean")
    root = Path(directory)
    project = load_project(root)
    if project.consent.retain_learning_progress == enabled:
        return False
    if not enabled and project.progress.exercises:
        if not clear_existing:
            raise ValueError("existing learning progress must be explicitly cleared")
        project.progress = ProjectProgress()
    project.consent.retain_learning_progress = enabled
    save_project(root, project)
    return True


def configure_feedback_policy(
    directory: str | Path,
    *,
    retain_revision_history: bool,
    note_character_limit: int,
) -> bool:
    """Update feedback editing policy and discard history when retention is disabled."""
    root = Path(directory)
    project = load_project(root)
    policy = FeedbackPolicy(retain_revision_history, note_character_limit)
    if project.feedback_policy == policy:
        return False
    if not retain_revision_history:
        for exercise in project.progress.exercises:
            for attempt in exercise.attempts:
                for review in attempt.reviews:
                    review.artist_feedback_history.clear()
    project.feedback_policy = policy
    project.validate()
    save_project(root, project)
    return True


def set_attempt_completion(directory: str | Path, *, attempt_id: str, completed: bool) -> bool:
    """Explicitly mark or unmark one attempt; reviews never call this implicitly."""
    if not isinstance(completed, bool):
        raise ValueError("attempt completion setting must be boolean")
    root = Path(directory)
    project = load_project(root)
    attempt = _find_attempt(project, attempt_id)
    if completed and attempt.completed_at is not None:
        return False
    if not completed and attempt.completed_at is None:
        return False
    attempt.completed_at = datetime.now(UTC).isoformat() if completed else None
    save_project(root, project)
    return True


def _find_attempt(project: Project, attempt_id: str) -> Attempt:
    matching = [
        attempt
        for exercise in project.progress.exercises
        for attempt in exercise.attempts
        if attempt.id == attempt_id
    ]
    if len(matching) != 1:
        raise ValueError("attempt identifier is missing or ambiguous")
    return matching[0]
