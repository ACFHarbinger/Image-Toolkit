"""Tests for portable exercise-project creation."""

import pytest

from colorization import (
    CharacterStyleBible,
    CorrespondenceSet,
    MaterialPalette,
    ReferenceView,
    RegionCorrespondence,
    StyleMaterial,
    save_correspondence_set,
    save_style_bible,
)
from project import (
    AdviceRating,
    Attempt,
    ExerciseProgress,
    ReviewRecord,
    SuggestionDecision,
    attach_correspondence_set,
    attach_style_bible,
    configure_capstone_policy,
    configure_feedback_policy,
    configure_identity_card_policy,
    configure_progress_retention,
    create_exercise_project,
    decide_attempt_review,
    detach_correspondence_set,
    detach_style_bible,
    import_compatible_capstone_review,
    import_reference_asset,
    load_project,
    project_correspondence_set_payload,
    project_progress_snapshot,
    propagate_project_correspondence,
    record_advice_feedback,
    record_attempt_review,
    revise_capstone_decision_rationale,
    save_project,
    set_attempt_completion,
    upsert_identity_card,
    upsert_project_correspondence_set,
    upsert_project_style_bible,
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


def test_capstone_import_copies_compatible_evidence_with_new_judgment(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(
        tmp_path,
        title="Capstone import",
        attempt_id="capstone-1",
        exercise_id="anime-head-review",
    )
    project = load_project(tmp_path)
    source_review = ReviewRecord(
        "source-review",
        "1.0.0",
        "anime-head-construction-v1",
        "anime-head-front-structure",
        "1.0.0",
        {"head_axis_consistency": 0.8},
        ["Prior lesson evidence."],
    )
    project.progress.exercises.append(
        ExerciseProgress(
            "anime-head-front-construction",
            [
                Attempt(
                    "anime-head-front-construction", id="source-attempt", reviews=[source_review]
                )
            ],
        )
    )
    save_project(tmp_path, project)

    imported = import_compatible_capstone_review(
        tmp_path,
        target_attempt_id="capstone-1",
        source_attempt_id="source-attempt",
        source_review_id="source-review",
        decision=SuggestionDecision.ACCEPTED,
        rationale="This recent compatible construction still represents my current method.",
    )
    assert imported.id != source_review.id
    assert imported.source_attempt_id == "source-attempt"
    assert imported.source_review_id == "source-review"
    assert imported.suggestion_decision is SuggestionDecision.ACCEPTED
    assert imported.measurements == source_review.measurements


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
            "import_candidates": [],
        },
        "style_bibles": [],
        "correspondence_sets": [],
    }
    assert configure_progress_retention(tmp_path, enabled=True)
    assert not configure_progress_retention(tmp_path, enabled=True)


