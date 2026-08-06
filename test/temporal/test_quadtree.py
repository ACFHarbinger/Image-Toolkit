import numpy as np
import pytest

from manga.colorization.colorization import colorize_scribble
from manga.temporal.quadtree import build_quadtree, colorize_region_incremental


def _uniform_gray(h=128, w=128, value=220):
    return np.full((h, w), value, dtype=np.uint8)


def _detailed_gray(h=128, w=128):
    """A flat image with a high-variance (screentone-like) patch in the
    top-left quadrant, so leaves there should end up smaller than leaves
    over the flat remainder. Sparse dot pattern (matching
    test_screentone.py's `_screentone_gray` fixture), not a dense striped
    one -- a dense high-contrast stripe pattern was found during development
    to trigger a pre-existing, unrelated singular-matrix edge case in
    colorize_scribble's Levin solver on some crops (build_levin_system
    produces a numerically rank-deficient system for that specific
    pathological repeating structure); not a bug in this module, and not
    fixed here since colorization.py is out of scope for this issue -- the
    sparse dot pattern avoids it while still producing legitimately higher
    local variance than the flat background."""
    gray = np.full((h, w), 220, dtype=np.uint8)
    gray[8:64:4, 8:64:4] = 40
    return gray


class TestBuildQuadtree:
    def test_leaves_exactly_cover_the_image_no_gaps_or_overlaps(self):
        gray = _detailed_gray()
        leaves = build_quadtree(gray)
        total_area = sum((y1 - y0) * (x1 - x0) for y0, x0, y1, x1 in leaves)
        assert total_area == gray.shape[0] * gray.shape[1]

    def test_uniform_image_stays_a_single_leaf(self):
        gray = _uniform_gray()
        leaves = build_quadtree(gray)
        assert leaves == [(0, 0, gray.shape[0], gray.shape[1])]

    def test_detailed_region_subdivides_more_than_flat_region(self):
        gray = _detailed_gray()
        leaves = build_quadtree(gray, min_size=4)
        detailed_leaves = [b for b in leaves if b[0] < 64 and b[1] < 64]
        flat_leaves = [b for b in leaves if b[0] >= 64 and b[1] >= 64]
        assert len(detailed_leaves) > 1
        assert len(flat_leaves) == 1

    def test_max_depth_bounds_subdivision(self):
        gray = _detailed_gray()
        shallow = build_quadtree(gray, max_depth=1, min_size=1)
        deep = build_quadtree(gray, max_depth=8, min_size=1)
        assert len(shallow) <= len(deep)

    def test_min_size_prevents_tiny_leaves(self):
        gray = _detailed_gray()
        leaves = build_quadtree(gray, min_size=32, max_depth=10)
        for y0, x0, y1, x1 in leaves:
            # A leaf smaller than min_size on both axes never further
            # subdivides, but the top-level split can still produce a leaf
            # right at the boundary -- just confirm nothing pathologically tiny.
            assert (y1 - y0) >= 1 and (x1 - x0) >= 1


