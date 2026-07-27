"""
Smoke tests for backend/src/models/data/captioner.py — issue #32 wiring.

Scope (deliberately narrow, per project testing rules — no GPU, no real model
downloads): exercises HybridCaptioner's booru/prose mode switch, trigger-token
prepending, and the WD14 backend adapter (_wd_tag) that normalizes both the
legacy local-path WD14Tagger and the shared WDTaggerWrapper (§4.4 auto-tagger)
to the same (rating, general, character) shape.

Both WD14 backends are exercised with fakes/mocks rather than real ONNX
sessions or downloaded weights:
  - onnxruntime is not installed in this environment, so a real WD14Tagger
    cannot be constructed; its instance is built via object.__new__ to bypass
    __init__ (which hard-requires onnxruntime) and its ONNX session is faked.
  - WDTaggerWrapper's __init__ has no heavy dependency, so a real instance is
    built normally and its internal ONNX session/labels are injected directly
    (mirrors backend/test/models/test_wd_tagger_wrapper.py's own approach).
"""

from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image

from backend.src.models.data.captioner import HybridCaptioner, WD14Tagger, _wd_tag
from backend.src.models.wrappers.wd_tagger_wrapper import WDTaggerWrapper, _load_labels

# ── Fakes ───────────────────────────────────────────────────────────────────

def _fake_image() -> Image.Image:
    return Image.new("RGB", (64, 64), color=(128, 64, 200))


class _FakeFlorence:
    """Duck-typed stand-in for Florence2Captioner — no model weights needed."""

    def __init__(self, text: str = "a girl standing in a garden"):
        self.text = text
        self.calls = 0

    def __call__(self, image, task="<MORE_DETAILED_CAPTION>"):
        self.calls += 1
        return self.text


def _make_legacy_wd14tagger() -> WD14Tagger:
    """Build a WD14Tagger instance without invoking __init__ (avoids the
    hard onnxruntime import check), with a faked ONNX session."""
    wd = object.__new__(WD14Tagger)
    wd.tag_names = ["general", "1girl", "blue_eyes", "hatsune_miku"]
    wd.tag_categories = [9, 0, 0, 4]
    wd.general_thresh = 0.35
    wd.character_thresh = 0.85
    fake_sess = MagicMock()
    # scores line up with tag_names order above
    fake_sess.run.return_value = [np.array([[0.9, 0.8, 0.1, 0.95]], dtype=np.float32)]
    wd.sess = fake_sess
    wd.input_name = "input"
    return wd


def _make_wd_tagger_wrapper(tmp_path: Path) -> WDTaggerWrapper:
    csv_path = tmp_path / "tags.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "category"])
        writer.writeheader()
        writer.writerows(
            [
                {"name": "general", "category": "9"},
                {"name": "1girl", "category": "0"},
                {"name": "blue_eyes", "category": "0"},
                {"name": "hatsune_miku", "category": "4"},
            ]
        )
    w = WDTaggerWrapper(threshold=0.35, cache_dir=str(tmp_path / "cache"))
    fake_sess = MagicMock()
    fake_sess.run.return_value = [np.array([[0.9, 0.8, 0.1, 0.95]], dtype=np.float32)]
    w._session = fake_sess
    w._input_name = "input"
    w._input_size = 448
    w._labels = _load_labels(str(csv_path))
    return w


# ── _wd_tag adapter ───────────────────────────────────────────────────────

class TestWdTagAdapter:
    def test_legacy_wd14tagger_path(self):
        wd = _make_legacy_wd14tagger()
        rating, general, character = _wd_tag(wd, _fake_image())
        assert rating == ["general"]
        assert general == ["1girl"]
        assert character == ["hatsune miku"]

    def test_wd_tagger_wrapper_requires_image_path(self, tmp_path):
        wd = _make_wd_tagger_wrapper(tmp_path)
        with pytest.raises(ValueError):
            _wd_tag(wd, _fake_image(), image_path=None)

    def test_wd_tagger_wrapper_path(self, tmp_path):
        wd = _make_wd_tagger_wrapper(tmp_path)
        img_path = tmp_path / "test.png"
        _fake_image().save(img_path)
        rating, general, character = _wd_tag(wd, _fake_image(), image_path=img_path)
        # Fixture mirrors the real WD CSV: the rating group's tags are named
        # general/sensitive/questionable/explicit but live under category "rating".
        assert rating == ["general"]
        assert "1girl" in general
        assert "blue eyes" not in general  # below threshold (0.1 < 0.35)
        assert character == ["hatsune miku"]


