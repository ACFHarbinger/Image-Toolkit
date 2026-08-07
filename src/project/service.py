"""Application services for portable learning projects."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from uuid import uuid4

from colorization import load_style_bible

from .model import (
    AdviceFeedback,
    AdviceRating,
    Attempt,
    CapstonePolicy,
    ExerciseProgress,
    FeedbackPolicy,
    IdentityAnchor,
    IdentityCard,
    IdentityCardPolicy,
    Project,
    ProjectProgress,
    ReviewRecord,
    SuggestionDecision,
)
from .storage import MANIFEST_NAME, load_project, save_project

FRONT_HEAD_EXERCISE_ID = "anime-head-front-construction"
CAPSTONE_RUBRICS = (
    ("front_structure", "02 Front Construction", "anime-head-front-structure"),
    (
        "turned_structure",
        "03 Right Three-Quarter Construction",
        "anime-head-orientation-structure",
    ),
    (
        "identity_retention",
        "03 Right Three-Quarter Construction",
        "anime-head-variation-selected_turned",
    ),
    (
        "expression_asymmetry",
        "04 Expression Asymmetry and Value Pass",
        "anime-head-asymmetry-expression",
    ),
    (
        "cel_value_grouping",
        "04 Expression Asymmetry and Value Pass",
        "anime-head-cel-value-mask",
    ),
)


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
    rationale: str | None = None,
) -> bool:
    """Persist one final decision with recovery history."""
    root = Path(directory)
    project = load_project(root)
    attempt = _find_attempt(project, attempt_id)
    matching = [review for review in attempt.reviews if review.id == review_id]
    if len(matching) != 1:
        raise ValueError("review does not uniquely identify a persisted attempt review")
    if attempt.exercise_id == "anime-head-review" and (rationale is None or not rationale.strip()):
        raise ValueError("capstone suggestion decisions require an artist rationale")
    changed = matching[0].decide(decision, rationale, _timestamp() if rationale else None)
    if changed:
        save_project(root, project)
    return changed


def revise_capstone_decision_rationale(
    directory: str | Path, *, attempt_id: str, review_id: str, rationale: str
) -> bool:
    """Revise only capstone rationale text, preserving the final decision."""
    root = Path(directory)
    project = load_project(root)
    attempt = _find_attempt(project, attempt_id)
    if attempt.exercise_id != "anime-head-review":
        raise ValueError("decision rationales are editable only for capstone attempts")
    matching = [review for review in attempt.reviews if review.id == review_id]
    if len(matching) != 1:
        raise ValueError("review does not uniquely identify a persisted attempt review")
    changed = matching[0].revise_rationale(rationale, _timestamp(), project.capstone_policy)
    if changed:
        save_project(root, project)
    return changed


def import_compatible_capstone_review(
    directory: str | Path,
    *,
    target_attempt_id: str,
    source_attempt_id: str,
    source_review_id: str,
    decision: SuggestionDecision,
    rationale: str,
) -> ReviewRecord:
    """Copy compatible prior evidence into a capstone with a fresh judgment."""
    root = Path(directory)
    project = load_project(root)
    target = _find_attempt(project, target_attempt_id)
    source = _find_attempt(project, source_attempt_id)
    if target.exercise_id != "anime-head-review" or source.id == target.id:
        raise ValueError("review import requires a distinct source and capstone target")
    matching = [review for review in source.reviews if review.id == source_review_id]
    if len(matching) != 1:
        raise ValueError("source review does not uniquely identify prior evidence")
    source_review = matching[0]
    required = {rubric_id for _, _, rubric_id in CAPSTONE_RUBRICS}
    if source_review.rubric_id not in required:
        raise ValueError("source review rubric is not part of the capstone")
    existing = [review for review in target.reviews if review.rubric_id == source_review.rubric_id]
    if existing and any(
        (review.method_id, review.rubric_version, review.exercise_version)
        != (source_review.method_id, source_review.rubric_version, source_review.exercise_version)
        for review in existing
    ):
        raise ValueError("source review is incompatible with existing capstone evidence")
    imported = deepcopy(source_review)
    imported.id = "capstone-import-" + str(uuid4())
    imported.source_attempt_id = source.id
    imported.source_review_id = source_review.id
    imported.suggestion_decision = SuggestionDecision.PENDING
    imported.suggestion_decision_rationale = None
    imported.suggestion_decision_rationale_updated_at = None
    imported.suggestion_decision_rationale_history.clear()
    imported.artist_feedback = None
    imported.artist_feedback_history.clear()
    imported.decide(decision, rationale, _timestamp())
    target.reviews.append(imported)
    save_project(root, project)
    return imported


def configure_capstone_policy(directory: str | Path, *, retain_rationale_history: bool) -> bool:
    """Configure independent project-local rationale revision retention."""
    root = Path(directory)
    project = load_project(root)
    policy = CapstonePolicy(retain_rationale_history)
    if project.capstone_policy == policy:
        return False
    if not retain_rationale_history:
        for exercise in project.progress.exercises:
            for attempt in exercise.attempts:
                for review in attempt.reviews:
                    review.suggestion_decision_rationale_history.clear()
    project.capstone_policy = policy
    save_project(root, project)
    return True


def attach_style_bible(directory: str | Path, *, asset_path: str) -> bool:
    """Attach one validated project-local style bible without copying assets."""
    root = Path(directory).resolve()
    relative, bible_path = _resolve_project_asset(root, asset_path)
    bible = load_style_bible(bible_path)
    for reference in bible.reference_views:
        _resolve_project_asset(root, reference.asset_path)
    project = load_project(root)
    if relative in project.style_bible_assets:
        return False
    project.style_bible_assets.append(relative)
    save_project(root, project)
    return True


def detach_style_bible(directory: str | Path, *, asset_path: str) -> bool:
    """Remove only a style-bible binding; never delete its files."""
    root = Path(directory).resolve()
    relative = PurePosixPath(asset_path).as_posix()
    project = load_project(root)
    if relative not in project.style_bible_assets:
        return False
    project.style_bible_assets.remove(relative)
    save_project(root, project)
    return True


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
        "identity_card_policy": {
            "retain_revision_history": project.identity_card_policy.retain_revision_history,
        },
        "capstone_policy": {
            "retain_rationale_history": project.capstone_policy.retain_rationale_history,
        },
        "identity_card": (
            {
                "name": project.identity_card.name,
                "anchors": [
                    {"key": item.key, "value": item.value, "description": item.description}
                    for item in project.identity_card.anchors
                ],
                "revision": project.identity_card.revision,
            }
            if project.identity_card is not None
            else None
        ),
        "style_bibles": [
            _style_bible_summary(Path(directory), path) for path in project.style_bible_assets
        ],
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
                                "suggestion_decision": review.suggestion_decision.value,
                                "suggestion_decision_rationale": (
                                    review.suggestion_decision_rationale
                                ),
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
        "capstone_dashboard": _capstone_dashboard(project),
    }


def _capstone_dashboard(project: Project) -> dict:
    """Aggregate capstone state while retaining each underlying rubric."""
    attempts = [
        attempt
        for exercise in project.progress.exercises
        if exercise.exercise_id == "anime-head-review"
        for attempt in exercise.attempts
    ]
    reviews = [review for attempt in attempts for review in attempt.reviews]
    import_candidates = [
        {
            "attempt_id": attempt.id,
            "review_id": review.id,
            "rubric_id": review.rubric_id,
            "method_id": review.method_id,
            "rubric_version": review.rubric_version,
            "exercise_version": review.exercise_version,
        }
        for exercise in project.progress.exercises
        if exercise.exercise_id != "anime-head-review"
        for attempt in exercise.attempts
        for review in attempt.reviews
        if review.rubric_id in {item[2] for item in CAPSTONE_RUBRICS}
    ]
    latest_by_rubric = {}
    for review in reviews:
        latest_by_rubric[(review.rubric_id, review.rubric_version)] = review
    stages = []
    for stage_id, layer_name, rubric_id in CAPSTONE_RUBRICS if attempts else ():
        matching = [review for review in reviews if review.rubric_id == rubric_id]
        latest = matching[-1] if matching else None
        stages.append(
            {
                "stage_id": stage_id,
                "layer_name": layer_name,
                "rubric_id": rubric_id,
                "status": (
                    "missing"
                    if latest is None
                    else (
                        "pending_decision"
                        if latest.suggestion_decision is SuggestionDecision.PENDING
                        else "complete"
                    )
                ),
                "review_id": latest.id if latest is not None else None,
            }
        )
    next_stage = next((stage for stage in stages if stage["status"] != "complete"), None)
    return {
        "attempt_count": len(attempts),
        "review_count": len(reviews),
        "pending_decision_count": sum(
            review.suggestion_decision is SuggestionDecision.PENDING for review in reviews
        ),
        "rubrics": [
            {
                "rubric_id": review.rubric_id,
                "rubric_version": review.rubric_version,
                "method_id": review.method_id,
                "measurements": dict(review.measurements),
                "suggestion_decision": review.suggestion_decision.value,
                "suggestion_decision_rationale": review.suggestion_decision_rationale,
                "suggestion_decision_rationale_updated_at": (
                    review.suggestion_decision_rationale_updated_at
                ),
                "suggestion_decision_rationale_history": [
                    {"text": item.text, "revised_at": item.revised_at}
                    for item in review.suggestion_decision_rationale_history
                ],
                "source_attempt_id": review.source_attempt_id,
                "source_review_id": review.source_review_id,
            }
            for _, review in sorted(latest_by_rubric.items())
        ],
        "collection_stages": stages,
        "next_stage": next_stage,
        "ready_for_manual_completion": bool(stages)
        and all(stage["status"] == "complete" for stage in stages),
        "import_candidates": import_candidates,
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


def upsert_identity_card(directory: str | Path, *, name: str, anchors: list[dict]) -> bool:
    """Create or revise the portable selected-character identity card."""
    root = Path(directory)
    project = load_project(root)
    card = IdentityCard(name, [IdentityAnchor(**item) for item in anchors])
    if project.identity_card is not None:
        if (
            project.identity_card.name == card.name
            and project.identity_card.anchors == card.anchors
        ):
            return False
        if project.identity_card_policy.retain_revision_history:
            project.identity_card_history.append(project.identity_card)
        else:
            project.identity_card_history.clear()
        card.revision = project.identity_card.revision + 1
    project.identity_card = card
    save_project(root, project)
    return True


def configure_identity_card_policy(directory: str | Path, *, retain_revision_history: bool) -> bool:
    """Update identity-card history retention and discard history when disabled."""
    root = Path(directory)
    project = load_project(root)
    policy = IdentityCardPolicy(retain_revision_history)
    if project.identity_card_policy == policy:
        return False
    if not retain_revision_history:
        project.identity_card_history.clear()
    project.identity_card_policy = policy
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


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _resolve_project_asset(root: Path, asset_path: str) -> tuple[str, Path]:
    relative = PurePosixPath(asset_path)
    if (
        not asset_path.strip()
        or relative.is_absolute()
        or ".." in relative.parts
        or "\\" in asset_path
    ):
        raise ValueError("project asset must use a safe relative POSIX path")
    path = root.joinpath(*relative.parts)
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
        raise ValueError("project asset must be an existing regular non-symlink file")
    return relative.as_posix(), path


def _style_bible_summary(root: Path, asset_path: str) -> dict:
    bible = load_style_bible(root / asset_path)
    return {
        "asset_path": asset_path,
        "id": bible.id,
        "character_name": bible.character_name,
        "style_name": bible.style_name,
        "material_count": len(bible.materials),
        "reference_view_count": len(bible.reference_views),
    }
