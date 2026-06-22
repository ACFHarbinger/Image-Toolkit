"""
Tests for S155 compositing features:
  §1.113 _COST_COL_SMOOTH_SIGMA column-wise cost smooth
  §1.114 _zone_contrast_eq
  §1.115 _cap_feather_jumps
"""
import numpy as np
import pytest


class TestCostColSmoothSigma:
    def test_flag_in_module(self):
        import backend.src.anim.compositing as comp
        assert hasattr(comp, "_COST_COL_SMOOTH_SIGMA")

    def test_flag_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_COST_COL_SMOOTH_SIGMA" in comp.__all__

    def test_default_is_zero(self):
        import backend.src.anim.compositing as comp
        assert comp._COST_COL_SMOOTH_SIGMA == pytest.approx(0.0)

    def test_column_smooth_spreads_cost(self):
        import backend.src.anim.compositing as comp
        orig = comp._COST_COL_SMOOTH_SIGMA
        comp._COST_COL_SMOOTH_SIGMA = 1.5
        try:
            import cv2
            zone = np.zeros((30, 50, 3), dtype=np.uint8)
            bg_a = np.ones((30, 50), dtype=np.uint8) * 255
            bg_b = np.ones((30, 50), dtype=np.uint8) * 255
            bg_a[:, 20:25] = 0
            bg_b[:, 20:25] = 0
            cost = comp._build_seam_cost_map(zone, bg_a, bg_b)
            # Column smooth should spread cost laterally from fg columns
            assert cost[:, 15].mean() > 0.0
        finally:
            comp._COST_COL_SMOOTH_SIGMA = orig

    def test_constant_defined(self):
        from backend.src.constants.anim import COST_COL_SMOOTH_SIGMA
        assert COST_COL_SMOOTH_SIGMA > 0.0


class TestZoneContrastEq:
    def test_identical_zones_returns_same_shape(self):
        from backend.src.anim.compositing import _zone_contrast_eq
        rng = np.random.default_rng(1)
        zone = rng.integers(50, 200, (20, 30, 3), dtype=np.uint8)
        out = _zone_contrast_eq(zone, zone)
        assert out.shape == zone.shape

    def test_equalizes_low_contrast_zone(self):
        from backend.src.anim.compositing import _zone_contrast_eq
        rng = np.random.default_rng(2)
        fa = rng.integers(50, 200, (20, 20, 3), dtype=np.uint8)
        # Near-flat fb
        fb_flat = np.clip(
            np.full((20, 20, 3), 128, dtype=np.int32) + rng.integers(-4, 5, (20, 20, 3)),
            0, 255
        ).astype(np.uint8)
        out = _zone_contrast_eq(fa, fb_flat)
        assert out.std() >= fb_flat.std() - 1

    def test_output_shape_and_dtype_preserved(self):
        from backend.src.anim.compositing import _zone_contrast_eq
        rng = np.random.default_rng(3)
        fa = rng.integers(0, 256, (25, 30, 3), dtype=np.uint8)
        fb = rng.integers(0, 256, (25, 30, 3), dtype=np.uint8)
        out = _zone_contrast_eq(fa, fb)
        assert out.shape == fb.shape
        assert out.dtype == np.uint8

    def test_black_zone_returns_copy(self):
        from backend.src.anim.compositing import _zone_contrast_eq
        fa = np.zeros((10, 10, 3), dtype=np.uint8)
        fb = np.full((10, 10, 3), 100, dtype=np.uint8)
        out = _zone_contrast_eq(fa, fb)
        assert np.array_equal(out, fb)

    def test_function_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_zone_contrast_eq" in comp.__all__
        assert "_ZONE_CONTRAST_EQ" in comp.__all__


class TestCapFeatherJumps:
    def test_no_jump_identity(self):
        from backend.src.anim.compositing import _cap_feather_jumps
        f = np.array([100, 110, 105, 108], dtype=np.int64)
        out = _cap_feather_jumps(f, max_jump=50)
        assert np.array_equal(out, f)

    def test_caps_large_jump(self):
        from backend.src.anim.compositing import _cap_feather_jumps
        f = np.array([80, 300, 80, 80], dtype=np.int64)
        out = _cap_feather_jumps(f, max_jump=100)
        assert out[1] <= 80 + 100

    def test_single_element_passthrough(self):
        from backend.src.anim.compositing import _cap_feather_jumps
        f = np.array([200], dtype=np.int64)
        out = _cap_feather_jumps(f, max_jump=50)
        assert len(out) == 1

    def test_zero_max_jump_passthrough(self):
        from backend.src.anim.compositing import _cap_feather_jumps
        f = np.array([80, 300, 80], dtype=np.int64)
        out = _cap_feather_jumps(f, max_jump=0)
        assert np.array_equal(out, f)

    def test_function_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_cap_feather_jumps" in comp.__all__
        assert "_FEATHER_JUMP_MAX" in comp.__all__
