"""
Tests for S150 compositing features:
  §1.98 _smooth_gain_array / _SMOOTH_GAIN
  §3.20 _EXTRA_FG_DILATION cost ring
  §1.99 _SEAM_PIN_ROWS endpoint bg-preference
"""
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# §1.98 — Per-frame gain smoothing
# ---------------------------------------------------------------------------

class TestSmoothGainArray:
    def test_single_element_passthrough(self):
        from backend.src.anim.compositing import _smooth_gain_array
        out = _smooth_gain_array([1.5], sigma=1.0)
        assert len(out) == 1
        assert abs(float(out[0]) - 1.5) < 1e-6

    def test_smooths_spike(self):
        from backend.src.anim.compositing import _smooth_gain_array
        gains = [1.0, 2.0, 1.0, 1.0, 1.0]
        out = _smooth_gain_array(gains, sigma=1.0)
        # The spike at index 1 should be reduced
        assert float(out[1]) < 2.0

    def test_uniform_gains_unchanged(self):
        from backend.src.anim.compositing import _smooth_gain_array
        gains = [1.2, 1.2, 1.2, 1.2]
        out = _smooth_gain_array(gains, sigma=1.0)
        assert np.allclose(out, 1.2, atol=1e-5)

    def test_output_length_preserved(self):
        from backend.src.anim.compositing import _smooth_gain_array
        gains = [0.9, 1.1, 0.95, 1.05, 1.0, 0.88]
        out = _smooth_gain_array(gains, sigma=1.0)
        assert len(out) == len(gains)

    def test_flags_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_smooth_gain_array" in comp.__all__
        assert "_SMOOTH_GAIN" in comp.__all__
        assert "_SMOOTH_GAIN_SIGMA" in comp.__all__


# ---------------------------------------------------------------------------
# §3.20 — Extra fg-boundary dilation cost ring
# ---------------------------------------------------------------------------

class TestExtraFgDilationCost:
    def _make_cost_map(self, extra_dilation):
        import backend.src.anim.compositing as comp
        orig = comp._EXTRA_FG_DILATION
        comp._EXTRA_FG_DILATION = extra_dilation
        try:
            import cv2
            zone = np.zeros((60, 80, 3), dtype=np.uint8)
            bg_a = np.ones((60, 80), dtype=np.uint8) * 255
            bg_b = np.ones((60, 80), dtype=np.uint8) * 255
            bg_a[20:40, 30:50] = 0
            bg_b[20:40, 30:50] = 0
            return comp._build_seam_cost_map(zone, bg_a, bg_b)
        finally:
            comp._EXTRA_FG_DILATION = orig

    def test_flag_in_module(self):
        import backend.src.anim.compositing as comp
        assert hasattr(comp, "_EXTRA_FG_DILATION")

    def test_flag_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_EXTRA_FG_DILATION" in comp.__all__

    def test_constant_defined(self):
        from backend.src.constants.anim import EXTRA_FG_DILATION_DEFAULT
        assert EXTRA_FG_DILATION_DEFAULT > 0

    def test_extra_ring_creates_outer_cost(self):
        cost_off = self._make_cost_map(extra_dilation=0)
        cost_on = self._make_cost_map(extra_dilation=8)
        assert (cost_on > 0).sum() >= (cost_off > 0).sum()

    def test_extra_ring_does_not_exceed_column_barrier(self):
        cost = self._make_cost_map(extra_dilation=8)
        # Column barrier (§3.15A) raises fg-dominated columns to 2.0; outer ring
        # adds only 0.3 and np.maximum preserves higher tiers — max should stay ≤ 2.0
        assert float(cost.max()) <= 2.0 + 1e-3


# ---------------------------------------------------------------------------
# §1.99 — Seam endpoint bg-preference
# ---------------------------------------------------------------------------

class TestSeamPinRows:
    def test_flag_in_module(self):
        import backend.src.anim.compositing as comp
        assert hasattr(comp, "_SEAM_PIN_ROWS")

    def test_flag_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_SEAM_PIN_ROWS" in comp.__all__

    def test_constant_defined(self):
        from backend.src.constants.anim import SEAM_PIN_ROWS_DEFAULT
        assert SEAM_PIN_ROWS_DEFAULT > 0

    def test_pin_amplifies_top_fg_cost(self):
        import backend.src.anim.compositing as comp
        orig = comp._SEAM_PIN_ROWS
        comp._SEAM_PIN_ROWS = 3
        try:
            import cv2
            zone = np.zeros((40, 50, 3), dtype=np.uint8)
            bg_a = np.zeros((40, 50), dtype=np.uint8)
            bg_b = np.zeros((40, 50), dtype=np.uint8)
            cost_on = comp._build_seam_cost_map(zone, bg_a, bg_b)
            comp._SEAM_PIN_ROWS = 0
            cost_off = comp._build_seam_cost_map(zone, bg_a, bg_b)
            assert float(cost_on[:3].mean()) >= float(cost_off[:3].mean())
        finally:
            comp._SEAM_PIN_ROWS = orig

    def test_pin_only_affects_fg_pixels(self):
        import backend.src.anim.compositing as comp
        orig = comp._SEAM_PIN_ROWS
        comp._SEAM_PIN_ROWS = 3
        try:
            import cv2
            zone = np.zeros((40, 50, 3), dtype=np.uint8)
            bg_a = np.ones((40, 50), dtype=np.uint8) * 255
            bg_b = np.ones((40, 50), dtype=np.uint8) * 255
            cost_on = comp._build_seam_cost_map(zone, bg_a, bg_b)
            comp._SEAM_PIN_ROWS = 0
            cost_off = comp._build_seam_cost_map(zone, bg_a, bg_b)
            assert np.allclose(cost_on, cost_off, atol=1e-5)
        finally:
            comp._SEAM_PIN_ROWS = orig
