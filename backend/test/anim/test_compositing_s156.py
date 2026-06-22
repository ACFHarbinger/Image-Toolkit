"""
Tests for S156 compositing features:
  §1.116 _ZONE_BG_FRAC_DIAG
  §1.117 _zone_pair_ncc
  §1.118 _measure_seam_sharpness
"""
import numpy as np
import pytest


class TestZoneBgFracDiag:
    def test_flag_in_module(self):
        import backend.src.anim.compositing as comp
        assert hasattr(comp, "_ZONE_BG_FRAC_DIAG")

    def test_flag_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_ZONE_BG_FRAC_DIAG" in comp.__all__

    def test_default_is_false(self):
        import backend.src.anim.compositing as comp
        assert comp._ZONE_BG_FRAC_DIAG is False

    def test_constant_defined(self):
        from backend.src.constants.anim import ZONE_BG_FRAC_DIAG_KEY
        assert isinstance(ZONE_BG_FRAC_DIAG_KEY, str)

    def test_config_schema_has_key(self):
        from backend.src.anim.config import _CONFIG_SCHEMA
        assert "ASP_ZONE_BG_FRAC_DIAG" in _CONFIG_SCHEMA


class TestZonePairNcc:
    def test_identical_zones_returns_one(self):
        from backend.src.anim.compositing import _zone_pair_ncc
        rng = np.random.default_rng(0)
        zone = rng.integers(30, 200, (30, 40, 3), dtype=np.uint8)
        ncc = _zone_pair_ncc(zone, zone)
        assert ncc == pytest.approx(1.0, abs=1e-4)

    def test_opposite_zones_low_ncc(self):
        from backend.src.anim.compositing import _zone_pair_ncc
        a = np.zeros((20, 20, 3), dtype=np.uint8)
        a[:10] = 200
        b = np.zeros((20, 20, 3), dtype=np.uint8)
        b[10:] = 200
        ncc = _zone_pair_ncc(a, b)
        assert ncc < 0.9

    def test_result_in_valid_range(self):
        from backend.src.anim.compositing import _zone_pair_ncc
        rng = np.random.default_rng(42)
        a = rng.integers(0, 256, (25, 30, 3), dtype=np.uint8)
        b = rng.integers(0, 256, (25, 30, 3), dtype=np.uint8)
        ncc = _zone_pair_ncc(a, b)
        assert -1.0 <= ncc <= 1.0

    def test_empty_zone_returns_one(self):
        from backend.src.anim.compositing import _zone_pair_ncc
        empty = np.zeros((0, 10, 3), dtype=np.uint8)
        ncc = _zone_pair_ncc(empty, empty)
        assert ncc == pytest.approx(1.0)

    def test_function_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_zone_pair_ncc" in comp.__all__
        assert "_ZONE_FAST_NCC_THRESH" in comp.__all__


class TestMeasureSeamSharpness:
    def test_flat_canvas_low_sharpness(self):
        from backend.src.anim.compositing import _measure_seam_sharpness
        canvas = np.full((100, 80, 3), 128, dtype=np.uint8)
        sharpness = _measure_seam_sharpness(canvas, [30.0, 60.0], band_px=5)
        assert len(sharpness) == 2
        assert sharpness[0] < 10.0
        assert sharpness[1] < 10.0

    def test_sharp_edge_high_variance(self):
        from backend.src.anim.compositing import _measure_seam_sharpness
        canvas = np.zeros((80, 60, 3), dtype=np.uint8)
        canvas[:40] = 200
        canvas[40:] = 0
        sharpness = _measure_seam_sharpness(canvas, [40.0], band_px=5)
        assert sharpness[0] > 100.0

    def test_returns_dict_keyed_by_index(self):
        from backend.src.anim.compositing import _measure_seam_sharpness
        canvas = np.full((80, 60, 3), 100, dtype=np.uint8)
        sharpness = _measure_seam_sharpness(canvas, [20.0, 40.0, 60.0])
        assert isinstance(sharpness, dict)
        assert set(sharpness.keys()) == {0, 1, 2}

    def test_empty_boundaries_empty_dict(self):
        from backend.src.anim.compositing import _measure_seam_sharpness
        canvas = np.full((60, 40, 3), 128, dtype=np.uint8)
        sharpness = _measure_seam_sharpness(canvas, [])
        assert sharpness == {}

    def test_function_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_measure_seam_sharpness" in comp.__all__
        assert "_SEAM_SHARP_MIN" in comp.__all__
