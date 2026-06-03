"""
Tests for foreground pose registration (fg_register.py, Stage 8.5).

Validates that the flow-guided midpoint re-posing reduces the displacement of
an animated foreground element across a strip seam, without disturbing the
aligned background. All tests run without GPU (OpenCV DISOpticalFlow).
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

_repo_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, _repo_root)

from backend.src.anim.fg_register import (  # noqa: E402
    register_foreground_at_seam,
    _seam_taper,
    _dense_flow,
)


# ---------------------------------------------------------------------------
# Synthetic scene helpers
# ---------------------------------------------------------------------------

def _make_scene(limb_x: int, h: int = 400, w: int = 360, limb_w: int = 40):
    """
    A canvas-aligned frame: textured static background + a bright 'limb'
    rectangle whose horizontal position is `limb_x` (the animated part).
    A textured pattern is painted inside the limb so optical flow can track it.
    Returns (bgr, fg_mask_bool).
    """
    rng = np.random.default_rng(0)
    bg = (rng.integers(40, 80, size=(h, w, 3))).astype(np.uint8)  # textured bg
    img = bg.copy()
    fg = np.zeros((h, w), dtype=bool)
    y0, y1 = 120, 280
    x0, x1 = limb_x, limb_x + limb_w
    x0c, x1c = max(0, x0), min(w, x1)
    if x1c > x0c:
        img[y0:y1, x0c:x1c] = (230, 200, 180)
        # Trackable texture: diagonal stripes inside the limb
        for k in range(x0c, x1c, 8):
            img[y0:y1, k:min(k + 3, x1c)] = (140, 110, 90)
        fg[y0:y1, x0c:x1c] = True
    return img, fg


def _fg_centroid_x(img, fg):
    ys, xs = np.where(fg)
    return float(xs.mean()) if xs.size else 0.0


# ---------------------------------------------------------------------------
# Taper weight
# ---------------------------------------------------------------------------

class TestSeamTaper:
    def test_peak_at_seam(self):
        t = _seam_taper(100, 50, seam_pos=50, taper_px=20, axis=0)
        assert t[50, 0] == pytest.approx(1.0)
        assert t[30, 0] == pytest.approx(0.0, abs=1e-6)
        assert t[70, 0] == pytest.approx(0.0, abs=1e-6)
        assert t[40, 0] == pytest.approx(0.5, abs=0.05)

    def test_horizontal_axis(self):
        t = _seam_taper(50, 100, seam_pos=50, taper_px=20, axis=1)
        assert t[0, 50] == pytest.approx(1.0)
        assert t[0, 30] == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Core registration
# ---------------------------------------------------------------------------

class TestForegroundRegistration:
    def test_reduces_limb_displacement_at_seam(self):
        """
        Frame A has the limb at x=120, frame B at x=150 (animated +30px).
        After midpoint re-posing both should converge toward x≈135, so the
        post-warp centroid gap must shrink substantially.
        """
        a, fa = _make_scene(120)
        b, fb = _make_scene(150)

        seam = 200  # horizontal seam mid-canvas
        adj_a, adj_b, info = register_foreground_at_seam(
            a, b, fa, fb, seam_pos=seam, axis=0
        )

        assert info["warped"] is True, info
        # Re-detect foreground by brightness (limb is brighter than bg)
        def bright_mask(img):
            return img.mean(axis=2) > 150
        cax = _fg_centroid_x(adj_a, bright_mask(adj_a))
        cbx = _fg_centroid_x(adj_b, bright_mask(adj_b))
        orig_gap = abs(150 - 120)
        new_gap = abs(cbx - cax)
        # A single tapered midpoint warp should remove a substantial fraction of
        # the seam gap (measured ~37% here; require ≥ 25%).
        assert new_gap < orig_gap * 0.75, (
            f"seam gap not reduced enough: {orig_gap} -> {new_gap}"
        )
        assert new_gap < orig_gap, "warp must not increase the gap"

    def test_background_untouched(self):
        """The aligned background outside the foreground must be unchanged."""
        a, fa = _make_scene(120)
        b, fb = _make_scene(150)
        adj_a, adj_b, info = register_foreground_at_seam(
            a, b, fa, fb, seam_pos=200, axis=0
        )
        # A region far from any foreground (top-left corner) must be identical.
        assert np.array_equal(adj_a[0:80, 0:80], a[0:80, 0:80])
        assert np.array_equal(adj_b[0:80, 0:80], b[0:80, 0:80])

    def test_no_foreground_returns_unchanged(self):
        """Seam with no foreground crossing → inputs returned, warped=False."""
        h, w = 400, 300
        rng = np.random.default_rng(1)
        a = rng.integers(40, 80, size=(h, w, 3)).astype(np.uint8)
        b = rng.integers(40, 80, size=(h, w, 3)).astype(np.uint8)
        empty = np.zeros((h, w), dtype=bool)
        adj_a, adj_b, info = register_foreground_at_seam(
            a, b, empty, empty, seam_pos=200, axis=0
        )
        assert info["warped"] is False
        assert info["fg_pixels"] == 0
        assert np.array_equal(adj_a, a)
        assert np.array_equal(adj_b, b)

    def test_large_residual_falls_back(self):
        """
        A large but still trackable animation gap (wide limb shifted 100px,
        with overlap so flow can measure it) exceeds max_residual=40 → the
        function must refuse to warp and signal fallback (warped=False).
        """
        a, fa = _make_scene(80, limb_w=150)
        b, fb = _make_scene(180, limb_w=150)  # overlap 180..230, shift 100px
        adj_a, adj_b, info = register_foreground_at_seam(
            a, b, fa, fb, seam_pos=200, axis=0, max_residual=40.0
        )
        assert info["warped"] is False, info
        assert np.array_equal(adj_a, a)
        assert np.array_equal(adj_b, b)


# ---------------------------------------------------------------------------
# Flow sanity
# ---------------------------------------------------------------------------

class TestDenseFlow:
    def test_flow_detects_horizontal_shift(self):
        a, _ = _make_scene(120)
        b, _ = _make_scene(150)
        flow = _dense_flow(a, b)
        # On the limb rows, mean horizontal flow should be ~ +30 (a→b shift).
        limb_rows = slice(120, 280)
        mean_dx = float(flow[limb_rows, 120:190, 0].mean())
        assert mean_dx > 8.0, f"expected positive dx, got {mean_dx}"