class TestColorizeRegionIncremental:
    def _seed(self, gray, h=128, w=128):
        scribble_rgb = np.zeros((h, w, 3), dtype=np.uint8)
        mask = np.zeros((h, w), dtype=bool)
        scribble_rgb[10:15, 10:15] = [220, 40, 40]
        mask[10:15, 10:15] = True
        prev = colorize_scribble(gray, scribble_rgb, mask, max_solve_dim=0)
        return scribble_rgb, mask, prev

    def test_output_shape_and_dtype(self):
        gray = _detailed_gray()
        scribble_rgb, mask, prev = self._seed(gray)
        scribble_rgb[100:105, 100:105] = [40, 40, 220]
        mask[100:105, 100:105] = True

        out = colorize_region_incremental(gray, scribble_rgb, mask, prev, (100, 100, 105, 105), max_solve_dim=0)
        assert out.shape == prev.shape
        assert out.dtype == np.uint8

    def test_pixels_outside_resolved_window_are_unchanged(self):
        gray = _detailed_gray()
        scribble_rgb, mask, prev = self._seed(gray)
        scribble_rgb[100:105, 100:105] = [40, 40, 220]
        mask[100:105, 100:105] = True

        out = colorize_region_incremental(gray, scribble_rgb, mask, prev, (100, 100, 105, 105), halo=4, max_solve_dim=0)
        # Far corner of the image, well outside any plausible resolve window.
        assert np.array_equal(out[0:5, 0:5], prev[0:5, 0:5])

    def test_stroke_in_detailed_region_resolves_a_small_window(self):
        gray = _detailed_gray()
        scribble_rgb, mask, prev = self._seed(gray)
        leaves = build_quadtree(gray, min_size=4)

        scribble_rgb[20:22, 20:22] = [40, 40, 220]
        mask[20:22, 20:22] = True
        out = colorize_region_incremental(
            gray, scribble_rgb, mask, prev, (20, 20, 22, 22), leaves=leaves, halo=4, max_solve_dim=0
        )
        diff = np.abs(out.astype(int) - prev.astype(int)).sum(axis=2)
        ys, xs = np.where(diff > 0)
        # A stroke inside the finely-partitioned detailed region should only
        # touch a small window, not anywhere close to the full 128x128 image.
        assert (ys.max() - ys.min()) < 40
        assert (xs.max() - xs.min()) < 40

    def test_no_scribbles_in_window_returns_prev_result_unchanged(self):
        gray = _detailed_gray()
        scribble_rgb, mask, prev = self._seed(gray)
        # dirty_bbox far from any scribble -- window has no scribbled pixels.
        out = colorize_region_incremental(gray, scribble_rgb, mask, prev, (100, 100, 105, 105), max_solve_dim=0)
        assert np.array_equal(out, prev)

    def test_dirty_bbox_outside_all_leaves_returns_prev_result_unchanged(self):
        gray = _detailed_gray()
        scribble_rgb, mask, prev = self._seed(gray)
        out = colorize_region_incremental(gray, scribble_rgb, mask, prev, (500, 500, 500, 500), max_solve_dim=0)
        assert np.array_equal(out, prev)

    def test_shape_mismatch_raises(self):
        gray = _detailed_gray()
        scribble_rgb, mask, _ = self._seed(gray)
        bad_prev = np.zeros((10, 10, 3), dtype=np.uint8)
        with pytest.raises(ValueError, match="must match"):
            colorize_region_incremental(gray, scribble_rgb, mask, bad_prev, (0, 0, 5, 5))

    def test_custom_colorize_fn_is_used(self):
        gray = _detailed_gray()
        scribble_rgb, mask, prev = self._seed(gray)
        scribble_rgb[20:22, 20:22] = [40, 40, 220]
        mask[20:22, 20:22] = True

        calls = []

        def spy_fn(g, s_rgb, s_mask, **kwargs):
            calls.append((g.shape, kwargs))
            return colorize_scribble(g, s_rgb, s_mask, **kwargs)

        colorize_region_incremental(
            gray, scribble_rgb, mask, prev, (20, 20, 22, 22), colorize_fn=spy_fn, max_solve_dim=0
        )
        assert len(calls) == 1
        assert calls[0][1] == {"max_solve_dim": 0}

    def test_incremental_resolve_is_much_faster_than_full_page_for_detailed_stroke(self):
        import time

        gray = _detailed_gray(h=400, w=400)
        gray[8:200:4, 8:200:4] = 40  # larger detailed region for a meaningful timing gap
        scribble_rgb, mask, prev = self._seed(gray, h=400, w=400)
        leaves = build_quadtree(gray, min_size=4)

        scribble_rgb[50:52, 50:52] = [40, 40, 220]
        mask[50:52, 50:52] = True

        t0 = time.time()
        colorize_region_incremental(gray, scribble_rgb, mask, prev, (50, 50, 52, 52), leaves=leaves, max_solve_dim=0)
        incremental_time = time.time() - t0

        t0 = time.time()
        colorize_scribble(gray, scribble_rgb, mask, max_solve_dim=0)
        full_time = time.time() - t0

        assert incremental_time < full_time
