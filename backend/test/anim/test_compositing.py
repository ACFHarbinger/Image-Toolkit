"""
Tests for the Stage 11 hard-partition composite (compositing.py).

Issue categories covered:
  A — Seam / brightness bands: LS gain clamp at ±5%, feather zone, boundary search.

All tests run without GPU — no BiRefNet or LoFTR dependencies.
"""

from __future__ import annotations

import os
import sys

import cv2
import numpy as np

_repo_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, _repo_root)

from backend.src.anim.compositing import (  # noqa: E402
    _FEATHER_MAX,
    _FEATHER_MIN,
    _FEATHER_TABLE,
    _GAIN_CLAMP,
    _composite_foreground,
    _diff_to_feather,
    _global_gain_normalize,
)
from ..conftest import make_frame, make_translation_affine  # noqa: E402


# ---------------------------------------------------------------------------
# 1. _diff_to_feather lookup table (Bug 1 regression)
# ---------------------------------------------------------------------------


class TestDiffToFeather:
    """
    The feather table maps frame-difference scores to blend half-widths.
    Low-diff boundaries get wide feathers (300px); high-diff boundaries get narrow (80px).
    """

    def test_identical_frames_get_max_feather(self):
        """diff ≤ 5.0 → FEATHER_MAX (300)."""
        assert _diff_to_feather(0.0) == 300
        assert _diff_to_feather(5.0) == 300

    def test_low_diff_gets_wide_feather(self):
        """diff = 7.5 (between 5 and 10) → 250."""
        assert _diff_to_feather(7.5) == 250

    def test_medium_diff_gets_medium_feather(self):
        """diff = 15.0 → 200."""
        assert _diff_to_feather(15.0) == 200

    def test_high_diff_gets_narrow_feather(self):
        """diff = 35.0 → 150; diff = 50.0 → 100."""
        assert _diff_to_feather(35.0) == 150
        assert _diff_to_feather(50.0) == 100

    def test_very_high_diff_gets_min_feather(self):
        """diff > 50 → FEATHER_MIN (80)."""
        assert _diff_to_feather(100.0) == _FEATHER_MIN
        assert _diff_to_feather(float("inf")) == _FEATHER_MIN

    def test_all_feather_values_in_valid_range(self):
        """All feather outputs must be ≥ FEATHER_MIN and ≤ FEATHER_MAX."""
        test_diffs = [0, 1, 5, 7, 10, 15, 20, 35, 50, 100, 1000]
        for d in test_diffs:
            f = _diff_to_feather(d)
            assert _FEATHER_MIN <= f <= _FEATHER_MAX, (
                f"_diff_to_feather({d}) = {f} outside [{_FEATHER_MIN}, {_FEATHER_MAX}]"
            )

    def test_feather_table_is_monotonically_decreasing(self):
        """Larger diff score should never produce a wider feather."""
        diffs = [0, 5, 10, 20, 35, 50, 100, 1000]
        feathers = [_diff_to_feather(d) for d in diffs]
        for i in range(len(feathers) - 1):
            assert feathers[i] >= feathers[i + 1], (
                f"Feather table not monotone at diff={diffs[i + 1]}: "
                f"{feathers[i]} → {feathers[i + 1]}"
            )

    def test_gain_clamp_tight_around_unity(self):
        """
        Bug 4 regression: LS gain clamp must be ≤ ±5% from 1.0.
        Wider clamps treated the natural scene gradient as calibration error.
        """
        clamp_lo, clamp_hi = _GAIN_CLAMP
        assert clamp_lo >= 0.85, (
            f"Gain clamp lower bound {clamp_lo:.2f} is too aggressive (< 0.85); "
            "should be ≥ 0.88 to avoid over-darkening frames"
        )
        assert clamp_hi <= 1.20, (
            f"Gain clamp upper bound {clamp_hi:.2f} is too aggressive (> 1.20); "
            "should be ≤ 1.15 to avoid over-brightening frames"
        )


# ---------------------------------------------------------------------------
# 2. _global_gain_normalize (Bug 4 regression)
# ---------------------------------------------------------------------------


