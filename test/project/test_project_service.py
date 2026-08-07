"""Tests for portable exercise-project creation."""

import pytest

from project import (
    AdviceRating,
    SuggestionDecision,
    configure_capstone_policy,
    configure_feedback_policy,
    configure_identity_card_policy,
    configure_progress_retention,
    create_exercise_project,
    decide_attempt_review,
    load_project,
    project_progress_snapshot,
    record_advice_feedback,
    record_attempt_review,
    revise_capstone_decision_rationale,
    set_attempt_completion,
    upsert_identity_card,
)


def test_creates_portable_manifest_around_new_krita_document(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"krita document placeholder")
    project = create_exercise_project(tmp_path, title="Head practice", attempt_id="attempt-1")
    loaded = load_project(tmp_path)
    assert loaded == project
    assert loaded.document_asset == "artwork/attempt-001.kra"
    attempt = loaded.progress.exercises[0].attempts[0]
    assert attempt.id == "attempt-1"
    assert attempt.artwork_asset is None
    assert not loaded.consent.retain_artwork_in_history


def test_creates_orientation_project_with_its_own_stable_exercise_id(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"krita document placeholder")
    create_exercise_project(
        tmp_path,
        title="Rotation sheet",
        attempt_id="orientation-1",
        exercise_id="anime-head-orientation",
    )

    exercise = load_project(tmp_path).progress.exercises[0]
    assert exercise.exercise_id == "anime-head-orientation"
    assert exercise.attempts[0].exercise_id == "anime-head-orientation"


