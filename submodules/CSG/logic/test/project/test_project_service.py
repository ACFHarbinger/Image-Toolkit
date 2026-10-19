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
    PageStatus,
    ReviewRecord,
    SignalWeights,
    SuggestionDecision,
    add_chapter_page,
    attach_correspondence_set,
    attach_editor_document,
    attach_style_bible,
    configure_capstone_policy,
    configure_feedback_policy,
    configure_identity_card_policy,
    configure_progress_retention,
    configure_study_consent,
    create_exercise_project,
    create_project,
    decide_attempt_review,
    detach_correspondence_set,
    detach_editor_document,
    detach_style_bible,
    import_compatible_capstone_review,
    import_reference_asset,
    load_project,
    next_pending_chapter_page,
    project_correspondence_set_payload,
    project_progress_snapshot,
    propagate_project_correspondence,
    rank_correspondence_materials,
    record_advice_feedback,
    record_attempt_review,
    record_correspondence_choice,
    record_study_session,
    revise_capstone_decision_rationale,
    save_project,
    set_attempt_completion,
    set_chapter_page_status,
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


def test_create_project_makes_a_bare_manifest_with_no_exercise(tmp_path):
    project = create_project(tmp_path, title="Standalone editor doc")
    loaded = load_project(tmp_path)
    assert loaded == project
    assert loaded.title == "Standalone editor doc"
    assert loaded.document_asset is None
    assert loaded.progress.exercises == []


