"""
Tests for backend.src.anim.grounding — Issue 10A1.

GroundingDINO is optional; all tests must pass when it is NOT installed.
"""

import numpy as np
import pytest

from backend.src.anim.grounding import (
    _detect_best_box,
    _detect_exclusion_mask,
    _detect_objects,
    _gdino_available,
    reset_grounding_dino_model,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

def _blank_frame(h=128, w=128):
    return np.zeros((h, w, 3), dtype=np.uint8)


# ── TestGdinoAvailable ────────────────────────────────────────────────────────

class TestGdinoAvailable:
    def test_returns_bool(self):
        result = _gdino_available()
        assert isinstance(result, bool)

    def test_consistent_across_calls(self):
        assert _gdino_available() == _gdino_available()


# ── TestDetectObjects ─────────────────────────────────────────────────────────

class TestDetectObjects:
    def test_returns_list_when_gdino_unavailable(self):
        # If GroundingDINO isn't installed, must return [] gracefully
        if _gdino_available():
            pytest.skip("GroundingDINO is installed; skip no-op path test")
        frame = _blank_frame()
        result = _detect_objects(frame, "cat")
        assert isinstance(result, list) and len(result) == 0

    def test_empty_prompt_returns_empty(self):
        frame = _blank_frame()
        result = _detect_objects(frame, "")
        assert result == []

    def test_none_frame_does_not_crash(self):
        result = _detect_objects(None, "cat")
        assert isinstance(result, list)

    def test_white_frame_empty_prompt(self):
        frame = np.full((64, 64, 3), 255, dtype=np.uint8)
        result = _detect_objects(frame, "")
        assert result == []

    def test_bboxes_are_float32_arrays(self):
        frame = _blank_frame()
        result = _detect_objects(frame, "character")
        for bbox in result:
            assert isinstance(bbox, np.ndarray)
            assert bbox.dtype == np.float32
            assert bbox.shape == (4,)


# ── TestDetectBestBox ─────────────────────────────────────────────────────────

class TestDetectBestBox:
    def test_returns_none_when_gdino_unavailable(self):
        if _gdino_available():
            pytest.skip("GroundingDINO is installed; skip no-op path test")
        frame = _blank_frame()
        result = _detect_best_box(frame, "cat")
        assert result is None

    def test_empty_prompt_returns_none(self):
        frame = _blank_frame()
        result = _detect_best_box(frame, "")
        assert result is None

    def test_result_is_none_or_4elem(self):
        frame = _blank_frame()
        result = _detect_best_box(frame, "character")
        assert result is None or (isinstance(result, np.ndarray) and result.shape == (4,))


# ── TestDetectExclusionMask ───────────────────────────────────────────────────

class TestDetectExclusionMask:
    def test_returns_none_when_gdino_unavailable(self):
        if _gdino_available():
            pytest.skip("GroundingDINO is installed; skip no-op path test")
        frame = _blank_frame(64, 64)
        result = _detect_exclusion_mask(frame, "right arm")
        assert result is None

    def test_empty_prompt_returns_none(self):
        frame = _blank_frame()
        result = _detect_exclusion_mask(frame, "")
        assert result is None

    def test_output_is_uint8_when_non_none(self):
        frame = _blank_frame()
        result = _detect_exclusion_mask(frame, "arm")
        if result is not None:
            assert result.dtype == np.uint8
            assert set(np.unique(result)).issubset({0, 255})

    def test_output_shape_matches_input(self):
        h, w = 72, 96
        frame = _blank_frame(h, w)
        result = _detect_exclusion_mask(frame, "arm")
        if result is not None:
            assert result.shape == (h, w)


# ── TestResetGroundingDinoModel ───────────────────────────────────────────────

class TestResetGroundingDinoModel:
    def test_reset_does_not_crash_when_not_loaded(self):
        reset_grounding_dino_model()

    def test_available_unchanged_after_reset(self):
        before = _gdino_available()
        reset_grounding_dino_model()
        assert _gdino_available() == before
