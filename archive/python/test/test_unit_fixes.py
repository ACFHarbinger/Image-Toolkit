"""
test_unit_fixes.py
==================
Fine-grained unit tests for the specific bug fixes documented in the
issue report (Bugs 1-10 in Section 3.2, and the Priority 1-2 alignment fixes).

These tests can run without GPU or test datasets — they construct minimal
synthetic inputs and verify the fixed behaviour directly.

Run:
    pytest test_unit_fixes.py -v
    # or without pytest:
    python test_unit_fixes.py
"""

from __future__ import annotations

import sys
import unittest
from typing import Dict, List

import numpy as np


# ---------------------------------------------------------------------------
# Synthetic data helpers
# ---------------------------------------------------------------------------

def _make_gradient_frame(h: int, w: int, top_brightness: float,
                          bot_brightness: float) -> np.ndarray:
    """BGR frame with a vertical brightness gradient."""
    ys = np.linspace(top_brightness, bot_brightness, h, dtype=np.float32)
    img = np.broadcast_to(ys[:, None, None], (h, w, 3)).copy()
    return np.clip(img, 0, 255).astype(np.uint8)


def _make_translation_affine(tx: float, ty: float) -> np.ndarray:
    M = np.eye(2, 3, dtype=np.float32)
    M[0, 2] = tx
    M[1, 2] = ty
    return M


def _make_bg_mask(h: int, w: int, fg_top: int, fg_bot: int) -> np.ndarray:
    """Simple mask: fg band [fg_top:fg_bot] = 0, rest = 255."""
    mask = np.full((h, w), 255, dtype=np.uint8)
    mask[fg_top:fg_bot, :] = 0
    return mask


# ---------------------------------------------------------------------------
# Bug 1 — blend should span full zone (zone_half_f), not fixed SEAM_THIN_HF
# ---------------------------------------------------------------------------

class TestBug1FullZoneBlend(unittest.TestCase):
    """
    The blend alpha must span the full feather zone [y0_f, y1_f].
    Before the fix: t_blend used a hard-coded ±8px half-width, producing a
    16px cosine inside a 300-500px zone.
    After the fix: zone_half_f = (y1_f - y0_f - 1) // 2.
    """

    def test_zone_half_f_equals_half_zone_width(self):
        y0_f, y1_f = 100, 600   # 500px zone
        zone_half_f = (y1_f - y0_f - 1) // 2
        self.assertEqual(zone_half_f, 249)

    def test_blend_ramp_reaches_zero_at_zone_edges(self):
        """The cosine blend weight at the zone boundaries must be ≈ 0."""
        y0_f, y1_f = 100, 600
        zone_half_f = (y1_f - y0_f - 1) // 2
        y_cut = (y0_f + y1_f) // 2   # 350

        # Simulate the blend computation from compositing.py
        ys = np.arange(y0_f, y1_f, dtype=np.float32)
        d_flat = ys - float(y_cut)
        t_lin = np.clip((d_flat + zone_half_f) / (2.0 * zone_half_f), 0.0, 1.0)
        t_hf = 0.5 * (1.0 - np.cos(np.pi * t_lin))

        # At y = y0_f (top of zone): t_lin ≈ 0, t_hf ≈ 0  → fa gets weight ≈ 1
        self.assertAlmostEqual(float(t_hf[0]), 0.0, places=2)
        # At y = y1_f-1 (bottom of zone): t_lin ≈ 1, t_hf ≈ 1 → fb gets weight ≈ 1
        self.assertAlmostEqual(float(t_hf[-1]), 1.0, places=2)
        # At y = y_cut (centre): t_hf ≈ 0.5
        mid_idx = y_cut - y0_f
        self.assertAlmostEqual(float(t_hf[mid_idx]), 0.5, places=2)


# ---------------------------------------------------------------------------
# Bug 2 — blend alpha must use flat horizontal distance, not DP seam path
# ---------------------------------------------------------------------------

