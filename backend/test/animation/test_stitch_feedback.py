"""Unit tests for backend/src/animation/stitch_feedback.py."""

import json
import pytest
from backend.src.animation.stitch_feedback import (
    log_stitch_feedback,
    load_stitch_feedback,
)


def test_log_and_load_stitch_feedback(tmp_path, monkeypatch):
    import backend.src.animation.stitch_feedback as sf
    test_file = tmp_path / "stitch_feedback.jsonl"
    monkeypatch.setattr(sf, "FEEDBACK_FILE", test_file)

    assert sf.load_stitch_feedback() == []

    rec1 = sf.log_stitch_feedback("test_01", 5, engine="asp", asp_score=0.92)
    rec2 = sf.log_stitch_feedback("test_02", 2, engine="opencv")

    assert rec1["user_rating"] == 5
    assert rec2["user_rating"] == 2

    loaded = sf.load_stitch_feedback()
    assert len(loaded) == 2
    assert loaded[0]["test_id"] == "test_01"
    assert loaded[1]["test_id"] == "test_02"