def test_refuses_unrelated_files_or_existing_manifest(tmp_path):
    (tmp_path / "unrelated.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError, match="must be empty"):
        create_exercise_project(tmp_path, title="Head", attempt_id="a")


@pytest.mark.parametrize("asset", ["/absolute.kra", "../escape.kra", "artwork\\bad.kra"])
def test_project_document_asset_must_remain_portable(tmp_path, asset):
    with pytest.raises(ValueError, match="safe relative"):
        create_exercise_project(
            tmp_path, title="Head", document_asset=asset, attempt_id="attempt-1"
        )


def test_records_and_decides_privacy_safe_review(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(tmp_path, title="Head", attempt_id="attempt-1")
    payload = {
        "id": "review-1",
        "exercise_version": "1",
        "method_id": "method",
        "rubric_id": "rubric",
        "rubric_version": "1",
        "measurements": {"axis": 0.8},
        "explanations": ["Straighten the axis."],
        "redlines": [{"geometry": [[0, 0], [1, 1]]}],
    }
    record_attempt_review(tmp_path, attempt_id="attempt-1", review_payload=payload)
    assert decide_attempt_review(
        tmp_path,
        attempt_id="attempt-1",
        review_id="review-1",
        decision=SuggestionDecision.ACCEPTED,
    )
    review = load_project(tmp_path).progress.exercises[0].attempts[0].reviews[0]
    assert review.suggestion_decision is SuggestionDecision.ACCEPTED
    assert not hasattr(review, "redlines")


def test_capstone_requires_rationale_and_dashboard_retains_rubrics(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(
        tmp_path,
        title="Capstone",
        attempt_id="capstone-1",
        exercise_id="anime-head-review",
    )
    for review_id, rubric_id in (("r1", "construction"), ("r2", "cel-values")):
        record_attempt_review(
            tmp_path,
            attempt_id="capstone-1",
            review_payload={
                "id": review_id,
                "exercise_version": "1",
                "method_id": "method",
                "rubric_id": rubric_id,
                "rubric_version": "1",
                "measurements": {"rubric_consistency": 0.8},
                "explanations": ["Review explanation."],
            },
        )
    with pytest.raises(ValueError, match="require an artist rationale"):
        decide_attempt_review(
            tmp_path,
            attempt_id="capstone-1",
            review_id="r1",
            decision=SuggestionDecision.ACCEPTED,
        )
    assert decide_attempt_review(
        tmp_path,
        attempt_id="capstone-1",
        review_id="r1",
        decision=SuggestionDecision.DEFERRED,
        rationale="I need another construction pass before choosing.",
    )
    snapshot = project_progress_snapshot(tmp_path)
    dashboard = snapshot["capstone_dashboard"]
    assert dashboard["pending_decision_count"] == 1
    assert {item["rubric_id"] for item in dashboard["rubrics"]} == {
        "construction",
        "cel-values",
    }
    assert dashboard["rubrics"][1]["measurements"] == {"rubric_consistency": 0.8}
    assert dashboard["next_stage"]["stage_id"] == "front_structure"
    assert dashboard["ready_for_manual_completion"] is False

    assert configure_capstone_policy(tmp_path, retain_rationale_history=True)
    assert revise_capstone_decision_rationale(
        tmp_path,
        attempt_id="capstone-1",
        review_id="r1",
        rationale="After another pass, I still need more construction evidence.",
    )
    revised = load_project(tmp_path).progress.exercises[0].attempts[0].reviews[0]
    assert revised.suggestion_decision is SuggestionDecision.DEFERRED
    assert len(revised.suggestion_decision_rationale_history) == 1
    assert revised.suggestion_decision_rationale_history[0].revised_at


def test_records_advice_feedback_with_idempotent_retry_and_recovery(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(tmp_path, title="Head", attempt_id="attempt-1")
    record_attempt_review(
        tmp_path,
        attempt_id="attempt-1",
        review_payload={
            "id": "review-1",
            "exercise_version": "1",
            "method_id": "method",
            "rubric_id": "rubric",
            "rubric_version": "1",
            "measurements": {"axis": 0.8},
            "explanations": ["Straighten the axis."],
        },
    )

    assert record_advice_feedback(
        tmp_path,
        attempt_id="attempt-1",
        review_id="review-1",
        rating=AdviceRating.HELPFUL,
        note="The axis example helped.",
    )
    assert not record_advice_feedback(
        tmp_path,
        attempt_id="attempt-1",
        review_id="review-1",
        rating=AdviceRating.HELPFUL,
        note="The axis example helped.",
    )
    review = load_project(tmp_path).progress.exercises[0].attempts[0].reviews[0]
    assert review.artist_feedback is not None
    assert review.artist_feedback.rating is AdviceRating.HELPFUL
    assert record_advice_feedback(
        tmp_path,
        attempt_id="attempt-1",
        review_id="review-1",
        rating=AdviceRating.INCORRECT,
    )
    revised = load_project(tmp_path).progress.exercises[0].attempts[0].reviews[0]
    assert revised.artist_feedback is not None
    assert revised.artist_feedback.rating is AdviceRating.INCORRECT
    assert revised.artist_feedback.revision == 2
    assert revised.artist_feedback_history == []


def test_feedback_revision_history_and_note_limit_are_project_settings(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(tmp_path, title="Head", attempt_id="attempt-1")
    record_attempt_review(
        tmp_path,
        attempt_id="attempt-1",
        review_payload={
            "id": "review-1",
            "exercise_version": "1",
            "method_id": "method",
            "rubric_id": "rubric",
            "rubric_version": "1",
        },
    )
    assert configure_feedback_policy(
        tmp_path, retain_revision_history=True, note_character_limit=12
    )
    record_advice_feedback(
        tmp_path,
        attempt_id="attempt-1",
        review_id="review-1",
        rating=AdviceRating.HELPFUL,
        note="Useful",
    )
    record_advice_feedback(
        tmp_path,
        attempt_id="attempt-1",
        review_id="review-1",
        rating=AdviceRating.UNHELPFUL,
        note="Needs detail",
    )
    review = load_project(tmp_path).progress.exercises[0].attempts[0].reviews[0]
    assert [item.rating for item in review.artist_feedback_history] == [AdviceRating.HELPFUL]
    assert review.artist_feedback is not None and review.artist_feedback.revision == 2
    with pytest.raises(ValueError, match="12-character limit"):
        record_advice_feedback(
            tmp_path,
            attempt_id="attempt-1",
            review_id="review-1",
            rating=AdviceRating.INCORRECT,
            note="This is much too long",
        )

    assert configure_feedback_policy(
        tmp_path, retain_revision_history=False, note_character_limit=12
    )
    assert (
        load_project(tmp_path).progress.exercises[0].attempts[0].reviews[0].artist_feedback_history
        == []
    )


def test_progress_snapshot_and_explicit_clear_disable_policy(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(tmp_path, title="Head", attempt_id="attempt-1")
    snapshot = project_progress_snapshot(tmp_path)
    assert snapshot["retain_learning_progress"] is True
    assert snapshot["exercises"][0]["attempts"][0]["attempt_id"] == "attempt-1"

    with pytest.raises(ValueError, match="explicitly cleared"):
        configure_progress_retention(tmp_path, enabled=False)
    assert configure_progress_retention(tmp_path, enabled=False, clear_existing=True)
    assert project_progress_snapshot(tmp_path) == {
        "retain_learning_progress": False,
        "feedback_policy": {
            "retain_revision_history": False,
            "note_character_limit": 2000,
        },
        "identity_card_policy": {"retain_revision_history": False},
        "capstone_policy": {"retain_rationale_history": False},
        "identity_card": None,
        "exercises": [],
        "capstone_dashboard": {
            "attempt_count": 0,
            "review_count": 0,
            "pending_decision_count": 0,
            "rubrics": [],
            "collection_stages": [],
            "next_stage": None,
            "ready_for_manual_completion": False,
        },
    }
    assert configure_progress_retention(tmp_path, enabled=True)
    assert not configure_progress_retention(tmp_path, enabled=True)


def test_identity_card_edits_and_optional_history_are_portable(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(tmp_path, title="Identity", attempt_id="attempt-1")
    anchors = [
        {"key": key, "value": 0.4 + index * 0.05, "description": key + " anchor"}
        for index, key in enumerate(
            ["cranial_radius", "lower_face", "eye_span", "jaw_span", "mouth_span"]
        )
    ]
    assert upsert_identity_card(tmp_path, name="Aiko", anchors=anchors)
    assert not upsert_identity_card(tmp_path, name="Aiko", anchors=anchors)
    first = project_progress_snapshot(tmp_path)["identity_card"]
    assert first["revision"] == 1
    assert first["anchors"][0]["description"] == "cranial_radius anchor"

    assert configure_identity_card_policy(tmp_path, retain_revision_history=True)
    changed = [dict(item) for item in anchors]
    changed[0]["value"] = 0.7
    assert upsert_identity_card(tmp_path, name="Aiko", anchors=changed)
    project = load_project(tmp_path)
    assert project.identity_card.revision == 2
    assert len(project.identity_card_history) == 1
    assert configure_identity_card_policy(tmp_path, retain_revision_history=False)
    assert load_project(tmp_path).identity_card_history == []


def test_attempt_completion_is_explicit_reversible_and_idempotent(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(tmp_path, title="Head", attempt_id="attempt-1")

    assert set_attempt_completion(tmp_path, attempt_id="attempt-1", completed=True)
    snapshot = project_progress_snapshot(tmp_path)
    assert snapshot["exercises"][0]["attempts"][0]["completed_at"] is not None
    assert not set_attempt_completion(tmp_path, attempt_id="attempt-1", completed=True)
    assert set_attempt_completion(tmp_path, attempt_id="attempt-1", completed=False)
    assert (
        project_progress_snapshot(tmp_path)["exercises"][0]["attempts"][0]["completed_at"] is None
    )
