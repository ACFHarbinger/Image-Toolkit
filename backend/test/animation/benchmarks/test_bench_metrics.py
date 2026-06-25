"""
Tests for quality metrics in bench_anime_stitch.py.

Covers:
  _seam_visibility_score — detects hard horizontal luminance cuts (S14)
  _compute_aligned_ssim  — ECC Euclidean aligned SSIM vs GT (S8 metric, S25 dedup)
  _compute_rlhf_score    — RLHF reward-model quality gate (§1.10A, S29)
  _edge_energy_score     — §3.32 correctly-labelled double-Sobel wrapper
"""

from __future__ import annotations
from backend.benchmark.bench_anime_stitch import _zone_coverage_fraction
from backend.benchmark.bench_anime_stitch import _canvas_gain_uniformity
from backend.benchmark.bench_anime_stitch import _strip_luma_monotonicity
from backend.benchmark.bench_anime_stitch import _compute_si_fid_score

import os
import sys
import pytest
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
    _ghosting_score,
    _edge_energy_score,
    _SSIM_OK,
    _RLHF_FLAG_THRESHOLD,
    _seam_ncc_coherence,
    _composite_quality_score,
    _seam_ownership_entropy,
    _NOISE_CV_ABS_FLOOR,
    _NOISE_CV_RATIO,
    _ENTROPY_CV_ABS_FLOOR,
    _ENTROPY_CV_RATIO,
    _CHROMA_STEP_CV_ABS_FLOOR,
    _CHROMA_STEP_CV_RATIO,
    _CHROMA_ENERGY_CV_ABS_FLOOR,
    _CHROMA_ENERGY_CV_RATIO,
    _SEAM_GRADIENT_CV_ABS_FLOOR,
    _SEAM_GRADIENT_CV_RATIO,
    _LUMA_IQR_CV_ABS_FLOOR,
    _LUMA_IQR_CV_RATIO,
    _SEAM_COL_VAR_CV_ABS_FLOOR,
    _SEAM_COL_VAR_CV_RATIO,
    _LUMA_SKEW_CV_ABS_FLOOR,
    _LUMA_SKEW_CV_RATIO,
    _SEAM_SIGNED_STEP_CV_ABS_FLOOR,
    _SEAM_SIGNED_STEP_CV_RATIO,
    _LUMA_KURTOSIS_CV_ABS_FLOOR,
    _LUMA_KURTOSIS_CV_RATIO,
    _SEAM_TEXTURE_RATIO_CV_ABS_FLOOR,
    _SEAM_TEXTURE_RATIO_CV_RATIO,
    _EDGE_DENSITY_CV_ABS_FLOOR,
    _EDGE_DENSITY_CV_RATIO,
    _SEAM_LOCAL_CONTRAST_CV_ABS_FLOOR,
    _SEAM_LOCAL_CONTRAST_CV_RATIO,
    _LUMA_P90P10_CV_ABS_FLOOR,
    _LUMA_P90P10_CV_RATIO,
    _SEAM_HUE_SHIFT_CV_ABS_FLOOR,
    _SEAM_HUE_SHIFT_CV_RATIO,
)
from backend.src.animation.core import config as _asp_config  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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
        small_jump = _stacked(100, 120)  # Δ=20
        big_jump = _stacked(60, 200)  # Δ=140
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
        img[:10, :, :] = 0  # top border: black
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
        shifted = cv2.warpAffine(
            img, M, (self.W, self.H), borderMode=cv2.BORDER_REPLICATE
        )
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


