"""Tests for backend/src/models/wd_tagger_wrapper.py — §3.6."""

from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from backend.src.models.wrappers.wd_tagger_wrapper import (
    DEFAULT_THRESHOLD,
    WDTaggerWrapper,
    _filter_tags,
    _load_labels,
    _load_and_preprocess,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "category"])
        writer.writeheader()
        writer.writerows(rows)


def _make_fake_image(path: Path, w: int = 64, h: int = 64) -> None:
    """Write a minimal valid PNG without requiring PIL."""
    from PIL import Image as PilImage
    img = PilImage.new("RGB", (w, h), color=(128, 200, 100))
    img.save(str(path))


@pytest.fixture()
def sample_csv(tmp_path):
    csv_path = tmp_path / "tags.csv"
    _make_csv(csv_path, [
        {"name": "1girl", "category": "0"},
        {"name": "blue_eyes", "category": "0"},
        {"name": "hatsune_miku", "category": "4"},
        {"name": "vocaloid", "category": "9"},
        {"name": "solo", "category": "0"},
    ])
    return csv_path


@pytest.fixture()
def sample_labels(sample_csv):
    return _load_labels(str(sample_csv))


@pytest.fixture()
def fake_image(tmp_path):
    img_path = tmp_path / "test.png"
    _make_fake_image(img_path)
    return img_path


# ── _load_labels ──────────────────────────────────────────────────────────────

class TestLoadLabels:
    def test_loads_correct_count(self, sample_csv):
        labels = _load_labels(str(sample_csv))
        assert len(labels) == 5

    def test_underscore_replaced_with_space(self, sample_csv):
        labels = _load_labels(str(sample_csv))
        assert labels[1]["tag"] == "blue eyes"

    def test_categories_mapped_correctly(self, sample_csv):
        labels = _load_labels(str(sample_csv))
        assert labels[0]["category"] == "general"
        assert labels[2]["category"] == "character"
        assert labels[3]["category"] == "copyright"

    def test_category_id_preserved(self, sample_csv):
        labels = _load_labels(str(sample_csv))
        assert labels[2]["category_id"] == 4

    def test_unknown_category_defaults_to_general(self, tmp_path):
        p = tmp_path / "unk.csv"
        _make_csv(p, [{"name": "test_tag", "category": "99"}])
        labels = _load_labels(str(p))
        assert labels[0]["category"] == "general"


# ── _filter_tags ──────────────────────────────────────────────────────────────

class TestFilterTags:
    @pytest.fixture()
    def labels(self):
        return [
            {"tag": "1girl", "category_id": 0, "category": "general"},
            {"tag": "blue eyes", "category_id": 0, "category": "general"},
            {"tag": "hatsune miku", "category_id": 4, "category": "character"},
        ]

    @pytest.fixture()
    def scores(self):
        return np.array([0.95, 0.25, 0.60], dtype=np.float32)

    def test_filters_below_threshold(self, labels, scores):
        result = _filter_tags(scores, labels, min_conf=0.35)
        tags = [r["tag"] for r in result]
        assert "1girl" in tags
        assert "hatsune miku" in tags
        assert "blue eyes" not in tags

    def test_sorted_by_confidence_descending(self, labels, scores):
        result = _filter_tags(scores, labels, min_conf=0.35)
        confs = [r["confidence"] for r in result]
        assert confs == sorted(confs, reverse=True)

    def test_max_conf_respected(self, labels, scores):
        # review band: [0.15, 0.35)
        result = _filter_tags(scores, labels, min_conf=0.15, max_conf=0.35)
        assert len(result) == 1
        assert result[0]["tag"] == "blue eyes"

    def test_confidence_field_is_float(self, labels, scores):
        result = _filter_tags(scores, labels, min_conf=0.0)
        for r in result:
            assert isinstance(r["confidence"], float)

    def test_scores_longer_than_labels_safe(self, labels):
        long_scores = np.full(100, 0.9, dtype=np.float32)
        result = _filter_tags(long_scores, labels, min_conf=0.5)
        assert len(result) == len(labels)


# ── _load_and_preprocess ──────────────────────────────────────────────────────

