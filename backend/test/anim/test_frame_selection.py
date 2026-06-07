"""
Tests for frame_selection.py — _fg_center_diff() pose metric and
_near_dup_luma_filter() §1.2B near-duplicate post-filter.

Validates that the new fg pixel L1 metric (session 5):
  1. Returns near-zero for two thumbnails with identical fg appearance
  2. Returns a clearly higher score for thumbnails with different fg appearance
  3. Is strictly background-invariant: changing the background while keeping
     fg identical does NOT change the score
  4. Falls back gracefully when fg_mask is None or too sparse
  5. Handles per-frame gain normalisation (same pose, different brightness)

Validates _near_dup_luma_filter (session 26 §1.2B):
  6. threshold=0 disables the filter (all paths returned unchanged)
  7. All identical frames → only first and last kept
  8. All different frames → all kept
  9. ≤2 frames passes through unchanged regardless of threshold
  10. Middle near-dup dropped; first and last always retained
"""

from __future__ import annotations

import os
import sys

import cv2
import numpy as np
import pytest

_repo_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, _repo_root)

from backend.src.anim.frame_selection import (
    _fg_center_diff,
    _detect_hold_blocks,
    _detect_hold_blocks_dhash,
    _compute_dhash,
    _refine_hold_ids_by_response,
    _temporal_variance_filter,
    _near_dup_luma_filter,
    _compute_dinov2_features,
    _DINOV2_CACHE,
)


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


class TestDetectHoldBlocks:
    """Tests for _detect_hold_blocks() — FD-Means animation hold detection."""

    def _thumbs(self, n: int, h: int = 64, w: int = 64) -> list:
        """Return N identical zero thumbnails (same hold)."""
        return [np.zeros((h, w), dtype=np.float32) for _ in range(n)]

    def test_all_same_single_block(self):
        """All identical frames → single hold block (index [0])."""
        thumbs = self._thumbs(10)
        blocks = _detect_hold_blocks(thumbs, hold_threshold=0.025)
        assert blocks == [0], f"Expected [0], got {blocks}"

    def test_three_distinct_holds(self):
        """Three groups of different fill values → three hold blocks."""
        thumbs = (
            self._thumbs(3)                                         # block 0: fill=0.0
            + [np.full((64, 64), 0.1, dtype=np.float32)] * 3       # block 1: fill=0.1
            + [np.full((64, 64), 0.2, dtype=np.float32)] * 4       # block 2: fill=0.2
        )
        blocks = _detect_hold_blocks(thumbs, hold_threshold=0.025)
        assert blocks == [0, 3, 6], f"Expected [0, 3, 6], got {blocks}"

    def test_every_frame_different(self):
        """Each frame slightly different → each frame starts a new block."""
        rng = np.random.RandomState(42)
        thumbs = [rng.uniform(0, 1, (64, 64)).astype(np.float32) for _ in range(5)]
        blocks = _detect_hold_blocks(thumbs, hold_threshold=0.0001)
        # Every consecutive pair should differ enough to be a new block
        assert len(blocks) == 5, f"Expected 5 blocks, got {len(blocks)}: {blocks}"
        assert blocks == [0, 1, 2, 3, 4]

    def test_zero_threshold_all_different(self):
        """threshold=0 → disabled, all frame indices returned."""
        thumbs = self._thumbs(5)
        blocks = _detect_hold_blocks(thumbs, hold_threshold=0.0)
        assert blocks == [0, 1, 2, 3, 4]

    def test_single_frame_returns_zero(self):
        """Single frame → [0]."""
        blocks = _detect_hold_blocks(self._thumbs(1), hold_threshold=0.025)
        assert blocks == [0]

    def test_empty_returns_empty(self):
        """Empty input → empty output."""
        blocks = _detect_hold_blocks([], hold_threshold=0.025)
        assert blocks == []

    def test_hold_boundary_above_threshold(self):
        """MAD exactly above threshold → detected as new block."""
        t_a = np.zeros((64, 64), dtype=np.float32)
        t_b = np.full((64, 64), 0.03, dtype=np.float32)  # MAD=0.03 > 0.025
        blocks = _detect_hold_blocks([t_a, t_b], hold_threshold=0.025)
        assert blocks == [0, 1], f"MAD=0.03 > threshold=0.025 → two blocks, got {blocks}"

    def test_hold_boundary_below_threshold(self):
        """MAD exactly below threshold → same block."""
        t_a = np.zeros((64, 64), dtype=np.float32)
        t_b = np.full((64, 64), 0.02, dtype=np.float32)  # MAD=0.02 < 0.025
        blocks = _detect_hold_blocks([t_a, t_b], hold_threshold=0.025)
        assert blocks == [0], f"MAD=0.02 < threshold=0.025 → one block, got {blocks}"

    def test_noise_within_hold_not_detected(self):
        """Small MPEG-style noise within a hold should not create new blocks."""
        rng = np.random.RandomState(7)
        base = np.full((64, 64), 0.5, dtype=np.float32)
        # Add tiny noise (< 0.01 MAD → within-hold compression artefact)
        thumbs = [
            np.clip(base + rng.uniform(-0.005, 0.005, (64, 64)).astype(np.float32), 0, 1)
            for _ in range(6)
        ]
        blocks = _detect_hold_blocks(thumbs, hold_threshold=0.025)
        assert blocks == [0], (
            f"Small noise within hold should not create extra blocks, got {blocks}"
        )


