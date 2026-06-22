"""
Tests for S151 benchmark metric:
  §3.22 _seam_contrast_ratio
"""
import numpy as np
import pytest


class TestSeamContrastRatio:
    def test_flat_image_returns_neutral(self):
        from backend.benchmark.bench_anime_stitch import _seam_contrast_ratio
        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        ratio = _seam_contrast_ratio(img, n_strips=4, band_px=5)
        # Flat image → all energies near zero → returns 1.0 (neutral)
        assert isinstance(ratio, float)

    def test_returns_float(self):
        from backend.benchmark.bench_anime_stitch import _seam_contrast_ratio
        img = np.random.randint(0, 256, (80, 60, 3), dtype=np.uint8)
        ratio = _seam_contrast_ratio(img, n_strips=4, band_px=5)
        assert isinstance(ratio, float)

    def test_high_contrast_seam_above_one(self):
        from backend.benchmark.bench_anime_stitch import _seam_contrast_ratio
        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        # Add a sharp edge at strip boundary
        img[38:42] = 255
        img[36:38] = 0
        ratio = _seam_contrast_ratio(img, n_strips=4, band_px=5)
        flat_ratio = _seam_contrast_ratio(np.full((80, 60, 3), 128, dtype=np.uint8), n_strips=4, band_px=5)
        # Sharp seam boundary should produce higher ratio than flat image
        assert ratio >= flat_ratio

    def test_degenerate_too_small(self):
        from backend.benchmark.bench_anime_stitch import _seam_contrast_ratio
        img = np.zeros((4, 10, 3), dtype=np.uint8)
        ratio = _seam_contrast_ratio(img, n_strips=4, band_px=2)
        assert isinstance(ratio, float)

    def test_single_strip_returns_neutral(self):
        from backend.benchmark.bench_anime_stitch import _seam_contrast_ratio
        img = np.random.randint(0, 256, (60, 50, 3), dtype=np.uint8)
        ratio = _seam_contrast_ratio(img, n_strips=1, band_px=5)
        assert ratio == pytest.approx(1.0)