class TestLoadAndPreprocess:
    def test_output_shape_matches_size(self, fake_image):
        arr = _load_and_preprocess(str(fake_image), 224)
        assert arr.shape == (1, 224, 224, 3)

    def test_output_dtype_float32(self, fake_image):
        arr = _load_and_preprocess(str(fake_image), 224)
        assert arr.dtype == np.float32

    def test_pixel_values_in_range(self, fake_image):
        arr = _load_and_preprocess(str(fake_image), 224)
        assert arr.min() >= 0.0
        assert arr.max() <= 255.0

    def test_non_square_image_pads_to_square(self, tmp_path):
        from PIL import Image as PilImage
        wide = PilImage.new("RGB", (200, 50), color=(0, 0, 0))
        wide_path = tmp_path / "wide.png"
        wide.save(str(wide_path))
        arr = _load_and_preprocess(str(wide_path), 448)
        assert arr.shape == (1, 448, 448, 3)

    def test_rgba_image_handled(self, tmp_path):
        from PIL import Image as PilImage
        rgba = PilImage.new("RGBA", (100, 100), color=(50, 100, 150, 200))
        rgba_path = tmp_path / "rgba.png"
        rgba.save(str(rgba_path))
        arr = _load_and_preprocess(str(rgba_path), 64)
        assert arr.shape == (1, 64, 64, 3)


# ── WDTaggerWrapper unit tests (mocked session) ───────────────────────────────

class TestWDTaggerWrapper:
    @pytest.fixture()
    def mock_session(self):
        sess = MagicMock()
        # Simulate 5 output tags with realistic scores
        sess.run.return_value = [np.array([[0.95, 0.25, 0.60, 0.10, 0.45]], dtype=np.float32)]
        mock_input = MagicMock()
        mock_input.name = "input"
        mock_input.shape = (1, 448, 448, 3)
        sess.get_inputs.return_value = [mock_input]
        return sess

    @pytest.fixture()
    def wrapper(self, mock_session, sample_csv, fake_image, tmp_path):
        w = WDTaggerWrapper(threshold=0.35, cache_dir=str(tmp_path / "cache"))
        w._session = mock_session
        w._input_name = "input"
        w._input_size = 448
        w._labels = _load_labels(str(sample_csv))
        return w

    def test_loaded_property_true_when_session_set(self, wrapper):
        assert wrapper.loaded is True

    def test_loaded_property_false_after_unload(self, wrapper):
        wrapper.unload()
        assert wrapper.loaded is False

    def test_tag_returns_list_of_dicts(self, wrapper, fake_image):
        result = wrapper.tag(str(fake_image))
        assert isinstance(result, list)
        for item in result:
            assert "tag" in item
            assert "confidence" in item
            assert "category" in item

    def test_tag_respects_threshold(self, wrapper, fake_image):
        result = wrapper.tag(str(fake_image), threshold=0.35)
        for item in result:
            assert item["confidence"] >= 0.35

    def test_tag_custom_threshold_override(self, wrapper, fake_image):
        result = wrapper.tag(str(fake_image), threshold=0.50)
        for item in result:
            assert item["confidence"] >= 0.50

    def test_tag_batch_returns_per_image_list(self, wrapper, fake_image):
        paths = [str(fake_image)] * 3
        results = wrapper.tag_batch(paths)
        assert len(results) == 3

    def test_tag_with_review_splits_correctly(self, wrapper, fake_image):
        auto, review = wrapper.tag_with_review(str(fake_image), threshold=0.35, review_threshold=0.15)
        for t in auto:
            assert t["confidence"] >= 0.35
        for t in review:
            assert 0.15 <= t["confidence"] < 0.35

    def test_tag_batch_bad_path_returns_empty_list(self, wrapper):
        results = wrapper.tag_batch(["/nonexistent/path.png"])
        assert results == [[]]

    def test_model_repo_env_override(self, tmp_path):
        os.environ["WD_TAGGER_MODEL_REPO"] = "custom/repo"
        try:
            w = WDTaggerWrapper(cache_dir=str(tmp_path))
            assert w.model_repo == "custom/repo"
        finally:
            del os.environ["WD_TAGGER_MODEL_REPO"]

    def test_is_available_returns_bool(self):
        result = WDTaggerWrapper.is_available()
        assert isinstance(result, bool)

    def test_default_threshold_constant(self):
        assert DEFAULT_THRESHOLD == 0.35
