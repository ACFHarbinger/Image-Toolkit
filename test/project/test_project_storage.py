"""Tests for versioned project and learner-profile persistence."""

from __future__ import annotations

import json
import os

import pytest

from project import (
    AdviceFeedback,
    AdviceRating,
    Attempt,
    Consent,
    ExerciseProgress,
    Feedback,
    FeedbackPolicy,
    LearnerProfile,
    Project,
    ProjectProgress,
    ReviewRecord,
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
    assert migrated["schema_version"] == 5
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

    assert migrated["schema_version"] == 5
    assert migrated["consent"]["retain_learning_progress"] is True
    review = migrated["progress"]["exercises"][0]["attempts"][0]["reviews"][0]
    assert review["artist_feedback"] is None


def test_version_three_migration_adds_editable_feedback_policy():
    payload = Project(title="Version three").to_dict()
    payload["schema_version"] = 3
    del payload["feedback_policy"]

    migrated = migrate_project_payload(payload)

    assert migrated["schema_version"] == 5
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

    assert migrated["schema_version"] == 5
    assert migrated["identity_card_policy"] == {"retain_revision_history": False}
    assert migrated["identity_card"] is None
    assert migrated["identity_card_history"] == []


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
