"""Application services for portable learning projects."""

from __future__ import annotations

import os
import re
import shutil
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from uuid import uuid4

from colorization import (
    CharacterStyleBible,
    CorrespondenceSet,
    load_correspondence_set,
    load_style_bible,
    save_correspondence_set,
    save_style_bible,
)

from .model import (
    AdviceFeedback,
    AdviceRating,
    Attempt,
    CapstonePolicy,
    ChapterPage,
    ExerciseProgress,
    FeedbackPolicy,
    IdentityAnchor,
    IdentityCard,
    IdentityCardPolicy,
    PageStatus,
    Project,
    ProjectProgress,
    ReviewRecord,
    StudyConsent,
    StudySession,
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


def upsert_project_style_bible(directory: str | Path, *, payload: dict) -> str:
    """Validate, atomically save, and attach one project-local style bible."""
    root = Path(directory).resolve()
    bible = CharacterStyleBible.from_dict(payload)
    relative = f"style-bibles/{bible.id}.json"
    for reference in bible.reference_views:
        _resolve_project_asset(root, reference.asset_path)
    save_style_bible(root / relative, bible)
    attach_style_bible(root, asset_path=relative)
    return relative


def import_reference_asset(directory: str | Path, *, source_path: str) -> str:
    """Copy an external reference into the project with a content-safe name."""
    root = Path(directory).resolve()
    source = Path(source_path).expanduser()
    if source.is_symlink() or not source.is_file():
        raise ValueError("reference source must be a regular non-symlink file")
    extension = source.suffix.lower()
    if extension not in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}:
        raise ValueError("reference source must use a supported raster-image extension")
    digest = _file_digest(source)
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", source.stem).strip("-._") or "reference"
    relative = f"references/{safe_stem}-{digest[:12]}{extension}"
    destination = root / relative
    if destination.exists():
        if _file_digest(destination) != digest:
            raise ValueError("reference destination collision has different content")
        return relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile("wb", dir=destination.parent, delete=False) as output:
            with source.open("rb") as input_file:
                shutil.copyfileobj(input_file, output)
            output.flush()
            os.fsync(output.fileno())
            temporary = Path(output.name)
        os.replace(temporary, destination)
    except BaseException:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise
    return relative


def project_style_bible_payload(directory: str | Path, *, asset_path: str) -> dict:
    """Return one bound, validated bible to a constrained local host."""
    root = Path(directory).resolve()
    project = load_project(root)
    if asset_path not in project.style_bible_assets:
        raise ValueError("style bible is not bound to this project")
    _, path = _resolve_project_asset(root, asset_path)
    return load_style_bible(path).to_dict()


def attach_correspondence_set(directory: str | Path, *, asset_path: str) -> bool:
    """Attach one validated project-local correspondence set without copying assets."""
    root = Path(directory).resolve()
    relative, set_path = _resolve_project_asset(root, asset_path)
    load_correspondence_set(set_path)
    project = load_project(root)
    if relative in project.correspondence_set_assets:
        return False
    project.correspondence_set_assets.append(relative)
    save_project(root, project)
    return True


def detach_correspondence_set(directory: str | Path, *, asset_path: str) -> bool:
    """Remove only a correspondence-set binding; never delete its files."""
    root = Path(directory).resolve()
    relative = PurePosixPath(asset_path).as_posix()
    project = load_project(root)
    if relative not in project.correspondence_set_assets:
        return False
    project.correspondence_set_assets.remove(relative)
    save_project(root, project)
    return True


def upsert_project_correspondence_set(directory: str | Path, *, payload: dict) -> str:
    """Validate, atomically save, and attach one project-local correspondence set."""
    root = Path(directory).resolve()
    correspondence_set = CorrespondenceSet.from_dict(payload)
    relative = f"correspondence/{correspondence_set.id}.json"
    save_correspondence_set(root / relative, correspondence_set)
    attach_correspondence_set(root, asset_path=relative)
    return relative


def project_correspondence_set_payload(directory: str | Path, *, asset_path: str) -> dict:
    """Return one bound, validated correspondence set to a constrained local host."""
    root = Path(directory).resolve()
    project = load_project(root)
    if asset_path not in project.correspondence_set_assets:
        raise ValueError("correspondence set is not bound to this project")
    _, path = _resolve_project_asset(root, asset_path)
    return load_correspondence_set(path).to_dict()


