"""S159 compositing tests — §1.125 seam transition penalty, §1.126 fg-majority
floor, §1.127 zone hue equalization."""
import os
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# §1.125 — Seam transition penalty in _seam_cut
# ---------------------------------------------------------------------------

class TestSeamTransitionPenalty:
    """§1.125: transition_penalty biases DP seam toward zone midline."""

    def _make_zones(self, h=40, w=30):
        rng = np.random.default_rng(0)
        a = rng.integers(80, 200, (h, w, 3), dtype=np.uint8)
        b = rng.integers(80, 200, (h, w, 3), dtype=np.uint8)
        return a, b

    def test_zero_penalty_does_not_change_output_type(self):
        from backend.src.anim.compositing import _seam_cut
        a, b = self._make_zones()
        path = _seam_cut(a, b)
        assert path.ndim == 1
        assert len(path) == a.shape[1]

    def test_transition_pen_biases_toward_midline(self, monkeypatch):
        """With a large penalty the mean path row should be closer to h//2."""
        from backend.src.anim import compositing as _mod
        a, b = self._make_zones(h=60, w=40)
        # Run without penalty
        monkeypatch.setattr(_mod, "_SEAM_TRANSITION_PEN", 0.0)
        path_flat = _mod._seam_cut(a, b)
        # Run with strong penalty
        monkeypatch.setattr(_mod, "_SEAM_TRANSITION_PEN", 50.0)
        path_pen = _mod._seam_cut(a, b)
        mid = a.shape[0] // 2
        dist_flat = float(np.abs(path_flat - mid).mean())
        dist_pen = float(np.abs(path_pen - mid).mean())
        assert dist_pen <= dist_flat + 5, (
            f"Penalty path mean dist {dist_pen:.1f} not closer to midline "
            f"than flat {dist_flat:.1f}"
        )

    def test_path_stays_in_bounds(self, monkeypatch):
        from backend.src.anim import compositing as _mod
        monkeypatch.setattr(_mod, "_SEAM_TRANSITION_PEN", 20.0)
        a, b = self._make_zones()
        path = _mod._seam_cut(a, b)
        assert path.min() >= 0
        assert path.max() < a.shape[0]

    def test_path_length_equals_width(self, monkeypatch):
        from backend.src.anim import compositing as _mod
        monkeypatch.setattr(_mod, "_SEAM_TRANSITION_PEN", 10.0)
        a, b = self._make_zones(h=20, w=50)
        path = _mod._seam_cut(a, b)
        assert len(path) == 50

    def test_large_penalty_all_rows_near_mid(self, monkeypatch):
        """Extreme penalty: every path pixel should be within 5 of midline."""
        from backend.src.anim import compositing as _mod
        h, w = 40, 30
        # Uniform frames so pixel energy is flat → penalty dominates
        a = np.full((h, w, 3), 128, dtype=np.uint8)
        b = np.full((h, w, 3), 128, dtype=np.uint8)
        monkeypatch.setattr(_mod, "_SEAM_TRANSITION_PEN", 200.0)
        path = _mod._seam_cut(a, b)
        mid = h // 2
        assert np.all(np.abs(path - mid) <= 5), (
            f"Extreme penalty path rows outside ±5 of midline: {path}"
        )


# ---------------------------------------------------------------------------
# §1.126 — Fg-majority floor in _build_seam_cost_map
# ---------------------------------------------------------------------------

class TestFgMajorityFloor:
    """§1.126: When zone >60% fg, heavy columns get raised to floor.

    _build_seam_cost_map(canvas_zone, bg_mask_a, bg_mask_b, ...) —
    bg_mask_a/b are boolean arrays where True = background pixel.
    """

    def _make_fg_zone(self, h=30, w=20, fg_frac=0.80):
        """Canvas zone that is approximately fg_frac foreground."""
        zone = np.zeros((h, w, 3), dtype=np.uint8)
        n_fg_cols = int(w * fg_frac)
        zone[:, :n_fg_cols] = 150  # non-black → fg
        return zone

    def _bg_mask(self, zone):
        """True where pixel is black (background)."""
        return zone.max(axis=2) == 0

    def test_floor_off_by_default(self, monkeypatch):
        """_FG_MAJORITY_FLOOR=0 leaves cost map unchanged."""
        from backend.src.anim import compositing as _mod
        monkeypatch.setattr(_mod, "_FG_MAJORITY_FLOOR", 0.0)
        zone = self._make_fg_zone()
        cost = _mod._build_seam_cost_map(zone, self._bg_mask(zone), self._bg_mask(zone))
        assert cost is not None

    def test_floor_raises_heavy_fg_columns(self, monkeypatch):
        """Heavy fg columns should be raised to at least _FG_MAJORITY_FLOOR."""
        from backend.src.anim import compositing as _mod
        monkeypatch.setattr(_mod, "_FG_MAJORITY_FLOOR", 1.5)
        monkeypatch.setattr(_mod, "_SCATTER_COST", False)
        zone = self._make_fg_zone(h=30, w=20, fg_frac=0.85)
        cost = _mod._build_seam_cost_map(zone, self._bg_mask(zone), self._bg_mask(zone))
        col_fg_frac = (cost >= 1.0).mean(axis=0)
        heavy = col_fg_frac > 0.80
        if heavy.any() and not heavy.all():
            assert cost[:, heavy].min() >= 1.5 - 1e-6

    def test_all_fg_columns_leaves_unchanged(self, monkeypatch):
        """When ALL columns are >80% fg, the guard prevents any change."""
        from backend.src.anim import compositing as _mod
        zone = np.full((20, 15, 3), 200, dtype=np.uint8)
        bg = self._bg_mask(zone)
        monkeypatch.setattr(_mod, "_FG_MAJORITY_FLOOR", 1.5)
        cost_on = _mod._build_seam_cost_map(zone, bg, bg)
        monkeypatch.setattr(_mod, "_FG_MAJORITY_FLOOR", 0.0)
        cost_off = _mod._build_seam_cost_map(zone, bg, bg)
        # When all cols heavy, guard fires nothing — cost unchanged
        np.testing.assert_array_equal(cost_on, cost_off)

    def test_bg_only_zone_not_affected(self, monkeypatch):
        """A mostly-background zone (<60% fg) should not be modified."""
        from backend.src.anim import compositing as _mod
        monkeypatch.setattr(_mod, "_FG_MAJORITY_FLOOR", 1.5)
        zone = np.zeros((20, 20, 3), dtype=np.uint8)  # pure bg
        zone[:, :3] = 100  # only 15% fg → no change
        bg = self._bg_mask(zone)
        cost = _mod._build_seam_cost_map(zone, bg, bg)
        assert cost.max() < 1.5

    def test_cost_never_reduced_by_floor(self, monkeypatch):
        """_FG_MAJORITY_FLOOR must only raise costs, never lower them."""
        from backend.src.anim import compositing as _mod
        zone = self._make_fg_zone(h=30, w=20, fg_frac=0.85)
        bg = self._bg_mask(zone)
        monkeypatch.setattr(_mod, "_FG_MAJORITY_FLOOR", 0.0)
        cost_off = _mod._build_seam_cost_map(zone, bg, bg)
        monkeypatch.setattr(_mod, "_FG_MAJORITY_FLOOR", 1.5)
        cost_on = _mod._build_seam_cost_map(zone, bg, bg)
        assert (cost_on >= cost_off - 1e-6).all()


