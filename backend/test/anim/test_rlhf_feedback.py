"""
Tests for FeedbackStore / StitchFeedback (§Issue 6A / S87).

Validates that the RLHF feedback persistence layer correctly stores and retrieves
stitch quality annotations without requiring GPU or file-system state.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import numpy as np

from backend.src.anim.rlhf.feedback_store import (
    FeedbackStore,
    StitchAnnotation,
    StitchFeedback,
)
from backend.src.anim.rlhf.reward_model import StitchRewardModel, MC_DROPOUT_UNCERTAINTY_THRESHOLD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_feedback(**kwargs) -> StitchFeedback:
    defaults = {
        "image_path": "/tmp/out.png",
        "image_hash": "abc123",
        "overall_rating": 7.5,
    }
    defaults.update(kwargs)
    return StitchFeedback(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStitchFeedbackRoundtrip:
    def test_to_dict_from_dict_roundtrip(self):
        ann = StitchAnnotation(
            x=0.1, y=0.2, w=0.8, h=0.3, flaw_type="seam", severity=0.6
        )
        fb = _make_feedback(
            overall_rating=8.0,
            annotations=[ann],
            pipeline_config={"ASP_SP_SOFT_PX": "6"},
        )
        d = fb.to_dict()
        restored = StitchFeedback.from_dict(d)
        assert restored.overall_rating == 8.0
        assert len(restored.annotations) == 1
        assert restored.annotations[0].flaw_type == "seam"
        assert restored.pipeline_config == {"ASP_SP_SOFT_PX": "6"}

    def test_empty_annotations_roundtrip(self):
        fb = _make_feedback()
        restored = StitchFeedback.from_dict(fb.to_dict())
        assert restored.annotations == []


class TestFeedbackStoreAdd:
    def test_add_and_iter(self, tmp_path):
        store = FeedbackStore(path=str(tmp_path / "rlhf.jsonl"))
        fb = _make_feedback(overall_rating=5.0)
        store.add(fb)
        records = store.all()
        assert len(records) == 1
        assert records[0].overall_rating == 5.0

    def test_add_multiple_records(self, tmp_path):
        store = FeedbackStore(path=str(tmp_path / "rlhf.jsonl"))
        for rating in [3.0, 7.0, 10.0]:
            store.add(_make_feedback(overall_rating=rating))
        assert store.count() == 3
        ratings = [r.overall_rating for r in store]
        assert sorted(ratings) == [3.0, 7.0, 10.0]

    def test_add_from_image_creates_record(self, tmp_path):
        img_path = tmp_path / "stitch.png"
        img_path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)  # minimal fake JPEG
        store = FeedbackStore(path=str(tmp_path / "rlhf.jsonl"))
        fb = store.add_from_image(
            image_path=str(img_path),
            overall_rating=9.0,
            annotations=[
                StitchAnnotation(
                    x=0.0, y=0.0, w=1.0, h=1.0, flaw_type="ghosting", severity=0.3
                )
            ],
        )
        assert fb.overall_rating == 9.0
        assert len(fb.annotations) == 1
        assert fb.image_hash  # non-empty MD5
        assert store.count() == 1

    def test_empty_store_iter_returns_nothing(self, tmp_path):
        store = FeedbackStore(path=str(tmp_path / "rlhf.jsonl"))
        assert store.all() == []

    def test_malformed_lines_are_skipped(self, tmp_path):
        p = tmp_path / "rlhf.jsonl"
        good = _make_feedback(overall_rating=4.0)
        p.write_text(
            json.dumps(good.to_dict()) + "\n"
            + "NOT_JSON\n"
            + json.dumps(good.to_dict()) + "\n",
            encoding="utf-8",
        )
        store = FeedbackStore(path=str(p))
        assert store.count() == 2  # malformed line silently skipped


# ---------------------------------------------------------------------------
# §1.10D — MC-dropout uncertainty estimation
# ---------------------------------------------------------------------------

def _make_test_image(h: int = 64, w: int = 64) -> np.ndarray:
    """Synthetic BGR image filled with a mid-grey value."""
    return np.full((h, w, 3), 128, dtype=np.uint8)


class TestMCDropoutUncertainty:
    """§1.10D: predict_with_uncertainty returns (mean, std) via MC dropout."""

    def test_returns_two_floats(self):
        model = StitchRewardModel()
        img = _make_test_image()
        result = model.predict_with_uncertainty(img, n_samples=5)
        assert isinstance(result, tuple) and len(result) == 2
        mean_score, std_dev = result
        assert isinstance(mean_score, float)
        assert isinstance(std_dev, float)

    def test_mean_in_unit_range(self):
        model = StitchRewardModel()
        img = _make_test_image()
        mean_score, _ = model.predict_with_uncertainty(img, n_samples=5)
        assert 0.0 <= mean_score <= 1.0

    def test_std_nonnegative(self):
        model = StitchRewardModel()
        img = _make_test_image()
        _, std_dev = model.predict_with_uncertainty(img, n_samples=10)
        assert std_dev >= 0.0

    def test_more_samples_does_not_raise(self):
        model = StitchRewardModel()
        img = _make_test_image()
        mean_score, std_dev = model.predict_with_uncertainty(img, n_samples=30)
        assert 0.0 <= mean_score <= 1.0
        assert std_dev >= 0.0

    def test_mc_uncertainty_threshold_exported(self):
        assert isinstance(MC_DROPOUT_UNCERTAINTY_THRESHOLD, float)
        assert 0.0 < MC_DROPOUT_UNCERTAINTY_THRESHOLD < 1.0