def propagate_project_correspondence(
    directory: str | Path,
    *,
    asset_path: str,
    source_id: str,
    target_region_ids: list[str],
) -> dict:
    """Propagate one bound correspondence onto explicitly selected target regions."""
    root = Path(directory).resolve()
    project = load_project(root)
    if asset_path not in project.correspondence_set_assets:
        raise ValueError("correspondence set is not bound to this project")
    _, path = _resolve_project_asset(root, asset_path)
    correspondence_set = load_correspondence_set(path)
    propagated = correspondence_set.propagate(
        source_id, target_region_ids, lambda: "correspondence-" + str(uuid4())
    )
    save_correspondence_set(path, propagated)
    return propagated.to_dict()


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
        "correspondence_sets": [
            _correspondence_set_summary(Path(directory), path)
            for path in project.correspondence_set_assets
        ],
        "study": {
            "consent": {
                "opted_in": project.study_consent.opted_in,
                "consent_version": project.study_consent.consent_version,
                "consented_at": project.study_consent.consented_at,
            },
            "sessions": [
                {
                    "session_id": session.id,
                    "baseline_attempt_id": session.baseline_attempt_id,
                    "remedial_exercise_id": session.remedial_exercise_id,
                    "redraw_attempt_id": session.redraw_attempt_id,
                    "explanation_rating": (
                        session.explanation_rating.value
                        if session.explanation_rating is not None
                        else None
                    ),
                    "completed_at": session.completed_at,
                }
                for session in project.study_sessions
            ],
        },
        "chapter": {
            "pages": [
                {
                    "page_id": page.id,
                    "document_asset": page.document_asset,
                    "panel_id": page.panel_id,
                    "status": page.status.value,
                    "notes": page.notes,
                }
                for page in project.chapter_pages
            ],
            "next_pending_page_id": next(
                (
                    page.id
                    for page in project.chapter_pages
                    if page.status != PageStatus.ACCEPTED
                ),
                None,
            ),
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


def configure_study_consent(
    directory: str | Path, *, opted_in: bool, clear_existing: bool = False
) -> bool:
    """Change beginner-study opt-in, requiring an explicit purge when withdrawing.

    This only records an artist's own consent choice for roadmap A4 (issue
    #14), which the roadmap itself gates on live checks being intentionally
    scheduled; recording consent does not start or claim any evaluation.
    """
    if not isinstance(opted_in, bool) or not isinstance(clear_existing, bool):
        raise ValueError("study-consent options must be boolean")
    root = Path(directory)
    project = load_project(root)
    if project.study_consent.opted_in == opted_in:
        return False
    if not opted_in and project.study_sessions:
        if not clear_existing:
            raise ValueError("existing study sessions must be explicitly cleared")
        project.study_sessions = []
    project.study_consent = StudyConsent(
        opted_in=opted_in,
        consent_version=project.study_consent.consent_version,
        consented_at=_timestamp() if opted_in else None,
    )
    save_project(root, project)
    return True


def record_study_session(
    directory: str | Path,
    *,
    baseline_attempt_id: str,
    remedial_exercise_id: str | None = None,
    redraw_attempt_id: str | None = None,
    explanation_rating: AdviceRating | None = None,
    completed: bool = False,
) -> StudySession:
    """Create or update the one study session tied to a baseline attempt.

    Requires explicit study consent. Sessions accumulate fields as the
    baseline/review/remedial/redraw protocol progresses; identifiers are
    validated against attempts that already exist in the project.
    """
    root = Path(directory)
    project = load_project(root)
    if not project.study_consent.opted_in:
        raise ValueError("study sessions require explicit study consent")
    _find_attempt(project, baseline_attempt_id)
    if redraw_attempt_id is not None:
        _find_attempt(project, redraw_attempt_id)
    existing = next(
        (
            session
            for session in project.study_sessions
            if session.baseline_attempt_id == baseline_attempt_id
        ),
        None,
    )
    session = StudySession(
        id=existing.id if existing is not None else "study-" + str(uuid4()),
        baseline_attempt_id=baseline_attempt_id,
        remedial_exercise_id=(
            remedial_exercise_id
            or (existing.remedial_exercise_id if existing is not None else None)
        ),
        redraw_attempt_id=(
            redraw_attempt_id or (existing.redraw_attempt_id if existing is not None else None)
        ),
        explanation_rating=(
            explanation_rating
            or (existing.explanation_rating if existing is not None else None)
        ),
        completed_at=(
            _timestamp()
            if completed
            else (existing.completed_at if existing is not None else None)
        ),
    )
    if existing is not None:
        project.study_sessions.remove(existing)
    project.study_sessions.append(session)
    save_project(root, project)
    return session


def add_chapter_page(
    directory: str | Path, *, document_asset: str, panel_id: str, notes: str | None = None
) -> ChapterPage:
    """Append one page to the project's batch-chapter review queue.

    Execution-agnostic (roadmap milestone 6): this only records queue
    position and starting status. Whatever later segments/corresponds the
    page -- an interactive Krita session today, an offline batch tool in a
    later slice -- reports back through `set_chapter_page_status`.
    """
    root = Path(directory).resolve()
    relative, _ = _resolve_project_asset(root, document_asset)
    project = load_project(root)
    page = ChapterPage(
        id="page-" + str(uuid4()), document_asset=relative, panel_id=panel_id, notes=notes
    )
    project.chapter_pages.append(page)
    save_project(root, project)
    return page


def set_chapter_page_status(
    directory: str | Path, *, page_id: str, status: PageStatus, notes: str | None = None
) -> bool:
    """Explicitly set one page's review status; repeated identical calls are idempotent.

    Any status may follow any other -- the artist stays in control of the
    queue rather than a fixed state machine enforcing one path through it.
    """
    root = Path(directory)
    project = load_project(root)
    page = _find_chapter_page(project, page_id)
    changed_notes = notes is not None and notes != page.notes
    if page.status == status and not changed_notes:
        return False
    page.status = status
    if notes is not None:
        page.notes = notes
    save_project(root, project)
    return True


def next_pending_chapter_page(directory: str | Path) -> ChapterPage | None:
    """Return the first not-yet-accepted page in queue order, or None if done."""
    project = load_project(Path(directory))
    return next(
        (page for page in project.chapter_pages if page.status != PageStatus.ACCEPTED), None
    )


def _find_chapter_page(project: Project, page_id: str) -> ChapterPage:
    matching = [page for page in project.chapter_pages if page.id == page_id]
    if len(matching) != 1:
        raise ValueError("chapter-page identifier is missing or ambiguous")
    return matching[0]


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


def _correspondence_set_summary(root: Path, asset_path: str) -> dict:
    correspondence_set = load_correspondence_set(root / asset_path)
    return {
        "asset_path": asset_path,
        "id": correspondence_set.id,
        "style_bible_id": correspondence_set.style_bible_id,
        "correspondence_count": len(correspondence_set.correspondences),
    }


def _file_digest(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
