"""Tests for versioned project and learner-profile persistence."""

from __future__ import annotations

import json
import os

import pytest

from project import (
    AdviceFeedback,
    AdviceRating,
    Attempt,
    ChapterPage,
    Consent,
    ExerciseProgress,
    Feedback,
    FeedbackPolicy,
    LearnerProfile,
    PageStatus,
    Project,
    ProjectProgress,
    ReviewRecord,
    SignalWeights,
    StudyConsent,
    StudySession,
    SuggestionDecision,
    load_profile,
    load_project,
    migrate_project_payload,
    save_profile,
    save_project,
)


def test_head_face_attempt_round_trips(tmp_path):
    project = Project(
        title="Anime head practice",
        consent=Consent(retain_artwork_in_history=True),
        progress=ProjectProgress(
            [
                ExerciseProgress(
                    "anime-head-front-v1",
                    [
                        Attempt(
                            exercise_id="anime-head-front-v1",
                            completed_at="2026-08-06T12:00:00+00:00",
                            metrics={"eye_alignment_error": 0.14},
                            feedback=[
                                Feedback(
                                    category="construction",
                                    explanation="Raise the far eye toward the guide.",
                                    score=0.78,
                                    redline_asset="assets/review-1.png",
                                )
                            ],
                            reviews=[
                                ReviewRecord(
                                    id="review-1",
                                    exercise_version="1.0.0",
                                    method_id="anime-head-construction-v1",
                                    rubric_id="anime-head-front-structure",
                                    rubric_version="1.0.0",
                                    measurements={"jaw_symmetry": 0.78},
                                    explanations=["Compare the large jaw widths."],
                                    suggestion_decision=SuggestionDecision.ACCEPTED,
                                    artist_feedback=AdviceFeedback(
                                        AdviceRating.HELPFUL, "The jaw-width explanation helped."
                                    ),
                                )
                            ],
                            artwork_asset="assets/attempt-1.kra",
                        )
                    ],
                )
            ]
        ),
    )

    save_project(tmp_path, project)

    assert load_project(tmp_path) == project


def test_review_decision_is_idempotent_and_cannot_be_reversed():
    review = ReviewRecord("r", "1", "method", "rubric", "1", {}, [])
    assert review.decide(SuggestionDecision.REJECTED)
    assert not review.decide(SuggestionDecision.REJECTED)
    with pytest.raises(ValueError, match="cannot be changed"):
        review.decide(SuggestionDecision.ACCEPTED)


def test_review_payload_excludes_redline_geometry_and_suggestions():
    review = ReviewRecord.from_review_payload(
        {
            "id": "r",
            "exercise_version": "1",
            "method_id": "method",
            "rubric_id": "rubric",
            "rubric_version": "1",
            "measurements": {"axis": 0.8},
            "explanations": ["Straighten the guide."],
            "redlines": [{"geometry": [[0, 0], [1, 1]]}],
            "suggestions": [{"preview_layer_name": "preview"}],
        }
    )
    assert review.measurements == {"axis": 0.8}
    assert not hasattr(review, "redlines")
    assert not hasattr(review, "suggestions")


def test_review_decision_save_has_recoverable_pending_revision(tmp_path):
    review = ReviewRecord("r", "1", "method", "rubric", "1", {}, ["Try again."])
    attempt = Attempt("head", reviews=[review])
    project = Project(
        title="Review recovery",
        progress=ProjectProgress([ExerciseProgress("head", [attempt])]),
    )
    save_project(tmp_path, project)
    review.decide(SuggestionDecision.ACCEPTED)
    save_project(tmp_path, project)

    assert (
        load_project(tmp_path).progress.exercises[0].attempts[0].reviews[0].suggestion_decision
        is SuggestionDecision.ACCEPTED
    )
    recovered = Project.from_dict(
        json.loads((tmp_path / ".recovery/project.1.json").read_text(encoding="utf-8"))
    )
    assert (
        recovered.progress.exercises[0].attempts[0].reviews[0].suggestion_decision
        is SuggestionDecision.PENDING
    )


def test_privacy_defaults_reject_artwork_history():
    project = Project(
        title="Private practice",
        progress=ProjectProgress(
            [ExerciseProgress("head", [Attempt("head", artwork_asset="attempt.kra")])]
        ),
    )

    with pytest.raises(ValueError, match="explicit retention consent"):
        project.to_dict()


def test_study_consent_requires_timestamp_only_when_opted_in():
    with pytest.raises(ValueError, match="requires a consent timestamp"):
        StudyConsent(opted_in=True)
    with pytest.raises(ValueError, match="must not retain a consent timestamp"):
        StudyConsent(opted_in=False, consented_at="2026-08-08T00:00:00+00:00")
    StudyConsent(opted_in=True, consented_at="2026-08-08T00:00:00+00:00")


