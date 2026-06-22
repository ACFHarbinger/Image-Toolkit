"""
Tests for S153 compositing features:
  §1.107 _adaptive_seam_band
  §1.108 _LAPLACIAN_ALPHA_SCHEDULE
  §1.109 _COST_MAP_NORM
"""
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# §1.107 — Adaptive seam band width
# ---------------------------------------------------------------------------

class TestAdaptiveSeamBand:
    def test_short_zone_uses_base_band(self):
        from backend.src.anim.compositing import _adaptive_seam_band
        # zone_h=10, base=10, max=40 → max(10, 10//6=1) = 10
        result = _adaptive_seam_band(zone_h=10, base_band=10, max_band=40)
        assert result == 10

    def test_tall_zone_grows_band(self):
        from backend.src.anim.compositing import _adaptive_seam_band
        # zone_h=120, base=10, max=40 → max(10, 120//6=20) = 20
        result = _adaptive_seam_band(zone_h=120, base_band=10, max_band=40)
        assert result == 20

    def test_very_tall_zone_clamped_to_max(self):
        from backend.src.anim.compositing import _adaptive_seam_band
        # zone_h=600, base=10, max=40 → min(40, max(10, 100)) = 40
        result = _adaptive_seam_band(zone_h=600, base_band=10, max_band=40)
        assert result == 40

    def test_result_at_least_base_band(self):
        from backend.src.anim.compositing import _adaptive_seam_band
        for zone_h in [1, 5, 10, 50, 200]:
            result = _adaptive_seam_band(zone_h=zone_h, base_band=8, max_band=40)
            assert result >= 8

    def test_function_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_adaptive_seam_band" in comp.__all__
        assert "_ADAPTIVE_SEAM_BAND" in comp.__all__


# ---------------------------------------------------------------------------
# §1.108 — Laplacian blend alpha schedule
# ---------------------------------------------------------------------------

class TestLaplacianAlphaSchedule:
    def test_flag_in_module(self):
        import backend.src.anim.compositing as comp
        assert hasattr(comp, "_LAPLACIAN_ALPHA_SCHEDULE")

    def test_flag_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_LAPLACIAN_ALPHA_SCHEDULE" in comp.__all__

    def test_alpha_schedule_accepted_by_laplacian_blend(self):
        from backend.src.anim.stateless import _laplacian_blend
        import inspect
        sig = inspect.signature(_laplacian_blend)
        assert "alpha_schedule" in sig.parameters

    def test_alpha_schedule_output_valid(self):
        from backend.src.anim.stateless import _laplacian_blend
        rng = np.random.default_rng(42)
        a = rng.integers(0, 256, (30, 40, 3), dtype=np.uint8)
        b = rng.integers(0, 256, (30, 40, 3), dtype=np.uint8)
        mask = np.ones((30, 40), dtype=np.float32) * 0.5
        out = _laplacian_blend(a, b, mask, alpha_schedule=True)
        assert out.shape == a.shape
        assert out.dtype == np.uint8

    def test_constant_defined(self):
        from backend.src.constants.anim import LAPLACIAN_ALPHA_FINE_WEIGHT
        assert 0.0 < LAPLACIAN_ALPHA_FINE_WEIGHT <= 1.0


# ---------------------------------------------------------------------------
# §1.109 — Seam cost map L-inf normalization
# ---------------------------------------------------------------------------

class TestCostMapNorm:
    def test_flag_in_module(self):
        import backend.src.anim.compositing as comp
        assert hasattr(comp, "_COST_MAP_NORM")

    def test_flag_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_COST_MAP_NORM" in comp.__all__

    def test_normalized_map_max_is_one(self):
        import backend.src.anim.compositing as comp
        orig = comp._COST_MAP_NORM
        comp._COST_MAP_NORM = True
        try:
            import cv2
            zone = np.zeros((40, 50, 3), dtype=np.uint8)
            bg_a = np.zeros((40, 50), dtype=np.uint8)  # all fg
            bg_b = np.zeros((40, 50), dtype=np.uint8)
            cost = comp._build_seam_cost_map(zone, bg_a, bg_b)
            # Non-barrier max should be <= 1.0 after normalization
            soft_max = float(cost[cost < 1e5].max()) if (cost < 1e5).any() else 0.0
            assert soft_max <= 1.0 + 1e-5
        finally:
            comp._COST_MAP_NORM = orig

    def test_barriers_preserved_after_norm(self):
        import backend.src.anim.compositing as comp
        orig_norm = comp._COST_MAP_NORM
        orig_barrier = comp._SEAM_HARD_BARRIER
        comp._COST_MAP_NORM = True
        comp._SEAM_HARD_BARRIER = True
        try:
            zone = np.zeros((40, 50, 3), dtype=np.uint8)
            # Mix fg (left half) and bg (right half) to trigger column barrier
            bg_a = np.ones((40, 50), dtype=np.uint8) * 255  # all bg initially
            bg_b = np.ones((40, 50), dtype=np.uint8) * 255
            bg_a[:, :25] = 0   # left columns are fg
            bg_b[:, :25] = 0
            cost = comp._build_seam_cost_map(zone, bg_a, bg_b)
            # With hard barrier enabled on fg-dominated columns, barriers should exist
            assert (cost >= 1e5).any()
        finally:
            comp._COST_MAP_NORM = orig_norm
            comp._SEAM_HARD_BARRIER = orig_barrier

    def test_config_schema_has_key(self):
        from backend.src.anim.config import _CONFIG_SCHEMA
        assert "ASP_COST_MAP_NORM" in _CONFIG_SCHEMA