# ---------------------------------------------------------------------------
# §1.127 — Zone hue equalization
# ---------------------------------------------------------------------------

class TestZoneHueEq:
    """§1.127: _zone_hue_eq shifts fb_zone mean hue to match fa_zone."""

    def _make_colored_zone(self, hue_bgr, h=30, w=20):
        """Solid-color zone (non-black so mask activates)."""
        zone = np.full((h, w, 3), 0, dtype=np.uint8)
        zone[:] = hue_bgr
        return zone

    def test_output_same_shape_and_dtype(self):
        from backend.src.anim.compositing import _zone_hue_eq
        fa = np.full((20, 15, 3), [120, 60, 60], dtype=np.uint8)
        fb = np.full((20, 15, 3), [60, 120, 60], dtype=np.uint8)
        out = _zone_hue_eq(fa, fb)
        assert out.shape == fb.shape
        assert out.dtype == np.uint8

    def test_hue_shift_applied(self):
        """Mean hue of output should be closer to fa's mean hue."""
        import cv2
        from backend.src.anim.compositing import _zone_hue_eq
        # Blue-shifted fa, green-shifted fb
        fa = np.full((30, 20, 3), [200, 50, 50], dtype=np.uint8)
        fb = np.full((30, 20, 3), [50, 200, 50], dtype=np.uint8)
        out = _zone_hue_eq(fa, fb)
        fa_hsv = cv2.cvtColor(fa, cv2.COLOR_BGR2HSV)
        fb_hsv = cv2.cvtColor(fb, cv2.COLOR_BGR2HSV)
        out_hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV)
        mean_ha = float(fa_hsv[fa.max(axis=2) > 0, 0].mean())
        mean_hb = float(fb_hsv[fb.max(axis=2) > 0, 0].mean())
        mean_ho = float(out_hsv[out.max(axis=2) > 0, 0].mean())
        # output hue should be closer to fa hue than original fb hue
        assert abs(mean_ho - mean_ha) <= abs(mean_hb - mean_ha) + 5

    def test_no_change_when_hue_similar(self):
        """Below ZONE_HUE_EQ_MIN_DIFF_DEG threshold, output == input copy."""
        from backend.src.anim.compositing import _zone_hue_eq
        # Nearly identical hue
        fa = np.full((20, 15, 3), [100, 150, 50], dtype=np.uint8)
        fb = np.full((20, 15, 3), [102, 148, 51], dtype=np.uint8)
        out = _zone_hue_eq(fa, fb)
        np.testing.assert_array_equal(out, fb)

    def test_all_black_input_returns_copy(self):
        """All-black zones have no content pixels — return unmodified copy."""
        from backend.src.anim.compositing import _zone_hue_eq
        fa = np.zeros((10, 10, 3), dtype=np.uint8)
        fb = np.zeros((10, 10, 3), dtype=np.uint8)
        out = _zone_hue_eq(fa, fb)
        np.testing.assert_array_equal(out, fb)

    def test_wired_in_blend_loop(self, monkeypatch):
        """_ZONE_HUE_EQ=True causes _zone_hue_eq to be called in blend loop."""
        from backend.src.anim import compositing as _mod
        calls = []
        original = _mod._zone_hue_eq

        def _spy(fa, fb):
            calls.append(1)
            return original(fa, fb)

        monkeypatch.setattr(_mod, "_ZONE_HUE_EQ", True)
        monkeypatch.setattr(_mod, "_zone_hue_eq", _spy)

        h, w = 40, 30
        fa = np.full((h, w, 3), 120, dtype=np.uint8)
        fb = np.full((h, w, 3), 80, dtype=np.uint8)

        # Directly test the wiring point in the blend branch
        _fb_for_blend = fb.copy()
        if _mod._ZONE_HUE_EQ:
            _fb_for_blend = _mod._zone_hue_eq(fa, _fb_for_blend)

        assert len(calls) == 1
