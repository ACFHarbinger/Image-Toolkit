"""
Tests for S155 benchmark metric:
  §3.26 _strip_sat_cv
"""
import numpy as np
import pytest


class TestStripSatCv:
    def test_returns_float(self):
        from backend.benchmark.bench_anime_stitch import _strip_sat_cv
        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _strip_sat_cv(img, n_strips=4)
        assert isinstance(result, float)

    def test_grayscale_image_zero_cv(self):
        from backend.benchmark.bench_anime_stitch import _strip_sat_cv
        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        result = _strip_sat_cv(img, n_strips=4)
        assert result == pytest.approx(0.0, abs=1e-3)

    def test_banded_sat_higher_than_flat(self):
        from backend.benchmark.bench_anime_stitch import _strip_sat_cv
        img = np.zeros((80, 60, 3), dtype=np.uint8)
        img[:40] = [200, 50, 50]
        img[40:] = [128, 128, 128]
        result = _strip_sat_cv(img, n_strips=2)
        gray_result = _strip_sat_cv(np.full((80, 60, 3), 128, dtype=np.uint8), n_strips=2)
        assert result > gray_result

    def test_degenerate_single_strip(self):
        from backend.benchmark.bench_anime_stitch import _strip_sat_cv
        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _strip_sat_cv(img, n_strips=1)
        assert result == 0.0

    def test_degenerate_small_image(self):
        from backend.benchmark.bench_anime_stitch import _strip_sat_cv
        img = np.zeros((3, 10, 3), dtype=np.uint8)
        result = _strip_sat_cv(img, n_strips=8)
        assert isinstance(result, float)