# ── HybridCaptioner: booru mode ──────────────────────────────────────────

class TestHybridCaptionerBooru:
    def test_booru_mode_with_legacy_wd14tagger(self):
        wd = _make_legacy_wd14tagger()
        cap = HybridCaptioner(wd=wd, florence=None, trigger="my_char_xyz")
        result = cap(_fake_image())
        assert result["final_caption"].startswith("my_char_xyz, hatsune miku, 1girl")
        assert result["wd14_character"] == ["hatsune miku"]
        assert result["nl_caption"] == ""

    def test_booru_mode_with_wd_tagger_wrapper(self, tmp_path):
        wd = _make_wd_tagger_wrapper(tmp_path)
        img_path = tmp_path / "test.png"
        _fake_image().save(img_path)
        cap = HybridCaptioner(wd=wd, florence=None, trigger="my_char_xyz")
        result = cap(_fake_image(), image_path=img_path)
        assert "my_char_xyz" in result["tags_ordered"]
        assert "hatsune miku" in result["tags_ordered"]
        assert "1girl" in result["tags_ordered"]

    def test_florence_augmentation_appended_after_tags(self):
        wd = _make_legacy_wd14tagger()
        fl = _FakeFlorence("a girl standing in a garden")
        cap = HybridCaptioner(wd=wd, florence=fl, trigger="my_char_xyz")
        result = cap(_fake_image())
        assert result["final_caption"].endswith("a girl standing in a garden")
        assert "my_char_xyz" in result["final_caption"]
        assert fl.calls == 1

    def test_default_confidence_threshold_matches_wd_tagger_wrapper(self):
        # WD14Tagger's default general_thresh and WDTaggerWrapper's
        # DEFAULT_THRESHOLD must agree so behavior is consistent across
        # backends (both should default to 0.35, per WD14 convention).
        from backend.src.models.wrappers.wd_tagger_wrapper import DEFAULT_THRESHOLD

        assert DEFAULT_THRESHOLD == 0.35

    def test_invalid_caption_mode_rejected(self):
        with pytest.raises(ValueError):
            HybridCaptioner(wd=None, florence=None, caption_mode="nonsense")


# ── HybridCaptioner: prose mode ──────────────────────────────────────────

class TestHybridCaptionerProse:
    def test_prose_mode_skips_wd14_entirely(self):
        wd = _make_legacy_wd14tagger()
        fl = _FakeFlorence("a girl standing in a garden")
        cap = HybridCaptioner(
            wd=wd, florence=fl, trigger="my_char_xyz", caption_mode="prose"
        )
        result = cap(_fake_image())
        assert result["wd14_character"] == []
        assert result["wd14_general"] == []
        assert result["tags_ordered"] == []
        assert result["final_caption"] == "my_char_xyz, a girl standing in a garden"

    def test_prose_mode_without_trigger(self):
        fl = _FakeFlorence("a scenic landscape")
        cap = HybridCaptioner(wd=None, florence=fl, caption_mode="prose")
        result = cap(_fake_image())
        assert result["final_caption"] == "a scenic landscape"

    def test_prose_mode_requires_florence(self):
        cap = HybridCaptioner(wd=None, florence=None, caption_mode="prose")
        with pytest.raises(RuntimeError):
            cap(_fake_image())


# ── write_caption_file ────────────────────────────────────────────────────

def test_write_caption_file(tmp_path):
    wd = _make_legacy_wd14tagger()
    cap = HybridCaptioner(wd=wd, florence=None, trigger="my_char_xyz")
    img_path = tmp_path / "sample.png"
    _fake_image().save(img_path)
    result = cap(_fake_image())
    cap.write_caption_file(img_path, result)
    txt_path = img_path.with_suffix(".txt")
    assert txt_path.exists()
    assert txt_path.read_text(encoding="utf-8") == result["final_caption"]
