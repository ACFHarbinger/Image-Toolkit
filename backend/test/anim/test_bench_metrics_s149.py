"""
Tests for S149 benchmark metric:
  §1.96 _chroma_seam_coherence
"""
import numpy as np
import pytest


class TestChromaSeamCoherence:
    def test_flat_image_low_score(self):
        from backend.benchmark.bench_anime_stitch import _chroma_seam_coherence
        img = np.full((100, 80, 3), 128, dtype=np.uint8)
        score = _chroma_seam_coherence(img, n_strips=4)
        assert score < 5.0

    def test_banded_image_higher_score(self):
        from backend.benchmark.bench_anime_stitch import _chroma_seam_coherence
        img = np.zeros((80, 60, 3), dtype=np.uint8)
        img[:40] = [200, 100, 50]
        img[40:] = [50, 100, 200]
        score = _chroma_seam_coherence(img, n_strips=2)
        flat_score = _chroma_seam_coherence(np.full((80, 60, 3), 128, dtype=np.uint8), n_strips=2)
        assert score > flat_score

    def test_returns_float(self):
        from backend.benchmark.bench_anime_stitch import _chroma_seam_coherence
        img = np.random.randint(0, 256, (60, 50, 3), dtype=np.uint8)
        score = _chroma_seam_coherence(img, n_strips=4)
        assert isinstance(score, float)

    def test_degenerate_small_image(self):
        from backend.benchmark.bench_anime_stitch import _chroma_seam_coherence
        img = np.zeros((2, 10, 3), dtype=np.uint8)
        score = _chroma_seam_coherence(img, n_strips=4)
        assert isinstance(score, float)

    def test_single_strip_returns_zero(self):
        from backend.benchmark.bench_anime_stitch import _chroma_seam_coherence
        img = np.random.randint(0, 256, (60, 50, 3), dtype=np.uint8)
        score = _chroma_seam_coherence(img, n_strips=1)
        assert score == 0.0