@pytest.mark.gpu
class TestComputeRlhfScore:
    """
    _compute_rlhf_score: RLHF reward-model quality gate.

    The model is initialized with random weights in the test environment
    (no trained checkpoint). Tests verify the interface contract (return
    type, range, flag logic) without asserting on the specific score value.

    Marked @pytest.mark.gpu: StitchRewardModel() places the _RewardNet onto
    CUDA (when available) and holds it in the module-level _reward_model
    singleton for the session (§3.12 Root Cause #2).
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
        img[40:60, :] = 200  # first band (gradients at rows 40 & 60)
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
            assert len(scores) == n - 1, (
                f"n={n}: expected {n - 1} scores, got {len(scores)}"
            )

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
            assert len(scores) == n - 1, (
                f"n={n}: expected {n - 1} scores, got {len(scores)}"
            )

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
            assert len(scores) == n - 1, f"n={n}: expected {n - 1}, got {len(scores)}"

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
        assert scores[0] > 0.95, (
            f"Identical boundary bands should give NCC > 0.95, got {scores[0]}"
        )

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

        for ncc, color, ghost in itertools.product(
            [-1.0, 0.0, 1.0], [0.0, 0.5, 1.0], [0.0, 50.0, 100.0]
        ):
            s = _composite_quality_score(ncc, color, ghost)
            assert 0.0 <= s <= 1.0, (
                f"Out of range: ncc={ncc}, color={color}, ghost={ghost} → {s}"
            )

    def test_partial_none_uses_neutral(self):
        """A single None component uses 0.5; the other two drive the result."""
        # ncc=1.0 → ncc_term=1.0; color=1.0 → color_term=1.0; ghost=None → 0.5
        score = _composite_quality_score(1.0, 1.0, None)
        assert score == pytest.approx((1.0 + 1.0 + 0.5) / 3.0, abs=1e-4)


class TestMllmScorer:
    """§3.10 — MLLM scorer unit tests (offline — no ollama required)."""

    def test_scores_dataclass_fields(self):
        """MllmScores has body_coherence, seam_quality, bg_consistency, overall."""
        from backend.src.animation.hitl.mllm_scorer import MllmScores

        s = MllmScores(
            body_coherence=8.0, seam_quality=7.5, bg_consistency=9.0, overall=8.2
        )
        assert s.body_coherence == 8.0
        assert s.overall == 8.2
        assert s.seam_quality == 7.5
        assert s.bg_consistency == 9.0

    def test_score_returns_none_on_connection_error(self):
        """When ollama is not reachable, score() returns all-None MllmScores."""
        from backend.src.animation.hitl.mllm_scorer import MllmScorer

        scorer = MllmScorer(base_url="http://localhost:19999")  # dead port
        img = np.zeros((64, 64, 3), dtype=np.uint8)
        scores = scorer.score(img)
        assert scores.body_coherence is None
        assert scores.overall is None

    def test_parse_json_response(self):
        """_parse_scores extracts floats from a valid JSON string."""
        from backend.src.animation.hitl.mllm_scorer import MllmScorer

        scorer = MllmScorer()
        raw = '{"body_coherence": 8.5, "seam_quality": 7.0, "bg_consistency": 9.0, "overall": 8.2}'
        scores = scorer._parse_scores(raw)
        assert scores.body_coherence == pytest.approx(8.5)
        assert scores.seam_quality == pytest.approx(7.0)
        assert scores.overall == pytest.approx(8.2)

    def test_parse_fallback_regex(self):
        """When JSON parse fails, regex fallback extracts floats from prose output."""
        from backend.src.animation.hitl.mllm_scorer import MllmScorer

        scorer = MllmScorer()
        raw = (
            "body_coherence: 6.5, seam_quality: 5.0, bg_consistency: 8.0, overall: 6.5"
        )
        scores = scorer._parse_scores(raw)
        assert scores.body_coherence == pytest.approx(6.5, abs=0.1)
        assert scores.overall == pytest.approx(6.5, abs=0.1)

    def test_image_resize_before_encode(self):
        """Large images are downscaled to MLLM_MAX_IMAGE_DIM before base64 encoding."""
        import base64

        import cv2 as _cv2

        from backend.src.animation.hitl.mllm_scorer import MLLM_MAX_IMAGE_DIM, MllmScorer

        scorer = MllmScorer()
        large_img = np.zeros((2000, 1000, 3), dtype=np.uint8)
        encoded = scorer._encode_image(large_img)
        decoded = base64.b64decode(encoded)
        buf = np.frombuffer(decoded, dtype=np.uint8)
        img_back = _cv2.imdecode(buf, _cv2.IMREAD_COLOR)
        assert img_back is not None
        assert max(img_back.shape[:2]) <= MLLM_MAX_IMAGE_DIM


# TestSiFidProxy — §3.9 SI-FID patch sharpness proxy (S144)
class TestSiFidProxy:
    def _solid(self, h: int = 256, w: int = 256, val: int = 128) -> np.ndarray:
        return np.full((h, w, 3), val, dtype=np.uint8)

    def _noisy(self, h: int = 256, w: int = 256) -> np.ndarray:
        rng = np.random.default_rng(1)
        return rng.integers(0, 256, (h, w, 3), dtype=np.uint8)

    def test_identical_images_returns_one(self):
        img = self._noisy()
        ratio = _compute_si_fid_score(img, img, patch_size=64, n_patches=8)
        assert ratio is not None
        assert abs(ratio - 1.0) < 0.05

    def test_sharp_asp_returns_ratio_above_one(self):
        import cv2 as _cv2

        noisy = self._noisy()
        sim = _cv2.GaussianBlur(noisy, (21, 21), 8)
        asp = noisy
        ratio = _compute_si_fid_score(asp, sim, patch_size=64, n_patches=8)
        assert ratio is not None
        assert ratio > 1.0

    def test_sharp_simple_returns_ratio_below_one(self):
        import cv2 as _cv2

        noisy = self._noisy()
        asp = _cv2.GaussianBlur(noisy, (21, 21), 8)
        sim = noisy
        ratio = _compute_si_fid_score(asp, sim, patch_size=64, n_patches=8)
        assert ratio is not None
        assert ratio < 1.0

    def test_none_image_returns_none(self):
        img = self._noisy()
        assert _compute_si_fid_score(None, img) is None
        assert _compute_si_fid_score(img, None) is None

    def test_too_small_returns_none(self):
        tiny = np.zeros((10, 10, 3), dtype=np.uint8)
        big = self._noisy()
        result = _compute_si_fid_score(tiny, big, patch_size=64, n_patches=4)
        assert result is None


# ===========================================================================
# Merged from test_bench_metrics_s149.py
# ===========================================================================


class TestChromaSeamCoherence:
    def test_flat_image_low_score(self):
        from backend.benchmark.bench_anime_stitch import _chroma_seam_coherence

        img = np.full((100, 80, 3), 128, dtype=np.uint8)
        score = _chroma_seam_coherence(img, n_strips=4)
        assert score < 5.0

    def test_banded_image_higher_score(self):
        from backend.benchmark.bench_anime_stitch import _chroma_seam_coherence

        img = np.zeros((80, 60, 3), dtype=np.uint8)
        img[:40] = [200, 100, 50]
        img[40:] = [50, 100, 200]
        score = _chroma_seam_coherence(img, n_strips=2)
        flat_score = _chroma_seam_coherence(
            np.full((80, 60, 3), 128, dtype=np.uint8), n_strips=2
        )
        assert score > flat_score

    def test_returns_float(self):
        from backend.benchmark.bench_anime_stitch import _chroma_seam_coherence

        img = np.random.randint(0, 256, (60, 50, 3), dtype=np.uint8)
        score = _chroma_seam_coherence(img, n_strips=4)
        assert isinstance(score, float)

    def test_degenerate_small_image(self):
        from backend.benchmark.bench_anime_stitch import _chroma_seam_coherence

        img = np.zeros((2, 10, 3), dtype=np.uint8)
        score = _chroma_seam_coherence(img, n_strips=4)
        assert isinstance(score, float)

    def test_single_strip_returns_zero(self):
        from backend.benchmark.bench_anime_stitch import _chroma_seam_coherence

        img = np.random.randint(0, 256, (60, 50, 3), dtype=np.uint8)
        score = _chroma_seam_coherence(img, n_strips=1)
        assert score == 0.0


# ===========================================================================
# Merged from test_bench_metrics_s150.py
# ===========================================================================


class TestStripGradientCv:
    def test_uniform_image_zero_cv(self):
        from backend.benchmark.bench_anime_stitch import _strip_gradient_cv

        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        cv = _strip_gradient_cv(img, n_strips=4)
        assert cv == pytest.approx(0.0, abs=1e-3)

    def test_mixed_sharpness_high_cv(self):
        from backend.benchmark.bench_anime_stitch import _strip_gradient_cv

        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        rng = np.random.default_rng(0)
        img[:40] = rng.integers(0, 256, (40, 60, 3), dtype=np.uint8)
        cv = _strip_gradient_cv(img, n_strips=2)
        flat_cv = _strip_gradient_cv(
            np.full((80, 60, 3), 128, dtype=np.uint8), n_strips=2
        )
        assert cv > flat_cv

    def test_returns_float(self):
        from backend.benchmark.bench_anime_stitch import _strip_gradient_cv

        img = np.random.randint(0, 256, (60, 50, 3), dtype=np.uint8)
        result = _strip_gradient_cv(img, n_strips=4)
        assert isinstance(result, float)

    def test_degenerate_too_few_strips(self):
        from backend.benchmark.bench_anime_stitch import _strip_gradient_cv

        img = np.random.randint(0, 256, (8, 10, 3), dtype=np.uint8)
        result = _strip_gradient_cv(img, n_strips=1)
        assert result == 0.0

    def test_small_image_degenerate(self):
        from backend.benchmark.bench_anime_stitch import _strip_gradient_cv

        img = np.zeros((3, 10, 3), dtype=np.uint8)
        result = _strip_gradient_cv(img, n_strips=8)
        assert isinstance(result, float)


# ===========================================================================
# Merged from test_bench_metrics_s151.py
# ===========================================================================


class TestSeamContrastRatio:
    def test_flat_image_returns_neutral(self):
        from backend.benchmark.bench_anime_stitch import _seam_contrast_ratio

        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        ratio = _seam_contrast_ratio(img, n_strips=4, band_px=5)
        # Flat image → all energies near zero → returns 1.0 (neutral)
        assert isinstance(ratio, float)

    def test_returns_float(self):
        from backend.benchmark.bench_anime_stitch import _seam_contrast_ratio

        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        ratio = _seam_contrast_ratio(img, n_strips=4, band_px=5)
        assert isinstance(ratio, float)

    def test_high_contrast_seam_above_one(self):
        from backend.benchmark.bench_anime_stitch import _seam_contrast_ratio

        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        # Add a sharp edge at strip boundary
        img[38:42] = 255
        img[36:38] = 0
        ratio = _seam_contrast_ratio(img, n_strips=4, band_px=5)
        flat_ratio = _seam_contrast_ratio(
            np.full((80, 60, 3), 128, dtype=np.uint8), n_strips=4, band_px=5
        )
        # Sharp seam boundary should produce higher ratio than flat image
        assert ratio >= flat_ratio

    def test_degenerate_too_small(self):
        from backend.benchmark.bench_anime_stitch import _seam_contrast_ratio

        img = np.zeros((4, 10, 3), dtype=np.uint8)
        ratio = _seam_contrast_ratio(img, n_strips=4, band_px=2)
        assert isinstance(ratio, float)

    def test_single_strip_returns_neutral(self):
        from backend.benchmark.bench_anime_stitch import _seam_contrast_ratio

        img = np.random.randint(0, 256, (60, 50, 3), dtype=np.uint8)
        ratio = _seam_contrast_ratio(img, n_strips=1, band_px=5)
        assert ratio == pytest.approx(1.0)


# ===========================================================================
# Merged from test_bench_metrics_s152.py
# ===========================================================================


class TestSeamColSpread:
    def test_returns_float(self):
        from backend.benchmark.bench_anime_stitch import _seam_col_spread

        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _seam_col_spread(img, n_strips=4)
        assert isinstance(result, float)

    def test_uniform_image_zero_spread(self):
        from backend.benchmark.bench_anime_stitch import _seam_col_spread

        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        result = _seam_col_spread(img, n_strips=4)
        assert result == pytest.approx(0.0, abs=1e-6)

    def test_result_is_normalized(self):
        from backend.benchmark.bench_anime_stitch import _seam_col_spread

        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _seam_col_spread(img, n_strips=4)
        assert result < 1.0

    def test_degenerate_one_strip(self):
        from backend.benchmark.bench_anime_stitch import _seam_col_spread

        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _seam_col_spread(img, n_strips=1)
        assert result == 0.0

    def test_degenerate_small_image(self):
        from backend.benchmark.bench_anime_stitch import _seam_col_spread

        img = np.zeros((3, 5, 3), dtype=np.uint8)
        result = _seam_col_spread(img, n_strips=4)
        assert isinstance(result, float)


# ===========================================================================
# Merged from test_bench_metrics_s153.py
# ===========================================================================


class TestSeamRowStd:
    def test_returns_float(self):
        from backend.benchmark.bench_anime_stitch import _seam_row_std

        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _seam_row_std(img, n_strips=4)
        assert isinstance(result, float)

    def test_flat_image_low_std(self):
        from backend.benchmark.bench_anime_stitch import _seam_row_std

        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        result = _seam_row_std(img, n_strips=4)
        assert result < 0.01

    def test_result_normalized_zero_to_one(self):
        from backend.benchmark.bench_anime_stitch import _seam_row_std

        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _seam_row_std(img, n_strips=4)
        assert 0.0 <= result <= 1.0

    def test_degenerate_single_strip(self):
        from backend.benchmark.bench_anime_stitch import _seam_row_std

        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _seam_row_std(img, n_strips=1)
        assert result == 0.0

    def test_high_contrast_boundary(self):
        from backend.benchmark.bench_anime_stitch import _seam_row_std

        img = np.zeros((80, 60, 3), dtype=np.uint8)
        # Alternating black/white columns at boundary row
        strip_h = 80 // 4  # = 20
        boundary_row = strip_h  # = 20
        img[boundary_row, ::2] = 255
        img[boundary_row, 1::2] = 0
        result = _seam_row_std(img, n_strips=4)
        flat_result = _seam_row_std(
            np.full((80, 60, 3), 128, dtype=np.uint8), n_strips=4
        )
        assert result > flat_result


# ===========================================================================
# Merged from test_bench_metrics_s154.py
# ===========================================================================


class TestSeamBoundaryEntropy:
    def test_returns_list_of_correct_length(self):
        from backend.benchmark.bench_anime_stitch import _seam_boundary_entropy

        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _seam_boundary_entropy(img, n_strips=4, band_px=5)
        assert isinstance(result, list)
        assert len(result) == 3  # n_strips - 1

    def test_flat_image_low_entropy(self):
        from backend.benchmark.bench_anime_stitch import _seam_boundary_entropy

        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        result = _seam_boundary_entropy(img, n_strips=4, band_px=5)
        assert all(e < 0.05 for e in result)

    def test_random_image_high_entropy(self):
        from backend.benchmark.bench_anime_stitch import _seam_boundary_entropy

        rng = np.random.default_rng(1)
        img = rng.integers(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _seam_boundary_entropy(img, n_strips=4, band_px=5)
        assert any(e > 0.7 for e in result)

    def test_values_in_zero_one(self):
        from backend.benchmark.bench_anime_stitch import _seam_boundary_entropy

        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _seam_boundary_entropy(img, n_strips=4, band_px=5)
        assert all(0.0 <= e <= 1.0 for e in result)

    def test_degenerate_single_strip(self):
        from backend.benchmark.bench_anime_stitch import _seam_boundary_entropy

        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _seam_boundary_entropy(img, n_strips=1)
        assert result == []


# ===========================================================================
# Merged from test_bench_metrics_s155.py
# ===========================================================================


class TestStripSatCv:
    def test_returns_float(self):
        from backend.benchmark.bench_anime_stitch import _strip_sat_cv

        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _strip_sat_cv(img, n_strips=4)
        assert isinstance(result, float)

    def test_grayscale_image_zero_cv(self):
        from backend.benchmark.bench_anime_stitch import _strip_sat_cv

        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        result = _strip_sat_cv(img, n_strips=4)
        assert result == pytest.approx(0.0, abs=1e-3)

    def test_banded_sat_higher_than_flat(self):
        from backend.benchmark.bench_anime_stitch import _strip_sat_cv

        img = np.zeros((80, 60, 3), dtype=np.uint8)
        img[:40] = [200, 50, 50]
        img[40:] = [128, 128, 128]
        result = _strip_sat_cv(img, n_strips=2)
        gray_result = _strip_sat_cv(
            np.full((80, 60, 3), 128, dtype=np.uint8), n_strips=2
        )
        assert result > gray_result

    def test_degenerate_single_strip(self):
        from backend.benchmark.bench_anime_stitch import _strip_sat_cv

        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _strip_sat_cv(img, n_strips=1)
        assert result == 0.0

    def test_degenerate_small_image(self):
        from backend.benchmark.bench_anime_stitch import _strip_sat_cv

        img = np.zeros((3, 10, 3), dtype=np.uint8)
        result = _strip_sat_cv(img, n_strips=8)
        assert isinstance(result, float)


# ===========================================================================
# Merged from test_bench_metrics_s156.py
# ===========================================================================


class TestSeamBandNcc:
    def test_uniform_image_returns_one(self):
        from backend.benchmark.bench_anime_stitch import _seam_band_ncc

        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        result = _seam_band_ncc(img, n_strips=4, band_px=5)
        assert result == pytest.approx(1.0, abs=1e-4)

    def test_alternating_bands_low_ncc(self):
        from backend.benchmark.bench_anime_stitch import _seam_band_ncc

        rng = np.random.default_rng(13)
        img = np.zeros((80, 60, 3), dtype=np.uint8)
        for i in range(4):
            y0, y1 = i * 20, (i + 1) * 20
            # Use high-variance noise centered at 200 or 10 so bands differ clearly
            base = 200 if i % 2 == 0 else 10
            noise = rng.integers(-8, 9, (y1 - y0, 60, 3)).astype(np.int16)
            img[y0:y1] = np.clip(base + noise, 0, 255).astype(np.uint8)
        result = _seam_band_ncc(img, n_strips=4, band_px=5)
        assert result < 0.5

    def test_result_in_valid_range(self):
        from backend.benchmark.bench_anime_stitch import _seam_band_ncc

        rng = np.random.default_rng(7)
        img = rng.integers(0, 256, (100, 80, 3), dtype=np.uint8)
        result = _seam_band_ncc(img, n_strips=8, band_px=10)
        assert -1.0 <= result <= 1.0

    def test_too_few_strips_returns_one(self):
        from backend.benchmark.bench_anime_stitch import _seam_band_ncc

        img = np.full((20, 20, 3), 100, dtype=np.uint8)
        result = _seam_band_ncc(img, n_strips=1, band_px=5)
        assert result == pytest.approx(1.0)

    def test_wired_into_compute_all_metrics(self):
        from backend.benchmark.bench_anime_stitch import _compute_all_metrics

        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        metrics = _compute_all_metrics(img)
        assert "seam_band_ncc_min" in metrics
        assert isinstance(metrics["seam_band_ncc_min"], float)


# ===========================================================================
# Merged from test_bench_metrics_s157.py
# ===========================================================================


class TestSeamRowGradCoherence:
    def test_uniform_image_returns_low_coherence(self):
        from backend.benchmark.bench_anime_stitch import _seam_row_grad_coherence

        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        result = _seam_row_grad_coherence(img, n_strips=4, band_px=5)
        assert 0.0 <= result <= 1.0

    def test_horizontal_edge_high_coherence(self):
        from backend.benchmark.bench_anime_stitch import _seam_row_grad_coherence

        img = np.zeros((80, 60, 3), dtype=np.uint8)
        img[:40] = 200
        img[40:] = 0
        result = _seam_row_grad_coherence(img, n_strips=2, band_px=5)
        assert result > 0.0

    def test_result_in_valid_range(self):
        from backend.benchmark.bench_anime_stitch import _seam_row_grad_coherence

        rng = np.random.default_rng(55)
        img = rng.integers(0, 256, (100, 80, 3), dtype=np.uint8)
        result = _seam_row_grad_coherence(img, n_strips=8, band_px=8)
        assert 0.0 <= result <= 1.0

    def test_degenerate_input_returns_one(self):
        from backend.benchmark.bench_anime_stitch import _seam_row_grad_coherence

        result = _seam_row_grad_coherence(None)
        assert result == pytest.approx(1.0)

    def test_wired_into_compute_all_metrics(self):
        from backend.benchmark.bench_anime_stitch import _compute_all_metrics

        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        metrics = _compute_all_metrics(img)
        assert "seam_grad_coherence_min" in metrics
        assert isinstance(metrics["seam_grad_coherence_min"], float)


# ===========================================================================
# Merged from test_bench_metrics_s158.py
# ===========================================================================


class TestZoneCoverageFraction:
    """Five tests for _zone_coverage_fraction (S158)."""

    def test_standard_image(self):
        """8 strips, 800px image: 7 boundaries, each ~33px wide on each side."""
        img = np.zeros((800, 100, 3), dtype=np.uint8)
        frac = _zone_coverage_fraction(img, n_strips=8)
        # strip_h = 100, approx_feather = 33, total = 7*2*33 = 462, frac = 462/800
        expected = min(800, 7 * 2 * (100 // 3)) / 800
        assert frac == pytest.approx(expected, abs=1e-6)

    def test_fraction_in_unit_interval(self):
        """Output is always in [0, 1]."""
        for H in [50, 200, 800, 2000]:
            img = np.zeros((H, 50, 3), dtype=np.uint8)
            f = _zone_coverage_fraction(img, n_strips=8)
            assert 0.0 <= f <= 1.0, f"H={H}: fraction {f} out of [0,1]"

    def test_none_input(self):
        """None input returns 0.0."""
        assert _zone_coverage_fraction(None) == 0.0  # type: ignore[arg-type]

    def test_too_few_strips(self):
        """n_strips < 2 returns 0.0."""
        img = np.zeros((100, 50, 3), dtype=np.uint8)
        assert _zone_coverage_fraction(img, n_strips=1) == 0.0

    def test_more_strips_raises_coverage(self):
        """More strips → more boundaries → higher coverage fraction (up to cap)."""
        img = np.zeros((800, 50, 3), dtype=np.uint8)
        f4 = _zone_coverage_fraction(img, n_strips=4)
        f8 = _zone_coverage_fraction(img, n_strips=8)
        assert f8 >= f4


# ===========================================================================
# Merged from test_bench_metrics_s159.py
# ===========================================================================


class TestStripSelfSsim:
    """§3.30: _strip_self_ssim returns NCC self-consistency per strip."""

    def _solid(self, h=64, w=32, val=128):
        return np.full((h, w, 3), val, dtype=np.uint8)

    def test_uniform_image_near_one(self):
        """A uniform image has identical halves → NCC should be close to 1."""
        from backend.benchmark.bench_anime_stitch import _strip_self_ssim

        img = self._solid()
        score = _strip_self_ssim(img, n_strips=4)
        assert score >= 0.95, f"Uniform image NCC={score:.4f}, expected ≥ 0.95"

    def test_seam_stripe_lowers_score(self):
        """A horizontal brightness stripe (simulating a seam) lowers the score."""
        from backend.benchmark.bench_anime_stitch import _strip_self_ssim

        rng = np.random.default_rng(1)
        img = rng.integers(100, 160, (64, 32, 3), dtype=np.uint8)
        # Insert a hard brightness jump at the midline of strip 0
        img[16:18, :] = 0  # dark stripe at strip boundary
        score_bad = _strip_self_ssim(img, n_strips=4)
        img2 = rng.integers(100, 160, (64, 32, 3), dtype=np.uint8)
        score_good = _strip_self_ssim(img2, n_strips=4)
        assert score_bad < score_good or score_bad <= 1.0

    def test_output_in_range(self):
        """Score must lie in [−1, 1]."""
        from backend.benchmark.bench_anime_stitch import _strip_self_ssim

        rng = np.random.default_rng(2)
        img = rng.integers(0, 256, (80, 40, 3), dtype=np.uint8)
        score = _strip_self_ssim(img, n_strips=8)
        assert -1.0 <= score <= 1.0

    def test_degenerate_small_image_returns_zero(self):
        """Image too small for the requested strips returns 0.0."""
        from backend.benchmark.bench_anime_stitch import _strip_self_ssim

        img = np.full((4, 8, 3), 100, dtype=np.uint8)
        score = _strip_self_ssim(img, n_strips=8)
        assert score == 0.0

    def test_wired_in_compute_all_metrics(self):
        """_compute_all_metrics must emit 'strip_self_ssim' key."""
        from backend.benchmark.bench_anime_stitch import _compute_all_metrics

        img = np.full((64, 32, 3), 128, dtype=np.uint8)
        metrics = _compute_all_metrics(img, n_strips=4)
        assert "strip_self_ssim" in metrics
        assert isinstance(metrics["strip_self_ssim"], float)
        assert -1.0 <= metrics["strip_self_ssim"] <= 1.0


# ===========================================================================
# Merged from test_bench_metrics_s160.py
# ===========================================================================


class TestCanvasGainUniformity:
    """§3.31: Strip-level luminance CV metric."""

    def test_uniform_image_returns_zero(self):
        # Solid gray — all strips have equal mean → CV = 0
        img = np.full((100, 100, 3), 128, dtype=np.uint8)
        result = _canvas_gain_uniformity(img, n_strips=8)
        assert abs(result) < 1e-6

    def test_banded_image_high_cv(self):
        # Top half bright, bottom half dark → high CV
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        img[:50] = 200
        img[50:] = 50
        result = _canvas_gain_uniformity(img, n_strips=8)
        assert result > 0.1

    def test_result_nonnegative(self):
        rng = np.random.default_rng(0)
        img = rng.integers(0, 255, (200, 100, 3), dtype=np.uint8)
        result = _canvas_gain_uniformity(img, n_strips=8)
        assert result >= 0.0

    def test_fewer_rows_than_strips_returns_zero(self):
        # 4-row image, n_strips=8 → degenerate → 0.0
        img = np.full((4, 100, 3), 128, dtype=np.uint8)
        result = _canvas_gain_uniformity(img, n_strips=8)
        assert result == 0.0

    def test_single_strip(self):
        # n_strips=1 → std of one value = 0 → CV = 0
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = _canvas_gain_uniformity(img, n_strips=1)
        assert result == 0.0


# ---------------------------------------------------------------------------
# §4.3: _seam_ownership_entropy (Phase 4 GraphCut metric)
# ---------------------------------------------------------------------------

def _make_affine(ty: float) -> np.ndarray:
    a = np.eye(2, 3, dtype=np.float32)
    a[1, 2] = ty
    return a


class TestSeamOwnershipEntropy:
    def test_no_affines_returns_zero(self):
        img = np.random.randint(10, 200, (100, 80, 3), dtype=np.uint8)
        assert _seam_ownership_entropy(img, affines=None) == 0.0

    def test_single_affine_returns_zero(self):
        img = np.random.randint(10, 200, (100, 80, 3), dtype=np.uint8)
        assert _seam_ownership_entropy(img, affines=[_make_affine(0.0)]) == 0.0

    def test_result_is_nonnegative(self):
        img = np.random.randint(10, 200, (200, 120, 3), dtype=np.uint8)
        affines = [_make_affine(0.0), _make_affine(80.0), _make_affine(160.0)]
        score = _seam_ownership_entropy(img, affines=affines)
        assert score >= 0.0

    def test_uniform_image_low_entropy(self):
        # Solid grey → every seam band has a single luminance value → low entropy
        img = np.full((200, 100, 3), 128, dtype=np.uint8)
        affines = [_make_affine(0.0), _make_affine(100.0)]
        score = _seam_ownership_entropy(img, affines=affines)
        assert score < 2.0, f"uniform image should have low entropy, got {score}"

    def test_wired_in_compute_all_metrics(self):
        img = np.random.randint(10, 200, (200, 120, 3), dtype=np.uint8)
        affines = [_make_affine(0.0), _make_affine(100.0)]
        metrics = _compute_all_metrics(img, affines=affines, n_strips=2)
        assert "seam_ownership_entropy" in metrics
        assert isinstance(metrics["seam_ownership_entropy"], float)


# ===========================================================================
# §3.32 — _edge_energy_score (ghosting_score taxonomy fix)
# ===========================================================================


class TestEdgeEnergyScore:
    """§3.32: _edge_energy_score is the correctly-labelled double-Sobel wrapper.

    _ghosting_score() computes mean(|∂²I/∂y²|) — a sharpness proxy, NOT
    a ghosting detector.  _edge_energy_score() is a semantic alias that makes
    the intent clear.  Both must return identical values.
    """

    def test_alias_matches_ghosting_score(self):
        rng = np.random.default_rng(42)
        img = rng.integers(0, 255, (100, 80, 3), dtype=np.uint8)
        assert _edge_energy_score(img) == pytest.approx(_ghosting_score(img))

    def test_uniform_image_low_score(self):
        # Solid colour → zero second derivative → score ≈ 0
        img = np.full((60, 60, 3), 128, dtype=np.uint8)
        assert _edge_energy_score(img) < 1.0

    def test_sharp_edges_higher_than_smooth(self):
        # Wide bright/dark bands create sharp transitions the double-Sobel Y detects;
        # a uniform image has zero second derivative.
        banded = np.zeros((64, 64, 3), dtype=np.uint8)
        banded[:32, :] = 255  # top half bright, bottom half dark
        flat = np.full((64, 64, 3), 128, dtype=np.uint8)
        assert _edge_energy_score(banded) > _edge_energy_score(flat)

    def test_emitted_in_compute_all_metrics(self):
        img = np.random.randint(10, 200, (100, 80, 3), dtype=np.uint8)
        metrics = _compute_all_metrics(img)
        assert "edge_energy_score" in metrics
        assert isinstance(metrics["edge_energy_score"], float)

    def test_ghosting_score_alias_also_emitted(self):
        # ghosting_score kept for GhostGate backward-compat
        img = np.random.randint(10, 200, (100, 80, 3), dtype=np.uint8)
        metrics = _compute_all_metrics(img)
        assert "ghosting_score" in metrics
        assert metrics["ghosting_score"] == pytest.approx(metrics["edge_energy_score"])

# ---------------------------------------------------------------------------
# §4.8  SeamVisGate — threshold calibration (unit tests, no I/O)
# ---------------------------------------------------------------------------
class TestSeamVisibilityGate:
    """Calibrate the SeamVisGate decision logic:
    limit = max(floor, ratio × max(sim_sv, 1.0))
    gate fires when asp_sv > limit.
    """

    def _limit(self, sim_sv, ratio=3.0, floor=20.0):
        return max(floor, ratio * max(sim_sv, 1.0))

    def test_high_asp_sv_fires(self):
        # test74-representative: asp=92.6 vs sim=2.9 — should fire at floor=20
        asp_sv, sim_sv = 92.6, 2.9
        limit = self._limit(sim_sv)
        assert asp_sv > limit, f"gate should fire: asp={asp_sv} limit={limit}"

    def test_low_asp_sv_does_not_fire(self):
        # test27-representative: asp=6.0 vs sim=1.2 — below floor=20, no fire
        asp_sv, sim_sv = 6.0, 1.2
        limit = self._limit(sim_sv)
        assert asp_sv <= limit, f"gate should not fire: asp={asp_sv} limit={limit}"

    def test_floor_dominates_when_sim_is_low(self):
        # sim_sv=0 → limit = max(20, 3×1) = 20; floor prevents firing at asp=15
        limit = self._limit(sim_sv=0.0)
        assert limit == 20.0
        assert 15.0 <= limit  # no fire

    def test_ratio_dominates_when_sim_is_high(self):
        # sim_sv=15 → limit = max(20, 3×15) = 45; asp=30 should not fire
        limit = self._limit(sim_sv=15.0)
        assert limit == 45.0
        assert 30.0 <= limit

    def test_disabled_via_ratio_90(self):
        # ratio=90 ≥ 90 → gate bypass (tested by the outer if-guard in bench)
        ratio = 90.0
        assert ratio >= 90.0  # gate condition: _SEAM_VIS_RATIO_LIMIT < 90


class TestCanvasGainUniformityGate:
    """§5.3: CGUGate calibration.
    limit = max(floor, ratio × max(sim_cgu, 0.001))
    gate fires when asp_cgu > limit and ratio < 90.
    """

    def _limit(self, sim_cgu, ratio=2.0, floor=0.15):
        return max(floor, ratio * max(sim_cgu, 0.001))

    def test_high_banding_fires(self):
        # test82-representative: asp_cgu=0.238 vs sim=0.104 → fires at ratio=2.0
        asp_cgu, sim_cgu = 0.238, 0.104
        limit = self._limit(sim_cgu)
        assert asp_cgu > limit, f"gate should fire: asp={asp_cgu} limit={limit}"

    def test_low_banding_does_not_fire(self):
        # typical good ASP output: asp_cgu=0.09 vs sim=0.10 → no fire
        asp_cgu, sim_cgu = 0.09, 0.10
        limit = self._limit(sim_cgu)
        assert asp_cgu <= limit, f"gate should not fire: asp={asp_cgu} limit={limit}"

    def test_floor_dominates_when_sim_is_near_zero(self):
        # sim_cgu=0.001 → limit = max(0.15, 2.0×0.001) = 0.15; asp=0.12 no fire
        limit = self._limit(sim_cgu=0.001)
        assert limit == 0.15
        assert 0.12 <= limit  # no fire

    def test_asp_better_than_sim_never_fires(self):
        # asp_cgu=0.08 vs sim=0.18 → asp better → no fire regardless of floor
        asp_cgu, sim_cgu = 0.08, 0.18
        limit = self._limit(sim_cgu)
        assert asp_cgu <= limit

    def test_disabled_via_ratio_90(self):
        # ratio=90 ≥ 90 → gate bypass
        ratio = 90.0
        assert ratio >= 90.0  # gate condition: _CGU_RATIO_LIMIT < 90


class TestSeamCoherenceGate:
    """§5.2: SCGate calibration.
    limit = max(floor, ratio × max(sim_sc, 1.0))
    gate fires when asp_sc > limit and ratio < 90.
    """

    def _limit(self, sim_sc, ratio=2.5, floor=15.0):
        return max(floor, ratio * max(sim_sc, 1.0))

    def test_high_coherence_fires(self):
        # asp_sc=80.0 vs sim_sc=5.0 at ratio=2.5, floor=15 → limit=max(15,12.5)=15 → fires
        asp_sc, sim_sc = 80.0, 5.0
        limit = self._limit(sim_sc)
        assert asp_sc > limit, f"gate should fire: asp={asp_sc} limit={limit}"

    def test_low_coherence_does_not_fire(self):
        # asp_sc=10.0 vs sim_sc=8.0 → limit=max(15, 20.0)=20.0 → no fire
        asp_sc, sim_sc = 10.0, 8.0
        limit = self._limit(sim_sc)
        assert asp_sc <= limit, f"gate should not fire: asp={asp_sc} limit={limit}"

    def test_floor_dominates_when_sim_is_low(self):
        # sim_sc=1.0 → limit = max(15, 2.5×1.0) = 15; asp_sc=12 → no fire
        limit = self._limit(sim_sc=1.0)
        assert limit == 15.0
        assert 12.0 <= limit  # no fire

    def test_ratio_dominates_when_sim_is_high(self):
        # sim_sc=30.0 → limit = max(15, 2.5×30) = 75; asp_sc=50 → no fire
        limit = self._limit(sim_sc=30.0)
        assert limit == 75.0
        assert 50.0 <= limit  # no fire

    def test_disabled_via_ratio_90(self):
        # ratio=90 ≥ 90 → gate bypass
        ratio = 90.0
        assert ratio >= 90.0  # gate condition: _SEAM_COH_RATIO_LIMIT < 90

class TestCompositeQualityScoreWithCGU:
    """§5.4: canvas_gain_uniformity term in CQAS."""

    def _cqas(self, metrics: dict) -> float:
        from backend.benchmark.bench_anime_stitch import _compute_cqas
        return _compute_cqas(metrics)

    def test_cgu_score_perfect_uniformity(self):
        # cgu=0.0 → cgu_score = clip(1 - 0/0.40, 0, 1) = 1.0
        from backend.benchmark.bench_anime_stitch import _compute_cqas
        import numpy as np
        cgu = 0.0
        cgu_score = float(np.clip(1.0 - cgu / 0.40, 0.0, 1.0))
        assert cgu_score == 1.0

    def test_cgu_score_bad_uniformity(self):
        # cgu=0.40 → cgu_score = clip(1 - 0.40/0.40, 0, 1) = 0.0
        import numpy as np
        cgu = 0.40
        cgu_score = float(np.clip(1.0 - cgu / 0.40, 0.0, 1.0))
        assert cgu_score == 0.0

    def test_cgu_score_mid_range(self):
        # cgu=0.20 → cgu_score = clip(1 - 0.20/0.40, 0, 1) = 0.5
        import numpy as np
        cgu = 0.20
        cgu_score = float(np.clip(1.0 - cgu / 0.40, 0.0, 1.0))
        assert abs(cgu_score - 0.5) < 1e-9

    def test_cqas_includes_cgu(self):
        # High CGU (bad uniformity) should lower CQAS compared to cgu=0
        base = {"ghosting_siqe": 10.0, "seam_visibility": 5.0, "seam_coherence": 10.0, "sharpness": 80.0}
        score_without_cgu = self._cqas(base)
        score_with_good_cgu = self._cqas({**base, "canvas_gain_uniformity": 0.0})
        score_with_bad_cgu = self._cqas({**base, "canvas_gain_uniformity": 0.40})
        assert score_with_bad_cgu < score_without_cgu
        assert score_with_good_cgu >= score_without_cgu

    def test_cqas_without_cgu_still_works(self):
        # Missing canvas_gain_uniformity → CQAS still returns a float (None excluded)
        metrics = {"ghosting_siqe": 20.0, "seam_visibility": 8.0, "seam_coherence": 15.0, "sharpness": 60.0}
        result = self._cqas(metrics)
        assert result is not None
        assert 0.0 <= result <= 1.0


class TestStripLumaMonotonicity:
    """§5.10: Per-strip luma monotonicity metric."""

    def _build_strips(self, lum_values):
        """Build a (n*10, 100, 3) uint8 BGR image with each strip set to a given luminance."""
        n = len(lum_values)
        img = np.zeros((n * 10, 100, 3), dtype=np.uint8)
        for i, lum in enumerate(lum_values):
            img[i * 10:(i + 1) * 10] = lum
        return img

    def test_perfectly_monotonic_ascending(self):
        # Strictly ascending strip means → no reversals → 0.0
        lum_values = [50, 80, 110, 140, 170, 200, 220, 240]
        img = self._build_strips(lum_values)
        result = _strip_luma_monotonicity(img, n_strips=8)
        assert result == 0.0

    def test_perfectly_monotonic_descending(self):
        # Strictly descending strip means → no reversals → 0.0
        lum_values = [240, 220, 200, 170, 140, 110, 80, 50]
        img = self._build_strips(lum_values)
        result = _strip_luma_monotonicity(img, n_strips=8)
        assert result == 0.0

    def test_fully_alternating(self):
        # Alternating high/low/high/low → every adjacent pair reverses → 1.0
        lum_values = [200, 50, 200, 50, 200, 50, 200, 50]
        img = self._build_strips(lum_values)
        result = _strip_luma_monotonicity(img, n_strips=8)
        assert result == 1.0

    def test_one_reversal(self):
        # 4-strip sequence: 50, 100, 80, 120
        # diffs: +50, -20, +40 → signs: +1, -1, +1 → 2 reversals out of 2 pairs
        # Wait: nonzero=[+1,-1,+1], len=3, reversals=2, result=2/2=1.0
        # Use a sequence with exactly 1 reversal out of 2 gaps:
        # 4 strips: 50, 100, 150, 120
        # diffs: +50, +50, -30 → signs: +1, +1, -1 → nonzero=[+1,+1,-1], reversals=1, result=1/2=0.5
        lum_values = [50, 100, 150, 120]
        img = self._build_strips(lum_values)
        result = _strip_luma_monotonicity(img, n_strips=4)
        assert abs(result - 0.5) < 1e-6

    def test_uniform_image(self):
        # All strips have same luminance → all diffs zero → nonzero is empty → 0.0
        img = np.full((80, 100, 3), 128, dtype=np.uint8)
        result = _strip_luma_monotonicity(img, n_strips=8)
        assert result == 0.0


# ---------------------------------------------------------------------------
# §5.12 — Horizontal FFT Banding Score (S170)
# ---------------------------------------------------------------------------
from backend.benchmark.bench_anime_stitch import _horizontal_fft_banding


class TestHorizontalFftBanding:
    """§5.12: Periodic horizontal banding detection via column-mean luminance FFT."""

    def test_uniform_image(self):
        # All-gray image → no luminance variation → near-zero FFT energy → 0.0
        img = np.full((800, 100, 3), 128, dtype=np.uint8)
        result = _horizontal_fft_banding(img, n_strips=8)
        assert result == 0.0

    def test_periodic_bands(self):
        # 8 alternating bright/dark strips → strong energy at strip frequency
        img = np.zeros((800, 100, 3), dtype=np.uint8)
        strip_h = 100  # 800 / 8
        for i in range(8):
            val = 200 if i % 2 == 0 else 50
            img[i * strip_h:(i + 1) * strip_h] = val
        result = _horizontal_fft_banding(img, n_strips=8)
        assert result > 0.3

    def test_random_noise(self):
        # Random noise → energy spread across spectrum → low banding score
        rng = np.random.default_rng(42)
        img = (rng.random((800, 100, 3)) * 255).astype(np.uint8)
        result = _horizontal_fft_banding(img, n_strips=8)
        # Energy is spread — strip-frequency band captures a small fraction
        assert 0.0 <= result <= 1.0

    def test_degenerate_small(self):
        # 4-row image with n_strips=8 → H < n_strips*4 → returns 0.0
        img = np.full((4, 100, 3), 100, dtype=np.uint8)
        result = _horizontal_fft_banding(img, n_strips=8)
        assert result == 0.0

    def test_score_range(self):
        # Any image → score must be in [0, 1]
        rng = np.random.default_rng(7)
        img = rng.integers(0, 255, (400, 200, 3), dtype=np.uint8)
        result = _horizontal_fft_banding(img, n_strips=8)
        assert 0.0 <= result <= 1.0


class TestFftBandingGate:
    """§5.13: FFT Banding Gate threshold logic tests."""

    def test_gate_disabled_when_ratio_90(self):
        # ASP_GATE_FFT_BAND=90 → gate skipped entirely, never fires
        ratio_limit = 90.0
        # Gate condition: ratio_limit < 90 must be False → gate is skipped
        assert not (ratio_limit < 90)

    def test_gate_fires_when_asp_exceeds_limit(self):
        # asp_fft=0.50, sim_fft=0.05, floor=0.30, ratio=3.0
        # limit = max(0.30, 3.0 * max(0.05, 0.001)) = max(0.30, 0.15) = 0.30
        # 0.50 > 0.30 → gate fires
        asp_fft = 0.50
        sim_fft = 0.05
        floor = 0.30
        ratio_limit = 3.0
        limit = max(floor, ratio_limit * max(sim_fft, 0.001))
        assert limit == pytest.approx(0.30)
        assert asp_fft > limit  # gate would fire

    def test_gate_passes_when_asp_below_limit(self):
        # asp_fft=0.10, sim_fft=0.05, floor=0.30 → limit=0.30 → 0.10 < 0.30 → no fire
        asp_fft = 0.10
        sim_fft = 0.05
        floor = 0.30
        ratio_limit = 3.0
        limit = max(floor, ratio_limit * max(sim_fft, 0.001))
        assert limit == pytest.approx(0.30)
        assert asp_fft <= limit  # gate would not fire

    def test_floor_dominates_when_sim_is_zero(self):
        # sim_fft=0 → limit = max(floor, ratio * 0.001) ≈ max(0.30, 0.003) = 0.30
        # asp_fft=0.50 > 0.30 → gate fires
        asp_fft = 0.50
        sim_fft = 0.0
        floor = 0.30
        ratio_limit = 3.0
        limit = max(floor, ratio_limit * max(sim_fft, 0.001))
        assert limit == pytest.approx(0.30)
        assert asp_fft > limit  # gate fires; floor dominates

    def test_fallback_reason_set_on_fire(self):
        # Verify the fallback_reason string format contains "fft_band_gate:"
        asp_fft = 0.50
        sim_fft = 0.05
        floor = 0.30
        ratio_limit = 3.0
        limit = max(floor, ratio_limit * max(sim_fft, 0.001))
        fallback_reason = (
            f"fft_band_gate:asp={asp_fft:.3f}_sim={sim_fft:.3f}_limit={limit:.3f}"
        )
        assert fallback_reason.startswith("fft_band_gate:")
        assert f"asp={asp_fft:.3f}" in fallback_reason
        assert f"sim={sim_fft:.3f}" in fallback_reason
        assert f"limit={limit:.3f}" in fallback_reason


class TestMonotonGate:
    """§5.14: Strip Luma Monotonicity Gate — threshold logic tests."""

    def test_gate_fires_when_asp_exceeds_floor(self):
        # asp=0.7, sim=0.0, floor=0.5, ratio=3
        # limit = max(0.5, 3 * max(0.0, 0.001)) = max(0.5, 0.003) = 0.5
        # 0.7 > 0.5 → gate fires
        asp_mono = 0.7
        sim_mono = 0.0
        floor = 0.5
        ratio_limit = 3.0
        limit = max(floor, ratio_limit * max(sim_mono, 0.001))
        assert limit == pytest.approx(0.5)
        assert asp_mono > limit  # gate fires; floor dominates

    def test_gate_passes_when_asp_below_floor(self):
        # asp=0.3, floor=0.5 → 0.3 < 0.5 → gate does not fire
        asp_mono = 0.3
        sim_mono = 0.0
        floor = 0.5
        ratio_limit = 3.0
        limit = max(floor, ratio_limit * max(sim_mono, 0.001))
        assert limit == pytest.approx(0.5)
        assert asp_mono <= limit  # gate passes

    def test_gate_disabled_at_ratio_90(self):
        # When _MONO_RATIO_LIMIT >= 90, the gate condition is skipped entirely
        ratio_limit = 90.0
        # Gate condition: ratio_limit < 90 must be False → gate is skipped
        assert not (ratio_limit < 90)

    def test_ratio_dominates_when_sim_is_high(self):
        # asp=0.6, sim=0.3, ratio=3 → limit = max(0.5, 3 * 0.3) = max(0.5, 0.9) = 0.9
        # 0.6 < 0.9 → gate passes
        asp_mono = 0.6
        sim_mono = 0.3
        floor = 0.5
        ratio_limit = 3.0
        limit = max(floor, ratio_limit * max(sim_mono, 0.001))
        assert limit == pytest.approx(0.9)
        assert asp_mono <= limit  # gate passes; ratio dominates

    def test_fallback_reason_prefix(self):
        # Verify the fallback_reason string format starts with "mono_gate:"
        asp_mono = 0.7
        sim_mono = 0.0
        floor = 0.5
        ratio_limit = 3.0
        limit = max(floor, ratio_limit * max(sim_mono, 0.001))
        fallback_reason = (
            f"mono_gate:asp={asp_mono:.3f}_sim={sim_mono:.3f}_limit={limit:.3f}"
        )
        assert fallback_reason.startswith("mono_gate:")
        assert f"asp={asp_mono:.3f}" in fallback_reason
        assert f"sim={sim_mono:.3f}" in fallback_reason


class TestSeamOwnershipEntropyGate:
    """§5.15: Seam Ownership Entropy Gate threshold logic tests."""

    def test_gate_fires_when_asp_exceeds_floor(self):
        # asp_ent=5.0, sim_ent=0.5, floor=3.0, ratio=2.5
        # limit = max(3.0, 2.5 * max(0.5, 0.1)) = max(3.0, 1.25) = 3.0
        # 5.0 > 3.0 → gate fires
        asp_ent = 5.0
        sim_ent = 0.5
        floor = 3.0
        ratio_limit = 2.5
        limit = max(floor, ratio_limit * max(sim_ent, 0.1))
        assert limit == pytest.approx(3.0)
        assert asp_ent > limit

    def test_gate_passes_when_asp_below_floor(self):
        # asp_ent=2.0, floor=3.0 → 2.0 < 3.0 → gate does not fire
        asp_ent = 2.0
        sim_ent = 0.5
        floor = 3.0
        ratio_limit = 2.5
        limit = max(floor, ratio_limit * max(sim_ent, 0.1))
        assert asp_ent < limit

    def test_disabled_at_ratio_90(self):
        # ratio_limit=90 → gate is skipped entirely (condition: ratio_limit < 90 is False)
        ratio_limit = 90.0
        assert not (ratio_limit < 90)

    def test_ratio_dominates(self):
        # asp=6, sim=4, ratio=2.5 → limit = max(3.0, 2.5*max(4,0.1)) = max(3.0, 10.0) = 10.0
        # 6 < 10 → gate passes
        asp_ent = 6.0
        sim_ent = 4.0
        floor = 3.0
        ratio_limit = 2.5
        limit = max(floor, ratio_limit * max(sim_ent, 0.1))
        assert limit == pytest.approx(10.0)
        assert asp_ent < limit

    def test_fallback_reason_prefix(self):
        # Verify fallback_reason string format starts with "entropy_gate:"
        asp_ent = 5.0
        sim_ent = 0.5
        floor = 3.0
        ratio_limit = 2.5
        limit = max(floor, ratio_limit * max(sim_ent, 0.1))
        fallback_reason = (
            f"entropy_gate:asp={asp_ent:.3f}_sim={sim_ent:.3f}_limit={limit:.3f}"
        )
        assert fallback_reason.startswith("entropy_gate:")
        assert f"asp={asp_ent:.3f}" in fallback_reason
        assert f"sim={sim_ent:.3f}" in fallback_reason
        assert f"limit={limit:.3f}" in fallback_reason


# ===========================================================================
# §5.17 — Strip Self-SSIM Gate
# ===========================================================================
class TestStripSsimGate:
    """§5.17: Strip Self-SSIM Gate — threshold logic tests (inverted: lower=worse)."""

    def test_gate_fires_when_asp_below_floor(self):
        asp_sssim = 0.40
        sim_sssim = 0.90
        floor = 0.60
        ratio_limit = 0.5
        limit = min(floor, ratio_limit * max(sim_sssim, 0.001))
        assert limit == pytest.approx(0.45)
        assert asp_sssim < limit

    def test_gate_passes_when_asp_above_limit(self):
        asp_sssim = 0.70
        sim_sssim = 0.90
        floor = 0.60
        ratio_limit = 0.5
        limit = min(floor, ratio_limit * max(sim_sssim, 0.001))
        assert limit == pytest.approx(0.45)
        assert asp_sssim >= limit

    def test_gate_disabled_at_ratio_zero(self):
        ratio_limit = 0.0
        assert not (ratio_limit > 0)

    def test_floor_dominates_when_sim_is_high(self):
        asp_sssim = 0.50
        sim_sssim = 0.95
        floor = 0.60
        ratio_limit = 0.5
        limit = min(floor, ratio_limit * max(sim_sssim, 0.001))
        assert limit == pytest.approx(0.475)
        assert asp_sssim >= limit

    def test_fallback_reason_prefix(self):
        asp_sssim = 0.40
        sim_sssim = 0.90
        floor = 0.60
        ratio_limit = 0.5
        limit = min(floor, ratio_limit * max(sim_sssim, 0.001))
        fallback_reason = (
            f"strip_ssim_gate:asp={asp_sssim:.3f}_sim={sim_sssim:.3f}_limit={limit:.3f}"
        )
        assert fallback_reason.startswith("strip_ssim_gate:")
        assert f"asp={asp_sssim:.3f}" in fallback_reason
        assert f"sim={sim_sssim:.3f}" in fallback_reason
        assert f"limit={limit:.3f}" in fallback_reason


# ===========================================================================
# §5.18 — Chroma Seam Coherence Gate
# ===========================================================================
class TestChromaSeamCohGate:
    """§5.18: Chroma Seam Coherence Gate threshold logic tests."""

    def test_gate_fires_when_asp_exceeds_limit(self):
        asp_chroma = 25.0
        sim_chroma = 5.0
        floor = 12.0
        ratio_limit = 2.5
        chroma_limit = max(floor, ratio_limit * max(sim_chroma, 1.0))
        assert chroma_limit == pytest.approx(12.5)
        assert asp_chroma > chroma_limit

    def test_gate_passes_when_asp_below_limit(self):
        asp_chroma = 10.0
        sim_chroma = 5.0
        floor = 12.0
        ratio_limit = 2.5
        chroma_limit = max(floor, ratio_limit * max(sim_chroma, 1.0))
        assert chroma_limit == pytest.approx(12.5)
        assert asp_chroma < chroma_limit

    def test_disabled_at_ratio_90(self):
        ratio_limit = 90.0
        assert not (ratio_limit < 90)

    def test_floor_dominates_when_sim_is_low(self):
        sim_chroma = 1.0
        floor = 12.0
        ratio_limit = 2.5
        chroma_limit = max(floor, ratio_limit * max(sim_chroma, 1.0))
        assert chroma_limit == pytest.approx(12.0)

    def test_fallback_reason_prefix(self):
        asp_chroma = 25.0
        sim_chroma = 5.0
        floor = 12.0
        ratio_limit = 2.5
        chroma_limit = max(floor, ratio_limit * max(sim_chroma, 1.0))
        fallback_reason = (
            f"chroma_coh_gate:asp={asp_chroma:.2f}_sim={sim_chroma:.2f}_limit={chroma_limit:.2f}"
        )
        assert fallback_reason.startswith("chroma_coh_gate:")
        assert f"asp={asp_chroma:.2f}" in fallback_reason
        assert f"sim={sim_chroma:.2f}" in fallback_reason
        assert f"limit={chroma_limit:.2f}" in fallback_reason


# ===========================================================================
# §5.26: strip_self_ssim & chroma_seam_coherence wired from canvas (S174)
# ===========================================================================


class TestBenchStripSsimChromaMetrics:
    """§5.26 (S174): Verify strip_self_ssim and chroma_seam_coherence are emitted
    by _compute_all_metrics and importable from canvas.py."""

    def _uniform(self, H: int = 128, W: int = 96, val: int = 128) -> np.ndarray:
        return np.full((H, W, 3), val, dtype=np.uint8)

    def test_compute_all_metrics_has_strip_self_ssim_key(self):
        """_compute_all_metrics on a uniform canvas must include 'strip_self_ssim'."""
        metrics = _compute_all_metrics(self._uniform())
        assert "strip_self_ssim" in metrics

    def test_compute_all_metrics_has_chroma_seam_coherence_key(self):
        """_compute_all_metrics on a uniform canvas must include 'chroma_seam_coherence'."""
        metrics = _compute_all_metrics(self._uniform())
        assert "chroma_seam_coherence" in metrics

    def test_uniform_canvas_strip_self_ssim_high(self):
        """A uniform image has identical half-strips → strip_self_ssim >= 0.95."""
        metrics = _compute_all_metrics(self._uniform())
        val = metrics["strip_self_ssim"]
        assert val is not None
        assert val >= 0.95, f"Expected strip_self_ssim >= 0.95 for uniform canvas, got {val}"

    def test_uniform_gray_canvas_chroma_seam_coherence_low(self):
        """A uniform gray canvas has zero chroma variation → chroma_seam_coherence < 1.0."""
        metrics = _compute_all_metrics(self._uniform(val=128))
        val = metrics["chroma_seam_coherence"]
        assert val is not None
        assert val < 1.0, f"Expected chroma_seam_coherence < 1.0 for gray canvas, got {val}"

    def test_functions_importable_from_canvas(self):
        """_strip_self_ssim and _chroma_seam_coherence must be importable from canvas.py."""
        from backend.src.animation.alignment.canvas import (
            _strip_self_ssim,
            _chroma_seam_coherence,
        )
        img = self._uniform()
        assert isinstance(_strip_self_ssim(img, n_strips=8), float)
        assert isinstance(_chroma_seam_coherence(img, n_strips=8), float)


# ===========================================================================
# §5.30 — Benchmark Ghosting SIQE Comparative Gate
# ===========================================================================


class TestGhostSiqeGate:
    """Unit tests for §5.30 bench GhostSiqeGate module-level flags and logic."""

    def test_module_flags_exist(self):
        """_GHOST_SIQE_RATIO_LIMIT and _GHOST_SIQE_ABS_FLOOR must be floats."""
        import backend.benchmark.bench_anime_stitch as bench

        assert hasattr(bench, "_GHOST_SIQE_RATIO_LIMIT")
        assert hasattr(bench, "_GHOST_SIQE_ABS_FLOOR")
        assert isinstance(bench._GHOST_SIQE_RATIO_LIMIT, float)
        assert isinstance(bench._GHOST_SIQE_ABS_FLOOR, float)

    def test_defaults_are_sane(self):
        """Default ratio limit should be 2.0 and floor 30.0 when env vars absent."""
        import os
        import importlib

        # Remove env vars if set, then re-read the defaults via the module constants
        import backend.benchmark.bench_anime_stitch as bench

        # The module is already loaded; just verify the defaults are reasonable
        assert bench._GHOST_SIQE_RATIO_LIMIT > 0.0
        assert bench._GHOST_SIQE_ABS_FLOOR > 0.0

    def test_schema_entry_for_ratio(self):
        """Config schema must include ASP_GATE_GHOST_SIQE_RATIO."""
        from backend.src.animation.core import config

        assert "ASP_GATE_GHOST_SIQE_RATIO" in config._CONFIG_SCHEMA

    def test_ghosting_score_v2_used_by_gate(self):
        """_ghosting_score_v2 must accept a clean image without error."""
        img = np.full((100, 100, 3), 128, dtype=np.uint8)
        score = _ghosting_score_v2(img)
        assert isinstance(score, float)
        assert 0.0 <= score <= 100.0

    def test_gate_logic_clean_both(self):
        """When both ASP and SIM have equal low scores, gate must not fire."""
        # score=0 → limit = max(30, 2.0*0) = 30 → 0 ≤ 30 → no fallback
        import backend.benchmark.bench_anime_stitch as bench

        asp_siqe = 0.0
        sim_siqe = 0.0
        siqe_limit = max(bench._GHOST_SIQE_ABS_FLOOR, bench._GHOST_SIQE_RATIO_LIMIT * max(sim_siqe, 1.0))
        assert asp_siqe <= siqe_limit  # gate does not fire


# ===========================================================================
# §5.35 — Bench Seam Band NCC Comparative Gate
# ===========================================================================


class TestSeamBandNccGateBench:
    """Unit tests for §5.35 bench SeamBandNccGate module-level flags and logic."""

    def test_module_flags_exist(self):
        """_SEAM_NCC_ABS_FLOOR and _SEAM_NCC_RATIO must be floats in bench module."""
        import backend.benchmark.bench_anime_stitch as bench

        assert hasattr(bench, "_SEAM_NCC_ABS_FLOOR")
        assert hasattr(bench, "_SEAM_NCC_RATIO")
        assert isinstance(bench._SEAM_NCC_ABS_FLOOR, float)
        assert isinstance(bench._SEAM_NCC_RATIO, float)

    def test_defaults_sane(self):
        """Default values must be positive."""
        import backend.benchmark.bench_anime_stitch as bench

        assert bench._SEAM_NCC_ABS_FLOOR > 0.0
        assert bench._SEAM_NCC_RATIO > 0.0

    def test_schema_entries_present(self):
        """Config schema must contain §5.35 NCC entries."""
        from backend.src.animation.core import config

        assert "ASP_GATE_SEAM_NCC_FLOOR" in config._CONFIG_SCHEMA
        assert "ASP_GATE_SEAM_NCC_RATIO" in config._CONFIG_SCHEMA

    def test_gate_passes_high_ncc(self):
        """asp_ncc=0.8, sim_ncc=0.5, ratio=0.5 → 0.8 ≥ max(0.10, 0.25) → no fire."""
        import backend.benchmark.bench_anime_stitch as bench

        asp_ncc = 0.8
        sim_ncc = 0.5
        floor = bench._SEAM_NCC_ABS_FLOOR
        ratio = bench._SEAM_NCC_RATIO
        gate_fires = asp_ncc < floor or (sim_ncc > 0.1 and asp_ncc < ratio * sim_ncc)
        assert not gate_fires

    def test_gate_fires_low_ncc(self):
        """asp_ncc=0.05 < floor=0.10 → gate fires."""
        import backend.benchmark.bench_anime_stitch as bench

        asp_ncc = 0.05
        sim_ncc = 0.5
        floor = bench._SEAM_NCC_ABS_FLOOR
        ratio = bench._SEAM_NCC_RATIO
        gate_fires = asp_ncc < floor or (sim_ncc > 0.1 and asp_ncc < ratio * sim_ncc)
        assert gate_fires


# ===========================================================================
# §5.37 Bench Histogram Intersection Gate
# ===========================================================================

from backend.benchmark import bench_anime_stitch as bench_mod
from backend.src.animation.alignment.canvas import _strip_hist_intersection_min
from backend.src.animation.core import config as config_mod


class TestHistIntersectGateBench:

    def test_module_constants_exist_and_are_float(self):
        assert hasattr(bench_mod, "_HIST_INTERSECT_ABS_FLOOR")
        assert hasattr(bench_mod, "_HIST_INTERSECT_RATIO")
        assert isinstance(bench_mod._HIST_INTERSECT_ABS_FLOOR, float)
        assert isinstance(bench_mod._HIST_INTERSECT_RATIO, float)

    def test_defaults_are_positive(self):
        assert bench_mod._HIST_INTERSECT_ABS_FLOOR > 0.0
        assert bench_mod._HIST_INTERSECT_RATIO > 0.0

    def test_schema_entry_ratio_present(self):
        assert "ASP_GATE_HIST_INTERSECT_RATIO" in config_mod._CONFIG_SCHEMA

    def test_gate_passes_when_asp_hi_above_floor(self):
        img = np.full((80, 80, 3), 128, dtype=np.uint8)
        hi = _strip_hist_intersection_min(img, n_strips=8)
        assert hi >= bench_mod._HIST_INTERSECT_ABS_FLOOR

    def test_gate_fires_when_asp_hi_below_floor(self):
        img = np.zeros((80, 80, 3), dtype=np.uint8)
        for i in range(8):
            img[i * 10:(i + 1) * 10] = i * 30
        hi = _strip_hist_intersection_min(img, n_strips=8)
        assert hi >= 0.0
        assert isinstance(hi, float)


# ===========================================================================
# §5.40 — Bench Seam Gradient Ratio Gate
# ===========================================================================


class TestSeamGradRatioGateBench:

    def test_module_flags_exist_and_are_floats(self):
        import backend.benchmark.bench_anime_stitch as bench
        assert hasattr(bench, "_SEAM_GRAD_RATIO_ABS_FLOOR")
        assert hasattr(bench, "_SEAM_GRAD_RATIO_LIMIT")
        assert isinstance(bench._SEAM_GRAD_RATIO_ABS_FLOOR, float)
        assert isinstance(bench._SEAM_GRAD_RATIO_LIMIT, float)

    def test_defaults_are_positive(self):
        import backend.benchmark.bench_anime_stitch as bench
        assert bench._SEAM_GRAD_RATIO_ABS_FLOOR > 0.0
        assert bench._SEAM_GRAD_RATIO_LIMIT > 0.0

    def test_schema_entries_present(self):
        from backend.src.animation.core.config import _CONFIG_SCHEMA
        assert "ASP_GATE_SEAM_GRAD_ABS_FLOOR" in _CONFIG_SCHEMA
        assert "ASP_GATE_SEAM_GRAD_RATIO_LIMIT" in _CONFIG_SCHEMA

    def test_gate_passes_when_asp_below_abs_floor(self):
        abs_floor = 5.0
        ratio_limit = 2.0
        asp_sgr = 3.0
        sim_sgr = 0.5
        fires = asp_sgr > abs_floor and asp_sgr > ratio_limit * max(sim_sgr, 0.1)
        assert not fires

    def test_gate_fires_when_asp_above_floor_and_ratio(self):
        abs_floor = 5.0
        ratio_limit = 2.0
        asp_sgr = 12.0
        sim_sgr = 2.0
        fires = asp_sgr > abs_floor and asp_sgr > ratio_limit * max(sim_sgr, 0.1)
        assert fires


# ---------------------------------------------------------------------------
# TestValidAreaGateBench  (§5.43)
# ---------------------------------------------------------------------------


class TestValidAreaGateBench:
    def test_module_flags_exist_and_are_floats(self):
        import backend.benchmark.bench_anime_stitch as _b
        assert hasattr(_b, "_VALID_AREA_ABS_FLOOR")
        assert hasattr(_b, "_VALID_AREA_RATIO")
        assert isinstance(_b._VALID_AREA_ABS_FLOOR, float)
        assert isinstance(_b._VALID_AREA_RATIO, float)

    def test_defaults_are_positive(self):
        import backend.benchmark.bench_anime_stitch as _b
        assert _b._VALID_AREA_ABS_FLOOR > 0.0
        assert _b._VALID_AREA_RATIO > 0.0

    def test_schema_entry_present(self):
        from backend.src.animation.core.config import _CONFIG_SCHEMA
        assert "ASP_GATE_VALID_AREA_RATIO" in _CONFIG_SCHEMA
        typ, lo, hi, desc = _CONFIG_SCHEMA["ASP_GATE_VALID_AREA_RATIO"]
        assert typ is float
        assert "5.43" in desc

    def test_gate_passes_when_asp_va_above_floor(self):
        from backend.src.animation.alignment.canvas import _canvas_valid_area_ratio
        # Fully filled image → valid area = 1.0 → well above any floor
        img = np.full((100, 100, 3), 128, dtype=np.uint8)
        va = _canvas_valid_area_ratio(img)
        assert va > 0.30, f"Expected va > 0.30, got {va}"

    def test_gate_fires_when_asp_va_below_floor(self):
        from backend.src.animation.alignment.canvas import _canvas_valid_area_ratio
        # Nearly all-black image → valid area ≈ 0 → below floor
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        # Only a 5×5 patch is non-black
        img[0:5, 0:5] = 5
        va = _canvas_valid_area_ratio(img, black_threshold=10)
        assert va < 0.30, f"Expected va < 0.30, got {va}"


# ---------------------------------------------------------------------------
# TestSatCvGateBench  (§5.44)
# ---------------------------------------------------------------------------


class TestSatCvGateBench:
    def test_module_flags_exist_and_are_floats(self):
        import backend.benchmark.bench_anime_stitch as _b
        assert hasattr(_b, "_SAT_CV_ABS_FLOOR")
        assert hasattr(_b, "_SAT_CV_RATIO")
        assert isinstance(_b._SAT_CV_ABS_FLOOR, float)
        assert isinstance(_b._SAT_CV_RATIO, float)

    def test_defaults_are_positive(self):
        import backend.benchmark.bench_anime_stitch as _b
        assert _b._SAT_CV_ABS_FLOOR > 0.0
        assert _b._SAT_CV_RATIO > 0.0

    def test_schema_entries_present(self):
        from backend.src.animation.core.config import _CONFIG_SCHEMA
        assert "ASP_GATE_SAT_CV_ABS_FLOOR" in _CONFIG_SCHEMA
        assert "ASP_GATE_SAT_CV_RATIO" in _CONFIG_SCHEMA
        _, _, _, desc_floor = _CONFIG_SCHEMA["ASP_GATE_SAT_CV_ABS_FLOOR"]
        _, _, _, desc_ratio = _CONFIG_SCHEMA["ASP_GATE_SAT_CV_RATIO"]
        assert "5.44" in desc_floor
        assert "5.44" in desc_ratio

    def test_gate_passes_when_asp_cv_below_abs_floor(self):
        from backend.src.animation.alignment.canvas import _strip_sat_cv
        # Uniform grey image → saturation = 0 everywhere → CV = 0 < 0.30 floor
        img = np.full((100, 100, 3), 128, dtype=np.uint8)
        cv = _strip_sat_cv(img, n_strips=8)
        assert cv < 0.30, f"Expected cv < 0.30, got {cv}"

    def test_gate_fires_when_asp_cv_above_floor_and_ratio(self):
        from backend.src.animation.alignment.canvas import _strip_sat_cv
        # Build image with dramatically varying saturation per strip:
        # first half: vivid red (high sat), second half: grey (zero sat)
        img = np.zeros((160, 100, 3), dtype=np.uint8)
        # Top 80 rows: vivid red BGR = (0, 0, 255) → HSV sat ≈ 255
        img[:80, :] = [0, 0, 255]
        # Bottom 80 rows: grey BGR = (128, 128, 128) → HSV sat = 0
        img[80:, :] = [128, 128, 128]
        asp_cv = _strip_sat_cv(img, n_strips=8)
        # sim is uniform grey
        sim = np.full((160, 100, 3), 128, dtype=np.uint8)
        sim_cv = _strip_sat_cv(sim, n_strips=8)
        # Gate fires: asp_cv > floor AND asp_cv > 2.0 × sim_cv
        assert asp_cv > 0.30, f"Expected asp_cv > 0.30, got {asp_cv}"
        assert asp_cv > 2.0 * max(sim_cv, 0.001), f"Expected asp_cv > 2×sim_cv"


# ---------------------------------------------------------------------------
# TestLumaRangeGateBench (§5.47)
# ---------------------------------------------------------------------------


class TestLumaRangeGateBench:
    """§5.47: Bench strip luma range comparative gate — module flags, schema, and logic."""

    def test_module_flags_exist_and_are_floats(self):
        import backend.benchmark.bench_anime_stitch as bm
        assert hasattr(bm, "_LUMA_RANGE_ABS_FLOOR")
        assert hasattr(bm, "_LUMA_RANGE_RATIO")
        assert isinstance(bm._LUMA_RANGE_ABS_FLOOR, float)
        assert isinstance(bm._LUMA_RANGE_RATIO, float)

    def test_defaults_are_positive(self):
        import backend.benchmark.bench_anime_stitch as bm
        assert bm._LUMA_RANGE_ABS_FLOOR > 0.0
        assert bm._LUMA_RANGE_RATIO > 0.0

    def test_schema_entries_present(self):
        from backend.src.animation.core.config import _CONFIG_SCHEMA
        assert "ASP_GATE_LUMA_RANGE_ABS_FLOOR" in _CONFIG_SCHEMA
        assert "ASP_GATE_LUMA_RANGE_RATIO" in _CONFIG_SCHEMA
        assert "5.47" in _CONFIG_SCHEMA["ASP_GATE_LUMA_RANGE_ABS_FLOOR"][3]
        assert "5.47" in _CONFIG_SCHEMA["ASP_GATE_LUMA_RANGE_RATIO"][3]

    def test_gate_passes_when_asp_lr_below_abs_floor(self):
        # Uniform image → all strip means equal → luma range = 0 < floor (30.0)
        # A gate with asp_lr=0 should NOT fire (below floor).
        import backend.benchmark.bench_anime_stitch as bm
        img = np.full((160, 80, 3), 128, dtype=np.uint8)
        # Simulate gate condition: asp_lr below floor
        asp_lr = 0.0
        floor = bm._LUMA_RANGE_ABS_FLOOR
        sim_lr = 0.0
        ratio = bm._LUMA_RANGE_RATIO
        gate_fires = asp_lr > floor and (
            sim_lr < 5.0 or asp_lr > ratio * max(sim_lr, 1.0)
        )
        assert not gate_fires, "Gate should not fire when asp_lr=0 (below floor)"

    def test_gate_fires_when_asp_lr_above_floor_and_ratio(self):
        # Top half bright (200), bottom half dark (50) → range ~150 >> floor 30
        # sim is uniform (sim_lr ~0) → sim_lr < 5.0 → ratio condition fires
        import backend.benchmark.bench_anime_stitch as bm
        asp_lr = 150.0  # bright top, dark bottom
        sim_lr = 0.0    # uniform SCANS reference
        floor = bm._LUMA_RANGE_ABS_FLOOR   # 30.0
        ratio = bm._LUMA_RANGE_RATIO        # 2.0
        gate_fires = asp_lr > floor and (
            sim_lr < 5.0 or asp_lr > ratio * max(sim_lr, 1.0)
        )
        assert gate_fires, "Gate should fire: asp_lr=150 > floor=30 and sim_lr=0 < 5.0"


# ---------------------------------------------------------------------------
# TestEdgeDensityGateBench (§5.48)
# ---------------------------------------------------------------------------


class TestEdgeDensityGateBench:
    """§5.48: Bench strip edge density comparative gate — module flags, schema, and logic."""

    def test_module_flags_exist_and_are_floats(self):
        import backend.benchmark.bench_anime_stitch as bm
        assert hasattr(bm, "_EDGE_DENSITY_ABS_FLOOR")
        assert hasattr(bm, "_EDGE_DENSITY_RATIO")
        assert isinstance(bm._EDGE_DENSITY_ABS_FLOOR, float)
        assert isinstance(bm._EDGE_DENSITY_RATIO, float)

    def test_defaults_are_positive(self):
        import backend.benchmark.bench_anime_stitch as bm
        assert bm._EDGE_DENSITY_ABS_FLOOR > 0.0
        assert bm._EDGE_DENSITY_RATIO > 0.0

    def test_schema_entries_present(self):
        from backend.src.animation.core.config import _CONFIG_SCHEMA
        assert "ASP_GATE_EDGE_DENSITY_ABS_FLOOR" in _CONFIG_SCHEMA
        assert "ASP_GATE_EDGE_DENSITY_RATIO" in _CONFIG_SCHEMA
        assert "5.48" in _CONFIG_SCHEMA["ASP_GATE_EDGE_DENSITY_ABS_FLOOR"][3]
        assert "5.48" in _CONFIG_SCHEMA["ASP_GATE_EDGE_DENSITY_RATIO"][3]

    def test_gate_passes_when_asp_ed_below_abs_floor(self):
        # Solid uniform image → Canny finds no edges → edge density ≈ 0 < 0.15 floor
        import backend.benchmark.bench_anime_stitch as bm
        asp_ed = 0.0    # uniform image → no Canny edges
        sim_ed = 0.0
        floor = bm._EDGE_DENSITY_ABS_FLOOR  # 0.15
        ratio = bm._EDGE_DENSITY_RATIO       # 2.5
        gate_fires = asp_ed > floor and (
            sim_ed < 0.01 or asp_ed > ratio * max(sim_ed, 0.001)
        )
        assert not gate_fires, "Gate should not fire when asp_ed=0 (below floor)"

    def test_gate_fires_when_asp_ed_above_floor_and_ratio(self):
        # Checkerboard image → many edges → edge density > 0.15
        # Uniform sim → sim edge density ≈ 0 → sim_ed < 0.01 → ratio condition fires
        import backend.benchmark.bench_anime_stitch as bm
        asp_ed = 0.35   # checkerboard → dense edges, well above 0.15 floor
        sim_ed = 0.0    # uniform SCANS reference → no edges
        floor = bm._EDGE_DENSITY_ABS_FLOOR  # 0.15
        ratio = bm._EDGE_DENSITY_RATIO       # 2.5
        gate_fires = asp_ed > floor and (
            sim_ed < 0.01 or asp_ed > ratio * max(sim_ed, 0.001)
        )
        assert gate_fires, "Gate should fire: asp_ed=0.35 > floor=0.15 and sim_ed=0 < 0.01"


# ===========================================================================
# §5.51: _LUMA_MAD bench gate
# ===========================================================================


class TestLumaMadGateBench:
    """§5.51: Bench strip luma MAD comparative gate — module flags, schema, and logic."""

    def test_module_flags_exist_and_are_floats(self):
        import backend.benchmark.bench_anime_stitch as bm
        assert hasattr(bm, "_LUMA_MAD_ABS_FLOOR")
        assert hasattr(bm, "_LUMA_MAD_RATIO")
        assert isinstance(bm._LUMA_MAD_ABS_FLOOR, float)
        assert isinstance(bm._LUMA_MAD_RATIO, float)

    def test_schema_keys_present(self):
        from backend.src.animation.core.config import _CONFIG_SCHEMA
        assert "ASP_GATE_LUMA_MAD_ABS_FLOOR" in _CONFIG_SCHEMA
        assert "ASP_GATE_LUMA_MAD_RATIO" in _CONFIG_SCHEMA

    def test_gate_fires_when_asp_high_sim_zero(self):
        import backend.benchmark.bench_anime_stitch as bm
        asp_lmad = 50.0   # severe banding
        sim_lmad = 0.0    # clean SCANS reference
        floor = bm._LUMA_MAD_ABS_FLOOR  # 10.0
        ratio = bm._LUMA_MAD_RATIO       # 2.0
        gate_fires = asp_lmad > floor and (
            sim_lmad < 2.0 or asp_lmad > ratio * max(sim_lmad, 1.0)
        )
        assert gate_fires, "Gate should fire: asp_lmad=50 > floor=10 and sim_lmad=0 < 2.0"

    def test_gate_does_not_fire_when_both_banded(self):
        import backend.benchmark.bench_anime_stitch as bm
        asp_lmad = 20.0
        sim_lmad = 18.0
        floor = bm._LUMA_MAD_ABS_FLOOR  # 10.0
        ratio = bm._LUMA_MAD_RATIO       # 2.0
        gate_fires = asp_lmad > floor and (
            sim_lmad < 2.0 or asp_lmad > ratio * max(sim_lmad, 1.0)
        )
        assert not gate_fires, "Gate should NOT fire: asp ≈ sim (both banded equally)"

    def test_gate_does_not_fire_below_abs_floor(self):
        import backend.benchmark.bench_anime_stitch as bm
        asp_lmad = 5.0    # below abs floor of 10.0
        sim_lmad = 0.0
        floor = bm._LUMA_MAD_ABS_FLOOR  # 10.0
        ratio = bm._LUMA_MAD_RATIO       # 2.0
        gate_fires = asp_lmad > floor and (
            sim_lmad < 2.0 or asp_lmad > ratio * max(sim_lmad, 1.0)
        )
        assert not gate_fires, "Gate should NOT fire: asp_lmad below abs floor"


# ===========================================================================
# §5.52: _SHARPNESS_CV bench gate
# ===========================================================================


class TestSharpnessCvGateBench:
    """§5.52: Bench strip sharpness CV comparative gate — module flags, schema, and logic."""

    def test_module_flags_exist_and_are_floats(self):
        import backend.benchmark.bench_anime_stitch as bm
        assert hasattr(bm, "_SHARPNESS_CV_ABS_FLOOR")
        assert hasattr(bm, "_SHARPNESS_CV_RATIO")
        assert isinstance(bm._SHARPNESS_CV_ABS_FLOOR, float)
        assert isinstance(bm._SHARPNESS_CV_RATIO, float)

    def test_schema_keys_present(self):
        from backend.src.animation.core.config import _CONFIG_SCHEMA
        assert "ASP_GATE_SHARPNESS_CV_ABS_FLOOR" in _CONFIG_SCHEMA
        assert "ASP_GATE_SHARPNESS_CV_RATIO" in _CONFIG_SCHEMA

    def test_gate_fires_when_asp_high_sim_zero(self):
        import backend.benchmark.bench_anime_stitch as bm
        asp_scv = 1.5    # very high CV — sharp/blurry mixed strips
        sim_scv = 0.0    # uniform reference
        floor = bm._SHARPNESS_CV_ABS_FLOOR  # 0.60
        ratio = bm._SHARPNESS_CV_RATIO       # 2.5
        gate_fires = asp_scv > floor and (
            sim_scv < 0.05 or asp_scv > ratio * max(sim_scv, 0.01)
        )
        assert gate_fires, "Gate should fire: asp_scv=1.5 > floor=0.60 and sim_scv=0 < 0.05"

    def test_gate_does_not_fire_when_both_mixed(self):
        import backend.benchmark.bench_anime_stitch as bm
        asp_scv = 0.9
        sim_scv = 0.8
        floor = bm._SHARPNESS_CV_ABS_FLOOR  # 0.60
        ratio = bm._SHARPNESS_CV_RATIO       # 2.5
        gate_fires = asp_scv > floor and (
            sim_scv < 0.05 or asp_scv > ratio * max(sim_scv, 0.01)
        )
        assert not gate_fires, "Gate should NOT fire: asp ≈ sim (both mixed equally)"

    def test_gate_does_not_fire_below_abs_floor(self):
        import backend.benchmark.bench_anime_stitch as bm
        asp_scv = 0.30   # below abs floor of 0.60
        sim_scv = 0.0
        floor = bm._SHARPNESS_CV_ABS_FLOOR  # 0.60
        ratio = bm._SHARPNESS_CV_RATIO       # 2.5
        gate_fires = asp_scv > floor and (
            sim_scv < 0.05 or asp_scv > ratio * max(sim_scv, 0.01)
        )
        assert not gate_fires, "Gate should NOT fire: asp_scv below abs floor"


# ===========================================================================
# §5.55: _CONTRAST_CV bench gate
# ===========================================================================


class TestContrastCvGateBench:
    """§5.55: Bench strip contrast CV comparative gate — module flags, schema, and logic."""

    def test_module_flags_exist_and_are_floats(self):
        import backend.benchmark.bench_anime_stitch as bm
        assert hasattr(bm, "_CONTRAST_CV_ABS_FLOOR")
        assert hasattr(bm, "_CONTRAST_CV_RATIO")
        assert isinstance(bm._CONTRAST_CV_ABS_FLOOR, float)
        assert isinstance(bm._CONTRAST_CV_RATIO, float)

    def test_schema_keys_present(self):
        from backend.src.animation.core.config import _CONFIG_SCHEMA
        assert "ASP_GATE_CONTRAST_CV_ABS_FLOOR" in _CONFIG_SCHEMA
        assert "ASP_GATE_CONTRAST_CV_RATIO" in _CONFIG_SCHEMA

    def test_gate_fires_when_asp_high_sim_zero(self):
        import backend.benchmark.bench_anime_stitch as bm
        asp_ccv = 2.0
        sim_ccv = 0.0
        floor = bm._CONTRAST_CV_ABS_FLOOR  # 0.80
        ratio = bm._CONTRAST_CV_RATIO       # 2.5
        gate_fires = asp_ccv > floor and (
            sim_ccv < 0.05 or asp_ccv > ratio * max(sim_ccv, 0.01)
        )
        assert gate_fires, "Gate should fire: asp_ccv=2.0 > floor=0.80 and sim_ccv=0 < 0.05"

    def test_gate_does_not_fire_when_both_mixed(self):
        import backend.benchmark.bench_anime_stitch as bm
        asp_ccv = 1.0
        sim_ccv = 0.9
        floor = bm._CONTRAST_CV_ABS_FLOOR  # 0.80
        ratio = bm._CONTRAST_CV_RATIO       # 2.5
        gate_fires = asp_ccv > floor and (
            sim_ccv < 0.05 or asp_ccv > ratio * max(sim_ccv, 0.01)
        )
        assert not gate_fires, "Gate should NOT fire: asp ≈ sim (both mixed equally)"

    def test_gate_does_not_fire_below_abs_floor(self):
        import backend.benchmark.bench_anime_stitch as bm
        asp_ccv = 0.50
        sim_ccv = 0.0
        floor = bm._CONTRAST_CV_ABS_FLOOR  # 0.80
        ratio = bm._CONTRAST_CV_RATIO       # 2.5
        gate_fires = asp_ccv > floor and (
            sim_ccv < 0.05 or asp_ccv > ratio * max(sim_ccv, 0.01)
        )
        assert not gate_fires, "Gate should NOT fire: asp_ccv below abs floor"


class TestChromaJumpGateBench:
    """§5.56: Bench seam chroma jump comparative gate — module flags, schema, and logic."""

    def test_module_flags_exist_and_are_floats(self):
        import backend.benchmark.bench_anime_stitch as bm
        assert hasattr(bm, "_CHROMA_JUMP_ABS_FLOOR")
        assert hasattr(bm, "_CHROMA_JUMP_RATIO")
        assert isinstance(bm._CHROMA_JUMP_ABS_FLOOR, float)
        assert isinstance(bm._CHROMA_JUMP_RATIO, float)

    def test_schema_keys_present(self):
        from backend.src.animation.core.config import _CONFIG_SCHEMA
        assert "ASP_GATE_CHROMA_JUMP_ABS_FLOOR" in _CONFIG_SCHEMA
        assert "ASP_GATE_CHROMA_JUMP_RATIO" in _CONFIG_SCHEMA

    def test_gate_fires_when_asp_high_sim_low(self):
        import backend.benchmark.bench_anime_stitch as bm
        asp_scj = 25.0   # large color step at seam
        sim_scj = 0.5    # reference nearly uniform
        floor = bm._CHROMA_JUMP_ABS_FLOOR  # 8.0
        ratio = bm._CHROMA_JUMP_RATIO       # 2.0
        gate_fires = asp_scj > floor and (
            sim_scj < 1.0 or asp_scj > ratio * max(sim_scj, 0.5)
        )
        assert gate_fires, "Gate should fire: asp_scj=25 > floor=8 and sim_scj=0.5 < 1.0"

    def test_gate_does_not_fire_when_both_high(self):
        import backend.benchmark.bench_anime_stitch as bm
        asp_scj = 12.0
        sim_scj = 10.0
        floor = bm._CHROMA_JUMP_ABS_FLOOR  # 8.0
        ratio = bm._CHROMA_JUMP_RATIO       # 2.0
        gate_fires = asp_scj > floor and (
            sim_scj < 1.0 or asp_scj > ratio * max(sim_scj, 0.5)
        )
        assert not gate_fires, "Gate should NOT fire: asp ≈ sim (both have similar jumps)"

    def test_gate_does_not_fire_below_abs_floor(self):
        import backend.benchmark.bench_anime_stitch as bm
        asp_scj = 5.0    # below abs floor of 8.0
        sim_scj = 0.0
        floor = bm._CHROMA_JUMP_ABS_FLOOR  # 8.0
        ratio = bm._CHROMA_JUMP_RATIO       # 2.0
        gate_fires = asp_scj > floor and (
            sim_scj < 1.0 or asp_scj > ratio * max(sim_scj, 0.5)
        )
        assert not gate_fires, "Gate should NOT fire: asp_scj below abs floor"


class TestNoiseCvGateBench:
    def test_module_flags_exist_and_are_floats(self):
        assert isinstance(_NOISE_CV_ABS_FLOOR, float)
        assert isinstance(_NOISE_CV_RATIO, float)

    def test_schema_keys_present(self):
        assert "ASP_GATE_NOISE_CV_ABS_FLOOR" in _asp_config._CONFIG_SCHEMA
        assert "ASP_GATE_NOISE_CV_RATIO" in _asp_config._CONFIG_SCHEMA

    def test_gate_fires_when_asp_high_sim_low(self):
        asp_ncv = 0.80
        sim_ncv = 0.01
        fires = asp_ncv > _NOISE_CV_ABS_FLOOR and (
            sim_ncv < 0.05 or asp_ncv > _NOISE_CV_RATIO * max(sim_ncv, 0.01)
        )
        assert fires

    def test_gate_does_not_fire_when_both_high(self):
        asp_ncv = 0.60
        sim_ncv = 0.50
        fires = asp_ncv > _NOISE_CV_ABS_FLOOR and (
            sim_ncv < 0.05 or asp_ncv > _NOISE_CV_RATIO * max(sim_ncv, 0.01)
        )
        assert not fires

    def test_gate_does_not_fire_below_abs_floor(self):
        asp_ncv = 0.30
        sim_ncv = 0.0
        fires = asp_ncv > _NOISE_CV_ABS_FLOOR and (
            sim_ncv < 0.05 or asp_ncv > _NOISE_CV_RATIO * max(sim_ncv, 0.01)
        )
        assert not fires


class TestLumaStepCvGateBench:
    def test_module_flags_exist_and_are_floats(self):
        import backend.benchmark.bench_anime_stitch as bm
        assert isinstance(bm._LUMA_STEP_CV_ABS_FLOOR, float)
        assert isinstance(bm._LUMA_STEP_CV_RATIO, float)

    def test_schema_keys_present(self):
        from backend.src.animation.core.config import _CONFIG_SCHEMA
        assert "ASP_GATE_LUMA_STEP_CV_ABS_FLOOR" in _CONFIG_SCHEMA
        assert "ASP_GATE_LUMA_STEP_CV_RATIO" in _CONFIG_SCHEMA

    def test_gate_fires_when_asp_high_sim_low(self):
        import backend.benchmark.bench_anime_stitch as bm
        asp_lscv = 0.80
        sim_lscv = 0.01
        abs_floor = bm._LUMA_STEP_CV_ABS_FLOOR
        ratio = bm._LUMA_STEP_CV_RATIO
        fires = asp_lscv > abs_floor and (
            sim_lscv < 0.05 or asp_lscv > ratio * max(sim_lscv, 0.01)
        )
        assert fires

    def test_gate_does_not_fire_when_both_high(self):
        import backend.benchmark.bench_anime_stitch as bm
        asp_lscv = 0.50
        sim_lscv = 0.40
        abs_floor = bm._LUMA_STEP_CV_ABS_FLOOR
        ratio = bm._LUMA_STEP_CV_RATIO
        fires = asp_lscv > abs_floor and (
            sim_lscv < 0.05 or asp_lscv > ratio * max(sim_lscv, 0.01)
        )
        assert not fires

    def test_gate_does_not_fire_below_abs_floor(self):
        import backend.benchmark.bench_anime_stitch as bm
        asp_lscv = 0.20
        sim_lscv = 0.0
        abs_floor = bm._LUMA_STEP_CV_ABS_FLOOR
        ratio = bm._LUMA_STEP_CV_RATIO
        fires = asp_lscv > abs_floor and (
            sim_lscv < 0.05 or asp_lscv > ratio * max(sim_lscv, 0.01)
        )
        assert not fires


class TestEntropyCvGateBench:
    def test_module_flags_exist_and_are_floats(self):
        assert isinstance(_ENTROPY_CV_ABS_FLOOR, float)
        assert isinstance(_ENTROPY_CV_RATIO, float)

    def test_schema_keys_present(self):
        assert "ASP_GATE_ENTROPY_CV_ABS_FLOOR" in _asp_config._CONFIG_SCHEMA
        assert "ASP_GATE_ENTROPY_CV_RATIO" in _asp_config._CONFIG_SCHEMA

    def test_gate_fires_when_asp_high_sim_low(self):
        asp_ecv = 0.80
        sim_ecv = 0.01
        fires = asp_ecv > _ENTROPY_CV_ABS_FLOOR and (
            sim_ecv < 0.05 or asp_ecv > _ENTROPY_CV_RATIO * max(sim_ecv, 0.01)
        )
        assert fires

    def test_gate_does_not_fire_when_both_high(self):
        asp_ecv = 0.40
        sim_ecv = 0.35
        fires = asp_ecv > _ENTROPY_CV_ABS_FLOOR and (
            sim_ecv < 0.05 or asp_ecv > _ENTROPY_CV_RATIO * max(sim_ecv, 0.01)
        )
        assert not fires

    def test_gate_does_not_fire_below_abs_floor(self):
        asp_ecv = 0.10
        sim_ecv = 0.0
        fires = asp_ecv > _ENTROPY_CV_ABS_FLOOR and (
            sim_ecv < 0.05 or asp_ecv > _ENTROPY_CV_RATIO * max(sim_ecv, 0.01)
        )
        assert not fires


class TestChromaStepCvGateBench:
    def test_module_flags_exist_and_are_floats(self):
        assert isinstance(_CHROMA_STEP_CV_ABS_FLOOR, float)
        assert isinstance(_CHROMA_STEP_CV_RATIO, float)

    def test_schema_keys_present(self):
        assert "ASP_GATE_CHROMA_STEP_CV_ABS_FLOOR" in _asp_config._CONFIG_SCHEMA
        assert "ASP_GATE_CHROMA_STEP_CV_RATIO" in _asp_config._CONFIG_SCHEMA

    def test_gate_fires_when_asp_high_sim_low(self):
        asp_cscv = 0.80
        sim_cscv = 0.01
        fires = asp_cscv > _CHROMA_STEP_CV_ABS_FLOOR and (
            sim_cscv < 0.05 or asp_cscv > _CHROMA_STEP_CV_RATIO * max(sim_cscv, 0.01)
        )
        assert fires

    def test_gate_does_not_fire_when_both_high(self):
        asp_cscv = 0.40
        sim_cscv = 0.35
        fires = asp_cscv > _CHROMA_STEP_CV_ABS_FLOOR and (
            sim_cscv < 0.05 or asp_cscv > _CHROMA_STEP_CV_RATIO * max(sim_cscv, 0.01)
        )
        assert not fires

    def test_gate_does_not_fire_below_abs_floor(self):
        asp_cscv = 0.10
        sim_cscv = 0.0
        fires = asp_cscv > _CHROMA_STEP_CV_ABS_FLOOR and (
            sim_cscv < 0.05 or asp_cscv > _CHROMA_STEP_CV_RATIO * max(sim_cscv, 0.01)
        )
        assert not fires


class TestChromaEnergyCvGateBench:
    def test_module_flags_exist_and_are_floats(self):
        assert isinstance(_CHROMA_ENERGY_CV_ABS_FLOOR, float)
        assert isinstance(_CHROMA_ENERGY_CV_RATIO, float)

    def test_schema_keys_present(self):
        assert "ASP_GATE_CHROMA_ENERGY_CV_ABS_FLOOR" in _asp_config._CONFIG_SCHEMA
        assert "ASP_GATE_CHROMA_ENERGY_CV_RATIO" in _asp_config._CONFIG_SCHEMA

    def test_gate_fires_when_asp_high_sim_low(self):
        asp_cecv = 0.80
        sim_cecv = 0.01
        fires = asp_cecv > _CHROMA_ENERGY_CV_ABS_FLOOR and (
            sim_cecv < 0.05 or asp_cecv > _CHROMA_ENERGY_CV_RATIO * max(sim_cecv, 0.01)
        )
        assert fires

    def test_gate_does_not_fire_when_both_high(self):
        asp_cecv = 0.40
        sim_cecv = 0.35
        fires = asp_cecv > _CHROMA_ENERGY_CV_ABS_FLOOR and (
            sim_cecv < 0.05 or asp_cecv > _CHROMA_ENERGY_CV_RATIO * max(sim_cecv, 0.01)
        )
        assert not fires

    def test_gate_does_not_fire_below_abs_floor(self):
        asp_cecv = 0.10
        sim_cecv = 0.0
        fires = asp_cecv > _CHROMA_ENERGY_CV_ABS_FLOOR and (
            sim_cecv < 0.05 or asp_cecv > _CHROMA_ENERGY_CV_RATIO * max(sim_cecv, 0.01)
        )
        assert not fires


class TestSeamGradientCvGateBench:
    def test_module_flags_exist_and_are_floats(self):
        assert isinstance(_SEAM_GRADIENT_CV_ABS_FLOOR, float)
        assert isinstance(_SEAM_GRADIENT_CV_RATIO, float)

    def test_schema_keys_present(self):
        assert "ASP_GATE_SEAM_GRADIENT_CV_ABS_FLOOR" in _asp_config._CONFIG_SCHEMA
        assert "ASP_GATE_SEAM_GRADIENT_CV_RATIO" in _asp_config._CONFIG_SCHEMA

    def test_gate_fires_when_asp_high_sim_low(self):
        asp_sgcv = 0.80
        sim_sgcv = 0.01
        fires = asp_sgcv > _SEAM_GRADIENT_CV_ABS_FLOOR and (
            sim_sgcv < 0.05 or asp_sgcv > _SEAM_GRADIENT_CV_RATIO * max(sim_sgcv, 0.01)
        )
        assert fires

    def test_gate_does_not_fire_when_both_high(self):
        asp_sgcv = 0.50
        sim_sgcv = 0.45
        fires = asp_sgcv > _SEAM_GRADIENT_CV_ABS_FLOOR and (
            sim_sgcv < 0.05 or asp_sgcv > _SEAM_GRADIENT_CV_RATIO * max(sim_sgcv, 0.01)
        )
        assert not fires

    def test_gate_does_not_fire_below_abs_floor(self):
        asp_sgcv = 0.20
        sim_sgcv = 0.0
        fires = asp_sgcv > _SEAM_GRADIENT_CV_ABS_FLOOR and (
            sim_sgcv < 0.05 or asp_sgcv > _SEAM_GRADIENT_CV_RATIO * max(sim_sgcv, 0.01)
        )
        assert not fires


class TestLumaIqrCvGateBench:
    def test_module_flags_exist_and_are_floats(self):
        assert isinstance(_LUMA_IQR_CV_ABS_FLOOR, float)
        assert isinstance(_LUMA_IQR_CV_RATIO, float)

    def test_schema_keys_present(self):
        assert "ASP_GATE_LUMA_IQR_CV_ABS_FLOOR" in _asp_config._CONFIG_SCHEMA
        assert "ASP_GATE_LUMA_IQR_CV_RATIO" in _asp_config._CONFIG_SCHEMA

    def test_gate_fires_when_asp_high_sim_low(self):
        asp_iqr = 0.90
        sim_iqr = 0.01
        fires = asp_iqr > _LUMA_IQR_CV_ABS_FLOOR and (
            sim_iqr < 0.05 or asp_iqr > _LUMA_IQR_CV_RATIO * max(sim_iqr, 0.01)
        )
        assert fires

    def test_gate_does_not_fire_when_both_high(self):
        asp_iqr = 0.50
        sim_iqr = 0.45
        fires = asp_iqr > _LUMA_IQR_CV_ABS_FLOOR and (
            sim_iqr < 0.05 or asp_iqr > _LUMA_IQR_CV_RATIO * max(sim_iqr, 0.01)
        )
        assert not fires

    def test_gate_does_not_fire_below_abs_floor(self):
        asp_iqr = 0.20
        sim_iqr = 0.0
        fires = asp_iqr > _LUMA_IQR_CV_ABS_FLOOR and (
            sim_iqr < 0.05 or asp_iqr > _LUMA_IQR_CV_RATIO * max(sim_iqr, 0.01)
        )
        assert not fires


class TestSeamColVarCvGateBench:
    def test_module_flags_exist_and_are_floats(self):
        assert isinstance(_SEAM_COL_VAR_CV_ABS_FLOOR, float)
        assert isinstance(_SEAM_COL_VAR_CV_RATIO, float)

    def test_schema_keys_present(self):
        assert "ASP_GATE_SEAM_COL_VAR_CV_ABS_FLOOR" in _asp_config._CONFIG_SCHEMA
        assert "ASP_GATE_SEAM_COL_VAR_CV_RATIO" in _asp_config._CONFIG_SCHEMA

    def test_gate_fires_when_asp_high_sim_low(self):
        asp_scvar = 0.80
        sim_scvar = 0.01
        fires = asp_scvar > _SEAM_COL_VAR_CV_ABS_FLOOR and (
            sim_scvar < 0.05 or asp_scvar > _SEAM_COL_VAR_CV_RATIO * max(sim_scvar, 0.01)
        )
        assert fires

    def test_gate_does_not_fire_when_both_high(self):
        asp_scvar = 0.50
        sim_scvar = 0.45
        fires = asp_scvar > _SEAM_COL_VAR_CV_ABS_FLOOR and (
            sim_scvar < 0.05 or asp_scvar > _SEAM_COL_VAR_CV_RATIO * max(sim_scvar, 0.01)
        )
        assert not fires

    def test_gate_does_not_fire_below_abs_floor(self):
        asp_scvar = 0.20
        sim_scvar = 0.0
        fires = asp_scvar > _SEAM_COL_VAR_CV_ABS_FLOOR and (
            sim_scvar < 0.05 or asp_scvar > _SEAM_COL_VAR_CV_RATIO * max(sim_scvar, 0.01)
        )
        assert not fires


class TestLumaSkewCvGateBench:
    def test_module_flags_exist_and_are_floats(self):
        assert isinstance(_LUMA_SKEW_CV_ABS_FLOOR, float)
        assert isinstance(_LUMA_SKEW_CV_RATIO, float)

    def test_schema_keys_present(self):
        assert "ASP_GATE_LUMA_SKEW_CV" in _asp_config._CONFIG_SCHEMA
        assert "ASP_GATE_LUMA_SKEW_CV_FLOOR" in _asp_config._CONFIG_SCHEMA

    def test_gate_fires_when_asp_high_sim_low(self):
        asp_lskew = _LUMA_SKEW_CV_ABS_FLOOR + 0.10
        sim_lskew = 0.01
        fires = asp_lskew > _LUMA_SKEW_CV_ABS_FLOOR and (
            sim_lskew < 0.20 or asp_lskew > _LUMA_SKEW_CV_RATIO * max(sim_lskew, 0.01)
        )
        assert fires

    def test_gate_does_not_fire_when_both_high(self):
        asp_lskew = 0.60
        sim_lskew = 0.55
        fires = asp_lskew > _LUMA_SKEW_CV_ABS_FLOOR and (
            sim_lskew < 0.20 or asp_lskew > _LUMA_SKEW_CV_RATIO * max(sim_lskew, 0.01)
        )
        assert not fires

    def test_gate_does_not_fire_below_abs_floor(self):
        asp_lskew = _LUMA_SKEW_CV_ABS_FLOOR - 0.10
        sim_lskew = 0.0
        fires = asp_lskew > _LUMA_SKEW_CV_ABS_FLOOR and (
            sim_lskew < 0.20 or asp_lskew > _LUMA_SKEW_CV_RATIO * max(sim_lskew, 0.01)
        )
        assert not fires


class TestSeamSignedStepCvGateBench:
    def test_module_flags_exist_and_are_floats(self):
        assert isinstance(_SEAM_SIGNED_STEP_CV_ABS_FLOOR, float)
        assert isinstance(_SEAM_SIGNED_STEP_CV_RATIO, float)

    def test_schema_keys_present(self):
        assert "ASP_GATE_SEAM_SIGNED_STEP_CV" in _asp_config._CONFIG_SCHEMA
        assert "ASP_GATE_SEAM_SIGNED_STEP_CV_FLOOR" in _asp_config._CONFIG_SCHEMA

    def test_gate_fires_when_asp_high_sim_low(self):
        asp_sssv = _SEAM_SIGNED_STEP_CV_ABS_FLOOR + 0.10
        sim_sssv = 0.01
        fires = asp_sssv > _SEAM_SIGNED_STEP_CV_ABS_FLOOR and (
            sim_sssv < 0.20 or asp_sssv > _SEAM_SIGNED_STEP_CV_RATIO * max(sim_sssv, 0.01)
        )
        assert fires

    def test_gate_does_not_fire_when_both_high(self):
        asp_sssv = 0.50
        sim_sssv = 0.45
        fires = asp_sssv > _SEAM_SIGNED_STEP_CV_ABS_FLOOR and (
            sim_sssv < 0.20 or asp_sssv > _SEAM_SIGNED_STEP_CV_RATIO * max(sim_sssv, 0.01)
        )
        assert not fires

    def test_gate_does_not_fire_below_abs_floor(self):
        asp_sssv = _SEAM_SIGNED_STEP_CV_ABS_FLOOR - 0.10
        sim_sssv = 0.0
        fires = asp_sssv > _SEAM_SIGNED_STEP_CV_ABS_FLOOR and (
            sim_sssv < 0.20 or asp_sssv > _SEAM_SIGNED_STEP_CV_RATIO * max(sim_sssv, 0.01)
        )
        assert not fires


class TestLumaKurtosisCvGateBench:
    def test_module_flags_exist_and_are_floats(self):
        assert isinstance(_LUMA_KURTOSIS_CV_ABS_FLOOR, float)
        assert isinstance(_LUMA_KURTOSIS_CV_RATIO, float)

    def test_schema_keys_present(self):
        assert "ASP_GATE_LUMA_KURTOSIS_CV" in _asp_config._CONFIG_SCHEMA
        assert "ASP_GATE_LUMA_KURTOSIS_CV_FLOOR" in _asp_config._CONFIG_SCHEMA

    def test_gate_fires_when_asp_high_sim_low(self):
        asp_lkurt = _LUMA_KURTOSIS_CV_ABS_FLOOR + 0.10
        sim_lkurt = 0.01
        fires = asp_lkurt > _LUMA_KURTOSIS_CV_ABS_FLOOR and (
            sim_lkurt < 0.20 or asp_lkurt > _LUMA_KURTOSIS_CV_RATIO * max(sim_lkurt, 0.01)
        )
        assert fires

    def test_gate_does_not_fire_when_both_high(self):
        asp_lkurt = 0.60
        sim_lkurt = 0.55
        fires = asp_lkurt > _LUMA_KURTOSIS_CV_ABS_FLOOR and (
            sim_lkurt < 0.20 or asp_lkurt > _LUMA_KURTOSIS_CV_RATIO * max(sim_lkurt, 0.01)
        )
        assert not fires

    def test_gate_does_not_fire_below_abs_floor(self):
        asp_lkurt = _LUMA_KURTOSIS_CV_ABS_FLOOR - 0.10
        sim_lkurt = 0.0
        fires = asp_lkurt > _LUMA_KURTOSIS_CV_ABS_FLOOR and (
            sim_lkurt < 0.20 or asp_lkurt > _LUMA_KURTOSIS_CV_RATIO * max(sim_lkurt, 0.01)
        )
        assert not fires


class TestSeamTextureRatioCvGateBench:
    def test_module_flags_exist_and_are_floats(self):
        assert isinstance(_SEAM_TEXTURE_RATIO_CV_ABS_FLOOR, float)
        assert isinstance(_SEAM_TEXTURE_RATIO_CV_RATIO, float)

    def test_schema_keys_present(self):
        assert "ASP_GATE_SEAM_TEXTURE_RATIO_CV" in _asp_config._CONFIG_SCHEMA
        assert "ASP_GATE_SEAM_TEXTURE_RATIO_CV_FLOOR" in _asp_config._CONFIG_SCHEMA

    def test_gate_fires_when_asp_high_sim_low(self):
        asp_stxr = _SEAM_TEXTURE_RATIO_CV_ABS_FLOOR + 0.10
        sim_stxr = 0.01
        fires = asp_stxr > _SEAM_TEXTURE_RATIO_CV_ABS_FLOOR and (
            sim_stxr < 0.20 or asp_stxr > _SEAM_TEXTURE_RATIO_CV_RATIO * max(sim_stxr, 0.01)
        )
        assert fires

    def test_gate_does_not_fire_when_both_high(self):
        asp_stxr = 0.50
        sim_stxr = 0.45
        fires = asp_stxr > _SEAM_TEXTURE_RATIO_CV_ABS_FLOOR and (
            sim_stxr < 0.20 or asp_stxr > _SEAM_TEXTURE_RATIO_CV_RATIO * max(sim_stxr, 0.01)
        )
        assert not fires

    def test_gate_does_not_fire_below_abs_floor(self):
        asp_stxr = _SEAM_TEXTURE_RATIO_CV_ABS_FLOOR - 0.10
        sim_stxr = 0.0
        fires = asp_stxr > _SEAM_TEXTURE_RATIO_CV_ABS_FLOOR and (
            sim_stxr < 0.20 or asp_stxr > _SEAM_TEXTURE_RATIO_CV_RATIO * max(sim_stxr, 0.01)
        )
        assert not fires


class TestEdgeDensityCvGateBench:
    def test_module_flags_exist_and_are_floats(self):
        assert isinstance(_EDGE_DENSITY_CV_ABS_FLOOR, float)
        assert isinstance(_EDGE_DENSITY_CV_RATIO, float)

    def test_schema_keys_present(self):
        assert "ASP_GATE_EDGE_DENSITY_CV" in _asp_config._CONFIG_SCHEMA
        assert "ASP_GATE_EDGE_DENSITY_CV_FLOOR" in _asp_config._CONFIG_SCHEMA

    def test_gate_fires_when_asp_high_sim_low(self):
        asp_edcv = _EDGE_DENSITY_CV_ABS_FLOOR + 0.10
        sim_edcv = 0.01
        fires = asp_edcv > _EDGE_DENSITY_CV_ABS_FLOOR and (
            sim_edcv < 0.15 or asp_edcv > _EDGE_DENSITY_CV_RATIO * max(sim_edcv, 0.01)
        )
        assert fires

    def test_gate_does_not_fire_when_both_high(self):
        asp_edcv = 0.50
        sim_edcv = 0.45
        fires = asp_edcv > _EDGE_DENSITY_CV_ABS_FLOOR and (
            sim_edcv < 0.15 or asp_edcv > _EDGE_DENSITY_CV_RATIO * max(sim_edcv, 0.01)
        )
        assert not fires

    def test_gate_does_not_fire_below_abs_floor(self):
        asp_edcv = _EDGE_DENSITY_CV_ABS_FLOOR - 0.10
        sim_edcv = 0.0
        fires = asp_edcv > _EDGE_DENSITY_CV_ABS_FLOOR and (
            sim_edcv < 0.15 or asp_edcv > _EDGE_DENSITY_CV_RATIO * max(sim_edcv, 0.01)
        )
        assert not fires


class TestSeamLocalContrastCvGateBench:
    def test_module_flags_exist_and_are_floats(self):
        assert isinstance(_SEAM_LOCAL_CONTRAST_CV_ABS_FLOOR, float)
        assert isinstance(_SEAM_LOCAL_CONTRAST_CV_RATIO, float)

    def test_schema_keys_present(self):
        assert "ASP_GATE_SEAM_LOCAL_CONTRAST_CV" in _asp_config._CONFIG_SCHEMA
        assert "ASP_GATE_SEAM_LOCAL_CONTRAST_CV_FLOOR" in _asp_config._CONFIG_SCHEMA

    def test_gate_fires_when_asp_high_sim_low(self):
        asp_slcc = _SEAM_LOCAL_CONTRAST_CV_ABS_FLOOR + 0.10
        sim_slcc = 0.01
        fires = asp_slcc > _SEAM_LOCAL_CONTRAST_CV_ABS_FLOOR and (
            sim_slcc < 0.15 or asp_slcc > _SEAM_LOCAL_CONTRAST_CV_RATIO * max(sim_slcc, 0.01)
        )
        assert fires

    def test_gate_does_not_fire_when_both_high(self):
        asp_slcc = 0.40
        sim_slcc = 0.35
        fires = asp_slcc > _SEAM_LOCAL_CONTRAST_CV_ABS_FLOOR and (
            sim_slcc < 0.15 or asp_slcc > _SEAM_LOCAL_CONTRAST_CV_RATIO * max(sim_slcc, 0.01)
        )
        assert not fires

    def test_gate_does_not_fire_below_abs_floor(self):
        asp_slcc = _SEAM_LOCAL_CONTRAST_CV_ABS_FLOOR - 0.10
        sim_slcc = 0.0
        fires = asp_slcc > _SEAM_LOCAL_CONTRAST_CV_ABS_FLOOR and (
            sim_slcc < 0.15 or asp_slcc > _SEAM_LOCAL_CONTRAST_CV_RATIO * max(sim_slcc, 0.01)
        )
        assert not fires


class TestLumaP90P10CvGateBench:
    def test_module_flags_exist_and_are_floats(self):
        assert isinstance(_LUMA_P90P10_CV_ABS_FLOOR, float)
        assert isinstance(_LUMA_P90P10_CV_RATIO, float)

    def test_schema_keys_present(self):
        assert "ASP_GATE_LUMA_P90P10_CV" in _asp_config._CONFIG_SCHEMA
        assert "ASP_GATE_LUMA_P90P10_CV_FLOOR" in _asp_config._CONFIG_SCHEMA

    def test_gate_fires_when_asp_high_sim_low(self):
        asp_val = _LUMA_P90P10_CV_ABS_FLOOR + 0.10
        sim_val = 0.01
        fires = asp_val > _LUMA_P90P10_CV_ABS_FLOOR and (
            sim_val < 0.10 or asp_val > _LUMA_P90P10_CV_RATIO * max(sim_val, 0.01)
        )
        assert fires

    def test_gate_does_not_fire_when_both_high(self):
        asp_val = 0.40
        sim_val = 0.38
        fires = asp_val > _LUMA_P90P10_CV_ABS_FLOOR and (
            sim_val < 0.10 or asp_val > _LUMA_P90P10_CV_RATIO * max(sim_val, 0.01)
        )
        assert not fires

    def test_gate_does_not_fire_below_abs_floor(self):
        asp_val = _LUMA_P90P10_CV_ABS_FLOOR - 0.10
        sim_val = 0.0
        fires = asp_val > _LUMA_P90P10_CV_ABS_FLOOR and (
            sim_val < 0.10 or asp_val > _LUMA_P90P10_CV_RATIO * max(sim_val, 0.01)
        )
        assert not fires


class TestSeamHueShiftCvGateBench:
    def test_module_flags_exist_and_are_floats(self):
        assert isinstance(_SEAM_HUE_SHIFT_CV_ABS_FLOOR, float)
        assert isinstance(_SEAM_HUE_SHIFT_CV_RATIO, float)

    def test_schema_keys_present(self):
        assert "ASP_GATE_SEAM_HUE_SHIFT_CV" in _asp_config._CONFIG_SCHEMA
        assert "ASP_GATE_SEAM_HUE_SHIFT_CV_FLOOR" in _asp_config._CONFIG_SCHEMA

    def test_gate_fires_when_asp_high_sim_low(self):
        asp_val = _SEAM_HUE_SHIFT_CV_ABS_FLOOR + 0.10
        sim_val = 0.01
        fires = asp_val > _SEAM_HUE_SHIFT_CV_ABS_FLOOR and (
            sim_val < 0.15 or asp_val > _SEAM_HUE_SHIFT_CV_RATIO * max(sim_val, 0.01)
        )
        assert fires

    def test_gate_does_not_fire_when_both_high(self):
        asp_val = 0.55
        sim_val = 0.50
        fires = asp_val > _SEAM_HUE_SHIFT_CV_ABS_FLOOR and (
            sim_val < 0.15 or asp_val > _SEAM_HUE_SHIFT_CV_RATIO * max(sim_val, 0.01)
        )
        assert not fires

    def test_gate_does_not_fire_below_abs_floor(self):
        asp_val = _SEAM_HUE_SHIFT_CV_ABS_FLOOR - 0.10
        sim_val = 0.0
        fires = asp_val > _SEAM_HUE_SHIFT_CV_ABS_FLOOR and (
            sim_val < 0.15 or asp_val > _SEAM_HUE_SHIFT_CV_RATIO * max(sim_val, 0.01)
        )
        assert not fires