class TestDINOv2Features:
    """Tests for _compute_dinov2_features() — DINOv2 submodular selection (§3.3).

    The current API takes a list of image file paths (session 9 upgrade).
    Tests write temp PNG files to exercise the real code path.
    """

    def _write_png(self, tmp_path, arr: np.ndarray) -> str:
        """Write a uint8 array as a PNG to tmp_path and return its str path."""
        import uuid
        img = (arr * 255).clip(0, 255).astype(np.uint8) if arr.dtype != np.uint8 else arr
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        path = str(tmp_path / f"{uuid.uuid4().hex}.png")
        cv2.imwrite(path, img)
        return path

    def test_returns_none_when_model_unavailable(self, tmp_path):
        """When the cache records a failed model load, the function returns None."""
        import torch
        import backend.src.anim.frame_selection as fs_mod

        device = "cuda" if torch.cuda.is_available() else "cpu"
        original = fs_mod._DINOV2_CACHE.get(device, "missing")
        # Pre-poison the cache to simulate a prior failed model load
        fs_mod._DINOV2_CACHE[device] = None
        try:
            rng = np.random.RandomState(42)
            paths = [
                self._write_png(tmp_path, rng.randint(0, 256, (64, 64, 3), dtype=np.uint8))
                for _ in range(3)
            ]
            result = _compute_dinov2_features(paths)
            assert result is None, "Should return None when cached model is None"
        finally:
            if original == "missing":
                fs_mod._DINOV2_CACHE.pop(device, None)
            else:
                fs_mod._DINOV2_CACHE[device] = original

    def test_identical_images_low_cosine_distance(self, tmp_path):
        """Identical input images must yield identical features → cosine dist ≈ 0."""
        rng = np.random.RandomState(0)
        img = rng.randint(0, 256, (64, 64, 3), dtype=np.uint8)
        path_a = self._write_png(tmp_path, img)
        path_b = self._write_png(tmp_path, img.copy())
        feats = _compute_dinov2_features([path_a, path_b])
        if feats is None:
            pytest.skip("DINOv2 not available in this environment")
        assert feats.shape == (2, 384), f"Expected (2, 384), got {feats.shape}"
        dist = 1.0 - float(np.dot(feats[0], feats[1]))
        assert dist < 0.05, f"Identical images should have cosine dist ~0, got {dist:.4f}"


# ---------------------------------------------------------------------------
# TestNearDupLumaFilter
# ---------------------------------------------------------------------------


class TestNearDupLumaFilter:
    """
    _near_dup_luma_filter: §1.2B near-duplicate post-filter (S26).

    Consecutive selected frames with mean grayscale diff < threshold are
    dropped.  First frame always kept; last frame always kept.
    """

    def _solid(self, lum: int) -> np.ndarray:
        """(16, 20, 3) uint8 BGR image at uniform luminance."""
        return np.full((16, 20, 3), lum, dtype=np.uint8)

    def _paths(self, n: int):
        return [f"frame_{i:02d}.png" for i in range(n)]

    def test_disabled_at_zero_threshold(self):
        """threshold=0.0 → filter is a no-op; all paths returned unchanged."""
        thumbs = [self._solid(100)] * 5
        paths = self._paths(5)
        assert _near_dup_luma_filter(thumbs, paths, threshold=0.0) == paths

    def test_all_identical_keeps_first_and_last(self):
        """All frames at same lum → only first and last survive."""
        thumbs = [self._solid(128)] * 5
        paths = self._paths(5)
        result = _near_dup_luma_filter(thumbs, paths, threshold=5.0)
        assert result[0] == paths[0]
        assert result[-1] == paths[-1]
        assert len(result) == 2

    def test_all_different_keeps_all(self):
        """Large luma steps between frames → no frames dropped."""
        thumbs = [self._solid(i * 60) for i in range(4)]
        paths = self._paths(4)
        result = _near_dup_luma_filter(thumbs, paths, threshold=5.0)
        assert result == paths

    def test_two_frames_passes_unchanged(self):
        """≤2 frames: filter is a no-op regardless of threshold."""
        thumbs = [self._solid(100), self._solid(100)]
        paths = self._paths(2)
        assert _near_dup_luma_filter(thumbs, paths, threshold=50.0) == paths

    def test_middle_near_dup_dropped_first_last_kept(self):
        """Middle frame nearly identical to prev → dropped; last always kept."""
        thumbs = [
            self._solid(100),  # f0: kept (first)
            self._solid(101),  # f1: diff=1 < 5 → near-dup, dropped
            self._solid(180),  # f2: diff=79 >= 5 → kept
        ]
        paths = self._paths(3)
        result = _near_dup_luma_filter(thumbs, paths, threshold=5.0)
        assert paths[0] in result
        assert paths[1] not in result
        assert paths[2] in result