def test_attach_and_detach_project_local_style_bible_without_deleting_assets(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(tmp_path, title="Color project", attempt_id="attempt-1")
    reference = tmp_path / "references/front.png"
    reference.parent.mkdir()
    reference.write_bytes(b"reference")
    bible_path = tmp_path / "style-bibles/aiko.json"
    save_style_bible(
        bible_path,
        CharacterStyleBible(
            "aiko",
            "Aiko",
            "TV cel",
            [StyleMaterial("hair", "Hair", MaterialPalette("#332233", "#665566", "#110F18"))],
            [ReferenceView("front", "Front", "references/front.png")],
        ),
    )
    assert attach_style_bible(tmp_path, asset_path="style-bibles/aiko.json")
    assert not attach_style_bible(tmp_path, asset_path="style-bibles/aiko.json")
    summary = project_progress_snapshot(tmp_path)["style_bibles"][0]
    assert summary == {
        "asset_path": "style-bibles/aiko.json",
        "id": "aiko",
        "character_name": "Aiko",
        "style_name": "TV cel",
        "material_count": 1,
        "reference_view_count": 1,
    }
    assert detach_style_bible(tmp_path, asset_path="style-bibles/aiko.json")
    assert bible_path.exists() and reference.exists()


def test_style_bible_binding_rejects_missing_escape_and_symlink(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(tmp_path, title="Color project", attempt_id="attempt-1")
    with pytest.raises(ValueError, match="safe relative"):
        attach_style_bible(tmp_path, asset_path="../outside.json")
    with pytest.raises(ValueError, match="existing regular"):
        attach_style_bible(tmp_path, asset_path="style-bibles/missing.json")
    outside = tmp_path.parent / "outside-style-bible.json"
    outside.write_text("{}", encoding="utf-8")
    link = tmp_path / "style-bibles/link.json"
    link.parent.mkdir()
    link.symlink_to(outside)
    with pytest.raises(ValueError, match="non-symlink"):
        attach_style_bible(tmp_path, asset_path="style-bibles/link.json")


def test_import_reference_and_upsert_bible_are_portable_and_idempotent(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(tmp_path, title="Color project", attempt_id="attempt-1")
    external = tmp_path.parent / "Aiko Front!.PNG"
    external.write_bytes(b"image bytes")
    reference = import_reference_asset(tmp_path, source_path=str(external))
    assert reference.startswith("references/Aiko-Front-") and reference.endswith(".png")
    assert import_reference_asset(tmp_path, source_path=str(external)) == reference
    bible = CharacterStyleBible(
        "aiko",
        "Aiko",
        "TV cel",
        [StyleMaterial("hair", "Hair", MaterialPalette("#332233", "#665566", "#110F18"))],
        [ReferenceView("front", "Front", reference)],
    )
    assert upsert_project_style_bible(tmp_path, payload=bible.to_dict()) == (
        "style-bibles/aiko.json"
    )
    assert load_project(tmp_path).style_bible_assets == ["style-bibles/aiko.json"]


def test_attach_and_detach_project_local_correspondence_set_without_deleting_assets(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(tmp_path, title="Color project", attempt_id="attempt-1")
    set_path = tmp_path / "correspondence/aiko-page-1.json"
    save_correspondence_set(
        set_path,
        CorrespondenceSet(
            "aiko-page-1",
            "aiko-tv",
            [RegionCorrespondence("r1", "hair-front-large", "hair")],
        ),
    )
    assert attach_correspondence_set(tmp_path, asset_path="correspondence/aiko-page-1.json")
    assert not attach_correspondence_set(tmp_path, asset_path="correspondence/aiko-page-1.json")
    summary = project_progress_snapshot(tmp_path)["correspondence_sets"][0]
    assert summary == {
        "asset_path": "correspondence/aiko-page-1.json",
        "id": "aiko-page-1",
        "style_bible_id": "aiko-tv",
        "correspondence_count": 1,
    }
    assert detach_correspondence_set(tmp_path, asset_path="correspondence/aiko-page-1.json")
    assert set_path.exists()


def test_correspondence_set_binding_rejects_missing_escape_and_symlink(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(tmp_path, title="Color project", attempt_id="attempt-1")
    with pytest.raises(ValueError, match="safe relative"):
        attach_correspondence_set(tmp_path, asset_path="../outside.json")
    with pytest.raises(ValueError, match="existing regular"):
        attach_correspondence_set(tmp_path, asset_path="correspondence/missing.json")
    outside = tmp_path.parent / "outside-correspondence.json"
    outside.write_text("{}", encoding="utf-8")
    link = tmp_path / "correspondence/link.json"
    link.parent.mkdir()
    link.symlink_to(outside)
    with pytest.raises(ValueError, match="non-symlink"):
        attach_correspondence_set(tmp_path, asset_path="correspondence/link.json")


def test_upsert_and_propagate_project_correspondence_set(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(tmp_path, title="Color project", attempt_id="attempt-1")
    correspondence_set = CorrespondenceSet(
        "aiko-page-1",
        "aiko-tv",
        [RegionCorrespondence("r1", "hair-front-large", "hair")],
    )
    relative = upsert_project_correspondence_set(tmp_path, payload=correspondence_set.to_dict())
    assert relative == "correspondence/aiko-page-1.json"
    assert load_project(tmp_path).correspondence_set_assets == [relative]
    assert upsert_project_correspondence_set(tmp_path, payload=correspondence_set.to_dict()) == (
        relative
    )

    propagated = propagate_project_correspondence(
        tmp_path,
        asset_path=relative,
        source_id="r1",
        target_region_ids=["hair-back-large"],
    )
    assert {item["region_id"] for item in propagated["correspondences"]} == {
        "hair-front-large",
        "hair-back-large",
    }
    assert project_correspondence_set_payload(tmp_path, asset_path=relative) == propagated

    with pytest.raises(ValueError, match="not bound"):
        project_correspondence_set_payload(tmp_path, asset_path="correspondence/missing.json")


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
