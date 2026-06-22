"""
Tests for S153 benchmark metric:
  §3.24 _seam_row_std
"""
import numpy as np
import pytest


class TestSeamRowStd:
    def test_returns_float(self):
        from backend.benchmark.bench_anime_stitch import _seam_row_std
        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _seam_row_std(img, n_strips=4)
        assert isinstance(result, float)

    def test_flat_image_low_std(self):
        from backend.benchmark.bench_anime_stitch import _seam_row_std
        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        result = _seam_row_std(img, n_strips=4)
        assert result < 0.01

    def test_result_normalized_zero_to_one(self):
        from backend.benchmark.bench_anime_stitch import _seam_row_std
        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _seam_row_std(img, n_strips=4)
        assert 0.0 <= result <= 1.0

    def test_degenerate_single_strip(self):
        from backend.benchmark.bench_anime_stitch import _seam_row_std
        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _seam_row_std(img, n_strips=1)
        assert result == 0.0

    def test_high_contrast_boundary(self):
        from backend.benchmark.bench_anime_stitch import _seam_row_std
        img = np.zeros((80, 60, 3), dtype=np.uint8)
        # Alternating black/white columns at boundary row
        strip_h = 80 // 4  # = 20
        boundary_row = strip_h  # = 20
        img[boundary_row, ::2] = 255
        img[boundary_row, 1::2] = 0
        result = _seam_row_std(img, n_strips=4)
        flat_result = _seam_row_std(np.full((80, 60, 3), 128, dtype=np.uint8), n_strips=4)
        assert result > flat_result
