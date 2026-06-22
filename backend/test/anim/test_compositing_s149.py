"""
Tests for S149 compositing features:
  §1.95 _SP_THRESH_FG_SCALE flag behaviour
  §3.19 _zone_chroma_align
  §1.97 _zone_entropy / _seam_zone_entropy_gap
"""
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# §1.95 — Fg-zone single-pose threshold scaling
# ---------------------------------------------------------------------------

class TestSpThreshFgScale:
    def test_flags_in_module(self):
        import backend.src.anim.compositing as comp
        assert hasattr(comp, "_SP_THRESH_FG_SCALE")
        assert hasattr(comp, "_SP_THRESH_FG_FACTOR")
        assert hasattr(comp, "_SP_FG_FRAC_THRESH")

    def test_fg_factor_default(self):
        import backend.src.anim.compositing as comp
        assert 0.0 < comp._SP_THRESH_FG_FACTOR <= 1.0

    def test_fg_frac_thresh_default(self):
        import backend.src.anim.compositing as comp
        assert 0.0 < comp._SP_FG_FRAC_THRESH < 1.0

    def test_flags_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_SP_THRESH_FG_SCALE" in comp.__all__

    def test_constants_defined(self):
        from backend.src.constants.anim import SP_THRESH_FG_FACTOR, SP_FG_FRAC_THRESH
        assert SP_THRESH_FG_FACTOR == pytest.approx(0.7)
        assert SP_FG_FRAC_THRESH == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# §3.19 — Per-zone pre-blend chroma alignment
# ---------------------------------------------------------------------------

class TestZoneChromaAlign:
    def test_identical_zones_returns_copy(self):
        from backend.src.anim.compositing import _zone_chroma_align
        zone = np.full((30, 40, 3), 128, dtype=np.uint8)
        out = _zone_chroma_align(zone, zone)
        assert out.shape == zone.shape

    def test_shifts_chroma_toward_reference(self):
        from backend.src.anim.compositing import _zone_chroma_align
        import cv2
        fa = np.full((20, 20, 3), [200, 100, 50], dtype=np.uint8)
        fb = np.full((20, 20, 3), [100, 200, 150], dtype=np.uint8)
        out = _zone_chroma_align(fa, fb)
        fa_lab = cv2.cvtColor(fa, cv2.COLOR_BGR2LAB).astype(np.float32)
        fb_lab = cv2.cvtColor(fb, cv2.COLOR_BGR2LAB).astype(np.float32)
        out_lab = cv2.cvtColor(out, cv2.COLOR_BGR2LAB).astype(np.float32)
        diff_before = abs(float(fa_lab[..., 1].mean()) - float(fb_lab[..., 1].mean()))
        diff_after = abs(float(fa_lab[..., 1].mean()) - float(out_lab[..., 1].mean()))
        assert diff_after <= diff_before + 1.0

    def test_output_shape_preserved(self):
        from backend.src.anim.compositing import _zone_chroma_align
        rng = np.random.default_rng(42)
        fa = rng.integers(50, 200, (25, 30, 3), dtype=np.uint8)
        fb = rng.integers(50, 200, (25, 30, 3), dtype=np.uint8)
        out = _zone_chroma_align(fa, fb)
        assert out.shape == fb.shape
        assert out.dtype == np.uint8

    def test_black_zone_returns_copy(self):
        from backend.src.anim.compositing import _zone_chroma_align
        black = np.zeros((10, 10, 3), dtype=np.uint8)
        fb = np.full((10, 10, 3), 100, dtype=np.uint8)
        out = _zone_chroma_align(black, fb)
        assert np.array_equal(out, fb)

    def test_function_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_zone_chroma_align" in comp.__all__
        assert "_ZONE_CHROMA_ALIGN" in comp.__all__


# ---------------------------------------------------------------------------
# §1.97 — Seam zone entropy asymmetry gate
# ---------------------------------------------------------------------------

class TestSeamZoneEntropyGap:
    def test_identical_zones_zero_gap(self):
        from backend.src.anim.compositing import _seam_zone_entropy_gap
        zone = np.random.randint(0, 256, (20, 30, 3), dtype=np.uint8)
        assert _seam_zone_entropy_gap(zone, zone) == pytest.approx(0.0)

    def test_flat_vs_noisy_high_gap(self):
        from backend.src.anim.compositing import _seam_zone_entropy_gap
        flat = np.full((30, 30, 3), 128, dtype=np.uint8)
        noisy = np.random.randint(0, 256, (30, 30, 3), dtype=np.uint8)
        gap = _seam_zone_entropy_gap(flat, noisy)
        assert gap > 1.0

    def test_entropy_positive(self):
        from backend.src.anim.compositing import _zone_entropy
        zone = np.random.randint(0, 256, (20, 20, 3), dtype=np.uint8)
        assert _zone_entropy(zone) >= 0.0

    def test_empty_zone_returns_zero(self):
        from backend.src.anim.compositing import _zone_entropy, _seam_zone_entropy_gap
        empty = np.zeros((0, 10, 3), dtype=np.uint8)
        assert _zone_entropy(empty) == 0.0
        assert _seam_zone_entropy_gap(empty, empty) == 0.0

    def test_functions_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_zone_entropy" in comp.__all__
        assert "_seam_zone_entropy_gap" in comp.__all__
        assert "_ENTROPY_GAP_THRESH" in comp.__all__
