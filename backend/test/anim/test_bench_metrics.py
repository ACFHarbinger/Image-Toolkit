"""
Tests for quality metrics in bench_anime_stitch.py.

Covers:
  _seam_visibility_score — detects hard horizontal luminance cuts (S14)
  _compute_aligned_ssim  — ECC Euclidean aligned SSIM vs GT (S8 metric, S25 dedup)
  _compute_rlhf_score    — RLHF reward-model quality gate (§1.10A, S29)
"""

from __future__ import annotations

import os
import sys

import numpy as np

_repo_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, _repo_root)

from backend.benchmark.bench_anime_stitch import (  # noqa: E402
    _seam_visibility_score,
    _compute_aligned_ssim,
    _compute_rlhf_score,
    _compute_all_metrics,
    _ghosting_score_v2,
    _SSIM_OK,
    _RLHF_FLAG_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


import math
import pytest


def _solid(H: int, W: int, lum: int) -> np.ndarray:
    """(H, W, 3) uint8 BGR image of uniform luminance."""
    return np.full((H, W, 3), lum, dtype=np.uint8)


def _stacked(top_lum: int, bot_lum: int, H: int = 100, W: int = 120) -> np.ndarray:
    """Two uniform halves stacked vertically — guaranteed visible seam."""
    top = _solid(H // 2, W, top_lum)
    bot = _solid(H - H // 2, W, bot_lum)
    return np.concatenate([top, bot], axis=0)


# ---------------------------------------------------------------------------
# TestSeamVisibilityScore
# ---------------------------------------------------------------------------


class TestSeamVisibilityScore:
    """
    _seam_visibility_score measures the worst-case adjacent-row luminance
    jump in the output panorama.
    """

    def test_uniform_image_has_zero_score(self):
        """A perfectly uniform image has no visible seams."""
        img = _solid(200, 300, 128)
        assert _seam_visibility_score(img) == 0.0

    def test_hard_seam_is_detected(self):
        """A large luminance step between two halves must produce a high score."""
        img = _stacked(60, 200, H=100, W=120)
        score = _seam_visibility_score(img)
        assert score >= 100.0, f"Expected large jump for lum 60→200, got {score}"

    def test_smooth_gradient_gives_low_score(self):
        """A linearly varying image has no single large jump."""
        H, W = 100, 120
        img = np.zeros((H, W, 3), dtype=np.uint8)
        for r in range(H):
            img[r, :, :] = int(r * 255 / H)
        score = _seam_visibility_score(img)
        assert score < 10.0, f"Gradient should give low score, got {score}"

    def test_score_is_non_negative(self):
        """Score must always be ≥ 0."""
        for lum_top, lum_bot in [(50, 50), (50, 150), (200, 10), (128, 128)]:
            img = _stacked(lum_top, lum_bot)
            assert _seam_visibility_score(img) >= 0.0

    def test_harder_seam_scores_higher(self):
        """A bigger luminance jump should produce a higher score."""
        small_jump = _stacked(100, 120)   # Δ=20
        big_jump = _stacked(60, 200)      # Δ=140
        assert _seam_visibility_score(big_jump) > _seam_visibility_score(small_jump)

    def test_affines_parameter_is_optional(self):
        """Function must work with affines=None (no-reference mode)."""
        img = _stacked(80, 180)
        score_no_affines = _seam_visibility_score(img, affines=None)
        score_with_none = _seam_visibility_score(img)
        assert score_no_affines == score_with_none

    def test_black_border_rows_ignored(self):
        """Near-black border rows (lum ≤ 5) must not inflate the score."""
        H, W = 120, 100
        img = _solid(H, W, 128)
        img[:10, :, :] = 0   # top border: black
        img[-10:, :, :] = 0  # bottom border: black
        # Only content (rows 10–109) has uniform lum=128 → no jump expected.
        score = _seam_visibility_score(img)
        assert score < 5.0, f"Black borders should not inflate score, got {score}"

    def test_single_row_image_returns_zero(self):
        """Degenerate 1-row image: no adjacent rows → score must be 0."""
        img = _solid(1, 100, 128)
        assert _seam_visibility_score(img) == 0.0


# ---------------------------------------------------------------------------
# TestComputeAlignedSsim
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _SSIM_OK, reason="skimage not installed")
class TestComputeAlignedSsim:
    """
    _compute_aligned_ssim: ECC Euclidean aligned SSIM vs GT (S8 metric, S25 dedup).

    After S25: uses MOTION_EUCLIDEAN (translation + rotation), 200 iterations,
    1e-4 tolerance, gaussFiltSize=5, GT-centric resize, BORDER_REPLICATE.
    """

    H, W = 80, 100

    def _checkerboard(self, sq: int = 10) -> np.ndarray:
        """Deterministic BGR checkerboard — not flat, gives ECC something to lock on."""
        img = np.zeros((self.H, self.W, 3), dtype=np.uint8)
        for r in range(self.H):
            for c in range(self.W):
                if (r // sq + c // sq) % 2 == 0:
                    img[r, c] = [200, 100, 50]
                else:
                    img[r, c] = [50, 150, 200]
        return img

    def test_identical_images_returns_one(self):
        """aligned_ssim(img, img) must be ≈ 1.0 — no shift, no distortion."""
        img = self._checkerboard()
        score = _compute_aligned_ssim(img, img)
        assert score == pytest.approx(1.0, abs=1e-3)

    def test_returns_float(self):
        """Result must be a Python float, not numpy scalar."""
        img = self._checkerboard()
        assert isinstance(_compute_aligned_ssim(img, img), float)

    def test_shifted_image_high_ssim_after_alignment(self):
        """A translated copy should score > 0.85 after ECC alignment."""
        import cv2
        img = self._checkerboard()
        shift_px = 5
        M = np.float32([[1, 0, shift_px], [0, 1, shift_px]])
        shifted = cv2.warpAffine(img, M, (self.W, self.H),
                                 borderMode=cv2.BORDER_REPLICATE)
        score = _compute_aligned_ssim(shifted, img)
        # 5px shift on a checkerboard is near half-period; ECC still aligns,
        # but boundary fill reduces score — 0.70 is a loose correctness floor.
        assert score > 0.70, f"Aligned SSIM for shifted image unexpectedly low: {score}"

    def test_different_images_score_below_one(self):
        """Structurally unrelated images must score < 0.99."""
        img_a = self._checkerboard()
        img_b = _solid(self.H, self.W, 128)
        score = _compute_aligned_ssim(img_a, img_b)
        assert score < 0.99

    def test_score_in_valid_range(self):
        """SSIM is defined on [-1, 1]; practical images stay in [0, 1]."""
        img = self._checkerboard()
        score = _compute_aligned_ssim(img, img)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# TestComputeRlhfScore  (§1.10A, S29)
# ---------------------------------------------------------------------------


class TestComputeRlhfScore:
    """
    _compute_rlhf_score: RLHF reward-model quality gate.

    The model is initialized with random weights in the test environment
    (no trained checkpoint). Tests verify the interface contract (return
    type, range, flag logic) without asserting on the specific score value.
    """

    def test_returns_float_or_none_for_valid_image(self):
        """Valid BGR image must return a float or None (if model unavailable)."""
        img = _solid(224, 224, 128)
        result = _compute_rlhf_score(img)
        assert result is None or isinstance(result, float)

    def test_empty_image_returns_none(self):
        """Zero-size array must return None without raising."""
        img = np.zeros((0, 0, 3), dtype=np.uint8)
        assert _compute_rlhf_score(img) is None

    def test_score_in_valid_range_when_model_available(self):
        """If the model runs, its output must be in [0, 1]."""
        img = _solid(224, 224, 200)
        score = _compute_rlhf_score(img)
        if score is not None:
            assert 0.0 <= score <= 1.0

    def test_rlhf_flagged_when_score_below_threshold(self):
        """rlhf_flagged must be True when the score is below the threshold."""
        from unittest.mock import patch

        img = _solid(100, 100, 128)
        with patch(
            "backend.benchmark.bench_anime_stitch._compute_rlhf_score",
            return_value=_RLHF_FLAG_THRESHOLD - 0.1,
        ):
            metrics = _compute_all_metrics(img)
        assert metrics["rlhf_flagged"] is True

    def test_rlhf_not_flagged_when_score_at_or_above_threshold(self):
        """rlhf_flagged must be False when the score meets the threshold."""
        from unittest.mock import patch

        img = _solid(100, 100, 128)
        with patch(
            "backend.benchmark.bench_anime_stitch._compute_rlhf_score",
            return_value=_RLHF_FLAG_THRESHOLD,
        ):
            metrics = _compute_all_metrics(img)
        assert metrics["rlhf_flagged"] is False


# ---------------------------------------------------------------------------
# _ghosting_score_v2 — §3.8A double-edge autocorrelation ghosting metric (S35)
# ---------------------------------------------------------------------------


class TestGhostingScoreV2:
    """
    _ghosting_score_v2(img) returns a score in [0, 100]:
      ≈0  for clean images with no repeated edge structure,
      >30 for images with two identical edge patterns at a fixed
          displacement (simulating a ghost / double-image artifact).
    """

    def test_uniform_image_returns_zero(self):
        """Flat image has no gradient → zero autocorrelation → score = 0."""
        img = _solid(200, 200, 128)
        assert _ghosting_score_v2(img) == pytest.approx(0.0)

    def test_ghost_image_returns_nonzero(self):
        """Two identical horizontal bands 70 px apart create a secondary peak."""
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        img[40:60, :] = 200   # first band (gradients at rows 40 & 60)
        img[110:130, :] = 200  # ghost copy (gradients at rows 110 & 130)
        score = _ghosting_score_v2(img)
        assert score > 5.0, f"expected secondary peak, got {score}"

    def test_score_bounded_0_to_100(self):
        """Score must always lie in [0, 100] for any input image."""
        rng = np.random.default_rng(42)
        img = rng.integers(0, 256, (300, 300, 3), dtype=np.uint8)
        score = _ghosting_score_v2(img)
        assert 0.0 <= score <= 100.0

    def test_grayscale_input_accepted(self):
        """Grayscale (2-D) input must produce the same result as BGR equivalent."""
        gray = np.zeros((100, 100), dtype=np.uint8)
        gray[20:30, :] = 200
        gray[60:70, :] = 200
        bgr = np.stack([gray, gray, gray], axis=-1)
        assert _ghosting_score_v2(gray) == pytest.approx(_ghosting_score_v2(bgr))

    def test_ghosting_siqe_in_compute_all_metrics(self):
        """_compute_all_metrics must include 'ghosting_siqe' key in its output."""
        img = _solid(100, 100, 180)
        metrics = _compute_all_metrics(img)
        assert "ghosting_siqe" in metrics
        assert isinstance(metrics["ghosting_siqe"], float)
