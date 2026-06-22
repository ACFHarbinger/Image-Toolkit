"""Tests for §3.28 _seam_row_grad_coherence (S157)."""
import numpy as np
import pytest


class TestSeamRowGradCoherence:
    def test_uniform_image_returns_low_coherence(self):
        from backend.benchmark.bench_anime_stitch import _seam_row_grad_coherence
        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        result = _seam_row_grad_coherence(img, n_strips=4, band_px=5)
        assert 0.0 <= result <= 1.0

    def test_horizontal_edge_high_coherence(self):
        from backend.benchmark.bench_anime_stitch import _seam_row_grad_coherence
        img = np.zeros((80, 60, 3), dtype=np.uint8)
        img[:40] = 200
        img[40:] = 0
        result = _seam_row_grad_coherence(img, n_strips=2, band_px=5)
        assert result > 0.0

    def test_result_in_valid_range(self):
        from backend.benchmark.bench_anime_stitch import _seam_row_grad_coherence
        rng = np.random.default_rng(55)
        img = rng.integers(0, 256, (100, 80, 3), dtype=np.uint8)
        result = _seam_row_grad_coherence(img, n_strips=8, band_px=8)
        assert 0.0 <= result <= 1.0

    def test_degenerate_input_returns_one(self):
        from backend.benchmark.bench_anime_stitch import _seam_row_grad_coherence
        result = _seam_row_grad_coherence(None)
        assert result == pytest.approx(1.0)

    def test_wired_into_compute_all_metrics(self):
        from backend.benchmark.bench_anime_stitch import _compute_all_metrics
        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        metrics = _compute_all_metrics(img)
        assert "seam_grad_coherence_min" in metrics
        assert isinstance(metrics["seam_grad_coherence_min"], float)
