"""
Tests for S154 benchmark metric:
  §3.25 _seam_boundary_entropy
"""
import numpy as np
import pytest


class TestSeamBoundaryEntropy:
    def test_returns_list_of_correct_length(self):
        from backend.benchmark.bench_anime_stitch import _seam_boundary_entropy
        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _seam_boundary_entropy(img, n_strips=4, band_px=5)
        assert isinstance(result, list)
        assert len(result) == 3  # n_strips - 1

    def test_flat_image_low_entropy(self):
        from backend.benchmark.bench_anime_stitch import _seam_boundary_entropy
        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        result = _seam_boundary_entropy(img, n_strips=4, band_px=5)
        assert all(e < 0.05 for e in result)

    def test_random_image_high_entropy(self):
        from backend.benchmark.bench_anime_stitch import _seam_boundary_entropy
        rng = np.random.default_rng(1)
        img = rng.integers(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _seam_boundary_entropy(img, n_strips=4, band_px=5)
        assert any(e > 0.7 for e in result)

    def test_values_in_zero_one(self):
        from backend.benchmark.bench_anime_stitch import _seam_boundary_entropy
        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _seam_boundary_entropy(img, n_strips=4, band_px=5)
        assert all(0.0 <= e <= 1.0 for e in result)

    def test_degenerate_single_strip(self):
        from backend.benchmark.bench_anime_stitch import _seam_boundary_entropy
        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        result = _seam_boundary_entropy(img, n_strips=1)
        assert result == []
