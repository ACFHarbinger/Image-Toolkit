"""Tests for §3.5B CamFlow background-masked phase correlation."""

import numpy as np
from backend.src.animation.flow.cam_flow import (
    bg_masked_phase_correlate,
    CamFlowEstimator,
    CAM_FLOW_MIN_BG_PIXELS,  # noqa: F401
)


class TestBgMaskedPhaseCorrelate:
    def test_no_mask_returns_tuple(self):
        rng = np.random.default_rng(0)
        a = rng.integers(0, 256, (64, 64, 3), dtype=np.uint8)
        b = np.roll(a, 5, axis=1)
        dx, dy, response = bg_masked_phase_correlate(a, b)
        assert isinstance(dx, float)
        assert isinstance(dy, float)
        assert isinstance(response, float)

    def test_with_bg_mask_detects_shift(self):
        """Background-only correlation should detect the camera shift."""
        a = np.zeros((64, 64), dtype=np.uint8)
        a[10:20, 10:20] = 200  # background texture patch
        b = np.roll(a, 4, axis=1)  # 4px horizontal shift
        bg = np.ones((64, 64), dtype=bool)
        bg[25:40, 25:40] = False  # foreground region
        dx, dy, response = bg_masked_phase_correlate(a, b, bg, bg)
        assert abs(dx - 4.0) < 1.5, f"Expected ~4px shift, got {dx:.2f}"

    def test_insufficient_bg_falls_back_to_whole_frame(self):
        """If bg area < min_bg_pixels, falls back to whole-frame — no crash."""
        rng = np.random.default_rng(42)
        a = rng.integers(0, 256, (64, 64, 3), dtype=np.uint8)
        b = a.copy()
        tiny_bg = np.zeros((64, 64), dtype=bool)
        tiny_bg[0, 0] = True  # only 1 bg pixel
        dx, dy, response = bg_masked_phase_correlate(
            a, b, tiny_bg, tiny_bg, min_bg_pixels=500
        )
        assert isinstance(dx, float)

    def test_camflow_estimator_zero_shift(self):
        """Identical frames should give ~zero displacement."""
        est = CamFlowEstimator()
        rng = np.random.default_rng(1)
        a = rng.integers(0, 256, (32, 32, 3), dtype=np.uint8)
        b = a.copy()
        dx, dy, response = est.estimate(a, b)
        assert abs(dx) < 1.0 and abs(dy) < 1.0

    def test_camflow_estimator_with_mask_vertical_shift(self):
        """Estimator with full-bg mask should detect a vertical shift."""
        est = CamFlowEstimator(min_bg_pixels=10)
        a = np.zeros((64, 64), dtype=np.uint8)
        a[5:15, 5:15] = 150
        b = np.roll(a, 3, axis=0)  # 3px downward scroll
        bg = np.ones((64, 64), dtype=bool)
        dx, dy, response = est.estimate(a, b, bg, bg)
        assert abs(abs(dy) - 3.0) < 1.5, f"Expected |dy|≈3, got {dy:.2f}"