def test_study_sessions_require_opted_in_consent():
    attempt = Attempt("head", id="attempt-1")
    project = Project(
        title="Study",
        progress=ProjectProgress([ExerciseProgress("head", [attempt])]),
        study_sessions=[StudySession("study-1", "attempt-1")],
    )
    with pytest.raises(ValueError, match="consent is not opted in"):
        project.to_dict()


def test_study_sessions_validate_known_attempt_ids():
    attempt = Attempt("head", id="attempt-1")
    consent = StudyConsent(opted_in=True, consented_at="2026-08-08T00:00:00+00:00")
    project = Project(
        title="Study",
        study_consent=consent,
        progress=ProjectProgress([ExerciseProgress("head", [attempt])]),
        study_sessions=[StudySession("study-1", "missing-attempt")],
    )
    with pytest.raises(ValueError, match="baseline attempt id is unknown"):
        project.to_dict()

    project.study_sessions = [StudySession("study-1", "attempt-1", redraw_attempt_id="missing")]
    with pytest.raises(ValueError, match="redraw attempt id is unknown"):
        project.to_dict()

    project.study_sessions = [StudySession("study-1", "attempt-1")]
    project.to_dict()


def test_study_session_round_trips_with_explanation_rating(tmp_path):
    attempt = Attempt("head", id="attempt-1")
    project = Project(
        title="Study",
        study_consent=StudyConsent(opted_in=True, consented_at="2026-08-08T00:00:00+00:00"),
        progress=ProjectProgress([ExerciseProgress("head", [attempt])]),
        study_sessions=[
            StudySession(
                "study-1",
                "attempt-1",
                remedial_exercise_id="anime-head-front-remedial",
                redraw_attempt_id=None,
                explanation_rating=AdviceRating.HELPFUL,
            )
        ],
    )
    save_project(tmp_path, project)
    assert load_project(tmp_path) == project


def test_chapter_page_rejects_invalid_fields():
    with pytest.raises(ValueError, match="must not be empty"):
        ChapterPage("", "pages/01.kra", "panel-1")
    with pytest.raises(ValueError, match="panel id must not be empty"):
        ChapterPage("page-1", "pages/01.kra", "")
    with pytest.raises(ValueError, match="safe relative"):
        ChapterPage("page-1", "../escape.kra", "panel-1")
    with pytest.raises(ValueError, match="notes must be absent or non-empty"):
        ChapterPage("page-1", "pages/01.kra", "panel-1", notes="  ")


def test_chapter_pages_require_unique_ids_assets_and_panels():
    page = ChapterPage("page-1", "pages/01.kra", "panel-1")
    duplicate_id = ChapterPage("page-1", "pages/02.kra", "panel-2")
    with pytest.raises(ValueError, match="chapter-page identifiers must be unique"):
        Project(title="Chapter", chapter_pages=[page, duplicate_id]).to_dict()

    duplicate_asset = ChapterPage("page-2", "pages/01.kra", "panel-2")
    with pytest.raises(ValueError, match="document assets must be unique"):
        Project(title="Chapter", chapter_pages=[page, duplicate_asset]).to_dict()

    duplicate_panel = ChapterPage("page-2", "pages/02.kra", "panel-1")
    with pytest.raises(ValueError, match="panel ids must be unique"):
        Project(title="Chapter", chapter_pages=[page, duplicate_panel]).to_dict()


def test_chapter_page_round_trips_with_status_and_notes(tmp_path):
    project = Project(
        title="Chapter",
        chapter_pages=[
            ChapterPage(
                "page-1",
                "pages/01.kra",
                "panel-1",
                status=PageStatus.REVIEWED,
                notes="Double-check the hair highlight.",
            )
        ],
    )
    save_project(tmp_path, project)
    assert load_project(tmp_path) == project


def test_signal_weights_default_to_an_even_split():
    weights = SignalWeights()
    assert weights.adjacency_weight == 0.5
    assert weights.name_weight == 0.5
    assert weights.update_count == 0


def test_signal_weights_reject_invalid_values():
    with pytest.raises(ValueError, match="must sum to one"):
        SignalWeights(adjacency_weight=0.6, name_weight=0.6)
    with pytest.raises(ValueError, match="adjacency weight"):
        SignalWeights(adjacency_weight=-0.1, name_weight=1.1)
    with pytest.raises(ValueError, match="update count"):
        SignalWeights(update_count=-1)


