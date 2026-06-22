"""
Tests for S152 benchmark metric:
  §3.23 _seam_col_spread
"""
import numpy as np
import pytest


class TestSeamColSpread:
    def test_returns_float(self):
        from backend.benchmark.bench_anime_stitch import _seam_col_spread
        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _seam_col_spread(img, n_strips=4)
        assert isinstance(result, float)

    def test_uniform_image_zero_spread(self):
        from backend.benchmark.bench_anime_stitch import _seam_col_spread
        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        result = _seam_col_spread(img, n_strips=4)
        assert result == pytest.approx(0.0, abs=1e-6)

    def test_result_is_normalized(self):
        from backend.benchmark.bench_anime_stitch import _seam_col_spread
        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _seam_col_spread(img, n_strips=4)
        assert result < 1.0

    def test_degenerate_one_strip(self):
        from backend.benchmark.bench_anime_stitch import _seam_col_spread
        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _seam_col_spread(img, n_strips=1)
        assert result == 0.0

    def test_degenerate_small_image(self):
        from backend.benchmark.bench_anime_stitch import _seam_col_spread
        img = np.zeros((3, 5, 3), dtype=np.uint8)
        result = _seam_col_spread(img, n_strips=4)
        assert isinstance(result, float)
