"""
Tests for S154 compositing features:
  §1.110 _COST_MAP_BLUR_SIGMA (seam cost map Gaussian blur)
  §1.111 _zone_sat_norm
  §1.112 _seam_path_drift + _SEAM_DRIFT_THRESH gate
"""
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# §1.110 — Seam cost map Gaussian blur
# ---------------------------------------------------------------------------

class TestCostMapBlur:
    def test_flag_in_module(self):
        import backend.src.anim.compositing as comp
        assert hasattr(comp, "_COST_MAP_BLUR_SIGMA")

    def test_flag_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_COST_MAP_BLUR_SIGMA" in comp.__all__

    def test_blur_smooths_cost_transitions(self):
        import backend.src.anim.compositing as comp
        orig = comp._COST_MAP_BLUR_SIGMA
        comp._COST_MAP_BLUR_SIGMA = 1.5
        try:
            zone = np.zeros((40, 50, 3), dtype=np.uint8)
            # Left half fg, right half bg → sharp tier boundary at column 25
            bg_a = np.ones((40, 50), dtype=np.uint8) * 255
            bg_b = np.ones((40, 50), dtype=np.uint8) * 255
            bg_a[:, :25] = 0
            bg_b[:, :25] = 0
            cost = comp._build_seam_cost_map(zone, bg_a, bg_b)
            # After blur the cost at the boundary column should be intermediate
            soft_mask = cost < 1e5
            assert soft_mask.any()
            # max cost among soft pixels should be > min (not all uniform)
            soft_vals = cost[soft_mask]
            assert soft_vals.max() > soft_vals.min()
        finally:
            comp._COST_MAP_BLUR_SIGMA = orig

    def test_barriers_preserved_with_blur(self):
        import backend.src.anim.compositing as comp
        orig_blur = comp._COST_MAP_BLUR_SIGMA
        orig_barrier = comp._SEAM_HARD_BARRIER
        comp._COST_MAP_BLUR_SIGMA = 2.0
        comp._SEAM_HARD_BARRIER = True
        try:
            zone = np.zeros((40, 50, 3), dtype=np.uint8)
            bg_a = np.ones((40, 50), dtype=np.uint8) * 255
            bg_b = np.ones((40, 50), dtype=np.uint8) * 255
            bg_a[:, :25] = 0
            bg_b[:, :25] = 0
            cost = comp._build_seam_cost_map(zone, bg_a, bg_b)
            assert (cost >= 1e5).any(), "Hard barriers must survive blur"
        finally:
            comp._COST_MAP_BLUR_SIGMA = orig_blur
            comp._SEAM_HARD_BARRIER = orig_barrier

    def test_zero_sigma_no_blur(self):
        import backend.src.anim.compositing as comp
        orig = comp._COST_MAP_BLUR_SIGMA
        comp._COST_MAP_BLUR_SIGMA = 0.0
        try:
            zone = np.zeros((40, 50, 3), dtype=np.uint8)
            bg_a = np.ones((40, 50), dtype=np.uint8) * 255
            bg_b = np.ones((40, 50), dtype=np.uint8) * 255
            bg_a[:, :25] = 0
            bg_b[:, :25] = 0
            cost_off = comp._build_seam_cost_map(zone, bg_a, bg_b)
            comp._COST_MAP_BLUR_SIGMA = 3.0
            cost_on = comp._build_seam_cost_map(zone, bg_a, bg_b)
            # Blurred cost should differ from unblurred
            soft = cost_off < 1e5
            assert not np.allclose(cost_off[soft], cost_on[soft])
        finally:
            comp._COST_MAP_BLUR_SIGMA = orig

    def test_constant_defined(self):
        from backend.src.constants.anim import COST_MAP_BLUR_SIGMA
        assert COST_MAP_BLUR_SIGMA > 0.0


# ---------------------------------------------------------------------------
# §1.111 — Zone background saturation normalization
# ---------------------------------------------------------------------------

class TestZoneSatNorm:
    def test_flag_in_module(self):
        import backend.src.anim.compositing as comp
        assert hasattr(comp, "_ZONE_SAT_NORM")

    def test_flag_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_ZONE_SAT_NORM" in comp.__all__

    def test_returns_uint8_same_shape(self):
        from backend.src.anim.compositing import _zone_sat_norm
        rng = np.random.default_rng(0)
        fa = rng.integers(10, 200, (30, 40, 3), dtype=np.uint8)
        fb = rng.integers(10, 200, (30, 40, 3), dtype=np.uint8)
        out = _zone_sat_norm(fa, fb)
        assert out.shape == fb.shape
        assert out.dtype == np.uint8

    def test_all_black_zone_returns_copy(self):
        from backend.src.anim.compositing import _zone_sat_norm
        fa = np.zeros((20, 30, 3), dtype=np.uint8)
        fb = np.ones((20, 30, 3), dtype=np.uint8) * 50
        out = _zone_sat_norm(fa, fb)
        np.testing.assert_array_equal(out, fb)

    def test_identical_saturation_unchanged(self):
        from backend.src.anim.compositing import _zone_sat_norm
        import cv2
        # Create a solid-color patch with defined saturation
        fa = np.full((30, 40, 3), 100, dtype=np.uint8)
        fb = fa.copy()
        out = _zone_sat_norm(fa, fb)
        # Same saturation → gain ~1.0 → output should be close to input
        assert np.abs(out.astype(np.float32) - fb.astype(np.float32)).mean() < 5.0


# ---------------------------------------------------------------------------
# §1.112 — Seam path vertical drift
# ---------------------------------------------------------------------------

class TestSeamPathDrift:
    def test_constant_path_zero_drift(self):
        from backend.src.anim.compositing import _seam_path_drift
        path = np.full(50, 10, dtype=np.int32)
        assert _seam_path_drift(path) == 0.0

    def test_single_large_jump(self):
        from backend.src.anim.compositing import _seam_path_drift
        path = np.zeros(50, dtype=np.int32)
        path[25:] = 20  # jump of 20 at column 25
        result = _seam_path_drift(path)
        assert result == pytest.approx(20.0)

    def test_gradual_slope_small_drift(self):
        from backend.src.anim.compositing import _seam_path_drift
        path = np.arange(50, dtype=np.int32)  # step of 1 per column
        result = _seam_path_drift(path)
        assert result == pytest.approx(1.0)

    def test_empty_path_returns_zero(self):
        from backend.src.anim.compositing import _seam_path_drift
        assert _seam_path_drift(np.array([], dtype=np.int32)) == 0.0

    def test_flag_and_constant_defined(self):
        import backend.src.anim.compositing as comp
        assert hasattr(comp, "_SEAM_DRIFT_THRESH")
        assert "_SEAM_DRIFT_THRESH" in comp.__all__
        from backend.src.constants.anim import SEAM_DRIFT_THRESH
        assert SEAM_DRIFT_THRESH > 0.0