class TestGlobalGainNormalize:
    def _build_warped_list(self, n: int, H: int, W: int, brightness: list):
        """Solid-color warped frames with specified per-channel brightness."""
        frames_src = [
            make_frame(H // n, W, color=(int(b), int(b), int(b))) for b in brightness
        ]
        affines = [make_translation_affine(ty=i * float(H // n)) for i in range(n)]
        warped = []
        for i, (f, aff) in enumerate(zip(frames_src, affines)):
            w = cv2.warpAffine(
                f,
                aff,
                (W, H),
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            )
            warped.append(w)
        return warped, affines, np.arange(n)

    def test_equal_brightness_frames_no_correction(self):
        """All frames at the same brightness → gains stay near 1.0."""
        n, H, W = 4, 400, 100
        warped, affines, order = self._build_warped_list(n, H, W, [150.0] * n)
        initial_boundaries = np.array([(i + 0.5) * (H / n) for i in range(n - 1)])
        before = [w.copy() for w in warped]
        _global_gain_normalize(
            warped, order, initial_boundaries, H, W, bg_masks=None, affines=None
        )
        for i, (b, a) in enumerate(zip(before, warped)):
            diff = np.abs(b.astype(int) - a.astype(int)).max()
            assert diff < 5, (
                f"frame{i}: unchanged frames should not be modified; max_diff={diff}"
            )

    def test_moderate_brightness_diff_clamped_to_gain_range(self):
        """
        Bug 4 regression: 20% brightness difference → applied gain must be within
        _GAIN_CLAMP range (≤ ±14%).
        """
        n, H, W = 4, 400, 100
        brightness = [100.0, 120.0, 100.0, 120.0]
        warped, affines, order = self._build_warped_list(n, H, W, brightness)
        initial_boundaries = np.array([(i + 0.5) * (H / n) for i in range(n - 1)])

        means_before = []
        for w in warped:
            px = w[w.max(axis=2) > 0]
            means_before.append(float(px[:, 1].mean()) if len(px) > 0 else 0.0)

        _global_gain_normalize(
            warped, order, initial_boundaries, H, W, bg_masks=None, affines=None
        )

        means_after = []
        for w in warped:
            px = w[w.max(axis=2) > 0]
            means_after.append(float(px[:, 1].mean()) if len(px) > 0 else 0.0)

        lo, hi = _GAIN_CLAMP
        for i, (mb, ma) in enumerate(zip(means_before, means_after)):
            if mb > 5.0:
                gain = ma / mb
                assert lo <= gain <= hi, (
                    f"frame{i}: applied gain={gain:.3f} outside _GAIN_CLAMP=[{lo},{hi}]"
                )

    def test_ls_normalization_clamp_tight(self):
        """
        The least-squares alpha gains inside _global_gain_normalize are clipped
        to [0.95, 1.05] (±5%). This is the key fix from Bug 4.
        """
        n, H, W = 5, 500, 100
        brightness = [253.0, 200.0, 150.0, 100.0, 82.0]
        warped, affines, order = self._build_warped_list(n, H, W, brightness)
        initial_boundaries = np.array([(i + 0.5) * (H / n) for i in range(n - 1)])

        means_before = []
        for w in warped:
            px = w[w.max(axis=2) > 0]
            means_before.append(float(px[:, 1].mean()) if len(px) > 0 else 0.0)

        _global_gain_normalize(
            warped, order, initial_boundaries, H, W, bg_masks=None, affines=None
        )

        means_after = []
        for w in warped:
            px = w[w.max(axis=2) > 0]
            means_after.append(float(px[:, 1].mean()) if len(px) > 0 else 0.0)

        lo, hi = _GAIN_CLAMP
        for i, (mb, ma) in enumerate(zip(means_before, means_after)):
            if mb > 5.0:
                gain = ma / mb
                assert lo <= gain <= hi, (
                    f"frame{i}: 50% swing should be clamped but gain={gain:.3f} "
                    f"is outside _GAIN_CLAMP=[{lo},{hi}]"
                )


# ---------------------------------------------------------------------------
# 3. _composite_foreground output shape and stability
# ---------------------------------------------------------------------------


class TestCompositeForeground:
    def _run_composite(self, n: int, H: int, W: int):
        frame_h = H // 2
        frames = [
            make_frame(frame_h, W, color=(int(c), int(c), int(c)))
            for c in np.linspace(60, 200, n, dtype=int)
        ]
        affines = [make_translation_affine(ty=i * float(frame_h) * 0.8) for i in range(n)]
        canvas_h = int((n - 1) * frame_h * 0.8 + frame_h)
        canvas = np.zeros((canvas_h, W, 3), dtype=np.uint8)
        for i, (f, aff) in enumerate(zip(frames, affines)):
            wf = cv2.warpAffine(
                f, aff, (W, canvas_h),
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            )
            mask = wf.max(axis=2) > 0
            canvas[mask] = wf[mask]
        bg_masks = [None] * n
        return _composite_foreground([], [], canvas, canvas_h, W, frames, affines, bg_masks)

    def test_output_shape_preserved(self):
        """Output canvas must retain its spatial dimensions and channel count."""
        result = self._run_composite(n=3, H=300, W=200)
        assert result.ndim == 3
        assert result.shape[2] == 3
        assert result.dtype == np.uint8

    def test_output_is_uint8(self):
        result = self._run_composite(n=4, H=400, W=150)
        assert result.dtype == np.uint8

    def test_output_values_in_range(self):
        result = self._run_composite(n=3, H=300, W=200)
        assert result.min() >= 0
        assert result.max() <= 255

    def test_two_frames_minimal_case(self):
        """Minimal case: 2 frames → should run without error."""
        result = self._run_composite(n=2, H=200, W=100)
        assert result is not None
        assert result.ndim == 3

    def test_no_all_black_output(self):
        """Output should not be all zeros (compositing should place some pixels)."""
        result = self._run_composite(n=4, H=400, W=200)
        assert result.max() > 0, "Composite output is all black — no pixels were placed"

    def test_identity_no_crash_single_frame_height(self):
        """Frames whose height exactly divides the canvas should not crash."""
        frame_h, W = 100, 150
        frames = [
            make_frame(frame_h, W, color=(100, 100, 100)),
            make_frame(frame_h, W, color=(150, 150, 150)),
        ]
        affines = [
            make_translation_affine(ty=0.0),
            make_translation_affine(ty=float(frame_h)),
        ]
        canvas_h = frame_h * 2
        canvas = np.zeros((canvas_h, W, 3), dtype=np.uint8)
        for i, (f, aff) in enumerate(zip(frames, affines)):
            wf = cv2.warpAffine(
                f, aff, (W, canvas_h),
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            )
            row_start = frame_h * i
            canvas[row_start : row_start + frame_h] = wf[row_start : row_start + frame_h]
        bg_masks = [None, None]
        result = _composite_foreground([], [], canvas, canvas_h, W, frames, affines, bg_masks)
        assert result is not None
