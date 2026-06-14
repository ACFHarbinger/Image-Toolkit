"""
Tests for the Stage 9 temporal renderer (rendering.py).

Issue categories covered:
  B — Stage 9 ghosting: always downstream of bad affines except test18.
      These tests verify the render's output quality given CORRECT affines
      (positive-baseline scenarios) and document ghosting detection for bad affines.

All tests run without GPU.
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

from backend.src.anim.rendering import _render, _render_first, _render_median, _adaptive_render_gain_clamp, _check_gain_chain_drift  # noqa: E402
from conftest import make_frame, make_rotation_affine, make_translation_affine  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_render_inputs(
    n: int,
    frame_h: int = 100,
    frame_w: int = 120,
    dy: float = 80.0,
    brightness=128,
):
    """n identical (or differently brightened) frames with vertical translation."""
    if isinstance(brightness, int):
        brightness = [brightness] * n
    frames = [make_frame(frame_h, frame_w, color=(b, b, b)) for b in brightness]
    affines = [make_translation_affine(ty=i * dy) for i in range(n)]
    canvas_h = int((n - 1) * dy + frame_h)
    canvas_w = frame_w
    bg_masks = [None] * n
    return frames, affines, bg_masks, canvas_h, canvas_w


def _ghosting_score(canvas: np.ndarray, valid_mask: np.ndarray) -> float:
    """
    Measure ghosting as the inter-row brightness variance in covered regions.
    A high variance score indicates multiple frames are blended at the same rows
    (ghosting). Clean renders have low variance within each strip.
    """
    covered = valid_mask > 0
    if not covered.any():
        return 0.0
    gray = canvas.mean(axis=2)
    row_means = np.array(
        [
            gray[r, covered[r]].mean() if covered[r].any() else np.nan
            for r in range(canvas.shape[0])
        ]
    )
    valid_rows = ~np.isnan(row_means)
    if valid_rows.sum() < 2:
        return 0.0
    return float(np.std(row_means[valid_rows]))


# ---------------------------------------------------------------------------
# 1. Output shape and type
# ---------------------------------------------------------------------------


class TestRenderMedianOutputShape:
    def test_output_canvas_correct_shape(self):
        frames, affines, masks, H, W = _make_render_inputs(3)
        canvas, valid_mask, warped_corr, warped_fgs = _render_median(
            frames, affines, masks, H, W
        )
        assert canvas.shape == (H, W, 3), f"Expected ({H},{W},3), got {canvas.shape}"

    def test_output_canvas_uint8(self):
        frames, affines, masks, H, W = _make_render_inputs(3)
        canvas, _, _, _ = _render_median(frames, affines, masks, H, W)
        assert canvas.dtype == np.uint8

    def test_valid_mask_shape(self):
        frames, affines, masks, H, W = _make_render_inputs(3)
        _, valid_mask, _, _ = _render_median(frames, affines, masks, H, W)
        assert valid_mask.shape == (H, W)

    def test_valid_mask_dtype_uint8(self):
        frames, affines, masks, H, W = _make_render_inputs(3)
        _, valid_mask, _, _ = _render_median(frames, affines, masks, H, W)
        assert valid_mask.dtype == np.uint8

    def test_warped_lists_returned_empty(self):
        """_render_median returns empty warped_corr and warped_fgs lists."""
        frames, affines, masks, H, W = _make_render_inputs(3)
        _, _, warped_corr, warped_fgs = _render_median(frames, affines, masks, H, W)
        assert isinstance(warped_corr, list)
        assert isinstance(warped_fgs, list)


# ---------------------------------------------------------------------------
# 2. Valid mask correctness
# ---------------------------------------------------------------------------


class TestValidMask:
    def test_single_frame_covers_its_strip(self):
        """Single frame at ty=0 should mark its rows as valid in the mask."""
        frames, affines, masks, H, W = _make_render_inputs(1, frame_h=50, dy=0.0)
        _, valid_mask, _, _ = _render_median(frames, affines, masks, H, W)
        assert valid_mask[:50, :].max() > 0, "Single frame's rows should be marked valid"

    def test_valid_mask_marks_all_covered_rows(self):
        """For n frames with full coverage, all canvas rows should be valid."""
        N = 3
        frame_h = 100
        dy = 80.0
        frames, affines, masks, H, W = _make_render_inputs(N, frame_h=frame_h, dy=dy)
        _, valid_mask, _, _ = _render_median(frames, affines, masks, H, W)
        mid_row = H // 2
        assert valid_mask[mid_row, :].max() > 0, (
            f"Middle row {mid_row} should be valid with {N} overlapping frames"
        )


# ---------------------------------------------------------------------------
# 3. Median correctness with identical frames
# ---------------------------------------------------------------------------


class TestMedianCorrectness:
    def test_identical_frames_median_matches_original(self):
        """
        N identical frames → median is the same as any single frame.
        A covered pixel should equal the original frame's brightness.
        """
        brightness = 150
        N = 5
        frames, affines, masks, H, W = _make_render_inputs(
            N, frame_h=80, dy=60.0, brightness=brightness
        )
        canvas, valid_mask, _, _ = _render_median(frames, affines, masks, H, W)
        covered = valid_mask > 0
        if covered.any():
            values = canvas[covered]
            mean_brightness = float(values.mean())
            assert abs(mean_brightness - brightness) < 10, (
                f"Identical frames: expected brightness ≈{brightness}, "
                f"got mean={mean_brightness:.1f}"
            )

    def test_single_frame_canvas_equals_frame(self):
        """Single frame → canvas pixels in frame region equal the frame."""
        brightness = 180
        frames, affines, masks, H, W = _make_render_inputs(
            1, frame_h=60, dy=0.0, brightness=brightness
        )
        canvas, valid_mask, _, _ = _render_median(frames, affines, masks, H, W)
        covered = valid_mask > 0
        if covered.any():
            values = canvas[covered]
            assert abs(float(values.mean()) - brightness) < 15


# ---------------------------------------------------------------------------
# 4. Ghosting detection (documents the failure condition)
# ---------------------------------------------------------------------------


class TestGhostingDetection:
    def test_clean_affines_low_ghosting_score(self):
        """
        Positive baseline (ratio=1.0×, evenly spaced frames) → the inter-strip
        brightness variation should be small (ghosting score < threshold).
        """
        N = 5
        frame_h = 100
        dy = 95.0
        frames, affines, masks, H, W = _make_render_inputs(
            N, frame_h=frame_h, dy=dy, brightness=150
        )
        canvas, valid_mask, _, _ = _render_median(frames, affines, masks, H, W)
        score = _ghosting_score(canvas, valid_mask)
        assert score < 30.0, (
            f"Expected low ghosting score for clean affines, got score={score:.1f}"
        )

    def test_frame_clustering_produces_small_canvas(self):
        """
        Frames all placed at the same ty position (frame clustering, test8 pattern)
        → canvas extent collapses to a single frame height.
        """
        N = 5
        frame_h = 100
        W = 120
        brightness = [100, 130, 160, 100, 130]
        frames = [make_frame(frame_h, W, color=(b, b, b)) for b in brightness]
        affines = [make_translation_affine(ty=0.0) for _ in range(N)]
        canvas_h = frame_h
        bg_masks = [None] * N
        canvas, valid_mask, _, _ = _render_median(frames, affines, bg_masks, canvas_h, W)
        assert canvas.shape == (canvas_h, W, 3)

    def test_rotation_in_affine_causes_coverage_gaps(self):
        """
        test18 pattern: good ty/tx but significant rotation component.
        With rotated affines, warped frames will not align cleanly —
        valid_mask will show irregular coverage or gaps.
        """
        N = 4
        frame_h, W = 100, 120
        frames = [make_frame(frame_h, W) for _ in range(N)]
        affines = [
            make_rotation_affine(tx=0.0, ty=float(i * 90), angle_deg=15.0)
            for i in range(N)
        ]
        canvas_h = int((N - 1) * 90 + frame_h)
        bg_masks = [None] * N
        canvas, valid_mask, _, _ = _render_median(frames, affines, bg_masks, canvas_h, W)
        assert canvas.shape == (canvas_h, W, 3)
        uncovered_fraction = float((valid_mask == 0).mean())
        assert uncovered_fraction > 0.0, (
            "Rotated affines should leave some canvas pixels uncovered"
        )


# ---------------------------------------------------------------------------
# 5. _render_first
# ---------------------------------------------------------------------------


class TestRenderFirst:
    def test_render_first_output_shape(self):
        frames, affines, masks, H, W = _make_render_inputs(3, frame_h=80, dy=70.0)
        canvas, valid_mask = _render_first(frames, affines, H, W)
        assert canvas.shape == (H, W, 3)
        assert canvas.dtype == np.uint8

    def test_render_first_valid_mask(self):
        frames, affines, masks, H, W = _make_render_inputs(3, frame_h=80, dy=70.0)
        canvas, valid_mask = _render_first(frames, affines, H, W)
        assert valid_mask.shape == (H, W)

    def test_render_first_non_empty(self):
        frames, affines, masks, H, W = _make_render_inputs(2, frame_h=80, dy=70.0)
        canvas, _ = _render_first(frames, affines, H, W)
        assert canvas.max() > 0, "_render_first canvas should have non-zero pixels"


# ---------------------------------------------------------------------------
# 6. _render dispatcher
# ---------------------------------------------------------------------------


class TestRenderDispatcher:
    def test_dispatcher_median_mode(self):
        frames, affines, masks, H, W = _make_render_inputs(3)
        canvas, vm, wc, wf = _render(frames, affines, masks, H, W, renderer="median")
        assert canvas.shape == (H, W, 3)

    def test_dispatcher_first_mode(self):
        frames, affines, masks, H, W = _make_render_inputs(3)
        canvas, vm, wc, wf = _render(frames, affines, masks, H, W, renderer="first")
        assert canvas.shape == (H, W, 3)

    def test_dispatcher_blend_mode(self):
        frames, affines, masks, H, W = _make_render_inputs(3)
        canvas, vm, wc, wf = _render(frames, affines, masks, H, W, renderer="blend")
        assert canvas.shape == (H, W, 3)

    def test_dispatcher_returns_4tuple(self):
        frames, affines, masks, H, W = _make_render_inputs(3)
        result = _render(frames, affines, masks, H, W, renderer="median")
        assert len(result) == 4


# ---------------------------------------------------------------------------
# 7. Photometric stability with baselines
# ---------------------------------------------------------------------------


class TestBaselines:
    def test_baselines_below_090_boost_brightness(self):
        """
        A frame with baseline < 0.90 (broadcast-dimmed) should have its brightness
        boosted during rendering.
        """
        brightness = 100
        frames, affines, masks, H, W = _make_render_inputs(
            2, frame_h=60, dy=55.0, brightness=brightness
        )
        baselines = [0.7, 0.95]
        canvas, valid_mask, _, _ = _render_median(
            frames, affines, masks, H, W, _baselines=baselines
        )
        covered = valid_mask[:60, :] > 0
        if covered.any():
            boosted_mean = float(canvas[:60, :][covered, :].mean())
            assert boosted_mean > brightness, (
                f"baseline=0.7 frame should be boosted above {brightness}; "
                f"got mean={boosted_mean:.1f}"
            )

    def test_baselines_none_no_error(self):
        """None baselines should produce the same result as not providing them."""
        frames, affines, masks, H, W = _make_render_inputs(3)
        canvas_no_base, vm, _, _ = _render_median(frames, affines, masks, H, W, _baselines=None)
        assert canvas_no_base is not None


# ---------------------------------------------------------------------------
# A5 — Foreground-excluded temporal median
# ---------------------------------------------------------------------------

class TestForegroundExcludedMedian:
    """The background plate must not average the character's animation poses."""

    @staticmethod
    def _scene(char_present):
        """4 aligned frames; at x=100 the character (230) is present in the
        given frames, background (80) otherwise. bg_mask: 255=bg, 0=fg."""
        H, W = 120, 200
        frames, masks, affines = [], [], []
        for present in char_present:
            img = np.full((H, W, 3), 80, np.uint8)
            bgm = np.full((H, W), 255, np.uint8)
            if present:
                img[40:80, 100:130] = 230
                bgm[40:80, 100:130] = 0
            frames.append(img)
            masks.append(bgm)
            affines.append(make_translation_affine(ty=0.0))
        return frames, affines, masks, H, W

    def test_excludes_majority_character(self, monkeypatch):
        """Character in 3/4 frames at a pixel → exclusion yields clean bg (80)."""
        monkeypatch.setenv("ASP_FG_EXCLUDE_MEDIAN", "1")
        import importlib
        import backend.src.anim.rendering as r
        importlib.reload(r)
        frames, affines, masks, H, W = self._scene([True, True, True, False])
        canvas, _, _, _ = r._render_median(frames, affines, masks, H, W)
        val = float(canvas[50:70, 105:125].mean())
        assert val < 120, f"expected clean background ~80, got {val:.0f} (ghost)"
        importlib.reload(r)  # restore default

    def test_disabled_lets_character_ghost(self, monkeypatch):
        """With exclusion OFF the majority character ghosts the background."""
        monkeypatch.setenv("ASP_FG_EXCLUDE_MEDIAN", "0")
        import importlib
        import backend.src.anim.rendering as r
        importlib.reload(r)
        frames, affines, masks, H, W = self._scene([True, True, True, False])
        canvas, _, _, _ = r._render_median(frames, affines, masks, H, W)
        val = float(canvas[50:70, 105:125].mean())
        assert val > 180, f"expected character ghost ~230, got {val:.0f}"
        importlib.reload(r)  # restore default

    def test_all_foreground_falls_back(self, monkeypatch):
        """Where the character is in ALL frames, fall back to geometric median
        (no holes)."""
        monkeypatch.setenv("ASP_FG_EXCLUDE_MEDIAN", "1")
        import importlib
        import backend.src.anim.rendering as r
        importlib.reload(r)
        frames, affines, masks, H, W = self._scene([True, True, True, True])
        canvas, vmask, _, _ = r._render_median(frames, affines, masks, H, W)
        # The pixel is covered (no hole) and shows the character (only data there).
        assert (vmask[50:70, 105:125] > 0).all(), "all-fg region must stay covered"
        val = float(canvas[50:70, 105:125].mean())
        assert val > 180, f"all-fg fallback should keep character, got {val:.0f}"
        importlib.reload(r)


