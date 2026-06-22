"""
Tests for S148 compositing + benchmark features:
  §1.91 _seam_lum_converge
  §1.92 _smooth_feather_array
  §3.18 _compute_cqas
  §1.94 _bg_consistency_score
"""
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# §1.91 — Iterative seam luminance convergence
# ---------------------------------------------------------------------------

class TestSeamLumConverge:
    def test_converges_when_delta_high(self):
        from backend.src.anim.compositing import _seam_lum_converge
        dom = np.full((30, 30, 3), 200, dtype=np.uint8)
        oth = np.full((30, 30, 3), 50, dtype=np.uint8)
        path = np.full(30, 15, dtype=int)
        out = _seam_lum_converge(dom, oth, path, band_px=8, target_delta=5.0, max_iters=2)
        # After convergence, band mean should be closer to 200 than 50
        band_mean = out[5:25, 7:23].mean()
        assert band_mean > 100

    def test_no_change_when_delta_already_small(self):
        from backend.src.anim.compositing import _seam_lum_converge
        val = 180
        dom = np.full((20, 20, 3), val, dtype=np.uint8)
        oth = np.full((20, 20, 3), val - 3, dtype=np.uint8)  # delta=3 < target=5
        path = np.full(20, 10, dtype=int)
        out = _seam_lum_converge(dom, oth, path, band_px=5, target_delta=5.0, max_iters=2)
        # Should not over-correct — result should be close to oth
        assert abs(float(out.mean()) - float(oth.mean())) < 5.0

    def test_zero_band_px_returns_copy(self):
        from backend.src.anim.compositing import _seam_lum_converge
        oth = np.full((10, 10, 3), 100, dtype=np.uint8)
        dom = np.full((10, 10, 3), 200, dtype=np.uint8)
        path = np.full(10, 5, dtype=int)
        out = _seam_lum_converge(dom, oth, path, band_px=0)
        assert np.array_equal(out, oth)

    def test_output_shape_preserved(self):
        from backend.src.anim.compositing import _seam_lum_converge
        rng = np.random.default_rng(1)
        dom = rng.integers(0, 256, (40, 50, 3), dtype=np.uint8)
        oth = rng.integers(0, 256, (40, 50, 3), dtype=np.uint8)
        path = np.full(40, 25, dtype=int)
        out = _seam_lum_converge(dom, oth, path, band_px=6)
        assert out.shape == oth.shape

    def test_function_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_seam_lum_converge" in comp.__all__


# ---------------------------------------------------------------------------
# §1.92 — Gaussian feather smoothing
# ---------------------------------------------------------------------------

class TestSmoothFeatherArray:
    def test_single_element_identity(self):
        from backend.src.anim.compositing import _smooth_feather_array
        f = np.array([200], dtype=np.int64)
        out = _smooth_feather_array(f, sigma=1.0)
        assert len(out) == 1

    def test_smooths_spike(self):
        from backend.src.anim.compositing import _smooth_feather_array
        # Spike at index 1: [80, 300, 80]
        f = np.array([80, 300, 80], dtype=np.int64)
        out = _smooth_feather_array(f, sigma=1.0)
        # After Gaussian smooth, the spike should be reduced
        assert out[1] < 300

    def test_uniform_array_unchanged(self):
        from backend.src.anim.compositing import _smooth_feather_array
        f = np.array([150, 150, 150, 150], dtype=np.int64)
        out = _smooth_feather_array(f, sigma=1.0)
        assert np.allclose(out, 150, atol=1)

    def test_clamps_to_feather_bounds(self):
        from backend.src.anim.compositing import _smooth_feather_array
        f = np.array([50, 50, 50], dtype=np.int64)
        out = _smooth_feather_array(f, sigma=1.0, feather_min=80, feather_max=300)
        assert (out >= 80).all()
        assert (out <= 300).all()

    def test_function_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_smooth_feather_array" in comp.__all__


# ---------------------------------------------------------------------------
# §3.18 — CQAS aggregate quality score
# ---------------------------------------------------------------------------

class TestComputeCqas:
    def _good_metrics(self):
        return {
            "ghosting_siqe": 2.0,    # nearly clean
            "seam_visibility": 3.0,  # invisible
            "seam_coherence": 5.0,   # coherent
            "sharpness": 90.0,       # sharp
        }

    def _bad_metrics(self):
        return {
            "ghosting_siqe": 70.0,   # heavy ghost
            "seam_visibility": 30.0, # hard cut
            "seam_coherence": 60.0,  # incoherent
            "sharpness": 10.0,       # blurry
        }

    def test_good_metrics_high_score(self):
        from backend.benchmark.bench_anime_stitch import _compute_cqas
        score = _compute_cqas(self._good_metrics())
        assert score is not None
        assert score > 0.7

    def test_bad_metrics_low_score(self):
        from backend.benchmark.bench_anime_stitch import _compute_cqas
        score = _compute_cqas(self._bad_metrics())
        assert score is not None
        assert score < 0.5

    def test_empty_metrics_returns_none(self):
        from backend.benchmark.bench_anime_stitch import _compute_cqas
        assert _compute_cqas({}) is None

    def test_partial_metrics_uses_available(self):
        from backend.benchmark.bench_anime_stitch import _compute_cqas
        # Only ghosting available
        score = _compute_cqas({"ghosting_siqe": 0.0})
        assert score is not None
        assert score > 0.9  # 0 ghost → ~1.0

    def test_score_in_unit_range(self):
        from backend.benchmark.bench_anime_stitch import _compute_cqas
        score = _compute_cqas(self._good_metrics())
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# §1.94 — Background plate consistency score
# ---------------------------------------------------------------------------

class TestBgConsistencyScore:
    def test_flat_image_low_score(self):
        from backend.benchmark.bench_anime_stitch import _bg_consistency_score
        img = np.full((100, 80, 3), 128, dtype=np.uint8)
        score = _bg_consistency_score(img, n_strips=1)
        assert score < 1.0  # flat image → near-zero variance

    def test_banded_image_high_score(self):
        from backend.benchmark.bench_anime_stitch import _bg_consistency_score
        img = np.zeros((100, 80, 3), dtype=np.uint8)
        # Alternating bright/dark rows = high row-mean variance
        img[::2] = 200
        img[1::2] = 50
        score = _bg_consistency_score(img, n_strips=1)
        assert score > 30.0  # high variance

    def test_output_shape(self):
        from backend.benchmark.bench_anime_stitch import _bg_consistency_score
        img = np.random.randint(0, 256, (60, 40, 3), dtype=np.uint8)
        score = _bg_consistency_score(img, n_strips=3)
        assert isinstance(score, float)

    def test_multiple_strips(self):
        from backend.benchmark.bench_anime_stitch import _bg_consistency_score
        img = np.random.randint(0, 256, (90, 60, 3), dtype=np.uint8)
        s1 = _bg_consistency_score(img, n_strips=1)
        s3 = _bg_consistency_score(img, n_strips=3)
        # Both should return floats without error
        assert isinstance(s1, float)
        assert isinstance(s3, float)

    def test_empty_image_returns_zero(self):
        from backend.benchmark.bench_anime_stitch import _bg_consistency_score
        import numpy as np
        img = np.zeros((0, 10, 3), dtype=np.uint8)
        score = _bg_consistency_score(img, n_strips=1)
        assert score == 0.0
