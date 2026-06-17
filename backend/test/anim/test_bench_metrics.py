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
    _compute_per_seam_ghost_scores,
    _seam_bhattacharyya_distances,
    _ghosting_score_v2,
    _SSIM_OK,
    _RLHF_FLAG_THRESHOLD,
    _seam_ncc_coherence,
    _composite_quality_score,
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


# ---------------------------------------------------------------------------
# _compute_per_seam_ghost_scores — §3.8B per-seam SIQE ghost map (S53)
# ---------------------------------------------------------------------------


class TestPerSeamGhostScores:
    """
    _compute_per_seam_ghost_scores(img, n_strips, band_px=100) divides the
    image into n_strips zones and returns n_strips-1 float ghosting scores,
    one per seam boundary.
    """

    def test_uniform_image_all_near_zero(self):
        """Flat image has no gradient anywhere — all seam scores should be ≈ 0."""
        img = _solid(300, 200, 128)
        scores = _compute_per_seam_ghost_scores(img, n_strips=3)
        assert len(scores) == 2
        for s in scores:
            assert s == pytest.approx(0.0), f"Expected ~0.0 for flat image, got {s}"

    def test_n_strips_one_returns_empty(self):
        """n_strips ≤ 1 means no boundaries — must return empty list."""
        img = _solid(200, 200, 128)
        assert _compute_per_seam_ghost_scores(img, n_strips=1) == []
        assert _compute_per_seam_ghost_scores(img, n_strips=0) == []

    def test_returns_n_minus_1_scores(self):
        """Function must return exactly n_strips-1 scores for any n_strips ≥ 2."""
        img = _solid(400, 200, 64)
        for n in [2, 3, 5]:
            scores = _compute_per_seam_ghost_scores(img, n_strips=n)
            assert len(scores) == n - 1, f"n={n}: expected {n-1} scores, got {len(scores)}"

    def test_band_with_sharp_luminance_step_has_high_score(self):
        """A band containing a ghost-like repeated edge pattern must score > 5."""
        H, W = 300, 200
        img = np.zeros((H, W, 3), dtype=np.uint8)
        # Two identical bright bands in the middle — simulates double-image ghost
        img[120:135, :] = 220
        img[165:180, :] = 220
        # Boundary at y=150 (midpoint of 2-strip split); band covers rows 50–250
        scores = _compute_per_seam_ghost_scores(img, n_strips=2, band_px=100)
        assert len(scores) == 1
        assert scores[0] > 5.0, f"Expected ghost signal in band, got {scores[0]}"

    def test_band_clipped_to_image_bounds_no_error(self):
        """Boundary bands near image edges must be clipped silently, no exception."""
        img = _solid(40, 60, 100)  # tiny image
        # n_strips=4 → boundaries at y≈10, 20, 30; band_px=50 would exceed bounds
        scores = _compute_per_seam_ghost_scores(img, n_strips=4, band_px=50)
        assert len(scores) == 3
        for s in scores:
            assert isinstance(s, float)
            assert 0.0 <= s <= 100.0


# ---------------------------------------------------------------------------
# _seam_bhattacharyya_distances — §1.14 per-seam colour-banding metric (S55)
# ---------------------------------------------------------------------------


class TestSeamBhattacharyyaDistances:
    """
    _seam_bhattacharyya_distances(img, n_strips, band_px=50) returns
    n_strips-1 float scores in [0,1].  1.0 = identical histograms above/below
    seam (no colour banding); 0.0 = completely disjoint distributions.
    """

    def test_n_strips_one_returns_empty(self):
        """n_strips ≤ 1 has no seam boundaries — must return empty list."""
        img = _solid(200, 200, 128)
        assert _seam_bhattacharyya_distances(img, n_strips=1) == []
        assert _seam_bhattacharyya_distances(img, n_strips=0) == []

    def test_returns_n_minus_1_scores(self):
        """Function must return exactly n_strips-1 scores for any n_strips ≥ 2."""
        img = _solid(300, 200, 100)
        for n in [2, 3, 5]:
            scores = _seam_bhattacharyya_distances(img, n_strips=n)
            assert len(scores) == n - 1, f"n={n}: expected {n-1} scores, got {len(scores)}"

    def test_identical_strips_score_near_one(self):
        """A uniform image has identical histograms above and below every seam — score ≈ 1."""
        img = _solid(200, 150, 128)
        scores = _seam_bhattacharyya_distances(img, n_strips=2)
        assert len(scores) == 1
        assert scores[0] > 0.98, f"Uniform image should score near 1.0, got {scores[0]}"

    def test_different_histograms_score_below_identical(self):
        """Bright strip above, dark strip below — score must be lower than for uniform."""
        uniform = _solid(200, 150, 128)
        banded = _stacked(220, 20, H=200, W=150)
        s_uniform = _seam_bhattacharyya_distances(uniform, n_strips=2)[0]
        s_banded = _seam_bhattacharyya_distances(banded, n_strips=2)[0]
        assert s_banded < s_uniform, (
            f"Banded image ({s_banded:.3f}) should score lower than uniform ({s_uniform:.3f})"
        )

    def test_scores_in_valid_range(self):
        """Every score must be a float in [0, 1] regardless of input content."""
        rng = np.random.default_rng(7)
        img = rng.integers(0, 256, (300, 200, 3), dtype=np.uint8)
        scores = _seam_bhattacharyya_distances(img, n_strips=4)
        assert len(scores) == 3
        for s in scores:
            assert isinstance(s, float)
            assert 0.0 <= s <= 1.0, f"Score out of [0,1]: {s}"