def test_signal_weights_round_trip(tmp_path):
    project = Project(
        title="Learning",
        signal_weights=SignalWeights(adjacency_weight=0.7, name_weight=0.3, update_count=4),
    )
    save_project(tmp_path, project)
    assert load_project(tmp_path) == project


def test_defaults_keep_multiple_recovery_revisions():
    project = Project(title="Recovery")
    assert project.autosave.enabled
    assert project.autosave.recovery_revisions > 1


def test_save_rotates_bounded_recovery_history(tmp_path):
    project = Project(title="Version zero")
    project.autosave.recovery_revisions = 2
    save_project(tmp_path, project)
    for title in ("Version one", "Version two", "Version three"):
        project.title = title
        save_project(tmp_path, project)

    recovery = tmp_path / ".recovery"
    assert json.loads((recovery / "project.1.json").read_text())["title"] == "Version two"
    assert json.loads((recovery / "project.2.json").read_text())["title"] == "Version one"
    assert not (recovery / "project.3.json").exists()


def test_failed_atomic_replace_preserves_existing_manifest(tmp_path, monkeypatch):
    manifest = save_project(tmp_path, Project(title="Original"))
    original = manifest.read_text()
    real_replace = os.replace

    def fail_replace(source, destination):
        if destination == manifest:
            raise OSError("simulated replace failure")
        return real_replace(source, destination)

    monkeypatch.setattr("project.storage.os.replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        save_project(tmp_path, Project(title="Replacement"))

    assert manifest.read_text() == original


def test_future_project_schema_fails_without_replacing_current_file(tmp_path):
    project = Project(title="Supported")
    manifest = save_project(tmp_path, project)
    original = manifest.read_text()
    payload = json.loads(original)
    payload["schema_version"] = 999
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported project schema version"):
        load_project(tmp_path)

    assert json.loads(manifest.read_text())["schema_version"] == 999


def test_legacy_migration_is_deterministic_and_privacy_preserving():
    legacy = {
        "schema_version": 0,
        "id": "project-1",
        "title": "Legacy practice",
        "created_at": "2026-08-01T00:00:00+00:00",
        "updated_at": "2026-08-02T00:00:00+00:00",
        "recovery_revisions": 5,
        "exercises": [],
    }

    first = migrate_project_payload(legacy)
    second = migrate_project_payload(legacy)

    assert first == second
    assert first["consent"] == {
        "retain_artwork_in_history": False,
        "contribute_to_global_profile": False,
        "retain_learning_progress": True,
    }
    assert Project.from_dict(first).autosave.recovery_revisions == 5
    assert legacy["schema_version"] == 0


def test_version_one_migration_adds_review_records_without_artwork(tmp_path):
    payload = Project(title="Version one").to_dict()
    payload["schema_version"] = 1
    payload["progress"] = {
        "exercises": [
            {
                "exercise_id": "head",
                "attempts": [{"exercise_id": "head", "id": "a", "started_at": "time"}],
            }
        ]
    }
    migrated = migrate_project_payload(payload)
    assert migrated["schema_version"] == 13
    assert migrated["progress"]["exercises"][0]["attempts"][0]["reviews"] == []
    assert migrate_project_payload(payload) == migrated


def test_version_two_migration_enables_existing_project_progress_and_feedback_slot():
    payload = Project(title="Version two").to_dict()
    payload["schema_version"] = 2
    del payload["consent"]["retain_learning_progress"]
    payload["progress"] = {
        "exercises": [
            {
                "exercise_id": "head",
                "attempts": [
                    {
                        "exercise_id": "head",
                        "id": "a",
                        "started_at": "time",
                        "reviews": [
                            {
                                "id": "r",
                                "exercise_version": "1",
                                "method_id": "method",
                                "rubric_id": "rubric",
                                "rubric_version": "1",
                                "measurements": {},
                                "explanations": [],
                            }
                        ],
                    }
                ],
            }
        ]
    }

    migrated = migrate_project_payload(payload)

    assert migrated["schema_version"] == 13
    assert migrated["consent"]["retain_learning_progress"] is True
    review = migrated["progress"]["exercises"][0]["attempts"][0]["reviews"][0]
    assert review["artist_feedback"] is None


def test_version_three_migration_adds_editable_feedback_policy():
    payload = Project(title="Version three").to_dict()
    payload["schema_version"] = 3
    del payload["feedback_policy"]

    migrated = migrate_project_payload(payload)

    assert migrated["schema_version"] == 13
    assert migrated["feedback_policy"] == {
        "retain_revision_history": False,
        "note_character_limit": 2000,
    }
    assert Project.from_dict(migrated).feedback_policy == FeedbackPolicy()


def test_version_four_migration_adds_identity_card_defaults():
    payload = Project(title="Version four").to_dict()
    payload["schema_version"] = 4
    del payload["identity_card_policy"]
    del payload["identity_card"]
    del payload["identity_card_history"]

    migrated = migrate_project_payload(payload)

    assert migrated["schema_version"] == 13
    assert migrated["identity_card_policy"] == {"retain_revision_history": False}
    assert migrated["identity_card"] is None
    assert migrated["identity_card_history"] == []


def test_version_five_migration_adds_decision_rationale():
    payload = Project(title="Version five").to_dict()
    payload["schema_version"] = 5
    payload["progress"] = {
        "exercises": [
            {
                "exercise_id": "head",
                "attempts": [
                    {
                        "exercise_id": "head",
                        "id": "a",
                        "started_at": "time",
                        "reviews": [
                            {
                                "id": "r",
                                "exercise_version": "1",
                                "method_id": "method",
                                "rubric_id": "rubric",
                                "rubric_version": "1",
                                "measurements": {},
                                "explanations": [],
                            }
                        ],
                    }
                ],
            }
        ]
    }
    migrated = migrate_project_payload(payload)
    review = migrated["progress"]["exercises"][0]["attempts"][0]["reviews"][0]
    assert migrated["schema_version"] == 13
    assert review["suggestion_decision_rationale"] is None


def test_version_six_migration_adds_capstone_rationale_policy_and_history():
    payload = Project(title="Version six").to_dict()
    payload["schema_version"] = 6
    del payload["capstone_policy"]
    migrated = migrate_project_payload(payload)
    assert migrated["schema_version"] == 13
    assert migrated["capstone_policy"] == {"retain_rationale_history": False}


def test_version_seven_migration_adds_review_import_provenance():
    payload = Project(title="Version seven").to_dict()
    payload["schema_version"] = 7
    migrated = migrate_project_payload(payload)
    assert migrated["schema_version"] == 13


def test_version_eight_migration_adds_style_bible_assets():
    payload = Project(title="Version eight").to_dict()
    payload["schema_version"] = 8
    del payload["style_bible_assets"]
    migrated = migrate_project_payload(payload)
    assert migrated["schema_version"] == 13
    assert migrated["style_bible_assets"] == []


def test_version_nine_migration_adds_correspondence_set_assets():
    payload = Project(title="Version nine").to_dict()
    payload["schema_version"] = 9
    del payload["correspondence_set_assets"]
    migrated = migrate_project_payload(payload)
    assert migrated["schema_version"] == 13
    assert migrated["correspondence_set_assets"] == []


def test_version_ten_migration_adds_study_consent_and_sessions():
    payload = Project(title="Version ten").to_dict()
    payload["schema_version"] = 10
    del payload["study_consent"]
    del payload["study_sessions"]
    migrated = migrate_project_payload(payload)
    assert migrated["schema_version"] == 13
    assert migrated["study_consent"] == {}
    assert migrated["study_sessions"] == []


def test_version_eleven_migration_adds_chapter_pages():
    payload = Project(title="Version eleven").to_dict()
    payload["schema_version"] = 11
    del payload["chapter_pages"]
    migrated = migrate_project_payload(payload)
    assert migrated["schema_version"] == 13
    assert migrated["chapter_pages"] == []


def test_version_twelve_migration_adds_default_signal_weights():
    payload = Project(title="Version twelve").to_dict()
    payload["schema_version"] = 12
    del payload["signal_weights"]
    migrated = migrate_project_payload(payload)
    assert migrated["schema_version"] == 13
    assert migrated["signal_weights"] == {}
    assert Project.from_dict(migrated).signal_weights == SignalWeights()


def test_learning_progress_retention_defaults_enabled_but_can_be_disabled():
    assert Project(title="Learning").consent.retain_learning_progress is True
    project = Project(
        title="No progress",
        consent=Consent(retain_learning_progress=False),
        progress=ProjectProgress([ExerciseProgress("head", [Attempt("head")])]),
    )
    with pytest.raises(ValueError, match="retention is disabled"):
        project.to_dict()


def test_global_profile_is_a_separate_opt_in_file(tmp_path):
    project = Project(title="Local metrics")
    save_project(tmp_path / "project", project)
    profile = LearnerProfile(
        aggregate_metrics={"attempts": 4.0},
        contributing_project_ids=[project.id],
    )

    profile_path = save_profile(tmp_path / "private" / "learner-profile.json", profile)

    assert load_profile(profile_path) == profile
    assert "aggregate_metrics" not in (tmp_path / "project" / "project.json").read_text()