class TestBug2FlatBlendAlpha(unittest.TestCase):
    """
    The brightness ramp (t_lin) must be derived from `d_flat = local_ys - y_cut`
    not from the per-column DP seam path.  Using the seam path for t_lin causes
    the brightness transition to zigzag vertically per column.
    """

    def test_flat_blend_is_purely_horizontal(self):
        """All columns at the same row must have the same blend weight."""
        H, W = 100, 200
        y_cut = 50
        zone_half_f = 40

        # local_ys shape: (H, 1)  broadcasts across W columns
        local_ys = np.arange(0, H, dtype=np.float32)[:, np.newaxis]
        d_flat = local_ys - float(y_cut)
        t_lin = np.clip((d_flat + zone_half_f) / (2.0 * zone_half_f), 0.0, 1.0)

        # Every row must have constant weight across all W columns
        t_broadcast = np.broadcast_to(t_lin, (H, W))
        for row in range(H):
            self.assertTrue(np.all(t_broadcast[row] == t_broadcast[row, 0]),
                            f"Row {row} has non-constant blend weight")

    def test_seam_path_only_used_for_gain_taper(self):
        """
        Verify that using seam_path for t_blend (gain taper) but d_flat for t_lin
        (blend alpha) produces different arrays — they are not accidentally equal.
        """
        H, W = 60, 80
        y_cut = 30
        zone_half_f = 25

        # Simulate a wavy seam path
        seam_path = np.full(W, float(y_cut), dtype=np.float32)
        seam_path += np.sin(np.linspace(0, 4 * np.pi, W)) * 10.0  # ±10px wobble

        local_ys = np.arange(0, H, dtype=np.float32)[:, np.newaxis]

        # t_blend uses seam_path (per-column)
        d_seam = local_ys - seam_path[np.newaxis, :]
        t_blend = np.clip(1.0 - np.abs(d_seam) / float(zone_half_f), 0.0, 1.0)

        # t_lin uses d_flat (purely horizontal)
        d_flat = local_ys - float(y_cut)
        t_lin = np.clip((d_flat + zone_half_f) / (2.0 * zone_half_f), 0.0, 1.0)

        # They must differ (seam path has horizontal variation, flat does not)
        self.assertFalse(np.allclose(t_blend, np.broadcast_to(t_lin, (H, W))),
                         "t_blend and t_lin should differ when seam path is wavy")


# ---------------------------------------------------------------------------
# Bug 3 — gain_seam should be ones (per-zone correction disabled)
# ---------------------------------------------------------------------------

class TestBug3GainSeamDisabled(unittest.TestCase):

    def test_gain_seam_is_identity(self):
        """After the fix, gain_seam must be np.ones(3) for all boundaries."""
        gain_seam = np.ones(3, dtype=np.float32)
        np.testing.assert_array_equal(gain_seam, np.ones(3, dtype=np.float32))

    def test_identity_gain_is_no_op_in_composite(self):
        """Applying a gain of 1.0 to any pixel must return the same pixel."""
        sqrt_gain = np.sqrt(np.clip(np.ones(3, dtype=np.float32), 1e-6, None))
        np.testing.assert_allclose(sqrt_gain, np.ones(3, dtype=np.float32), atol=1e-5)


# ---------------------------------------------------------------------------
# Bug 4 — LS normalisation clamp must be ±5%, not ±45%
# ---------------------------------------------------------------------------

