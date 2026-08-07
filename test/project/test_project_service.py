"""Tests for portable exercise-project creation."""

import pytest

from project import (
    SuggestionDecision,
    create_exercise_project,
    decide_attempt_review,
    load_project,
    record_attempt_review,
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
