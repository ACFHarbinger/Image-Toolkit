"""S158 benchmark metric tests: §3.29 zone_coverage_fraction."""
import numpy as np
import pytest

from backend.benchmark.bench_anime_stitch import _zone_coverage_fraction


class TestZoneCoverageFraction:
    """Five tests for _zone_coverage_fraction (S158)."""

    def test_standard_image(self):
        """8 strips, 800px image: 7 boundaries, each ~33px wide on each side."""
        img = np.zeros((800, 100, 3), dtype=np.uint8)
        frac = _zone_coverage_fraction(img, n_strips=8)
        # strip_h = 100, approx_feather = 33, total = 7*2*33 = 462, frac = 462/800
        expected = min(800, 7 * 2 * (100 // 3)) / 800
        assert frac == pytest.approx(expected, abs=1e-6)

    def test_fraction_in_unit_interval(self):
        """Output is always in [0, 1]."""
        for H in [50, 200, 800, 2000]:
            img = np.zeros((H, 50, 3), dtype=np.uint8)
            f = _zone_coverage_fraction(img, n_strips=8)
            assert 0.0 <= f <= 1.0, f"H={H}: fraction {f} out of [0,1]"

    def test_none_input(self):
        """None input returns 0.0."""
        assert _zone_coverage_fraction(None) == 0.0  # type: ignore[arg-type]

    def test_too_few_strips(self):
        """n_strips < 2 returns 0.0."""
        img = np.zeros((100, 50, 3), dtype=np.uint8)
        assert _zone_coverage_fraction(img, n_strips=1) == 0.0

    def test_more_strips_raises_coverage(self):
        """More strips → more boundaries → higher coverage fraction (up to cap)."""
        img = np.zeros((800, 50, 3), dtype=np.uint8)
        f4 = _zone_coverage_fraction(img, n_strips=4)
        f8 = _zone_coverage_fraction(img, n_strips=8)
        assert f8 >= f4
