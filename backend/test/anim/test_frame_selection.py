"""
Tests for frame_selection.py — _fg_center_diff() pose metric.

Validates that the new fg pixel L1 metric (session 5):
  1. Returns near-zero for two thumbnails with identical fg appearance
  2. Returns a clearly higher score for thumbnails with different fg appearance
  3. Is strictly background-invariant: changing the background while keeping
     fg identical does NOT change the score
  4. Falls back gracefully when fg_mask is None or too sparse
  5. Handles per-frame gain normalisation (same pose, different brightness)
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

_repo_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, _repo_root)

from backend.src.anim.frame_selection import _fg_center_diff


def _make_thumb(h: int = 144, w: int = 256, fill: float = 0.5) -> np.ndarray:
    """Return a uniform float32 thumbnail."""
    return np.full((h, w), fill, dtype=np.float32)


def _make_fg_mask(h: int = 144, w: int = 256, region: str = "center") -> np.ndarray:
    """Return a binary fg mask with the character in the specified region."""
    mask = np.zeros((h, w), dtype=np.float32)
    if region == "center":
        mask[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4] = 1.0
    elif region == "left":
        mask[:, : w // 2] = 1.0
    return mask


class TestFgCenterDiffNearZeroForIdentical:
    def test_identical_thumbs_with_mask(self):
        """Score should be near zero when fg pixels are identical."""
        thumb = np.random.RandomState(42).uniform(0, 1, (144, 256)).astype(np.float32)
        mask = _make_fg_mask()
        score = _fg_center_diff(thumb, thumb.copy(), fg_mask=mask)
        assert score < 0.01, f"Identical fg should score ~0, got {score:.4f}"

    def test_different_gain_same_pose(self):
        """Score should be near zero when fg is identical but scaled (gain normalisation)."""
        thumb_a = np.random.RandomState(7).uniform(0.2, 0.8, (144, 256)).astype(np.float32)
        # Simulate a different gain (10% brighter)
        thumb_b = np.clip(thumb_a * 1.10, 0.0, 1.0)
        mask = _make_fg_mask()
        score = _fg_center_diff(thumb_a, thumb_b, fg_mask=mask)
        # After per-frame normalisation the gain offset is removed; score should be small
        assert score < 0.05, f"Same pose, different gain should score ~0, got {score:.4f}"


class TestFgCenterDiffHighScoreForDifferentPose:
    def test_different_fg_pixels_score_high(self):
        """Score should be clearly > 0 when fg pixels differ significantly."""
        rng = np.random.RandomState(99)
        thumb_a = rng.uniform(0, 1, (144, 256)).astype(np.float32)
        # Flip fg region in thumb_b to create a completely different "pose"
        thumb_b = thumb_a.copy()
        mask = _make_fg_mask()
        fg_rows = slice(36, 108)
        fg_cols = slice(64, 192)
        thumb_b[fg_rows, fg_cols] = 1.0 - thumb_a[fg_rows, fg_cols]
        score = _fg_center_diff(thumb_a, thumb_b, fg_mask=mask)
        assert score > 0.5, f"Very different fg should score >0.5, got {score:.4f}"

    def test_pose_change_beats_same_pose(self):
        """Different pose scores strictly higher than same pose."""
        rng = np.random.RandomState(13)
        thumb_a = rng.uniform(0, 1, (144, 256)).astype(np.float32)
        thumb_b_same = thumb_a.copy()  # same pose
        thumb_b_diff = thumb_a.copy()  # different pose
        # Shift fg region content by 30px to simulate a limb moving
        fg = thumb_a[36:108, 64:192].copy()
        thumb_b_diff[36:108, 64:192] = np.roll(fg, 30, axis=1)
        mask = _make_fg_mask()
        score_same = _fg_center_diff(thumb_a, thumb_b_same, fg_mask=mask)
        score_diff = _fg_center_diff(thumb_a, thumb_b_diff, fg_mask=mask)
        assert score_diff > score_same * 2, (
            f"Different pose ({score_diff:.3f}) should score much higher than "
            f"same pose ({score_same:.3f})"
        )


class TestFgCenterDiffBackgroundInvariant:
    def test_background_change_does_not_affect_score(self):
        """Changing only background pixels should not affect the score."""
        rng = np.random.RandomState(55)
        thumb_a = rng.uniform(0, 1, (144, 256)).astype(np.float32)
        thumb_b = thumb_a.copy()

        # Change ONLY background pixels (outside the fg mask center region)
        mask = _make_fg_mask()
        bg_rows = list(range(0, 36)) + list(range(108, 144))
        for r in bg_rows:
            thumb_b[r, :] = rng.uniform(0, 1, 256).astype(np.float32)
        # Also change columns outside the fg band
        thumb_b[:, :64] = rng.uniform(0, 1, (144, 64)).astype(np.float32)
        thumb_b[:, 192:] = rng.uniform(0, 1, (144, 64)).astype(np.float32)

        score = _fg_center_diff(thumb_a, thumb_b, fg_mask=mask)
        assert score < 0.01, (
            f"Background-only changes should not affect fg score, got {score:.4f}"
        )


class TestFgCenterDiffFallback:
    def test_fallback_when_no_mask(self):
        """Should return a finite float without crashing when fg_mask=None."""
        rng = np.random.RandomState(0)
        a = rng.uniform(0, 1, (144, 256)).astype(np.float32)
        b = rng.uniform(0, 1, (144, 256)).astype(np.float32)
        score = _fg_center_diff(a, b, fg_mask=None)
        assert np.isfinite(score) and score >= 0.0

    def test_fallback_when_mask_too_sparse(self):
        """Should fall back to central-crop diff when fg_mask has < 50 positive pixels."""
        rng = np.random.RandomState(1)
        a = rng.uniform(0, 1, (144, 256)).astype(np.float32)
        b = rng.uniform(0, 1, (144, 256)).astype(np.float32)
        # Sparse mask: only 10 pixels
        sparse_mask = np.zeros((144, 256), dtype=np.float32)
        sparse_mask[70:72, 120:125] = 1.0  # 10 pixels
        score = _fg_center_diff(a, b, fg_mask=sparse_mask)
        assert np.isfinite(score) and score >= 0.0

    def test_fallback_returns_same_as_no_mask_for_sparse(self):
        """Sparse-mask fallback should return the same as no-mask (central-crop) path."""
        rng = np.random.RandomState(2)
        a = rng.uniform(0, 1, (144, 256)).astype(np.float32)
        b = rng.uniform(0, 1, (144, 256)).astype(np.float32)
        sparse_mask = np.zeros((144, 256), dtype=np.float32)
        sparse_mask[70, 120] = 1.0  # 1 pixel — way below 50 threshold
        score_no_mask = _fg_center_diff(a, b, fg_mask=None)
        score_sparse = _fg_center_diff(a, b, fg_mask=sparse_mask)
        assert abs(score_no_mask - score_sparse) < 1e-6, (
            f"Sparse mask should fall back to same path as no-mask: "
            f"{score_no_mask:.5f} vs {score_sparse:.5f}"
        )