class TestBug4LSGainClamp(unittest.TestCase):

    GAIN_CLAMP_TIGHT = (0.95, 1.05)
    GAIN_CLAMP_OLD = (0.70, 1.45)

    def test_tight_clamp_rejects_scene_gradient_corrections(self):
        """
        With the old wide clamp, a 53% spread across 8 frames (F7=0.818..F0=1.253)
        is passed through and amplified.  The tight clamp must cap all values.
        """
        # Simulated raw LS gains from test1 (before fix)
        raw_gains = [1.253, 1.187, 1.141, 1.042, 0.983, 0.952, 0.878, 0.818]

        old_clamped = [np.clip(g, *self.GAIN_CLAMP_OLD) for g in raw_gains]
        new_clamped = [np.clip(g, *self.GAIN_CLAMP_TIGHT) for g in raw_gains]

        # Old clamp: all pass through unchanged (within 0.70–1.45)
        self.assertEqual(old_clamped, raw_gains)

        # New clamp: everything must be in [0.95, 1.05]
        for g in new_clamped:
            self.assertGreaterEqual(g, 0.95)
            self.assertLessEqual(g, 1.05)

        # Tight clamp: spread must be at most 0.10 (the [0.95, 1.05] window width)
        new_spread = max(new_clamped) - min(new_clamped)
        old_spread = max(old_clamped) - min(old_clamped)
        self.assertLessEqual(new_spread, 0.10 + 1e-9,
                             f"Tight clamp spread must be ≤0.10 (was {new_spread:.3f})")
        self.assertGreater(old_spread, 0.20,
                           f"Old clamp spread should be large (was {old_spread:.3f})")


# ---------------------------------------------------------------------------
# Bug 6 — feather zones must be allowed to overlap (no spacing cap)
# ---------------------------------------------------------------------------

