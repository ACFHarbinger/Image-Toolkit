"""
Tests for S150 benchmark metric:
  §3.21 _strip_gradient_cv
"""
import numpy as np
import pytest


class TestStripGradientCv:
    def test_uniform_image_zero_cv(self):
        from backend.benchmark.bench_anime_stitch import _strip_gradient_cv
        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        cv = _strip_gradient_cv(img, n_strips=4)
        assert cv == pytest.approx(0.0, abs=1e-3)

    def test_mixed_sharpness_high_cv(self):
        from backend.benchmark.bench_anime_stitch import _strip_gradient_cv
        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        rng = np.random.default_rng(0)
        img[:40] = rng.integers(0, 256, (40, 60, 3), dtype=np.uint8)
        cv = _strip_gradient_cv(img, n_strips=2)
        flat_cv = _strip_gradient_cv(np.full((80, 60, 3), 128, dtype=np.uint8), n_strips=2)
        assert cv > flat_cv

    def test_returns_float(self):
        from backend.benchmark.bench_anime_stitch import _strip_gradient_cv
        img = np.random.randint(0, 256, (60, 50, 3), dtype=np.uint8)
        result = _strip_gradient_cv(img, n_strips=4)
        assert isinstance(result, float)

    def test_degenerate_too_few_strips(self):
        from backend.benchmark.bench_anime_stitch import _strip_gradient_cv
        img = np.random.randint(0, 256, (8, 10, 3), dtype=np.uint8)
        result = _strip_gradient_cv(img, n_strips=1)
        assert result == 0.0

    def test_small_image_degenerate(self):
        from backend.benchmark.bench_anime_stitch import _strip_gradient_cv
        img = np.zeros((3, 10, 3), dtype=np.uint8)
        result = _strip_gradient_cv(img, n_strips=8)
        assert isinstance(result, float)
