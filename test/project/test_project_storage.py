"""Tests for versioned project and learner-profile persistence."""

from __future__ import annotations

import json
import os

import pytest

from cel_shaded_generator.project import (
    Attempt,
    Consent,
    ExerciseProgress,
    Feedback,
    LearnerProfile,
    Project,
    ProjectProgress,
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
                            artwork_asset="assets/attempt-1.kra",
                        )
                    ],
                )
            ]
        ),
    )

    save_project(tmp_path, project)

    assert load_project(tmp_path) == project


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

    monkeypatch.setattr("cel_shaded_generator.project.storage.os.replace", fail_replace)
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
    }
    assert Project.from_dict(first).autosave.recovery_revisions == 5
    assert legacy["schema_version"] == 0


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