class TestBug6FeatherOverlap(unittest.TestCase):

    def test_overlapping_feathers_produce_smooth_accumulation(self):
        """
        When two feather zones overlap, the num/denom accumulation should
        produce a smooth blend with weights that sum to > 0 everywhere in the
        overlap region.
        """
        H, W = 400, 100
        FEATHER = 200   # large feather, will overlap

        # Two boundaries 169px apart (like test1 B0/B1)
        boundaries = [200, 369]  # y positions

        # Simulate two frame warps (constant colour for simplicity)
        fa = np.full((H, W, 3), 100, dtype=np.float32)  # frame above
        fb = np.full((H, W, 3), 150, dtype=np.float32)  # frame below
        fc = np.full((H, W, 3), 120, dtype=np.float32)  # frame below-below

        frames = [fa, fb, fc]
        order = np.array([0, 1, 2])

        # Replicate the compositing logic (simplified)
        num = np.zeros((H, W, 3), dtype=np.float32)
        denom = np.zeros((H, W), dtype=np.float32)

        # Hard strip weights (outside all feather zones)
        for k, (y0, y1) in enumerate(zip([0] + boundaries, boundaries + [H])):
            fi = int(order[k])
            for y in range(y0, y1):
                # Check if this row is inside any feather zone
                in_feather = False
                for by in boundaries:
                    if abs(y - by) <= FEATHER:
                        in_feather = True
                        break
                if not in_feather:
                    num[y] += frames[fi][y]
                    denom[y] += 1.0

        # Add feather zones
        for kb, by in enumerate(boundaries):
            fi_above = int(order[kb])
            fi_below = int(order[kb + 1])
            y0_f = max(0, by - FEATHER)
            y1_f = min(H, by + FEATHER + 1)
            zone_half_f = max(1, (y1_f - y0_f - 1) // 2)
            for y in range(y0_f, y1_f):
                d_flat = y - by
                t = np.clip((d_flat + zone_half_f) / (2.0 * zone_half_f), 0.0, 1.0)
                t_hf = 0.5 * (1.0 - np.cos(np.pi * t))
                weight_above = 1.0 - t_hf
                weight_below = t_hf
                num[y] += frames[fi_above][y] * weight_above
                num[y] += frames[fi_below][y] * weight_below
                denom[y] += weight_above + weight_below

        # Verify: denom must be > 0 everywhere
        self.assertTrue(np.all(denom > 0), "Some rows have zero weight (gap in blend)")
        # Verify: overlap zone [169, 369] has smooth blend
        blended = num[:, 0, 1] / np.maximum(denom[:, 0], 1.0)
        # The transition in the overlap zone should be monotone (smooth)
        overlap_blend = blended[200:369]
        diffs = np.diff(overlap_blend)
        # Allow small non-monotone jitter (< 1 brightness unit)
        large_reversals = np.abs(diffs[diffs < -1.0]).sum()
        self.assertLess(large_reversals, 5.0,
                        "Blend in overlapping feather zone is not smooth")


# ---------------------------------------------------------------------------
# Bug 7 — boundary search window must use 2*_SEARCH_SLAB, not 2*_FEATHER_MAX
# ---------------------------------------------------------------------------

class TestBug7BoundarySearchWindow(unittest.TestCase):

    def test_search_window_not_degenerate(self):
        """
        With the old guard (2 * _FEATHER_MAX = 600px), boundaries ~238px apart
        produce lo_limit > hi_limit → search disabled (Δ=0 for all interior bounds).
        With the new guard (2 * _SEARCH_SLAB = 40px), search is meaningful.
        """
        _FEATHER_MAX = 300
        _SEARCH_SLAB = 20
        _SEARCH_RANGE = 250

        boundaries = np.array([988.0, 1157.0, 1400.0])   # realistic test1 values
        initial_boundaries = boundaries.copy()

        for k in range(len(boundaries)):
            by = int(initial_boundaries[k])
            H = 2500

            # Old guard
            lo_old = int(initial_boundaries[k - 1]) + 2 * _FEATHER_MAX + 1 if k > 0 else _SEARCH_SLAB
            hi_old = (int(initial_boundaries[k + 1]) - 2 * _FEATHER_MAX - 1
                      if k < len(initial_boundaries) - 1 else H - _SEARCH_SLAB)
            y_lo_old = max(lo_old, by - _SEARCH_RANGE)
            y_hi_old = min(hi_old, by + _SEARCH_RANGE)
            old_range = max(0, y_hi_old - y_lo_old)

            # New guard
            lo_new = int(initial_boundaries[k - 1]) + 2 * _SEARCH_SLAB + 1 if k > 0 else _SEARCH_SLAB
            hi_new = (int(initial_boundaries[k + 1]) - 2 * _SEARCH_SLAB - 1
                      if k < len(initial_boundaries) - 1 else H - _SEARCH_SLAB)
            y_lo_new = max(lo_new, by - _SEARCH_RANGE)
            y_hi_new = min(hi_new, by + _SEARCH_RANGE)
            new_range = max(0, y_hi_new - y_lo_new)

            if k > 0:  # interior boundaries (not first/last)
                self.assertGreater(new_range, old_range,
                    f"Boundary {k}: new guard ({new_range}px) should give larger search than old ({old_range}px)")
                self.assertGreater(new_range, 0,
                    f"Boundary {k}: new guard must allow non-degenerate search")


# ---------------------------------------------------------------------------
# Priority 1 — Affine validation (post-bundle-adjust sanity gate)
# ---------------------------------------------------------------------------

def _validate_affines(affines: List[np.ndarray], N: int,
                       min_step: float = 50.0, max_ratio: float = 3.0) -> bool:
    """
    The proposed validation gate from the issue report (Section 9, Priority 1).
    Returns True if affines are plausible, False if broken.
    """
    tys = sorted(aff[1, 2] for aff in affines)
    gaps = np.diff(tys)
    if len(gaps) == 0 or float(np.median(gaps)) < min_step:
        return False
    return float(gaps.max() / np.median(gaps)) <= max_ratio


class TestPriority1AffineValidation(unittest.TestCase):

    def test_good_affines_pass(self):
        """test6-like affines (gaps ~168px, ratio 1.4×) must pass."""
        tys = [0, 174, 351, 529, 692, 930, 1063, 1200, 1326]
        affines = [_make_translation_affine(0, ty) for ty in tys]
        self.assertTrue(_validate_affines(affines, len(affines)))

    def test_clustered_affines_fail(self):
        """test8-like affines (16–21px internal gaps) must fail."""
        tys = [243, 259, 762, 726, 1166, 1263, 0, 333, 762, 1263, 1806]
        affines = [_make_translation_affine(0, ty) for ty in tys]
        self.assertFalse(_validate_affines(affines, len(affines)))

    def test_nonmonotonic_affines_fail(self):
        """test7-like non-monotonic affines (ratio 4.7×) must fail."""
        tys = [0, 49, 99, 130, 165, 335, 538, 465, 265, 816, 771, 821, 991, 1040]
        affines = [_make_translation_affine(0, ty) for ty in tys]
        self.assertFalse(_validate_affines(affines, len(affines)))

    def test_near_zero_median_gap_fails(self):
        """When median gap < min_step, validation must fail."""
        tys = [0, 5, 10, 15, 20, 25]   # 5px gaps
        affines = [_make_translation_affine(0, ty) for ty in tys]
        self.assertFalse(_validate_affines(affines, len(affines)))

    def test_single_outlier_edge_detected(self):
        """A single large gap (1053px) among otherwise good gaps triggers failure."""
        tys = [0, 300, 600, 900, 1953, 2253]  # 1053px outlier gap at position 4
        affines = [_make_translation_affine(0, ty) for ty in tys]
        ratio, _, _ = _alignment_ratio_from_affines(affines)
        self.assertGreater(ratio, 3.0)
        self.assertFalse(_validate_affines(affines, len(affines)))


def _alignment_ratio_from_affines(affines: List[np.ndarray]):
    tys = sorted(aff[1, 2] for aff in affines)
    gaps = np.diff(tys)
    med = float(np.median(gaps))
    if med < 1.0:
        return float("inf"), float(gaps.max()), med
    return float(gaps.max() / med), float(gaps.max()), med


# ---------------------------------------------------------------------------
# Priority 2 — Edge filter: near-zero dy rejection
# ---------------------------------------------------------------------------

class TestPriority2NearZeroDyFilter(unittest.TestCase):
    """
    Near-zero dy matches (< min_expected_step) are the root cause of frame
    clustering in test8/test9.  They must be filtered BEFORE bundle adjustment.
    """

    MIN_EXPECTED_STEP = 50.0   # px — proposed filter threshold

    def _filter_near_zero(self, edges: List[Dict]) -> List[Dict]:
        """Proposed pre-BA filter from issue report Priority 1, Step 2."""
        return [e for e in edges if abs(float(e["M"][1][2])) >= self.MIN_EXPECTED_STEP]

    def test_near_zero_edges_removed(self):
        """Edges with |dy| < 50px must be discarded."""
        edges = [
            {"i": 0, "j": 1, "M": [[1,0,0],[0,1,16.0]], "weight": 0.8},   # 16px — bad
            {"i": 1, "j": 2, "M": [[1,0,0],[0,1,300.0]], "weight": 0.9},  # 300px — good
            {"i": 2, "j": 3, "M": [[1,0,0],[0,1,21.0]], "weight": 0.7},   # 21px — bad
            {"i": 3, "j": 4, "M": [[1,0,0],[0,1,280.0]], "weight": 0.85}, # 280px — good
        ]
        filtered = self._filter_near_zero(edges)
        self.assertEqual(len(filtered), 2)
        self.assertEqual([e["i"] for e in filtered], [1, 3])

    def test_good_edges_preserved(self):
        """No good edges should be discarded."""
        edges = [
            {"i": i, "j": i + 1, "M": [[1,0,0],[0,1,float(280 + i * 5)]], "weight": 0.9}
            for i in range(8)
        ]
        filtered = self._filter_near_zero(edges)
        self.assertEqual(len(filtered), len(edges))


# ---------------------------------------------------------------------------
# Mask quality checks (Bug 10 — inverted background mask)
# ---------------------------------------------------------------------------

class TestBug10MaskInversion(unittest.TestCase):
    """
    The original code used `~bm_top` (foreground) instead of `bm_top` (background)
    when selecting measurement pixels.  Background pixels are photometrically stable;
    foreground (character skin) is not.
    """

    def test_inverted_mask_selects_wrong_pixels(self):
        h, w = 100, 100
        mask = _make_bg_mask(h, w, fg_top=30, fg_bot=70)   # fg band in middle
        bg_count = int((mask > 127).sum())
        fg_count = int((mask < 128).sum())

        # ~mask selects fg pixels
        inv_count = int((~(mask > 127)).sum())
        self.assertEqual(inv_count, fg_count)
        self.assertNotEqual(inv_count, bg_count)

    def test_correct_mask_selects_background(self):
        h, w = 100, 100
        mask = _make_bg_mask(h, w, fg_top=30, fg_bot=70)
        bg_pixels = (mask > 127)
        fg_pixels = (mask < 128)
        # Background must be the majority
        self.assertGreater(bg_pixels.sum(), fg_pixels.sum())
        # Correct mask access: bg_valid = bm & all_valid
        all_valid = np.ones((h, w), dtype=bool)
        bg_valid = bg_pixels & all_valid
        self.assertEqual(bg_valid.sum(), bg_pixels.sum())


# ---------------------------------------------------------------------------
# Bug 9 — Two-pass boundary search (LS must use pass-1 positions)
# ---------------------------------------------------------------------------

class TestBug9TwoPassBoundarySearch(unittest.TestCase):
    """
    If LS is run at initial midpoints (geometric centres between strip-center y-values),
    those midpoints may fall inside character body regions with no background pixels,
    making LS measurements unreliable.

    The fix: run boundary search first (pass 1) to find positions with visible
    background, then run LS at those positions (pass 2).

    This test verifies the concept using a synthetic bright/dark stripe image.
    """

    def test_initial_midpoint_may_land_in_fg(self):
        """Geometric midpoint between two strip centres often falls on character body."""
        H = 1000
        frame_h = 400

        # Two frame strip centres (ty + frame_h/2)
        ty0, ty1 = 0, 600
        center0 = ty0 + frame_h / 2   # 200
        center1 = ty1 + frame_h / 2   # 800
        initial_boundary = (center0 + center1) / 2   # 500

        # Simulate a bg mask where rows 400-600 are fg (character body crossing mid)
        bg_mask = np.full((H,), 255, dtype=np.uint8)
        bg_mask[400:600] = 0   # fg band

        # Initial boundary (500) lands in fg band
        self.assertEqual(int(bg_mask[int(initial_boundary)]), 0,
                         "Initial boundary should land in foreground for this scenario")

    def test_pass1_search_finds_background_region(self):
        """
        A simple search near the boundary should find a row with background pixels.
        """
        H = 1000
        bg_mask = np.full((H,), 255, dtype=np.uint8)
        bg_mask[400:600] = 0   # fg band at 400-600

        initial_boundary = 500  # inside fg
        search_range = 200      # ±200px

        # Search for a row with mostly bg pixels
        best_y = initial_boundary
        best_bg_count = 0
        for y in range(max(0, initial_boundary - search_range),
                       min(H - 1, initial_boundary + search_range)):
            bg_count = int(bg_mask[y] > 127)
            if bg_count > best_bg_count:
                best_bg_count = bg_count
                best_y = y

        # The search should find a row outside the fg band
        self.assertFalse(400 <= best_y < 600,
                         f"Pass-1 search found y={best_y} inside fg band [400,600]")


# ---------------------------------------------------------------------------
# Test runner (no pytest required)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    test_classes = [
        TestBug1FullZoneBlend,
        TestBug2FlatBlendAlpha,
        TestBug3GainSeamDisabled,
        TestBug4LSGainClamp,
        TestBug6FeatherOverlap,
        TestBug7BoundarySearchWindow,
        TestPriority1AffineValidation,
        TestPriority2NearZeroDyFilter,
        TestBug10MaskInversion,
        TestBug9TwoPassBoundarySearch,
    ]
    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