# ---------------------------------------------------------------------------
# TestRefineHoldIdsByResponse — §1.11C phase-correlation hold refinement (S38)
# ---------------------------------------------------------------------------


class TestRefineHoldIdsByResponse:
    """
    _refine_hold_ids_by_response merges hold blocks whose consecutive
    phaseCorrelate response >= threshold.  High response means the two frames
    are near-identical (same character cel) that MAD detection split due to
    MPEG compression noise.

    After merging, block IDs are renumbered consecutively (0-based,
    first-occurrence order).
    """

    def test_all_high_responses_merge_to_one_block(self):
        """All pairs with response >= threshold → single hold block for all frames."""
        # 4 frames initially split into 4 separate blocks
        hold_ids = [0, 1, 2, 3]
        responses = [0.90, 0.92, 0.88]  # all above 0.85
        result, n_blocks = _refine_hold_ids_by_response(hold_ids, responses, 0.85)
        assert n_blocks == 1
        assert result == [0, 0, 0, 0]

    def test_low_responses_leave_blocks_unchanged(self):
        """Responses below threshold → no merging; original blocks preserved."""
        hold_ids = [0, 1, 2, 3]
        responses = [0.30, 0.40, 0.20]
        result, n_blocks = _refine_hold_ids_by_response(hold_ids, responses, 0.85)
        assert n_blocks == 4
        assert result == [0, 1, 2, 3]

    def test_partial_merge_only_high_response_pairs(self):
        """Only pairs above threshold are merged; low-response boundaries preserved."""
        # Frames: 0-1 high (merge), 1-2 low (split), 2-3 high (merge)
        hold_ids = [0, 1, 2, 3]
        responses = [0.90, 0.20, 0.91]
        result, n_blocks = _refine_hold_ids_by_response(hold_ids, responses, 0.85)
        # Blocks 0 and 1 merge; blocks 2 and 3 merge; boundary between stays split
        assert n_blocks == 2
        assert result[0] == result[1]   # 0 and 1 in same block
        assert result[2] == result[3]   # 2 and 3 in same block
        assert result[0] != result[2]   # the two merged groups are separate

    def test_output_ids_are_consecutive_from_zero(self):
        """After merging, IDs are renumbered 0, 1, 2, … in first-occurrence order."""
        # Merge pairs 0-1 and 2-3; pair 1-2 stays split
        hold_ids = [0, 1, 2, 3]
        responses = [0.95, 0.10, 0.95]
        result, n_blocks = _refine_hold_ids_by_response(hold_ids, responses, 0.85)
        assert sorted(set(result)) == list(range(n_blocks))

    def test_single_frame_returns_unchanged(self):
        """N=1 → no pairs to inspect; original hold_ids and block count returned."""
        hold_ids = [0]
        responses: list = []
        result, n_blocks = _refine_hold_ids_by_response(hold_ids, responses, 0.85)
        assert result == [0]
        assert n_blocks == 1


# ---------------------------------------------------------------------------
# TestTemporalVarianceFilter — §1.2D static-frame pre-filter (S39)
# ---------------------------------------------------------------------------


