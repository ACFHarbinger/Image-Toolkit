"""
Tests for S152 compositing features:
  §1.104 _zone_lum_norm
  §1.105 _FG_OVERLAP_BLEND_CAP
  §1.106 _audit_seam_lum_steps
"""
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# §1.104 — Per-zone luminance normalization
# ---------------------------------------------------------------------------

class TestZoneLumNorm:
    def test_identical_zones_unchanged(self):
        from backend.src.anim.compositing import _zone_lum_norm
        zone = np.full((20, 30, 3), 150, dtype=np.uint8)
        out = _zone_lum_norm(zone, zone)
        assert out.shape == zone.shape

    def test_normalizes_darker_zone(self):
        from backend.src.anim.compositing import _zone_lum_norm
        fa = np.full((20, 20, 3), 200, dtype=np.uint8)
        fb = np.full((20, 20, 3), 100, dtype=np.uint8)
        out = _zone_lum_norm(fa, fb)
        assert float(out.mean()) > 100.0

    def test_output_shape_preserved(self):
        from backend.src.anim.compositing import _zone_lum_norm
        rng = np.random.default_rng(0)
        fa = rng.integers(50, 200, (25, 30, 3), dtype=np.uint8)
        fb = rng.integers(50, 200, (25, 30, 3), dtype=np.uint8)
        out = _zone_lum_norm(fa, fb)
        assert out.shape == fb.shape
        assert out.dtype == np.uint8

    def test_black_zone_returns_copy(self):
        from backend.src.anim.compositing import _zone_lum_norm
        fa = np.zeros((10, 10, 3), dtype=np.uint8)
        fb = np.full((10, 10, 3), 100, dtype=np.uint8)
        out = _zone_lum_norm(fa, fb)
        assert np.array_equal(out, fb)

    def test_function_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_zone_lum_norm" in comp.__all__
        assert "_ZONE_LUM_NORM" in comp.__all__


# ---------------------------------------------------------------------------
# §1.105 — Fg-overlap blend weight cap
# ---------------------------------------------------------------------------

class TestFgOverlapBlendCap:
    def test_flag_in_module(self):
        import backend.src.anim.compositing as comp
        assert hasattr(comp, "_FG_OVERLAP_BLEND_CAP")

    def test_flag_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_FG_OVERLAP_BLEND_CAP" in comp.__all__

    def test_default_is_zero(self):
        import backend.src.anim.compositing as comp
        assert comp._FG_OVERLAP_BLEND_CAP == pytest.approx(0.0)

    def test_constant_defined(self):
        from backend.src.constants.anim import FG_OVERLAP_BLEND_CAP_DEFAULT
        assert 0.0 < FG_OVERLAP_BLEND_CAP_DEFAULT <= 0.5

    def test_config_schema_has_key(self):
        from backend.src.anim.config import _CONFIG_SCHEMA
        assert "ASP_FG_OVERLAP_BLEND_CAP" in _CONFIG_SCHEMA


# ---------------------------------------------------------------------------
# §1.106 — Post-composite seam luminance step audit
# ---------------------------------------------------------------------------

class TestAuditSeamLumSteps:
    def test_flat_canvas_zero_steps(self):
        from backend.src.anim.compositing import _audit_seam_lum_steps
        canvas = np.full((100, 80, 3), 128, dtype=np.uint8)
        steps = _audit_seam_lum_steps(canvas, [30.0, 60.0], band_px=5, warn_thresh=8.0)
        assert len(steps) == 2
        assert steps[0] < 1.0
        assert steps[1] < 1.0

    def test_sharp_step_detected(self):
        from backend.src.anim.compositing import _audit_seam_lum_steps
        canvas = np.zeros((100, 80, 3), dtype=np.uint8)
        canvas[:50] = 200
        canvas[50:] = 50
        steps = _audit_seam_lum_steps(canvas, [50.0], band_px=5, warn_thresh=8.0)
        assert steps[0] > 50.0

    def test_returns_dict_keyed_by_index(self):
        from backend.src.anim.compositing import _audit_seam_lum_steps
        canvas = np.full((80, 60, 3), 100, dtype=np.uint8)
        steps = _audit_seam_lum_steps(canvas, [20.0, 40.0, 60.0])
        assert isinstance(steps, dict)
        assert set(steps.keys()) == {0, 1, 2}

    def test_empty_boundaries_empty_dict(self):
        from backend.src.anim.compositing import _audit_seam_lum_steps
        canvas = np.full((60, 40, 3), 128, dtype=np.uint8)
        steps = _audit_seam_lum_steps(canvas, [])
        assert steps == {}

    def test_function_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_audit_seam_lum_steps" in comp.__all__
        assert "_POST_SEAM_WARN_THRESH" in comp.__all__