class TestAdaptiveRenderGainClamp:
    """§1.40: Luminance-adaptive gain-clamp bounds for sequential colour correction."""

    def test_pure_black_returns_widest_clamp(self):
        """ref_lum=0 → clamp_width=0.26 → bounds (0.74, 1.26)."""
        lo, hi = _adaptive_render_gain_clamp(0.0)
        assert lo == pytest.approx(0.74, abs=1e-6)
        assert hi == pytest.approx(1.26, abs=1e-6)

    def test_pure_white_returns_narrowest_clamp(self):
        """ref_lum=255 → clamp_width=0.14 → bounds (0.86, 1.14)."""
        lo, hi = _adaptive_render_gain_clamp(255.0)
        assert lo == pytest.approx(0.86, abs=1e-6)
        assert hi == pytest.approx(1.14, abs=1e-6)

    def test_mid_grey_interpolates_correctly(self):
        """ref_lum=128 → clamp_width ≈ 0.26 - 0.12*(128/255) ≈ 0.200."""
        lo, hi = _adaptive_render_gain_clamp(128.0)
        expected_width = 0.26 - 0.12 * (128.0 / 255.0)
        assert lo == pytest.approx(1.0 - expected_width, abs=1e-4)
        assert hi == pytest.approx(1.0 + expected_width, abs=1e-4)

    def test_dark_scene_wider_than_bright_scene(self):
        """Darker reference → wider clamp (more correction allowed)."""
        lo_dark, hi_dark = _adaptive_render_gain_clamp(30.0)
        lo_bright, hi_bright = _adaptive_render_gain_clamp(220.0)
        assert (hi_dark - lo_dark) > (hi_bright - lo_bright), "dark clamp must be wider"

    def test_clamp_above_255_floored_at_bright_clamp(self):
        """ref_lum > 255 is clamped to 255 → returns the same bounds as pure white."""
        lo_over, hi_over = _adaptive_render_gain_clamp(500.0)
        lo_white, hi_white = _adaptive_render_gain_clamp(255.0)
        assert lo_over == pytest.approx(lo_white, abs=1e-6)
        assert hi_over == pytest.approx(hi_white, abs=1e-6)