class TestTemporalVarianceFilter:
    """
    _temporal_variance_filter drops interior frames whose mean per-pixel
    variance across the thumbnail triplet (i-1, i, i+1) is below sigma_threshold.

    Thumbnails are [0,1] float32 grayscale.  First and last frames are never
    dropped regardless of variance.  Disabled when threshold=0.0.
    """

    def _flat(self, val: float = 0.5, h: int = 16, w: int = 24) -> np.ndarray:
        """(H, W) float32 thumbnail with uniform value."""
        return np.full((h, w), val, dtype=np.float32)

    def _noisy(self, rng: np.random.RandomState, h: int = 16, w: int = 24) -> np.ndarray:
        """(H, W) float32 thumbnail with high random variance."""
        return rng.uniform(0.0, 1.0, (h, w)).astype(np.float32)

    def test_static_triplet_drops_middle_frame(self):
        """Three near-identical frames → middle dropped (variance near zero)."""
        thumbs = [self._flat(0.5), self._flat(0.5), self._flat(0.5)]
        paths = ["a.png", "b.png", "c.png"]
        result_t, result_p, n_drop = _temporal_variance_filter(thumbs, paths, sigma_threshold=1e-3)
        assert n_drop == 1
        assert len(result_p) == 2
        assert "b.png" not in result_p  # middle dropped
        assert "a.png" in result_p and "c.png" in result_p

    def test_high_variance_frames_kept(self):
        """Frames with large inter-frame differences → none dropped."""
        rng = np.random.RandomState(0)
        thumbs = [self._noisy(rng), self._noisy(rng), self._noisy(rng)]
        paths = ["a.png", "b.png", "c.png"]
        result_t, result_p, n_drop = _temporal_variance_filter(thumbs, paths, sigma_threshold=1e-3)
        assert n_drop == 0
        assert result_p == paths

    def test_first_and_last_never_dropped(self):
        """Even if first/last are identical to their neighbours, they are kept."""
        v = self._flat(0.3)
        thumbs = [v, v, v, v, v]  # all identical
        paths = [f"{i}.png" for i in range(5)]
        result_t, result_p, n_drop = _temporal_variance_filter(thumbs, paths, sigma_threshold=1e-3)
        assert result_p[0] == "0.png"
        assert result_p[-1] == "4.png"

    def test_threshold_zero_disables_filter(self):
        """threshold=0.0 → no drops regardless of content."""
        v = self._flat(0.5)
        thumbs = [v, v, v]
        paths = ["a.png", "b.png", "c.png"]
        result_t, result_p, n_drop = _temporal_variance_filter(thumbs, paths, sigma_threshold=0.0)
        assert n_drop == 0
        assert result_p == paths

    def test_fewer_than_three_frames_passes_unchanged(self):
        """N < 3 → no processing; lists returned as-is."""
        thumbs = [self._flat(0.5), self._flat(0.5)]
        paths = ["a.png", "b.png"]
        result_t, result_p, n_drop = _temporal_variance_filter(thumbs, paths, sigma_threshold=1e-3)
        assert n_drop == 0
        assert result_p == paths


# ---------------------------------------------------------------------------
# TestDetectHoldBlocksDhash — §3.4A dHash hold detection (S43)
# ---------------------------------------------------------------------------


class TestDetectHoldBlocksDhash:
    """
    _detect_hold_blocks_dhash uses INTER_AREA-downscaled horizontal gradient
    binarisation (dHash) instead of raw MAD, so MPEG block noise is averaged
    out before the comparison.  _compute_dhash returns a flat bool array.
    """

    @staticmethod
    def _uniform_thumb(val: float = 0.5) -> np.ndarray:
        return np.full((64, 64), val, dtype=np.float32)

    def test_identical_thumbs_produce_single_block(self):
        """Two pixel-identical thumbnails must collapse into one hold block → [0]."""
        t = self._uniform_thumb(0.4)
        result = _detect_hold_blocks_dhash([t, t], distance_threshold=4)
        assert result == [0]

    def test_very_different_thumbs_split_into_two_blocks(self):
        """Thumbnails with opposite horizontal gradients must be separate blocks.

        A left-to-right ramp hashes as all-True (every pixel > previous);
        a right-to-left ramp hashes as all-False — Hamming distance = 64 >> 4.
        """
        # Ramp left→right (increasing): dHash ≈ all True
        t_a = np.tile(np.linspace(0.0, 1.0, 64, dtype=np.float32), (64, 1))
        # Ramp right→left (decreasing): dHash ≈ all False
        t_b = np.tile(np.linspace(1.0, 0.0, 64, dtype=np.float32), (64, 1))
        result = _detect_hold_blocks_dhash([t_a, t_b], distance_threshold=4)
        assert result == [0, 1]

    def test_threshold_zero_every_frame_is_own_block(self):
        """distance_threshold=0 → every frame starts a new block (no holds)."""
        thumbs = [self._uniform_thumb(v) for v in [0.3, 0.3, 0.3]]
        result = _detect_hold_blocks_dhash(thumbs, distance_threshold=0)
        assert result == [0, 1, 2]

    def test_single_frame_returns_single_block(self):
        """N=1 must return [0] without error."""
        result = _detect_hold_blocks_dhash([self._uniform_thumb()], distance_threshold=4)
        assert result == [0]

    def test_compute_dhash_same_image_zero_distance(self):
        """The same image must hash to distance 0 with itself."""
        t = np.random.default_rng(0).random((32, 32)).astype(np.float32)
        h = _compute_dhash(t)
        assert int(np.sum(h != h)) == 0
        assert h.dtype == bool
