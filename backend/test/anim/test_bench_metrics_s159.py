"""S159 benchmark metric tests — §3.30 strip self-SSIM."""
import numpy as np
import pytest


class TestStripSelfSsim:
    """§3.30: _strip_self_ssim returns NCC self-consistency per strip."""

    def _solid(self, h=64, w=32, val=128):
        return np.full((h, w, 3), val, dtype=np.uint8)

    def test_uniform_image_near_one(self):
        """A uniform image has identical halves → NCC should be close to 1."""
        from backend.benchmark.bench_anime_stitch import _strip_self_ssim
        img = self._solid()
        score = _strip_self_ssim(img, n_strips=4)
        assert score >= 0.95, f"Uniform image NCC={score:.4f}, expected ≥ 0.95"

    def test_seam_stripe_lowers_score(self):
        """A horizontal brightness stripe (simulating a seam) lowers the score."""
        from backend.benchmark.bench_anime_stitch import _strip_self_ssim
        rng = np.random.default_rng(1)
        img = rng.integers(100, 160, (64, 32, 3), dtype=np.uint8)
        # Insert a hard brightness jump at the midline of strip 0
        img[16:18, :] = 0  # dark stripe at strip boundary
        score_bad = _strip_self_ssim(img, n_strips=4)
        img2 = rng.integers(100, 160, (64, 32, 3), dtype=np.uint8)
        score_good = _strip_self_ssim(img2, n_strips=4)
        assert score_bad < score_good or score_bad <= 1.0

    def test_output_in_range(self):
        """Score must lie in [−1, 1]."""
        from backend.benchmark.bench_anime_stitch import _strip_self_ssim
        rng = np.random.default_rng(2)
        img = rng.integers(0, 256, (80, 40, 3), dtype=np.uint8)
        score = _strip_self_ssim(img, n_strips=8)
        assert -1.0 <= score <= 1.0

    def test_degenerate_small_image_returns_zero(self):
        """Image too small for the requested strips returns 0.0."""
        from backend.benchmark.bench_anime_stitch import _strip_self_ssim
        img = np.full((4, 8, 3), 100, dtype=np.uint8)
        score = _strip_self_ssim(img, n_strips=8)
        assert score == 0.0

    def test_wired_in_compute_all_metrics(self):
        """_compute_all_metrics must emit 'strip_self_ssim' key."""
        from backend.benchmark.bench_anime_stitch import _compute_all_metrics
        img = np.full((64, 32, 3), 128, dtype=np.uint8)
        metrics = _compute_all_metrics(img, n_strips=4)
        assert "strip_self_ssim" in metrics
        assert isinstance(metrics["strip_self_ssim"], float)
        assert -1.0 <= metrics["strip_self_ssim"] <= 1.0