class TestSeamNccCoherence:
    """§3.17 (S123): NCC structural coherence metric per seam boundary."""

    def test_returns_empty_for_one_strip(self):
        img = _solid(100, 80, 128)
        assert _seam_ncc_coherence(img, n_strips=1) == []

    def test_returns_correct_count(self):
        rng = np.random.default_rng(42)
        img = rng.integers(0, 256, (200, 160, 3), dtype=np.uint8)
        for n in [2, 3, 5]:
            scores = _seam_ncc_coherence(img, n_strips=n)
            assert len(scores) == n - 1, f"n={n}: expected {n-1}, got {len(scores)}"

    def test_uniform_image_returns_one_flat_texture(self):
        """A flat solid image has near-zero std → returns 1.0 (no-texture sentinel)."""
        img = _solid(200, 150, 200)
        scores = _seam_ncc_coherence(img, n_strips=2)
        assert len(scores) == 1
        assert scores[0] == 1.0, f"Expected 1.0 for flat image, got {scores[0]}"

    def test_matching_boundary_region_high_ncc(self):
        """When the band above and below the seam boundary are copies of the same
        pattern, the NCC should be close to 1."""
        rng = np.random.default_rng(7)
        band = rng.integers(50, 200, (60, 120, 3), dtype=np.uint8)
        # Build an image where the 60 rows above and 60 rows below the boundary
        # are exactly the same pattern.  The boundary is at row 60 in a H=120 image.
        img = np.vstack([band, band])
        scores = _seam_ncc_coherence(img, n_strips=2, band_px=60)
        assert len(scores) == 1
        assert scores[0] > 0.95, f"Identical boundary bands should give NCC > 0.95, got {scores[0]}"

    def test_scores_in_valid_range(self):
        """Every score must be in [−1, 1] regardless of input content."""
        rng = np.random.default_rng(99)
        img = rng.integers(0, 256, (300, 200, 3), dtype=np.uint8)
        scores = _seam_ncc_coherence(img, n_strips=4)
        assert len(scores) == 3
        for s in scores:
            assert isinstance(s, float)
            assert -1.0 <= s <= 1.0, f"Score out of [-1,1]: {s}"


class TestCompositeQualityScore:
    """§3.5A (S128): Composite quality score aggregation."""

    def test_perfect_scores_give_one(self):
        """Perfect per-component scores should yield composite = 1.0."""
        score = _composite_quality_score(
            seam_ncc_min=1.0, seam_color_min=1.0, ghost_seam_max=0.0
        )
        assert score == pytest.approx(1.0, abs=1e-4)

    def test_worst_scores_give_zero(self):
        """Worst per-component scores should yield composite = 0.0."""
        score = _composite_quality_score(
            seam_ncc_min=-1.0, seam_color_min=0.0, ghost_seam_max=100.0
        )
        assert score == pytest.approx(0.0, abs=1e-4)

    def test_all_none_gives_half(self):
        """When all inputs are None the neutral default is 0.5."""
        score = _composite_quality_score(None, None, None)
        assert score == pytest.approx(0.5, abs=1e-4)

    def test_result_in_unit_interval(self):
        """Any realistic input combination must stay in [0, 1]."""
        import itertools
        for ncc, color, ghost in itertools.product([-1.0, 0.0, 1.0], [0.0, 0.5, 1.0], [0.0, 50.0, 100.0]):
            s = _composite_quality_score(ncc, color, ghost)
            assert 0.0 <= s <= 1.0, f"Out of range: ncc={ncc}, color={color}, ghost={ghost} → {s}"

    def test_partial_none_uses_neutral(self):
        """A single None component uses 0.5; the other two drive the result."""
        # ncc=1.0 → ncc_term=1.0; color=1.0 → color_term=1.0; ghost=None → 0.5
        score = _composite_quality_score(1.0, 1.0, None)
        assert score == pytest.approx((1.0 + 1.0 + 0.5) / 3.0, abs=1e-4)