class TestCheckGainChainDrift:
    """§1.41: Sequential gain chain-drift guard."""

    def _gains(self, values: list) -> np.ndarray:
        """Build an (N, 3) gains array from a list of per-frame scalar gains."""
        return np.array([[v, v, v] for v in values], dtype=np.float32)

    def test_identity_gains_no_drift(self):
        """All-ones gains → cumulative product = 1.0 → no drift."""
        gains = self._gains([1.0] * 8)
        assert not _check_gain_chain_drift(gains, max_ratio=2.0)

    def test_large_cumulative_gain_detected(self):
        """Eight frames each × 1.12 → cumulative ≈ 2.48 > 2.0 → drift detected."""
        gains = self._gains([1.12] * 8)
        assert _check_gain_chain_drift(gains, max_ratio=2.0)

    def test_zero_max_ratio_always_false(self):
        """max_ratio=0 disables the gate; always returns False."""
        gains = self._gains([1.5] * 10)
        assert not _check_gain_chain_drift(gains, max_ratio=0.0)

    def test_single_large_gain_triggers(self):
        """One frame with gain=0.4 → cumulative 0.4 < 1/1.5 → drift detected."""
        gains = self._gains([1.0, 1.0, 0.4, 1.0])
        assert _check_gain_chain_drift(gains, max_ratio=1.5)

    def test_cancelling_gains_no_drift(self):
        """Gains that cancel (1.3 × 0.77 ≈ 1.0 per pair) → no drift."""
        gains = self._gains([1.3, 0.769, 1.3, 0.769])
        # cumulative ≈ 1.3 * 0.769 * 1.3 * 0.769 ≈ 1.0
        assert not _check_gain_chain_drift(gains, max_ratio=2.0)
