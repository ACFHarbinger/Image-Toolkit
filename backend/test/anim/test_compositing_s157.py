"""
Tests for S157 compositing features:
  §1.119 _zone_width_cv
  §1.120 _audit_seam_sat_steps
  §1.121 _zone_hist_intersection
"""
import numpy as np
import pytest


class TestZoneWidthCv:
    def test_uniform_widths_zero_cv(self):
        from backend.src.anim.compositing import _zone_width_cv
        boundaries = [0.0, 100.0, 200.0, 300.0]
        cv = _zone_width_cv(boundaries)
        assert cv == pytest.approx(0.0, abs=1e-6)

    def test_uneven_widths_high_cv(self):
        from backend.src.anim.compositing import _zone_width_cv
        boundaries = [0.0, 5.0, 200.0, 205.0]
        cv = _zone_width_cv(boundaries)
        assert cv > 0.5

    def test_single_boundary_returns_zero(self):
        from backend.src.anim.compositing import _zone_width_cv
        assert _zone_width_cv([50.0]) == pytest.approx(0.0)

    def test_empty_boundaries_returns_zero(self):
        from backend.src.anim.compositing import _zone_width_cv
        assert _zone_width_cv([]) == pytest.approx(0.0)

    def test_function_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_zone_width_cv" in comp.__all__
        assert "_ZONE_WIDTH_CV_MAX" in comp.__all__


class TestAuditSeamSatSteps:
    def test_uniform_image_zero_step(self):
        from backend.src.anim.compositing import _audit_seam_sat_steps
        canvas = np.full((80, 60, 3), 128, dtype=np.uint8)
        sat_steps = _audit_seam_sat_steps(canvas, [40.0], band_px=5)
        assert len(sat_steps) == 1
        assert sat_steps[0] < 5.0

    def test_saturated_vs_grey_high_step(self):
        from backend.src.anim.compositing import _audit_seam_sat_steps
        canvas = np.zeros((80, 60, 3), dtype=np.uint8)
        # Top half: vivid red (high sat in HSV)
        canvas[:40] = (0, 0, 200)
        # Bottom half: grey (zero sat)
        canvas[40:] = (128, 128, 128)
        sat_steps = _audit_seam_sat_steps(canvas, [40.0], band_px=5)
        assert sat_steps[0] > 10.0

    def test_empty_boundaries_empty_dict(self):
        from backend.src.anim.compositing import _audit_seam_sat_steps
        canvas = np.full((60, 40, 3), 100, dtype=np.uint8)
        sat_steps = _audit_seam_sat_steps(canvas, [])
        assert sat_steps == {}

    def test_returns_dict_keyed_by_index(self):
        from backend.src.anim.compositing import _audit_seam_sat_steps
        canvas = np.full((90, 60, 3), 120, dtype=np.uint8)
        sat_steps = _audit_seam_sat_steps(canvas, [30.0, 60.0])
        assert isinstance(sat_steps, dict)
        assert set(sat_steps.keys()) == {0, 1}

    def test_flag_and_function_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_audit_seam_sat_steps" in comp.__all__
        assert "_SEAM_SAT_WARN_THRESH" in comp.__all__


class TestZoneHistIntersection:
    def test_identical_zones_returns_one(self):
        from backend.src.anim.compositing import _zone_hist_intersection
        rng = np.random.default_rng(1)
        zone = rng.integers(20, 200, (30, 40, 3), dtype=np.uint8)
        score = _zone_hist_intersection(zone, zone)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_different_palettes_low_score(self):
        from backend.src.anim.compositing import _zone_hist_intersection
        a = np.zeros((30, 30, 3), dtype=np.uint8)
        a[:] = (200, 50, 50)
        b = np.zeros((30, 30, 3), dtype=np.uint8)
        b[:] = (50, 50, 200)
        score = _zone_hist_intersection(a, b)
        assert score < 0.7

    def test_result_in_valid_range(self):
        from backend.src.anim.compositing import _zone_hist_intersection
        rng = np.random.default_rng(99)
        a = rng.integers(0, 256, (20, 20, 3), dtype=np.uint8)
        b = rng.integers(0, 256, (20, 20, 3), dtype=np.uint8)
        score = _zone_hist_intersection(a, b)
        assert 0.0 <= score <= 1.0

    def test_empty_zone_returns_one(self):
        from backend.src.anim.compositing import _zone_hist_intersection
        empty = np.zeros((0, 10, 3), dtype=np.uint8)
        score = _zone_hist_intersection(empty, empty)
        assert score == pytest.approx(1.0)

    def test_function_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_zone_hist_intersection" in comp.__all__
        assert "_ZONE_HIST_THRESH" in comp.__all__
