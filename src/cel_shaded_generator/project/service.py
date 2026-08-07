"""Application services for portable learning projects."""

from __future__ import annotations

from pathlib import Path

from .model import (
    Attempt,
    ExerciseProgress,
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
    project = Project(
        title=title,
        document_asset=document_asset,
        progress=ProjectProgress(
            [
                ExerciseProgress(
                    FRONT_HEAD_EXERCISE_ID, [Attempt(FRONT_HEAD_EXERCISE_ID, id=attempt_id)]
                )
            ]
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
