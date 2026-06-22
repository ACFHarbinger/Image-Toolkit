"""Tests for §3.27 _seam_band_ncc (S156)."""
import numpy as np
import pytest


class TestSeamBandNcc:
    def test_uniform_image_returns_one(self):
        from backend.benchmark.bench_anime_stitch import _seam_band_ncc
        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        result = _seam_band_ncc(img, n_strips=4, band_px=5)
        assert result == pytest.approx(1.0, abs=1e-4)

    def test_alternating_bands_low_ncc(self):
        from backend.benchmark.bench_anime_stitch import _seam_band_ncc
        rng = np.random.default_rng(13)
        img = np.zeros((80, 60, 3), dtype=np.uint8)
        for i in range(4):
            y0, y1 = i * 20, (i + 1) * 20
            # Use high-variance noise centered at 200 or 10 so bands differ clearly
            base = 200 if i % 2 == 0 else 10
            noise = rng.integers(-8, 9, (y1 - y0, 60, 3)).astype(np.int16)
            img[y0:y1] = np.clip(base + noise, 0, 255).astype(np.uint8)
        result = _seam_band_ncc(img, n_strips=4, band_px=5)
        assert result < 0.5

    def test_result_in_valid_range(self):
        from backend.benchmark.bench_anime_stitch import _seam_band_ncc
        rng = np.random.default_rng(7)
        img = rng.integers(0, 256, (100, 80, 3), dtype=np.uint8)
        result = _seam_band_ncc(img, n_strips=8, band_px=10)
        assert -1.0 <= result <= 1.0

    def test_too_few_strips_returns_one(self):
        from backend.benchmark.bench_anime_stitch import _seam_band_ncc
        img = np.full((20, 20, 3), 100, dtype=np.uint8)
        result = _seam_band_ncc(img, n_strips=1, band_px=5)
        assert result == pytest.approx(1.0)

    def test_wired_into_compute_all_metrics(self):
        from backend.benchmark.bench_anime_stitch import _compute_all_metrics
        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        metrics = _compute_all_metrics(img)
        assert "seam_band_ncc_min" in metrics
        assert isinstance(metrics["seam_band_ncc_min"], float)