def test_create_project_refuses_nonempty_directory(tmp_path):
    (tmp_path / "unrelated.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError, match="must be empty"):
        create_project(tmp_path, title="Head")


def test_create_project_refuses_a_directory_that_already_has_a_project(tmp_path):
    create_project(tmp_path, title="First")
    with pytest.raises(ValueError, match="must be empty"):
        create_project(tmp_path, title="Second")


def test_create_project_can_bind_a_style_bible_and_correspondence_set(tmp_path):
    create_project(tmp_path, title="Standalone editor doc")
    bible = CharacterStyleBible(
        "aiko",
        "Aiko",
        "TV cel",
        [StyleMaterial("hair", "Hair", MaterialPalette("#332233", "#665566", "#110F18"))],
    )
    bible_asset = upsert_project_style_bible(tmp_path, payload=bible.to_dict())
    correspondence_set = CorrespondenceSet(id="editor-correspondence", style_bible_id="aiko")
    correspondence_asset = upsert_project_correspondence_set(
        tmp_path, payload=correspondence_set.to_dict()
    )

    loaded = load_project(tmp_path)
    assert bible_asset in loaded.style_bible_assets
    assert correspondence_asset in loaded.correspondence_set_assets


def test_attach_and_detach_editor_document_without_deleting_files(tmp_path):
    create_project(tmp_path, title="Standalone editor doc")
    document_dir = tmp_path / "canvas" / "main"
    document_dir.mkdir(parents=True)
    (document_dir / "manifest.json").write_text("{}", encoding="utf-8")

    assert attach_editor_document(tmp_path, asset_path="canvas/main")
    assert not attach_editor_document(tmp_path, asset_path="canvas/main")
    assert load_project(tmp_path).editor_document_assets == ["canvas/main"]

    assert detach_editor_document(tmp_path, asset_path="canvas/main")
    assert not detach_editor_document(tmp_path, asset_path="canvas/main")
    assert load_project(tmp_path).editor_document_assets == []
    assert document_dir.exists()  # detaching never deletes files


def test_attach_editor_document_rejects_missing_directory_or_escape(tmp_path):
    create_project(tmp_path, title="Standalone editor doc")
    with pytest.raises(ValueError, match="existing directory"):
        attach_editor_document(tmp_path, asset_path="canvas/missing")
    with pytest.raises(ValueError, match="safe relative"):
        attach_editor_document(tmp_path, asset_path="../escape")


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
        "study": {
            "consent": {"opted_in": False, "consent_version": 1, "consented_at": None},
            "sessions": [],
        },
        "chapter": {"pages": [], "next_pending_page_id": None},
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


def _attach_two_material_bible(tmp_path) -> str:
    reference = tmp_path / "references/front.png"
    reference.parent.mkdir(exist_ok=True)
    reference.write_bytes(b"reference")
    bible = CharacterStyleBible(
        "aiko",
        "Aiko",
        "TV cel",
        [
            StyleMaterial("hair", "Hair", MaterialPalette("#332233", "#665566", "#110F18")),
            StyleMaterial("skin", "Skin", MaterialPalette("#EEDDCC", "#FFEEDD", "#AA8866")),
        ],
        [ReferenceView("front", "Front", "references/front.png")],
    )
    return upsert_project_style_bible(tmp_path, payload=bible.to_dict())


def test_rank_correspondence_materials_orders_by_weighted_confidence(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(tmp_path, title="Color project", attempt_id="attempt-1")
    bible_asset_path = _attach_two_material_bible(tmp_path)

    ranked = rank_correspondence_materials(
        tmp_path,
        bible_asset_path=bible_asset_path,
        region_id="hair-front-large",
        adjacency_agreements={"hair": 0.2, "skin": 0.9},
    )
    # skin wins on the default even split despite zero name overlap, because
    # its adjacency agreement (0.9) dominates hair's higher name_score (1/3).
    assert [item["material_id"] for item in ranked] == ["skin", "hair"]
    by_material = {item["material_id"]: item for item in ranked}
    assert by_material["hair"]["name_score"] > by_material["skin"]["name_score"]
    assert by_material["skin"]["adjacency_score"] > by_material["hair"]["adjacency_score"]

    with pytest.raises(ValueError, match="not bound"):
        rank_correspondence_materials(
            tmp_path,
            bible_asset_path="style-bibles/missing.json",
            region_id="hair-front-large",
            adjacency_agreements={},
        )


def test_record_correspondence_choice_shifts_weights_toward_agreeing_signal(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(tmp_path, title="Color project", attempt_id="attempt-1")
    bible_asset_path = _attach_two_material_bible(tmp_path)
    assert load_project(tmp_path).signal_weights == SignalWeights()

    ranked = rank_correspondence_materials(
        tmp_path,
        bible_asset_path=bible_asset_path,
        region_id="hair-front-large",
        adjacency_agreements={"hair": 0.1, "skin": 0.9},
    )
    weights = record_correspondence_choice(
        tmp_path, chosen_material_id="hair", candidates=ranked
    )
    assert weights.name_weight > weights.adjacency_weight
    assert weights.update_count == 1
    assert load_project(tmp_path).signal_weights == weights


def test_record_correspondence_choice_is_a_no_op_without_a_real_alternative(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(tmp_path, title="Color project", attempt_id="attempt-1")
    starting = load_project(tmp_path).signal_weights
    assert (
        record_correspondence_choice(tmp_path, chosen_material_id="hair", candidates=[])
        == starting
    )
    assert (
        record_correspondence_choice(
            tmp_path,
            chosen_material_id="unknown",
            candidates=[
                {"material_id": "hair", "adjacency_score": 0.5, "name_score": 0.5},
                {"material_id": "skin", "adjacency_score": 0.5, "name_score": 0.5},
            ],
        )
        == starting
    )


def test_configure_study_consent_requires_explicit_clear_on_withdrawal(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    project = create_exercise_project(tmp_path, title="Study", attempt_id="attempt-1")

    assert configure_study_consent(tmp_path, opted_in=True)
    assert not configure_study_consent(tmp_path, opted_in=True)
    assert load_project(tmp_path).study_consent.opted_in

    record_study_session(tmp_path, baseline_attempt_id=project.progress.exercises[0].attempts[0].id)
    with pytest.raises(ValueError, match="explicitly cleared"):
        configure_study_consent(tmp_path, opted_in=False)
    assert configure_study_consent(tmp_path, opted_in=False, clear_existing=True)
    reloaded = load_project(tmp_path)
    assert not reloaded.study_consent.opted_in
    assert reloaded.study_sessions == []


def test_record_study_session_requires_consent_and_known_attempts(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(tmp_path, title="Study", attempt_id="attempt-1")

    with pytest.raises(ValueError, match="explicit study consent"):
        record_study_session(tmp_path, baseline_attempt_id="attempt-1")

    configure_study_consent(tmp_path, opted_in=True)
    with pytest.raises(ValueError, match="attempt identifier"):
        record_study_session(tmp_path, baseline_attempt_id="missing")


def test_record_study_session_accumulates_protocol_fields(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(tmp_path, title="Study", attempt_id="attempt-1")
    configure_study_consent(tmp_path, opted_in=True)

    first = record_study_session(tmp_path, baseline_attempt_id="attempt-1")
    assert first.remedial_exercise_id is None
    assert first.completed_at is None

    second = record_study_session(
        tmp_path,
        baseline_attempt_id="attempt-1",
        remedial_exercise_id="anime-head-front-remedial",
    )
    assert second.id == first.id
    assert second.remedial_exercise_id == "anime-head-front-remedial"

    completed = record_study_session(
        tmp_path,
        baseline_attempt_id="attempt-1",
        explanation_rating=AdviceRating.HELPFUL,
        completed=True,
    )
    assert completed.id == first.id
    assert completed.remedial_exercise_id == "anime-head-front-remedial"
    assert completed.explanation_rating is AdviceRating.HELPFUL
    assert completed.completed_at is not None

    project = load_project(tmp_path)
    assert len(project.study_sessions) == 1

    snapshot = project_progress_snapshot(tmp_path)
    assert snapshot["study"]["consent"]["opted_in"] is True
    assert snapshot["study"]["sessions"] == [
        {
            "session_id": completed.id,
            "baseline_attempt_id": "attempt-1",
            "remedial_exercise_id": "anime-head-front-remedial",
            "redraw_attempt_id": None,
            "explanation_rating": "helpful",
            "completed_at": completed.completed_at,
        }
    ]


def test_add_chapter_page_validates_and_binds_existing_assets(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(tmp_path, title="Chapter", attempt_id="attempt-1")
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "01.kra").write_bytes(b"page one")

    with pytest.raises(ValueError, match="existing regular"):
        add_chapter_page(tmp_path, document_asset="pages/missing.kra", panel_id="panel-1")

    page = add_chapter_page(tmp_path, document_asset="pages/01.kra", panel_id="panel-1")
    assert page.status is PageStatus.PENDING
    assert page.document_asset == "pages/01.kra"
    assert load_project(tmp_path).chapter_pages == [page]


def test_chapter_page_status_transitions_are_explicit_and_idempotent(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(tmp_path, title="Chapter", attempt_id="attempt-1")
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "01.kra").write_bytes(b"page one")
    page = add_chapter_page(tmp_path, document_asset="pages/01.kra", panel_id="panel-1")

    assert set_chapter_page_status(tmp_path, page_id=page.id, status=PageStatus.IN_PROGRESS)
    assert not set_chapter_page_status(tmp_path, page_id=page.id, status=PageStatus.IN_PROGRESS)
    assert set_chapter_page_status(
        tmp_path, page_id=page.id, status=PageStatus.IN_PROGRESS, notes="Retry hair region."
    )
    reloaded = load_project(tmp_path).chapter_pages[0]
    assert reloaded.status is PageStatus.IN_PROGRESS
    assert reloaded.notes == "Retry hair region."

    with pytest.raises(ValueError, match="missing or ambiguous"):
        set_chapter_page_status(tmp_path, page_id="missing", status=PageStatus.ACCEPTED)


def test_next_pending_chapter_page_follows_queue_order(tmp_path):
    artwork = tmp_path / "artwork/attempt-001.kra"
    artwork.parent.mkdir()
    artwork.write_bytes(b"document")
    create_exercise_project(tmp_path, title="Chapter", attempt_id="attempt-1")
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    for name in ("01.kra", "02.kra", "03.kra"):
        (pages_dir / name).write_bytes(b"page")
    first = add_chapter_page(tmp_path, document_asset="pages/01.kra", panel_id="panel-1")
    second = add_chapter_page(tmp_path, document_asset="pages/02.kra", panel_id="panel-2")
    add_chapter_page(tmp_path, document_asset="pages/03.kra", panel_id="panel-3")

    assert next_pending_chapter_page(tmp_path).id == first.id
    set_chapter_page_status(tmp_path, page_id=first.id, status=PageStatus.ACCEPTED)
    assert next_pending_chapter_page(tmp_path).id == second.id

    snapshot = project_progress_snapshot(tmp_path)
    assert snapshot["chapter"]["next_pending_page_id"] == second.id
    assert [page["status"] for page in snapshot["chapter"]["pages"]] == [
        "accepted",
        "pending",
        "pending",
    ]


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
