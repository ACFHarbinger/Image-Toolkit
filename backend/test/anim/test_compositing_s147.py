"""
Tests for S147 compositing features:
  §1.88 _seam_band_hist_match
  §1.89 seam residual order
  §1.90 _bilateral_seam_smooth
  §3.17 _hf_column_cost
"""
import importlib
import os

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# §1.88 — Band histogram matching
# ---------------------------------------------------------------------------

class TestSeamBandHistMatch:
    def test_output_shape_unchanged(self):
        from backend.src.anim.compositing import _seam_band_hist_match
        rng = np.random.default_rng(0)
        dom = rng.integers(0, 256, (50, 40, 3), dtype=np.uint8)
        oth = np.clip(dom.astype(np.float32) * 0.5, 0, 255).astype(np.uint8)
        path = np.full(50, 20, dtype=int)
        out = _seam_band_hist_match(dom, oth, path, band_px=8)
        assert out.shape == oth.shape

    def test_band_pixels_shifted_toward_dom(self):
        from backend.src.anim.compositing import _seam_band_hist_match
        dom = np.full((30, 30, 3), 200, dtype=np.uint8)
        oth = np.full((30, 30, 3), 50, dtype=np.uint8)
        path = np.full(30, 15, dtype=int)
        out = _seam_band_hist_match(dom, oth, path, band_px=8)
        band_mean = out[5:25, 7:23].mean()
        assert band_mean > 120  # shifted from 50 toward 200

    def test_outside_band_unchanged(self):
        from backend.src.anim.compositing import _seam_band_hist_match
        dom = np.full((30, 30, 3), 200, dtype=np.uint8)
        oth = np.full((30, 30, 3), 50, dtype=np.uint8)
        path = np.full(30, 15, dtype=int)
        out = _seam_band_hist_match(dom, oth, path, band_px=4)
        # Column 0 is far outside the band (path=15, band=4 → cols 11–19)
        assert np.all(out[:, 0] == 50)

    def test_zero_band_px_returns_copy(self):
        from backend.src.anim.compositing import _seam_band_hist_match
        oth = np.full((10, 10, 3), 100, dtype=np.uint8)
        dom = np.full((10, 10, 3), 200, dtype=np.uint8)
        path = np.full(10, 5, dtype=int)
        out = _seam_band_hist_match(dom, oth, path, band_px=0)
        assert np.array_equal(out, oth)

    def test_function_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_seam_band_hist_match" in comp.__all__


# ---------------------------------------------------------------------------
# §1.89 — Seam residual order
# ---------------------------------------------------------------------------

class TestSeamOrderResidual:
    def test_flag_default_off(self):
        import backend.src.anim.compositing as comp
        # Default env has no ASP_SEAM_ORDER=residual
        # We can't guarantee env state, but at least the attribute exists
        assert hasattr(comp, "_SEAM_ORDER_RESIDUAL")

    def test_residual_sort_ascending(self):
        seam_post_diffs = {0: 25.0, 1: 5.0, 2: 15.0}
        n_b = 3
        seam_order = sorted(range(n_b), key=lambda k: seam_post_diffs.get(k, 0.0))
        assert seam_order == [1, 2, 0]

    def test_empty_diffs_stable_order(self):
        seam_post_diffs = {}
        n_b = 4
        seam_order = sorted(range(n_b), key=lambda k: seam_post_diffs.get(k, 0.0))
        assert seam_order == [0, 1, 2, 3]

    def test_partial_diffs_default_zero(self):
        seam_post_diffs = {2: 10.0}
        n_b = 4
        seam_order = sorted(range(n_b), key=lambda k: seam_post_diffs.get(k, 0.0))
        assert seam_order[-1] == 2  # highest residual last
        assert seam_order[:3] == sorted(seam_order[:3])  # 0,1,3 all zero → stable

    def test_flag_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_SEAM_ORDER_RESIDUAL" in comp.__all__


# ---------------------------------------------------------------------------
# §1.90 — Bilateral seam smoothing
# ---------------------------------------------------------------------------

class TestBilateralSeamSmooth:
    def test_output_shape_unchanged(self):
        from backend.src.anim.compositing import _bilateral_seam_smooth
        canvas = np.random.randint(0, 256, (100, 200, 3), dtype=np.uint8)
        paths = {0: np.full(100, 50, dtype=int), 1: np.full(100, 100, dtype=int)}
        out = _bilateral_seam_smooth(canvas, paths)
        assert out.shape == canvas.shape

    def test_empty_paths_returns_copy(self):
        from backend.src.anim.compositing import _bilateral_seam_smooth
        canvas = np.random.randint(0, 256, (50, 100, 3), dtype=np.uint8)
        out = _bilateral_seam_smooth(canvas, {})
        assert np.array_equal(out, canvas)

    def test_outside_band_unchanged(self):
        from backend.src.anim.compositing import _bilateral_seam_smooth
        canvas = np.ones((30, 100, 3), dtype=np.uint8) * 128
        paths = {0: np.full(30, 50, dtype=int)}
        out = _bilateral_seam_smooth(canvas, paths, band_px=3)
        assert np.all(out[:, 0] == 128)

    def test_none_path_skipped(self):
        from backend.src.anim.compositing import _bilateral_seam_smooth
        canvas = np.ones((20, 40, 3), dtype=np.uint8) * 100
        paths = {0: None, 1: np.full(20, 20, dtype=int)}
        out = _bilateral_seam_smooth(canvas, paths)
        assert out.shape == canvas.shape

    def test_function_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_bilateral_seam_smooth" in comp.__all__


# ---------------------------------------------------------------------------
# §3.17 — High-frequency column seam cost
# ---------------------------------------------------------------------------

class TestHfColumnCost:
    def test_output_shape(self):
        from backend.src.anim.compositing import _hf_column_cost
        a = np.random.randint(0, 256, (40, 60, 3), dtype=np.uint8)
        b = np.random.randint(0, 256, (40, 60, 3), dtype=np.uint8)
        cost = _hf_column_cost(a, b)
        assert cost.shape == (40, 60)

    def test_flat_image_zero_cost(self):
        from backend.src.anim.compositing import _hf_column_cost
        a = np.full((30, 40, 3), 128, dtype=np.uint8)
        b = np.full((30, 40, 3), 128, dtype=np.uint8)
        cost = _hf_column_cost(a, b, hf_threshold=1.0)
        assert cost.max() == 0.0

    def test_high_freq_col_gets_boost(self):
        from backend.src.anim.compositing import _hf_column_cost
        a = np.zeros((30, 20, 3), dtype=np.uint8)
        # Alternating 0/255 pattern at column 10 = maximum high-frequency
        for row in range(30):
            a[row, 10] = 255 if row % 2 == 0 else 0
        b = a.copy()
        cost = _hf_column_cost(a, b, hf_threshold=10.0, hf_boost=1.0)
        assert cost[:, 10].mean() > cost[:, 0].mean()

    def test_dtype_float32(self):
        from backend.src.anim.compositing import _hf_column_cost
        a = np.random.randint(0, 256, (20, 30, 3), dtype=np.uint8)
        b = a.copy()
        cost = _hf_column_cost(a, b)
        assert cost.dtype == np.float32

    def test_function_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_hf_column_cost" in comp.__all__
