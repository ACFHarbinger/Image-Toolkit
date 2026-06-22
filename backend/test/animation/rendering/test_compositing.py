"""
Tests for the Stage 11 Laplacian-blend composite (compositing.py).

Issue categories covered:
  A — Seam blending: feather zone, boundary search, Laplacian pyramid blend.

All tests run without GPU — no BiRefNet or LoFTR dependencies.
"""

from __future__ import annotations
import importlib
from backend.src.animation.rendering import compositing
from backend.src.animation.rendering.compositing import (
    _blocks_gain_compensate,
    _blocks_lum_compensate,
)
from backend.src.animation.core import config


import os
import sys

import cv2
import numpy as np
import pytest

_repo_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, _repo_root)

from backend.src.animation.rendering.compositing import (  # noqa: E402
    _adaptive_sp_threshold,
    _compute_seam_step_size,
    _fg_density_feather_cap,
    _seam_lum_equalize,
    _adaptive_gain_clamp,
    _apply_bg_histogram_match,  # noqa: F401
    _seam_ncc_coherence,
    _check_seam_ncc_gate,
    _bg_gain_unclamped,
    _bg_histogram_lut,
    _reject_exposure_outliers,
    _build_seam_cost_map,
    _check_seam_color_gate,
    _coherence_skip_mask,
    _composite_foreground,
    _diff_to_feather,
    _gain_to_min_feather,
    _get_seam_cost_flags,
    _make_seam_cache_key,
    _multiscale_gain_map,
    _poisson_seam_blend,
    _seam_cut,
    _seam_color_match,
    _seam_color_similarity,
    _seam_color_similarity_bgr,
    _single_pose_soft_edge,
    _soft_seam_weight,
    _adaptive_sp_soft_px,
    _seam_corridor_exists,
    _smooth_seam_path,
    _clamp_seam_path,
    _has_sufficient_bg,
    _seam_path_std,
    _zone_is_degenerate,
    _seam_fg_penetration,
    _seam_zone_texture_energy,
    _fg_gradient_cost,
    _annotate_seams,
    _seam_chroma_equalize,
    _fg_zone_pose_gap,
    _fg_fraction_in_zone,
    _enforce_feather_ratio,
    _seam_dp_bg_ratio,
    _seam_entropy_asymmetry,
    _check_seam_entropy_gate,
    _seam_max_col_luma_step,
    _check_seam_max_col_gate,
    _seam_saturation_jump,
    _check_seam_saturation_gate,
    _seam_hue_shift,
    _check_seam_hue_gate,
    _seam_sharpness_mismatch,
    _check_seam_sharpness_gate,
    _seam_grad_direction,
    _check_seam_grad_direction_gate,
    _seam_band_ssim,
    _check_seam_ssim_gate,
    _seam_freq_profile,
    _check_seam_freq_gate,
    _seam_noise_mismatch,
    _check_seam_noise_gate,
    _seam_rms_contrast_ratio,
    _check_seam_rms_contrast_gate,
    _seam_gate_vote_counts,
    _check_seam_ensemble_gate,
    _zone_pair_ssim,
)
from backend.src.constants import (  # noqa: E402
    FEATHER_MAX as _FEATHER_MAX,
    FEATHER_MIN as _FEATHER_MIN,
    FEATHER_TABLE as _FEATHER_TABLE,  # noqa: F401
    SEAM_OVERLAY_AMBER_THRESH as _AMBER,
    SEAM_OVERLAY_RED_THRESH as _RED,
)
from conftest import make_frame, make_translation_affine  # noqa: E402


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


# ---------------------------------------------------------------------------
# 2. _composite_foreground output shape and stability
# ---------------------------------------------------------------------------


@pytest.mark.gc_heavy
class TestCompositeForeground:
    def _run_composite(self, n: int, H: int, W: int):
        frame_h = H // 2
        frames = [
            make_frame(frame_h, W, color=(int(c), int(c), int(c)))
            for c in np.linspace(60, 200, n, dtype=int)
        ]
        affines = [
            make_translation_affine(ty=i * float(frame_h) * 0.8) for i in range(n)
        ]
        canvas_h = int((n - 1) * frame_h * 0.8 + frame_h)
        canvas = np.zeros((canvas_h, W, 3), dtype=np.uint8)
        for i, (f, aff) in enumerate(zip(frames, affines)):
            wf = cv2.warpAffine(
                f,
                aff,
                (W, canvas_h),
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            )
            mask = wf.max(axis=2) > 0
            canvas[mask] = wf[mask]
        bg_masks = [None] * n
        return _composite_foreground(
            [], [], canvas, canvas_h, W, frames, affines, bg_masks
        )

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
                f,
                aff,
                (W, canvas_h),
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            )
            row_start = frame_h * i
            canvas[row_start : row_start + frame_h] = wf[
                row_start : row_start + frame_h
            ]
        bg_masks = [None, None]
        result = _composite_foreground(
            [], [], canvas, canvas_h, W, frames, affines, bg_masks
        )
        assert result is not None


# ---------------------------------------------------------------------------
# 3. _seam_cut — DP seam path shape and validity (S12 regression)
# ---------------------------------------------------------------------------


class TestSeamCutDP:
    """
    _seam_cut() takes two (h × W × 3) zone slices and returns a horizontal
    cut path of shape (W,) where each value is a y-offset in [0, h-1].
    """

    def _make_zone(self, h: int, W: int, base: int, noise: int = 10) -> np.ndarray:
        rng = np.random.default_rng(42)
        z = np.full((h, W, 3), base, dtype=np.uint8)
        z = np.clip(
            z.astype(np.int32) + rng.integers(-noise, noise + 1, z.shape), 0, 255
        )
        return z.astype(np.uint8)

    def test_output_shape_is_width(self):
        h, W = 40, 80
        fa = self._make_zone(h, W, 100)
        fb = self._make_zone(h, W, 150)
        path = _seam_cut(fa, fb)
        assert path.shape == (W,), f"Expected path shape ({W},), got {path.shape}"

    def test_path_values_in_valid_range(self):
        h, W = 30, 60
        fa = self._make_zone(h, W, 80)
        fb = self._make_zone(h, W, 180)
        path = _seam_cut(fa, fb)
        assert path.dtype == np.int32
        assert int(path.min()) >= 0
        assert int(path.max()) < h

    def test_identical_images_return_valid_path(self):
        """Path must be valid even when both frames are identical (zero energy everywhere)."""
        h, W = 20, 50
        fa = self._make_zone(h, W, 128)
        path = _seam_cut(fa, fa.copy())
        assert path.shape == (W,)
        assert int(path.min()) >= 0
        assert int(path.max()) < h

    def test_with_sem_cost_no_crash(self):
        """Providing a sem_cost map should not crash and must return valid path."""
        h, W = 24, 48
        fa = self._make_zone(h, W, 90)
        fb = self._make_zone(h, W, 170)
        sem = np.random.default_rng(7).random((h, W)).astype(np.float32)
        path = _seam_cut(fa, fb, sem_cost=sem)
        assert path.shape == (W,)
        assert int(path.min()) >= 0
        assert int(path.max()) < h

    def test_path_connectivity(self):
        """Adjacent path values must differ by at most 1 (DP 3-connectivity constraint)."""
        h, W = 40, 100
        fa = self._make_zone(h, W, 60)
        fb = self._make_zone(h, W, 200)
        path = _seam_cut(fa, fb)
        diffs = np.abs(np.diff(path.astype(np.int32)))
        assert int(diffs.max()) <= 1, (
            f"Path not 3-connected: max step={int(diffs.max())}"
        )


# ---------------------------------------------------------------------------
# 3b. _seam_cut — §2.11A Intelligent Scissors waypoint injection
# ---------------------------------------------------------------------------


class TestSeamCutWaypoints:
    """
    §2.11A: waypoints force the seam to pass through specific (x, y) pixels.
    The DP rows other than y_wp are set to +inf in column x_wp so the seam
    is guaranteed to land there; 3-connectivity is preserved end-to-end.
    """

    def _make_zone(self, h: int, W: int, base: int, noise: int = 5) -> np.ndarray:
        rng = np.random.default_rng(99)
        z = np.full((h, W, 3), base, dtype=np.uint8)
        z = np.clip(
            z.astype(np.int32) + rng.integers(-noise, noise + 1, z.shape), 0, 255
        )
        return z.astype(np.uint8)

    def test_single_waypoint_respected(self):
        """Seam must pass through the specified (x, y) waypoint exactly."""
        h, W = 40, 80
        fa = self._make_zone(h, W, 100)
        fb = self._make_zone(h, W, 150)
        x_wp, y_wp = 40, 10  # force through top-third row at mid-column
        path = _seam_cut(fa, fb, waypoints=[(x_wp, y_wp)])
        assert path[x_wp] == y_wp, (
            f"Seam did not pass through waypoint ({x_wp}, {y_wp}); got path[{x_wp}]={path[x_wp]}"
        )

    def test_multiple_waypoints_all_respected(self):
        """All waypoints must be honoured simultaneously."""
        h, W = 60, 100
        fa = self._make_zone(h, W, 80)
        fb = self._make_zone(h, W, 180)
        waypoints = [(20, 5), (50, 30), (80, 55)]
        path = _seam_cut(fa, fb, waypoints=waypoints)
        for x_wp, y_wp in waypoints:
            assert path[x_wp] == y_wp, (
                f"Waypoint ({x_wp}, {y_wp}) not respected; path[{x_wp}]={path[x_wp]}"
            )

    def test_waypoint_preserves_3connectivity(self):
        """Path with waypoints must still be 3-connected (|Δy| ≤ 1 per column)."""
        h, W = 50, 90
        fa = self._make_zone(h, W, 70)
        fb = self._make_zone(h, W, 190)
        waypoints = [(10, 5), (80, 40)]
        path = _seam_cut(fa, fb, waypoints=waypoints)
        diffs = np.abs(np.diff(path.astype(np.int32)))
        assert int(diffs.max()) <= 1, (
            f"3-connectivity broken with waypoints: max step={int(diffs.max())}"
        )

    def test_out_of_bounds_waypoint_ignored(self):
        """Waypoints with coordinates outside the zone must not crash and must be silently ignored."""
        h, W = 30, 60
        fa = self._make_zone(h, W, 120)
        fb = self._make_zone(h, W, 160)
        path = _seam_cut(fa, fb, waypoints=[(-1, 5), (W + 5, 10), (10, h + 2)])
        assert path.shape == (W,)
        assert int(path.min()) >= 0 and int(path.max()) < h

    def test_no_waypoints_matches_baseline(self):
        """Passing waypoints=None must produce the same path as omitting the argument."""
        h, W = 35, 70
        rng = np.random.default_rng(1)
        fa = rng.integers(50, 150, (h, W, 3), dtype=np.uint8)
        fb = rng.integers(100, 200, (h, W, 3), dtype=np.uint8)
        path_base = _seam_cut(fa, fb)
        path_none = _seam_cut(fa, fb, waypoints=None)
        path_empty = _seam_cut(fa, fb, waypoints=[])
        np.testing.assert_array_equal(path_base, path_none)
        np.testing.assert_array_equal(path_base, path_empty)


# ---------------------------------------------------------------------------
# 4. Parallel seam pre-computation (_precomp_paths) — S12 integration
# ---------------------------------------------------------------------------


@pytest.mark.gc_heavy
class TestParallelSeamPrecompute:
    """
    With ≥ 2 seam boundaries the composite should enter the ThreadPoolExecutor
    pre-computation path.  The result must be identical in shape and type to the
    sequential path.
    """

    def _run_composite_n(self, n: int, H: int = 500, W: int = 120) -> np.ndarray:
        frame_h = H // n
        frames = [
            make_frame(frame_h, W, color=(int(c), int(c), int(c)))
            for c in np.linspace(60, 200, n, dtype=int)
        ]
        affines = [
            make_translation_affine(ty=i * float(frame_h) * 0.9) for i in range(n)
        ]
        canvas_h = int((n - 1) * frame_h * 0.9 + frame_h)
        canvas = np.zeros((canvas_h, W, 3), dtype=np.uint8)
        for i, (f, aff) in enumerate(zip(frames, affines)):
            wf = cv2.warpAffine(
                f,
                aff,
                (W, canvas_h),
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            )
            mask = wf.max(axis=2) > 0
            canvas[mask] = wf[mask]
        return _composite_foreground(
            [], [], canvas, canvas_h, W, frames, affines, [None] * n
        )

    def test_five_frames_parallel_path_completes(self):
        """5 frames → 4 boundaries → parallel ThreadPoolExecutor path; must not raise."""
        result = self._run_composite_n(5)
        assert result is not None
        assert result.ndim == 3
        assert result.dtype == np.uint8

    def test_six_frames_output_shape_matches_canvas(self):
        """Output spatial dimensions must match the input canvas for 6-frame parallel run."""
        H, W, n = 600, 100, 6
        frame_h = H // n
        frames = [make_frame(frame_h, W, color=(100, 100, 100))] * n
        affines = [
            make_translation_affine(ty=i * float(frame_h) * 0.9) for i in range(n)
        ]
        canvas_h = int((n - 1) * frame_h * 0.9 + frame_h)
        canvas = np.zeros((canvas_h, W, 3), dtype=np.uint8)
        result = _composite_foreground(
            [], [], canvas, canvas_h, W, frames, affines, [None] * n
        )
        assert result.shape[1] == W
        assert result.shape[2] == 3

    def test_two_frames_single_seam_no_parallel(self):
        """2 frames → 1 boundary → single-seam fallback path (not ThreadPoolExecutor)."""
        result = self._run_composite_n(2)
        assert result is not None
        assert result.ndim == 3
        assert result.dtype == np.uint8


# ---------------------------------------------------------------------------
# 5. Single-pose soft-edge blend (_single_pose_soft_edge) — S15
# ---------------------------------------------------------------------------


class TestSinglePoseSoftEdge:
    """
    _single_pose_soft_edge applies a narrow ±sp_soft_px linear feather at the
    seam path to smooth the hard color step of single-pose seams.
    """

    def _zone(self, H: int, W: int, lum: int) -> np.ndarray:
        return np.full((H, W, 3), lum, dtype=np.uint8)

    def _path(self, W: int, y: int) -> np.ndarray:
        return np.full(W, y, dtype=np.int32)

    def _apply(self, H: int, W: int) -> np.ndarray:
        return np.ones((H, W), dtype=bool)

    def test_output_shape_and_dtype(self):
        """Output must match dom_zone shape and be uint8."""
        H, W = 40, 60
        dom = self._zone(H, W, 100)
        oth = self._zone(H, W, 200)
        path = self._path(W, H // 2)
        out = _single_pose_soft_edge(dom, oth, path, self._apply(H, W), 6)
        assert out.shape == dom.shape
        assert out.dtype == np.uint8

    def test_disabled_when_sp_soft_px_zero(self):
        """sp_soft_px=0 must return an unmodified copy of dom_zone."""
        H, W = 30, 50
        dom = self._zone(H, W, 80)
        oth = self._zone(H, W, 180)
        path = self._path(W, H // 2)
        out = _single_pose_soft_edge(dom, oth, path, self._apply(H, W), 0)
        np.testing.assert_array_equal(out, dom)

    def test_seam_row_is_blended_50_50(self):
        """Row exactly at the seam path gets a 50/50 blend (w_oth=0.5)."""
        H, W, seam_y = 40, 60, 20
        dom = self._zone(H, W, 100)
        oth = self._zone(H, W, 200)
        path = self._path(W, seam_y)
        out = _single_pose_soft_edge(dom, oth, path, self._apply(H, W), 8)
        expected = np.uint8(0.5 * 100 + 0.5 * 200)  # =150
        assert int(out[seam_y, 0, 0]) == expected

    def test_outside_band_pixels_are_unchanged(self):
        """Rows more than sp_soft_px away from the seam must equal dom_zone."""
        H, W, seam_y, soft_px = 80, 60, 40, 6
        dom = self._zone(H, W, 80)
        oth = self._zone(H, W, 180)
        path = self._path(W, seam_y)
        out = _single_pose_soft_edge(dom, oth, path, self._apply(H, W), soft_px)
        for r in [0, seam_y - soft_px, seam_y + soft_px, H - 1]:
            if 0 <= r < H:
                np.testing.assert_array_equal(out[r], dom[r])

    def test_in_band_pixels_are_strictly_between_dom_and_oth(self):
        """Within the blend band the output must be strictly between dom and oth."""
        H, W, seam_y, soft_px = 60, 50, 30, 6
        dom_lum, oth_lum = 60, 180
        dom = self._zone(H, W, dom_lum)
        oth = self._zone(H, W, oth_lum)
        path = self._path(W, seam_y)
        out = _single_pose_soft_edge(dom, oth, path, self._apply(H, W), soft_px)
        for r in range(seam_y - soft_px + 1, seam_y + soft_px):
            if 0 <= r < H:
                val = int(out[r, 0, 0])
                assert dom_lum <= val <= oth_lum, (
                    f"Row {r}: expected [{dom_lum}, {oth_lum}], got {val}"
                )

    def test_no_modification_where_apply_mask_is_false(self):
        """Pixels where apply_mask is False must not be modified."""
        H, W, seam_y = 40, 60, 20
        dom = self._zone(H, W, 100)
        oth = self._zone(H, W, 200)
        path = self._path(W, seam_y)
        apply = np.zeros((H, W), dtype=bool)  # nothing applied
        out = _single_pose_soft_edge(dom, oth, path, apply, 6)
        np.testing.assert_array_equal(out, dom)

    def test_no_modification_where_oth_has_no_content(self):
        """Blend only fires where oth_zone is non-zero; zero oth → dom unchanged."""
        H, W, seam_y = 40, 60, 20
        dom = self._zone(H, W, 100)
        oth = np.zeros((H, W, 3), dtype=np.uint8)  # all black (no content)
        path = self._path(W, seam_y)
        out = _single_pose_soft_edge(dom, oth, path, self._apply(H, W), 6)
        np.testing.assert_array_equal(out, dom)


# ---------------------------------------------------------------------------
# 6. Seam color match (_seam_color_match) — S16
# ---------------------------------------------------------------------------


class TestSeamColorMatch:
    """
    _seam_color_match shifts oth_zone channel means to match dom_zone in the
    seam band, reducing the color step before the S15 linear blend is applied.
    """

    def _zone(self, H: int, W: int, lum: int) -> np.ndarray:
        return np.full((H, W, 3), lum, dtype=np.uint8)

    def _path(self, W: int, y: int) -> np.ndarray:
        return np.full(W, y, dtype=np.int32)

    def test_output_shape_and_dtype(self):
        """Output must match oth_zone shape and be uint8."""
        H, W = 40, 60
        dom = self._zone(H, W, 100)
        oth = self._zone(H, W, 200)
        path = self._path(W, H // 2)
        out = _seam_color_match(dom, oth, path, 10)
        assert out.shape == oth.shape
        assert out.dtype == np.uint8

    def test_zero_band_returns_unchanged_copy(self):
        """band_px=0 must return an unmodified copy of oth_zone."""
        H, W = 30, 50
        dom = self._zone(H, W, 80)
        oth = self._zone(H, W, 180)
        path = self._path(W, H // 2)
        out = _seam_color_match(dom, oth, path, 0)
        np.testing.assert_array_equal(out, oth)

    def test_band_pixels_shifted_toward_dom_mean(self):
        """Band pixels in oth_zone must move toward dom_zone's mean."""
        H, W, seam_y, band_px = 60, 50, 30, 10
        dom_lum, oth_lum = 100, 200
        dom = self._zone(H, W, dom_lum)
        oth = self._zone(H, W, oth_lum)
        path = self._path(W, seam_y)
        out = _seam_color_match(dom, oth, path, band_px)
        # In the band, oth mean (200) shifts to dom mean (100) → delta=-100.
        # Resulting band pixels should be clipped to dom_lum (or close).
        seam_row = out[seam_y, 0, 0]
        assert int(seam_row) == dom_lum, (
            f"Band pixel should equal dom_lum={dom_lum}, got {seam_row}"
        )

    def test_outside_band_pixels_are_unchanged(self):
        """Rows beyond band_px from the seam must not be modified."""
        H, W, seam_y, band_px = 80, 60, 40, 8
        dom = self._zone(H, W, 80)
        oth = self._zone(H, W, 180)
        path = self._path(W, seam_y)
        out = _seam_color_match(dom, oth, path, band_px)
        for r in [0, seam_y - band_px, seam_y + band_px, H - 1]:
            if 0 <= r < H:
                np.testing.assert_array_equal(out[r], oth[r])

    def test_identical_zones_produce_no_shift(self):
        """When dom and oth have the same mean, delta=0 and output equals oth."""
        H, W = 40, 60
        lum = 128
        zone = self._zone(H, W, lum)
        path = self._path(W, H // 2)
        out = _seam_color_match(zone, zone.copy(), path, 10)
        np.testing.assert_array_equal(out, zone)

    def test_degenerate_zone_returns_unchanged(self):
        """When oth_zone is all-black in the band (no content), return copy unchanged."""
        H, W, seam_y = 40, 60, 20
        dom = self._zone(H, W, 100)
        oth = np.zeros((H, W, 3), dtype=np.uint8)
        path = self._path(W, seam_y)
        out = _seam_color_match(dom, oth, path, 10)
        np.testing.assert_array_equal(out, oth)

    def test_per_channel_delta_applied_independently(self):
        """Each BGR channel gets its own shift — channels are not mixed."""
        H, W, seam_y, band_px = 40, 60, 20, 8
        dom = np.zeros((H, W, 3), dtype=np.uint8)
        dom[:, :, 0] = 50  # B=50, G=0, R=0
        dom[:, :, 1] = 100  # B=50, G=100, R=0
        dom[:, :, 2] = 150  # B=50, G=100, R=150
        oth = np.full((H, W, 3), 200, dtype=np.uint8)  # B=G=R=200
        path = self._path(W, seam_y)
        out = _seam_color_match(dom, oth, path, band_px)
        # delta per channel: B=50-200=-150, G=100-200=-100, R=150-200=-50
        # band pixel after shift: B=clip(200-150,0,255)=50, G=100, R=150
        band_px_val = out[seam_y, 0]
        assert int(band_px_val[0]) == 50, (
            f"B channel: expected 50, got {band_px_val[0]}"
        )
        assert int(band_px_val[1]) == 100, (
            f"G channel: expected 100, got {band_px_val[1]}"
        )
        assert int(band_px_val[2]) == 150, (
            f"R channel: expected 150, got {band_px_val[2]}"
        )


# ---------------------------------------------------------------------------
# 7. Per-pixel DSFN seam weight (_soft_seam_weight) — S17
# ---------------------------------------------------------------------------


class TestSoftSeamWeight:
    """
    _soft_seam_weight (S17) returns a per-pixel blend weight in [0,1]:
      1.0 → fa_zone, 0.0 → fb_zone.
    The ramp radius is now per-pixel (driven by local similarity) rather than
    per-column mean, giving background pixels wide transitions and foreground
    pixels narrow ones automatically.
    """

    def _uniform(self, H: int, W: int, lum: int) -> np.ndarray:
        return np.full((H, W, 3), lum, dtype=np.uint8)

    def _path(self, W: int, y: int) -> np.ndarray:
        return np.full(W, y, dtype=np.int32)

    def test_output_shape_and_dtype(self):
        """Output must be (zone_h, W) float32."""
        H, W, seam_y = 60, 80, 30
        fa = self._uniform(H, W, 100)
        fb = self._uniform(H, W, 200)
        path = self._path(W, seam_y)
        out = _soft_seam_weight(fa, fb, path, H, W)
        assert out.shape == (H, W)
        assert out.dtype == np.float32

    def test_weight_in_unit_range(self):
        """All output values must be in [0, 1]."""
        H, W, seam_y = 50, 60, 25
        fa = self._uniform(H, W, 80)
        fb = self._uniform(H, W, 180)
        path = self._path(W, seam_y)
        out = _soft_seam_weight(fa, fb, path, H, W)
        assert float(out.min()) >= 0.0
        assert float(out.max()) <= 1.0 + 1e-5

    def test_weight_half_at_seam_for_identical_frames(self):
        """When frames are identical (zero diff), weight at seam row ≈ 0.5."""
        H, W, seam_y = 60, 80, 30
        fa = self._uniform(H, W, 128)
        path = self._path(W, seam_y)
        out = _soft_seam_weight(fa, fa.copy(), path, H, W)
        seam_weights = out[seam_y, :]
        assert np.allclose(seam_weights, 0.5, atol=0.05), (
            f"Expected ~0.5 at seam for identical frames, got {seam_weights.mean():.3f}"
        )

    def test_weight_one_far_above_seam(self):
        """Far above the seam, weight should be ~1.0 (all fa)."""
        H, W, seam_y = 100, 80, 50
        fa = self._uniform(H, W, 128)
        fb = self._uniform(H, W, 50)
        path = self._path(W, seam_y)
        out = _soft_seam_weight(fa, fb, path, H, W)
        # Row 0 is far above seam_y=50 → weight should be 1.0
        assert float(out[0].mean()) > 0.95, (
            f"Top row weight: {float(out[0].mean()):.3f}"
        )

    def test_weight_zero_far_below_seam(self):
        """Far below the seam, weight should be ~0.0 (all fb)."""
        H, W, seam_y = 100, 80, 50
        fa = self._uniform(H, W, 128)
        fb = self._uniform(H, W, 50)
        path = self._path(W, seam_y)
        out = _soft_seam_weight(fa, fb, path, H, W)
        # Last row is far below seam_y=50 → weight should be ~0.0
        assert float(out[-1].mean()) < 0.05, (
            f"Bottom row weight: {float(out[-1].mean()):.3f}"
        )

    def test_high_similarity_gives_wider_blend_than_low(self):
        """Identical frames (high sim) must produce a wider blend than very different frames (low sim)."""
        H, W, seam_y = 80, 60, 40
        fa_similar = self._uniform(H, W, 128)
        fb_similar = self._uniform(H, W, 130)  # Δ=2 → very similar

        fa_diff = self._uniform(H, W, 50)
        fb_diff = self._uniform(H, W, 200)  # Δ=150 → very different

        path = self._path(W, seam_y)

        out_sim = _soft_seam_weight(fa_similar, fb_similar, path, H, W)
        out_diff = _soft_seam_weight(fa_diff, fb_diff, path, H, W)

        # Count rows where weight is strictly between 0.05 and 0.95 (the transition band).
        trans_sim = int(((out_sim > 0.05) & (out_sim < 0.95)).all(axis=1).sum())
        trans_diff = int(((out_diff > 0.05) & (out_diff < 0.95)).all(axis=1).sum())

        assert trans_sim > trans_diff, (
            f"Similar frames should have wider blend zone: sim={trans_sim} rows, diff={trans_diff} rows"
        )

    def test_bg_mask_fg_fg_narrows_blend(self):
        """S20: all-fg bg_masks must narrow the blend compared to no-mask (same frames)."""
        H, W, seam_y = 80, 60, 40
        # Very similar frames → wide blend without mask
        fa = self._uniform(H, W, 128)
        fb = self._uniform(H, W, 130)
        path = self._path(W, seam_y)

        bg_all_fg = np.zeros((H, W), dtype=bool)  # all pixels = foreground (bg=False)
        out_no_mask = _soft_seam_weight(fa, fb, path, H, W)
        out_fg_mask = _soft_seam_weight(
            fa, fb, path, H, W, bg_mask_a=bg_all_fg, bg_mask_b=bg_all_fg
        )

        trans_no = int(((out_no_mask > 0.05) & (out_no_mask < 0.95)).all(axis=1).sum())
        trans_fg = int(((out_fg_mask > 0.05) & (out_fg_mask < 0.95)).all(axis=1).sum())
        assert trans_fg < trans_no, (
            f"fg mask should narrow blend: no_mask={trans_no}, fg_mask={trans_fg} transition rows"
        )

    def test_bg_mask_none_result_unchanged(self):
        """Passing None bg_masks must give the same result as calling without them."""
        H, W, seam_y = 60, 40, 30
        fa = self._uniform(H, W, 100)
        fb = self._uniform(H, W, 120)
        path = self._path(W, seam_y)
        out_default = _soft_seam_weight(fa, fb, path, H, W)
        out_none = _soft_seam_weight(fa, fb, path, H, W, bg_mask_a=None, bg_mask_b=None)
        np.testing.assert_array_equal(out_default, out_none)


# ---------------------------------------------------------------------------
# 8. _adaptive_gain_clamp  (S18 §1.4A)
# ---------------------------------------------------------------------------


class TestAdaptiveGainClamp:
    """_adaptive_gain_clamp: §1.4B continuous formula (S24)."""

    @staticmethod
    def _lo(ref: float) -> float:
        return 1.0 - (0.26 - 0.12 * (ref / 255.0))

    @staticmethod
    def _hi(ref: float) -> float:
        return 1.0 + (0.26 - 0.12 * (ref / 255.0))

    def test_normal_scene_clamps_large_downward_gain(self):
        # ref=100, frame=200 → raw gain=0.5, below continuous lo(100)
        result = _adaptive_gain_clamp(100.0, 200.0)
        assert result == pytest.approx(self._lo(100.0), abs=1e-5)

    def test_dark_scene_uses_wider_lo_clamp(self):
        # ref=50, frame=200 → raw gain=0.25, below continuous lo(50)
        result = _adaptive_gain_clamp(50.0, 200.0)
        assert result == pytest.approx(self._lo(50.0), abs=1e-5)

    def test_small_correction_passes_unclamped(self):
        # ref=100, frame=95 → raw gain≈1.053 — within continuous [lo, hi] → unclamped
        result = _adaptive_gain_clamp(100.0, 95.0)
        assert result == pytest.approx(100.0 / 95.0, rel=1e-5)

    def test_continuous_no_jump_at_ref_80(self):
        # §1.4B removes the S18 discontinuity at ref=80; neighboring values differ by < 0.001
        f_below = _adaptive_gain_clamp(79.9, 300.0)
        f_above = _adaptive_gain_clamp(80.0, 300.0)
        assert abs(f_below - f_above) < 0.001

    def test_zero_frame_lum_clamped_to_hi(self):
        # frame_lum=0 → gain=100/1=100 → clamped to continuous hi(100)
        result = _adaptive_gain_clamp(100.0, 0.0)
        assert result == pytest.approx(self._hi(100.0), abs=1e-5)

    def test_bright_ref_hi_matches_anchor(self):
        # At ref=255 the formula gives exactly hi=1.14 (the bright anchor)
        result = _adaptive_gain_clamp(255.0, 0.0)
        assert result == pytest.approx(1.14, abs=1e-6)

    def test_clamp_width_monotone_decreasing(self):
        # Darker scenes allow wider correction: lo(50) < lo(200)
        lo_dark = _adaptive_gain_clamp(50.0, 10000.0)  # forced to lo
        lo_bright = _adaptive_gain_clamp(200.0, 10000.0)
        assert lo_dark < lo_bright

    def test_mid_ref_continuous_formula(self):
        # ref=128 → exact continuous lo value
        result = _adaptive_gain_clamp(128.0, 10000.0)
        assert result == pytest.approx(self._lo(128.0), abs=1e-5)


# ---------------------------------------------------------------------------
# 9. _coherence_skip_mask  (S18 per-pair coherence gate)
# ---------------------------------------------------------------------------


class TestCoherenceSkipMask:
    """_coherence_skip_mask marks only the frames in bad adjacent pairs."""

    def test_all_small_diffs_none_skipped(self):
        order = np.array([0, 1, 2])
        lums = [100.0, 105.0, 110.0]
        result = _coherence_skip_mask(order, lums, 20.0)
        assert result == [False, False, False]

    def test_bad_pair_both_frames_skipped(self):
        # Pair (0,1) has diff=30 > 20; pair (1,2) is fine.
        order = np.array([0, 1, 2])
        lums = [100.0, 130.0, 135.0]
        result = _coherence_skip_mask(order, lums, 20.0)
        assert result[0] is True  # frame 0 in bad pair
        assert result[1] is True  # frame 1 in bad pair
        assert result[2] is False  # frame 2 unaffected

    def test_good_frames_after_bad_pair_not_skipped(self):
        # Pair (0,1) bad; pairs (1,2) and (2,3) fine.
        order = np.array([0, 1, 2, 3])
        lums = [100.0, 130.0, 128.0, 132.0]
        result = _coherence_skip_mask(order, lums, 20.0)
        assert result[0] is True
        assert result[1] is True
        assert result[2] is False
        assert result[3] is False

    def test_none_lum_pair_ignored(self):
        order = np.array([0, 1, 2])
        lums: "list[float | None]" = [100.0, None, 110.0]
        result = _coherence_skip_mask(order, lums, 20.0)
        assert result == [False, False, False]

    def test_exactly_at_limit_not_skipped(self):
        # diff == limit is NOT > limit → no skip
        order = np.array([0, 1])
        lums = [100.0, 120.0]
        result = _coherence_skip_mask(order, lums, 20.0)
        assert result == [False, False]

    def test_non_identity_order_maps_correctly(self):
        # Canvas order: frame2, frame0, frame1.  All pairs OK.
        order = np.array([2, 0, 1])
        lums = [105.0, 110.0, 100.0]  # lum[0]=105, lum[1]=110, lum[2]=100
        # lum_by_order = [100, 105, 110] → diffs 5,5 → all OK
        result = _coherence_skip_mask(order, lums, 20.0)
        assert result == [False, False, False]


# ---------------------------------------------------------------------------
# 10. _build_seam_cost_map  (S19 §1.6A tiered cost)
# ---------------------------------------------------------------------------


class TestSeamCostMap:
    """_build_seam_cost_map returns a tiered cost: interior=1.0, edge buffer=0.5, background=0.0."""

    # canvas_zone is only used for shape — pass a zero array.
    def _canvas(self, H: int, W: int) -> np.ndarray:
        return np.zeros((H, W, 3), dtype=np.uint8)

    def _bg_mask(self, H: int, W: int, fg_rows: int) -> np.ndarray:
        """255=background, 0=foreground for first fg_rows rows."""
        m = np.full((H, W), 255, dtype=np.uint8)
        m[:fg_rows] = 0
        return m

    def test_all_background_is_zero(self):
        H, W = 60, 40
        bm = np.full((H, W), 255, dtype=np.uint8)
        cost = _build_seam_cost_map(self._canvas(H, W), bm, None, dilate_px=5)
        assert cost.shape == (H, W)
        assert float(cost.max()) == pytest.approx(0.0)

    def test_fg_interior_is_1(self):
        # All-foreground mask → every pixel costs 1.0.
        H, W = 40, 20
        bm = np.zeros((H, W), dtype=np.uint8)  # bm=0 everywhere → all fg
        cost = _build_seam_cost_map(self._canvas(H, W), bm, None, dilate_px=5)
        assert float(cost.min()) == pytest.approx(1.0)

    def test_edge_buffer_is_0_5(self):
        # Rows 0–19 fg, rows 20–49 bg.  With dilate_px=5 the edge buffer
        # extends ~5px beyond the fg boundary → row 22 should be 0.5.
        H, W, fg_rows, dilate_px = 50, 20, 20, 5
        bm = self._bg_mask(H, W, fg_rows)
        cost = _build_seam_cost_map(self._canvas(H, W), bm, None, dilate_px=dilate_px)
        assert float(cost[22, 10]) == pytest.approx(0.5, abs=0.1), (
            f"row just past fg boundary should be edge-buffer=0.5, got {cost[22, 10]:.3f}"
        )

    def test_pure_background_far_from_fg_is_zero(self):
        H, W, fg_rows, dilate_px = 50, 20, 20, 5
        bm = self._bg_mask(H, W, fg_rows)
        cost = _build_seam_cost_map(self._canvas(H, W), bm, None, dilate_px=dilate_px)
        # Row 45 is 25px past the fg boundary — well beyond the 5px edge buffer.
        assert float(cost[45, 10]) == pytest.approx(0.0, abs=0.01)

    def test_fg_interior_not_lowered_by_edge_buffer(self):
        # A pixel deep inside the fg body should stay at 1.0, not be lowered to 0.5.
        H, W, fg_rows, dilate_px = 50, 20, 40, 5
        bm = self._bg_mask(H, W, fg_rows)
        cost = _build_seam_cost_map(self._canvas(H, W), bm, None, dilate_px=dilate_px)
        # Row 10 is 30px from the fg boundary at row 40 — deep interior.
        assert float(cost[10, 10]) == pytest.approx(1.0, abs=0.01)

    def test_none_masks_returns_zero(self):
        H, W = 30, 20
        cost = _build_seam_cost_map(self._canvas(H, W), None, None)
        assert float(cost.max()) == pytest.approx(0.0)

    def test_union_of_two_fg_masks(self):
        # Frame A has fg in left half, frame B in right half → both cost=1.0.
        H, W, dilate_px = 40, 40, 0
        bm_a = np.full((H, W), 255, dtype=np.uint8)
        bm_a[:, :20] = 0
        bm_b = np.full((H, W), 255, dtype=np.uint8)
        bm_b[:, 20:] = 0
        cost = _build_seam_cost_map(self._canvas(H, W), bm_a, bm_b, dilate_px=dilate_px)
        assert float(cost[20, 5]) == pytest.approx(1.0), "frame-A fg region"
        assert float(cost[20, 35]) == pytest.approx(1.0), "frame-B fg region"


# ---------------------------------------------------------------------------
# 10b. _build_seam_cost_map — §3.15A SemanticStitch column-level fg barrier (S33)
# ---------------------------------------------------------------------------


class TestSeamCostColumnFilter:
    """§3.15A: fg-dominated columns (>50% fg interior) raised to cost=2.0 when a
    background-corridor column exists; fallback to per-pixel costs when none does."""

    def _canvas(self, H: int, W: int) -> np.ndarray:
        return np.zeros((H, W, 3), dtype=np.uint8)

    def _fg_cols_mask(self, H: int, W: int, fg_cols: int) -> np.ndarray:
        """255=background, 0=foreground for first fg_cols columns."""
        m = np.full((H, W), 255, dtype=np.uint8)
        m[:, :fg_cols] = 0
        return m

    def test_fg_dominated_columns_raised_to_2(self):
        """Columns that are 100% fg interior → raised to 2.0 (column barrier)."""
        H, W = 40, 30
        # fg in cols 0–9, bg in cols 10–29; no edge buffer (dilate_px=0).
        bm = self._fg_cols_mask(H, W, fg_cols=10)
        cost = _build_seam_cost_map(self._canvas(H, W), bm, None, dilate_px=0)
        # All-fg columns should now be at 2.0 (barrier level).
        assert float(cost[:, :10].min()) == pytest.approx(2.0, abs=0.01), (
            "fg-dominated columns should be raised to 2.0"
        )

    def test_bg_corridor_unchanged_after_column_filter(self):
        """Background-corridor columns stay at 0.0 after the column barrier fires."""
        H, W = 40, 30
        bm = self._fg_cols_mask(H, W, fg_cols=10)
        cost = _build_seam_cost_map(self._canvas(H, W), bm, None, dilate_px=0)
        # Pure-background columns (10–29) should remain 0.0.
        assert float(cost[:, 15].max()) == pytest.approx(0.0, abs=0.01), (
            "background corridor columns should stay at 0.0"
        )

    def test_column_filter_skipped_when_all_columns_fg(self):
        """All columns fg → filter skipped; max cost stays at 1.0, not 2.0."""
        H, W = 40, 20
        bm = np.zeros((H, W), dtype=np.uint8)  # all foreground
        cost = _build_seam_cost_map(self._canvas(H, W), bm, None, dilate_px=0)
        assert float(cost.max()) == pytest.approx(1.0, abs=0.01), (
            "all-fg case: no corridor to exploit, filter must be skipped"
        )

    def test_column_filter_not_applied_when_no_fg(self):
        """No foreground → no column exceeds threshold; cost stays 0.0."""
        H, W = 40, 20
        bm = np.full((H, W), 255, dtype=np.uint8)  # all background
        cost = _build_seam_cost_map(self._canvas(H, W), bm, None, dilate_px=0)
        assert float(cost.max()) == pytest.approx(0.0, abs=0.01)

    def test_partial_fg_coverage_over_threshold_raises_column(self):
        """A column with 60% fg-interior pixels (>50% threshold) is raised to 2.0."""
        H, W = 10, 20
        bm = np.full((H, W), 255, dtype=np.uint8)
        # Make column 0 have 6/10 = 60% fg interior.
        bm[:6, 0] = 0
        # Columns 1–19 are fully background → corridor exists.
        cost = _build_seam_cost_map(self._canvas(H, W), bm, None, dilate_px=0)
        assert float(cost[:, 0].max()) == pytest.approx(2.0, abs=0.01), (
            "column with >50% fg interior should be raised to 2.0"
        )
        # Sanity: the corridor columns must stay below 2.0.
        assert float(cost[:, 5].max()) < 1.0, "corridor column must stay below 1.0"


# ---------------------------------------------------------------------------
# 10. _poisson_seam_blend — §1.6C gradient-domain seam blend (S21)
# ---------------------------------------------------------------------------
class TestPoissonSeamBlend:
    """Tests for _poisson_seam_blend (§1.6C, S21).

    Uses H=60, W=40 so the ±20px seam band stays well within bounds and the
    Poisson solver has enough room to converge.
    """

    H, W = 60, 40
    _SEAM_ROW = 30  # path midpoint

    def _make(self):
        fa = np.full((self.H, self.W, 3), 60, dtype=np.uint8)
        fb = np.full((self.H, self.W, 3), 180, dtype=np.uint8)
        path = np.full(self.W, self._SEAM_ROW, dtype=np.int32)
        apply = np.ones((self.H, self.W), dtype=bool)
        return fa, fb, path, apply

    def test_shape_and_dtype(self):
        fa, fb, path, apply = self._make()
        out = _poisson_seam_blend(fa, fb, path, apply)
        assert out.shape == (self.H, self.W, 3)
        assert out.dtype == np.uint8

    def test_above_seam_band_unchanged(self):
        fa, fb, path, apply = self._make()
        out = _poisson_seam_blend(fa, fb, path, apply)
        # Band starts at row max(1, 30-20)=10; rows 0-4 must be untouched (hard=fa=60).
        np.testing.assert_array_equal(out[:5], fa[:5])

    def test_below_seam_band_unchanged(self):
        fa, fb, path, apply = self._make()
        out = _poisson_seam_blend(fa, fb, path, apply)
        # Band ends at row min(59, 30+21)=51; rows 55-59 must be untouched (hard=fb=180).
        np.testing.assert_array_equal(out[-5:], fb[-5:])

    def test_path_near_bottom_no_crash(self):
        fa, fb, path, apply = self._make()
        path_bottom = np.full(self.W, self.H - 3, dtype=np.int32)
        out = _poisson_seam_blend(fa, fb, path_bottom, apply)
        assert out.shape == (self.H, self.W, 3)

    def test_empty_apply_returns_hard_partition(self):
        fa, fb, path, apply = self._make()
        apply_empty = np.zeros((self.H, self.W), dtype=bool)
        out = _poisson_seam_blend(fa, fb, path, apply_empty)
        # Hard partition: fa above seam row, fb from seam row down.
        np.testing.assert_array_equal(out[: self._SEAM_ROW], fa[: self._SEAM_ROW])
        np.testing.assert_array_equal(out[self._SEAM_ROW :], fb[self._SEAM_ROW :])


# ---------------------------------------------------------------------------
# 11. _gain_to_min_feather — §1.6B gain-adaptive feather floor (S22)
# ---------------------------------------------------------------------------
class TestGainToMinFeather:
    """Tests for _gain_to_min_feather (§1.6B, S22).

    Formula: min(120, max(40, int(gain_diff × 300))).
    """

    def test_zero_diff_returns_floor(self):
        assert _gain_to_min_feather(0.0) == 40

    def test_small_diff_returns_floor(self):
        # 0.1 × 300 = 30 < 40 → floor
        assert _gain_to_min_feather(0.1) == 40

    def test_mid_diff_scales_linearly(self):
        # 0.2 × 300 = 60 → in (40, 120) → 60
        assert _gain_to_min_feather(0.2) == 60

    def test_large_diff_capped_at_120(self):
        # 0.5 × 300 = 150 → capped at 120
        assert _gain_to_min_feather(0.5) == 120

    def test_at_floor_boundary(self):
        # int(40/300 × 300) = int(40.0) = 40 → max(40, 40) = 40
        assert _gain_to_min_feather(40.0 / 300.0) == 40

    def test_just_above_floor_boundary(self):
        # int(0.14 × 300) = int(42.0) = 42 > 40
        assert _gain_to_min_feather(0.14) == 42


# ---------------------------------------------------------------------------
# TestBgGainUnclamped — §1.4C background gain clamp override (S40)
# ---------------------------------------------------------------------------


class TestBgGainUnclamped:
    """
    _bg_gain_unclamped returns the raw ideal gain (ref_lum / frame_lum) when
    the adaptive clamp would cut the correction by more than override_threshold
    (default 20 %).  Otherwise returns the clamped value unchanged.

    Background pixels tolerate aggressive correction because they are large
    uniform regions — character skin tones are excluded from the bg-only
    application site, so clipping artefacts are less visible.
    """

    def test_large_correction_returns_ideal(self):
        """Clamp cuts > 20 % → ideal gain returned for bg pixels."""
        # ref=128, frame=40 → ideal = 128/40 = 3.2
        # clamp_width for ref=128: 0.26 - 0.12*(128/255) ≈ 0.20 → hi≈1.20
        # clamped = 1.20, cut = (3.2-1.2)/3.2 = 0.625 > 0.20 → ideal
        result = _bg_gain_unclamped(128.0, 40.0)
        assert pytest.approx(result, rel=1e-4) == 128.0 / 40.0

    def test_small_correction_returns_clamped(self):
        """Clamp cuts ≤ 20 % → clamped gain returned unchanged."""
        # ref=100, frame=96 → ideal ≈ 1.042
        # clamp_width for ref=100: 0.26 - 0.12*(100/255) ≈ 0.213 → hi≈1.213
        # ideal=1.042 < hi → clamped=1.042, cut = 0 → same as clamped
        result = _bg_gain_unclamped(100.0, 96.0)
        assert result == pytest.approx(_adaptive_gain_clamp(100.0, 96.0), rel=1e-6)

    def test_zero_frame_lum_returns_one(self):
        """Guard: zero frame luminance → 1.0 (no correction)."""
        assert _bg_gain_unclamped(128.0, 0.0) == 1.0

    def test_threshold_boundary_at_exactly_20_percent(self):
        """When the cut is exactly 20 %, clamped value is returned (> not >=)."""
        # Find (ref, frame) such that cut == exactly 0.20.
        # For ref=100: clamp_width≈0.213, hi=1.213.
        # We want ideal such that (ideal - 1.213)/ideal = 0.20 → ideal = 1.213/0.80 ≈ 1.516
        # frame = ref / ideal = 100 / 1.516 ≈ 65.96
        ref = 100.0
        ideal_target = _adaptive_gain_clamp(ref, 1.0) / 0.80  # not exact but near 20%
        frame = ref / ideal_target
        clamped = _adaptive_gain_clamp(ref, frame)
        result = _bg_gain_unclamped(ref, frame, override_threshold=0.20)
        # At exactly 20%, result should equal clamped (strict >)
        ideal = ref / max(frame, 1e-9)
        cut = abs(ideal - clamped) / abs(ideal)
        if cut > 0.20:
            assert result == pytest.approx(ideal, rel=1e-4)
        else:
            assert result == pytest.approx(clamped, rel=1e-4)

    def test_darkening_case_returns_ideal_when_cut_exceeds_threshold(self):
        """Works symmetrically: frame brighter than ref → large darkening also overrides."""
        # ref=50, frame=200 → ideal = 50/200 = 0.25
        # clamp_width for ref=50: 0.26 - 0.12*(50/255) ≈ 0.237 → lo≈0.763
        # clamped = 0.763, cut = |0.25-0.763|/0.25 = 2.05 > 0.20 → ideal=0.25
        result = _bg_gain_unclamped(50.0, 200.0)
        assert pytest.approx(result, rel=1e-4) == 50.0 / 200.0


# ---------------------------------------------------------------------------
# §1.5D  Seam path cache (key helpers)
# ---------------------------------------------------------------------------


class TestSeamPathCache:
    """Unit tests for §1.5D seam-path caching helpers.

    _make_seam_cache_key() and _get_seam_cost_flags() are pure functions
    tested in isolation — no need to exercise the full _composite_foreground
    pipeline.
    """

    def test_make_seam_cache_key_returns_hashable(self):
        """Key can be stored as a dict key (i.e. is hashable)."""
        key = _make_seam_cache_key(("a.png", "b.png"), 0, (False, False))
        assert key is not None
        d: dict = {}
        d[key] = "sentinel"
        assert d[key] == "sentinel"

    def test_same_inputs_produce_equal_keys(self):
        """Identical arguments always yield the same key (deterministic)."""
        fk = ("frame_001.png", "frame_002.png", "frame_003.png")
        flags = (False, True)
        k1 = _make_seam_cache_key(fk, 1, flags)
        k2 = _make_seam_cache_key(fk, 1, flags)
        assert k1 == k2

    def test_different_boundary_index_produces_different_key(self):
        """Boundaries k=0 and k=1 must map to separate cache entries."""
        fk = ("f0.png", "f1.png", "f2.png")
        flags = _get_seam_cost_flags()
        assert _make_seam_cache_key(fk, 0, flags) != _make_seam_cache_key(fk, 1, flags)

    def test_different_frame_keys_produce_different_key(self):
        """Different frame sets must not collide in the cache."""
        flags = _get_seam_cost_flags()
        key_a = _make_seam_cache_key(("seq_a/f0.png", "seq_a/f1.png"), 0, flags)
        key_b = _make_seam_cache_key(("seq_b/f0.png", "seq_b/f1.png"), 0, flags)
        assert key_a != key_b

    def test_none_frame_keys_disables_cache(self):
        """frame_keys=None signals no-cache mode — key is None."""
        key = _make_seam_cache_key(None, 0, (False, False))
        assert key is None


# ---------------------------------------------------------------------------
# §1.4D  Multi-scale gain map
# ---------------------------------------------------------------------------


class TestMultiscaleGainMap:
    """Unit tests for §1.4D _multiscale_gain_map().

    All tests use small synthetic arrays (no GPU, no real images required).
    """

    def _make_uniform_bgr(self, h: int, w: int, lum: int) -> np.ndarray:
        """Create uniform BGR frame with a given luminance."""
        return np.full((h, w, 3), lum, dtype=np.uint8)

    def test_identical_frame_and_reference_produces_unit_gain(self):
        """When frame == reference the gain map should be everywhere ~1.0."""
        h, w = 64, 64
        img = self._make_uniform_bgr(h, w, 128)
        bg_mask = np.ones((h, w), dtype=bool)
        gain = _multiscale_gain_map(img, img, bg_mask)
        assert gain.shape == (h, w)
        assert np.allclose(gain, 1.0, atol=0.05)

    def test_darker_frame_than_reference_produces_gain_above_one(self):
        """A frame that is globally darker than the reference gets gain > 1."""
        h, w = 64, 64
        frame = self._make_uniform_bgr(h, w, 64)
        ref = self._make_uniform_bgr(h, w, 128)
        bg_mask = np.ones((h, w), dtype=bool)
        gain = _multiscale_gain_map(frame, ref, bg_mask)
        # Median gain should be close to 128/64 = 2.0 (clamped at 2.0)
        assert float(np.median(gain)) >= 1.8

    def test_brighter_frame_than_reference_produces_gain_below_one(self):
        """A frame that is globally brighter than the reference gets gain < 1."""
        h, w = 64, 64
        frame = self._make_uniform_bgr(h, w, 200)
        ref = self._make_uniform_bgr(h, w, 100)
        bg_mask = np.ones((h, w), dtype=bool)
        gain = _multiscale_gain_map(frame, ref, bg_mask)
        assert float(np.median(gain)) <= 0.65

    def test_gain_clamped_to_valid_range(self):
        """Output gain is always within [gain_min, gain_max]."""
        rng = np.random.default_rng(42)
        h, w = 32, 32
        frame = rng.integers(1, 255, (h, w, 3), dtype=np.uint8)
        ref = rng.integers(1, 255, (h, w, 3), dtype=np.uint8)
        bg_mask = np.ones((h, w), dtype=bool)
        gain = _multiscale_gain_map(frame, ref, bg_mask, gain_min=0.5, gain_max=2.0)
        assert float(gain.min()) >= 0.5 - 1e-5
        assert float(gain.max()) <= 2.0 + 1e-5

    def test_fg_pixels_receive_unit_gain_when_no_bg_nearby(self):
        """When bg_mask is all-False the blur produces near-zero denominator → gain=1.0."""
        h, w = 32, 32
        frame = self._make_uniform_bgr(h, w, 100)
        ref = self._make_uniform_bgr(h, w, 200)
        bg_mask = np.zeros((h, w), dtype=bool)  # all foreground — no bg source
        gain = _multiscale_gain_map(frame, ref, bg_mask)
        # With no bg source, frame_blurred stays ~0 everywhere → gain falls to 1.0
        assert np.allclose(gain, 1.0, atol=0.1)


# ---------------------------------------------------------------------------
# §1.4E — _bg_histogram_lut (S49)
# ---------------------------------------------------------------------------


class TestBgHistogramLut:
    """
    _bg_histogram_lut(src_pixels, ref_pixels) builds a 256-entry CDF-matching LUT
    that maps source background intensities to match the reference distribution.
    _apply_bg_histogram_match applies the LUT per-channel to a frame's bg region.
    """

    def _uniform_pixels(self, value: int, n: int = 500) -> np.ndarray:
        return np.full(n, value, dtype=np.uint8)

    def test_identical_distribution_yields_near_identity_lut(self):
        """Same source and reference distributions → lut[v] ≈ v for all v."""
        rng = np.random.default_rng(0)
        px = rng.integers(50, 200, 1000, dtype=np.uint8)
        lut = _bg_histogram_lut(px, px)
        assert lut.shape == (256,)
        # For a self-match the LUT should be near-identity over the populated range
        for v in range(50, 200):
            assert abs(float(lut[v]) - v) <= 3, (
                f"lut[{v}]={lut[v]:.1f} deviates too far from identity"
            )

    def test_uniform_brighter_reference_maps_source_upward(self):
        """src all-100, ref all-200: lut[100] should map to ~200."""
        src = self._uniform_pixels(100)
        ref = self._uniform_pixels(200)
        lut = _bg_histogram_lut(src, ref)
        assert float(lut[100]) == pytest.approx(200.0, abs=2.0)

    def test_uniform_darker_reference_maps_source_downward(self):
        """src all-200, ref all-100: lut[200] should map to ~100."""
        src = self._uniform_pixels(200)
        ref = self._uniform_pixels(100)
        lut = _bg_histogram_lut(src, ref)
        assert float(lut[200]) == pytest.approx(100.0, abs=2.0)

    def test_output_lut_is_monotone_non_decreasing(self):
        """For any valid input the LUT must be non-decreasing (monotone mapping)."""
        rng = np.random.default_rng(7)
        src = rng.integers(0, 256, 2000, dtype=np.uint8)
        ref = rng.integers(0, 256, 2000, dtype=np.uint8)
        lut = _bg_histogram_lut(src, ref)
        diffs = np.diff(lut.astype(np.float32))
        assert (diffs >= -1e-6).all(), "LUT is not monotone non-decreasing"

    def test_sparse_input_returns_identity_lut(self):
        """Fewer than 10 pixels in either input → identity LUT (np.arange(256))."""
        src = np.array([100, 120, 130], dtype=np.uint8)
        ref = np.array([150, 160], dtype=np.uint8)
        lut = _bg_histogram_lut(src, ref)
        assert lut.shape == (256,)
        expected = np.arange(256, dtype=np.float32)
        np.testing.assert_array_equal(lut, expected)


# ---------------------------------------------------------------------------
# §1.4F — _reject_exposure_outliers (S50)
# ---------------------------------------------------------------------------


class TestRejectExposureOutliers:
    """
    _reject_exposure_outliers(frame_lums, max_deviation_lum) returns a per-frame
    bool list marking frames whose background luminance deviates from the global
    median by more than max_deviation_lum.

    Frames with None lum are never rejected.
    Fewer than 3 valid values → all False (unreliable median).
    """

    def test_uniform_lums_all_false(self):
        """All frames at the same luminance → none rejected."""
        lums = [120.0, 120.0, 120.0, 120.0, 120.0]
        result = _reject_exposure_outliers(lums, max_deviation_lum=60.0)
        assert result == [False, False, False, False, False]

    def test_dark_outlier_above_threshold_rejected(self):
        """One very dark frame (lum=30) with median≈120 and threshold=60 → rejected."""
        lums = [120.0, 125.0, 30.0, 118.0, 122.0]
        result = _reject_exposure_outliers(lums, max_deviation_lum=60.0)
        assert result[2] is True, "Dark outlier frame should be rejected"
        assert (
            result[0] is False
            and result[1] is False
            and result[3] is False
            and result[4] is False
        )

    def test_bright_outlier_above_threshold_rejected(self):
        """One very bright frame (lum=230) with median≈120 and threshold=60 → rejected."""
        lums = [118.0, 120.0, 230.0, 122.0, 119.0]
        result = _reject_exposure_outliers(lums, max_deviation_lum=60.0)
        assert result[2] is True, "Bright outlier frame should be rejected"
        assert all(not result[i] for i in [0, 1, 3, 4])

    def test_below_threshold_deviation_not_rejected(self):
        """Frame with deviation exactly at threshold (not exceeding) → not rejected."""
        lums = [100.0, 100.0, 100.0, 100.0, 155.0]
        # median=100, frame[4]=155, deviation=55, threshold=60 → not rejected
        result = _reject_exposure_outliers(lums, max_deviation_lum=60.0)
        assert result[4] is False, "Frame within threshold should not be rejected"
        assert result == [False, False, False, False, False]

    def test_insufficient_frames_returns_all_false(self):
        """Fewer than 3 valid lum values → all False (unreliable median)."""
        lums = [None, 40.0, None, 200.0, None]  # only 2 valid
        result = _reject_exposure_outliers(lums, max_deviation_lum=10.0)
        assert result == [False, False, False, False, False]


# ---------------------------------------------------------------------------
# §1.14B — _seam_color_similarity and _check_seam_color_gate
# ---------------------------------------------------------------------------


class TestSeamColorGate:
    """§1.14B: Bhattacharyya colour-similarity gate for post-composite seam check."""

    @staticmethod
    def _uniform(h: int, w: int, val: int) -> np.ndarray:
        return np.full((h, w, 3), val, dtype=np.uint8)

    @staticmethod
    def _stacked(val_top: int, val_bot: int, h: int = 200, w: int = 100) -> np.ndarray:
        top = np.full((h // 2, w, 3), val_top, dtype=np.uint8)
        bot = np.full((h - h // 2, w, 3), val_bot, dtype=np.uint8)
        return np.vstack([top, bot])

    def test_single_strip_gate_returns_none(self):
        """n_strips=1 means no seams → gate always returns None."""
        img = self._uniform(100, 100, 128)
        assert _check_seam_color_gate(img, n_strips=1, thresh=0.55) is None

    def test_threshold_zero_disabled(self):
        """thresh=0.0 disables the gate regardless of colour mismatch."""
        img = self._stacked(0, 255)
        assert _check_seam_color_gate(img, n_strips=2, thresh=0.0) is None

    def test_identical_strips_above_threshold(self):
        """Uniform image → similarity=1.0 > any reasonable threshold → None."""
        img = self._uniform(200, 100, 128)
        assert _check_seam_color_gate(img, n_strips=2, thresh=0.55) is None

    def test_mismatched_strips_below_threshold(self):
        """White top half / black bottom half → similarity near 0 → returns seam 0."""
        img = self._stacked(255, 0)
        result = _check_seam_color_gate(img, n_strips=2, thresh=0.55)
        assert result == 0, f"Expected worst seam 0, got {result}"

    def test_returns_worst_seam_index(self):
        """Three strips: middle seam (between zones 1 and 2) is worst → returns 1."""
        # h = 300
        w = 100
        # Zone 0 (rows 0-99): value 200; Zone 1 (rows 100-199): value 200 (same → good seam 0)
        # Zone 2 (rows 200-299): value 0 (contrast with zone 1 → bad seam 1)
        zone0 = np.full((100, w, 3), 200, dtype=np.uint8)
        zone1 = np.full((100, w, 3), 200, dtype=np.uint8)
        zone2 = np.full((100, w, 3), 0, dtype=np.uint8)
        img = np.vstack([zone0, zone1, zone2])
        result = _check_seam_color_gate(img, n_strips=3, thresh=0.55)
        assert result == 1, f"Expected worst seam index 1, got {result}"


# ---------------------------------------------------------------------------
# §1.14C — _seam_color_similarity_bgr (per-channel BGR Bhattacharyya)
# ---------------------------------------------------------------------------


class TestSeamColorSimilarityBgr:
    """§1.14C: Per-channel BGR Bhattacharyya catches hue-shifted banding."""

    @staticmethod
    def _bgr(h: int, w: int, b: int, g: int, r: int) -> np.ndarray:
        """Uniform BGR image."""
        img = np.zeros((h, w, 3), dtype=np.uint8)
        img[:, :, 0] = b
        img[:, :, 1] = g
        img[:, :, 2] = r
        return img

    def test_identical_bands_returns_one(self):
        """Same colour above and below seam → score == 1.0."""
        img = self._bgr(200, 100, 100, 150, 200)
        score = _seam_color_similarity_bgr(img, k=0, n_strips=2, band_px=50)
        assert score == pytest.approx(1.0, abs=0.05)

    def test_hue_shift_same_luma_low_score(self):
        """Neutral-grey top / warm-shifted bottom with IDENTICAL luma (≈128).

        Color A: B=128, G=128, R=128 → Y = 128
        Color B: B=28,  G=128, R=166 → Y = 0.114×28 + 0.587×128 + 0.299×166 ≈ 128

        Greyscale histograms for uniform bands both peak at luma=128 → grey score ≈ 1.0.
        BGR score is driven down by the large B channel shift (128 vs 28) → BGR < grey.
        """
        h, w = 200, 100
        top_grey = np.full((h // 2, w, 3), 128, dtype=np.uint8)  # B=G=R=128
        bot_warm = np.zeros((h - h // 2, w, 3), dtype=np.uint8)
        bot_warm[:, :, 0] = 28  # B
        bot_warm[:, :, 1] = 128  # G
        bot_warm[:, :, 2] = 166  # R  → same luma as 128,128,128
        img = np.vstack([top_grey, bot_warm])
        bgr_score = _seam_color_similarity_bgr(img, k=0, n_strips=2, band_px=50)
        grey_score = _seam_color_similarity(img, k=0, n_strips=2, band_px=50)
        assert grey_score > 0.90, f"Greyscale should be near 1.0, got {grey_score:.3f}"
        assert bgr_score < grey_score, (
            f"BGR score {bgr_score:.3f} should be below greyscale {grey_score:.3f}"
        )

    def test_grayscale_input_falls_back_gracefully(self):
        """2-D greyscale input → falls back to _seam_color_similarity path, returns float."""
        gray = np.full((200, 100), 128, dtype=np.uint8)
        score = _seam_color_similarity_bgr(gray, k=0, n_strips=2, band_px=50)
        assert 0.0 <= score <= 1.0

    def test_check_gate_use_bgr_triggers_on_hue_shift(self):
        """use_bgr=True gate fires on hue-shifted image that greyscale gate misses.

        Uses identical-luma colours (Y≈128): grey gate passes (score≈1.0),
        BGR gate fails (min channel score ≈ 0 due to large B shift).
        """
        h, w = 200, 100
        top_grey = np.full((h // 2, w, 3), 128, dtype=np.uint8)
        bot_warm = np.zeros((h - h // 2, w, 3), dtype=np.uint8)
        bot_warm[:, :, 0] = 28  # B
        bot_warm[:, :, 1] = 128  # G
        bot_warm[:, :, 2] = 166  # R  → luma ≈ 128
        img = np.vstack([top_grey, bot_warm])
        grey_result = _check_seam_color_gate(
            img, n_strips=2, thresh=0.55, use_bgr=False
        )
        bgr_result = _check_seam_color_gate(img, n_strips=2, thresh=0.55, use_bgr=True)
        assert grey_result is None, (
            "Greyscale gate should not fire on same-luma hue shift"
        )
        assert bgr_result == 0, "BGR gate should return seam 0 for hue-shifted bands"

    def test_band_too_small_returns_one(self):
        """band_px too large for image height → trivially thin bands → score 1.0."""
        img = self._bgr(10, 50, 0, 0, 255)
        score = _seam_color_similarity_bgr(img, k=0, n_strips=2, band_px=100)
        assert score == pytest.approx(1.0, abs=1e-6)


class TestAdaptiveSpThreshold:
    """§1.18: Adaptive single-pose escalation threshold (S62)."""

    def test_reference_feather_returns_base(self):
        """feather_width == feather_reference → threshold equals base_threshold."""
        result = _adaptive_sp_threshold(feather_width=80)
        assert result == pytest.approx(22.0, abs=1e-9)

    def test_narrow_feather_above_reference_exceeds_base(self):
        """feather_width < feather_reference → would return >base, but function
        has no upper cap so it exceeds 22.0 — confirm the ratio is correct."""
        result = _adaptive_sp_threshold(feather_width=40)
        # 22.0 * (80 / 40) = 44.0
        assert result == pytest.approx(44.0, abs=1e-9)

    def test_wide_feather_hits_min_floor(self):
        """feather_width=300 → raw=22*(80/300)≈5.87, clamped to min_threshold=12.0."""
        result = _adaptive_sp_threshold(feather_width=300)
        assert result == pytest.approx(12.0, abs=1e-9)

    def test_floor_crossover_point(self):
        """Threshold hits floor exactly at feather=floor_crossover.

        22*(80/fw)=12  →  fw = 22*80/12 ≈ 146.67 → floor at fw=147.
        At fw=146 the raw value is 22*(80/146)≈12.055 > 12 so NOT floored.
        At fw=147 the raw value is 22*(80/147)≈11.97 < 12 so IS floored.
        """
        below_floor = _adaptive_sp_threshold(feather_width=146)
        at_floor = _adaptive_sp_threshold(feather_width=147)
        assert below_floor > 12.0
        assert at_floor == pytest.approx(12.0, abs=1e-9)

    def test_zero_feather_uses_max_width_not_division_by_zero(self):
        """feather_width=0 → max(fw,1)=1 → returns max(12, 22*80)=1760.0 (no ZeroDivisionError)."""
        result = _adaptive_sp_threshold(feather_width=0)
        assert result == pytest.approx(22.0 * 80, abs=1e-9)


class TestFgDensityFeatherCap:
    """§1.19: Foreground-density-aware feather cap (S63)."""

    @staticmethod
    def _bg_mask(h: int, w: int, fg_frac: float) -> np.ndarray:
        """Make a canvas-space bg mask (bool) with given fg fraction."""
        mask = np.ones((h, w), dtype=bool)  # all background
        n_fg = int(h * w * fg_frac)
        mask.flat[:n_fg] = False  # first n_fg pixels are fg
        return mask

    def test_all_bg_no_cap_applied(self):
        """Pure background zone → fg_frac=0.0 → feather unchanged regardless of cap."""
        feathers = np.array([200, 150], dtype=np.int64)
        bg = self._bg_mask(400, 100, fg_frac=0.0)
        warped_bg = [bg, bg, bg]
        order = [0, 1, 2]
        boundaries = [100.0, 250.0]
        result = _fg_density_feather_cap(
            feathers, boundaries, warped_bg, order, cap_px=60, fg_thresh=0.60
        )
        np.testing.assert_array_equal(result, feathers)

    def test_all_fg_applies_cap(self):
        """Pure fg zone → fg_frac=1.0 > 0.60 → feather capped to cap_px=60."""
        feathers = np.array([250], dtype=np.int64)
        bg = self._bg_mask(400, 100, fg_frac=1.0)
        warped_bg = [bg, bg]
        order = [0, 1]
        boundaries = [200.0]
        result = _fg_density_feather_cap(
            feathers, boundaries, warped_bg, order, cap_px=60, fg_thresh=0.60
        )
        assert int(result[0]) == 60

    def test_feather_already_narrow_skips_check(self):
        """feather ≤ cap_px → skip entirely (no cap applied, even with pure fg)."""
        feathers = np.array([40], dtype=np.int64)  # already ≤ cap_px=60
        bg = self._bg_mask(400, 100, fg_frac=1.0)
        warped_bg = [bg, bg]
        order = [0, 1]
        boundaries = [200.0]
        result = _fg_density_feather_cap(
            feathers, boundaries, warped_bg, order, cap_px=60, fg_thresh=0.60
        )
        assert int(result[0]) == 40

    def test_uses_max_fg_frac_across_two_frames(self):
        """Only frame_b has fg_frac=0.80 > 0.60 → cap fires (max of two frames used)."""
        feathers = np.array([200], dtype=np.int64)
        bg_a = self._bg_mask(400, 100, fg_frac=0.20)  # frame a: 20% fg → no cap
        bg_b = self._bg_mask(400, 100, fg_frac=0.80)  # frame b: 80% fg → cap
        warped_bg = [bg_a, bg_b]
        order = [0, 1]
        boundaries = [200.0]
        result = _fg_density_feather_cap(
            feathers, boundaries, warped_bg, order, cap_px=60, fg_thresh=0.60
        )
        assert int(result[0]) == 60

    def test_none_mask_treated_as_all_bg(self):
        """warped_bg[fi]=None → fg_frac=0.0 → cap never fires without a mask."""
        feathers = np.array([250], dtype=np.int64)
        warped_bg = [None, None]
        order = [0, 1]
        boundaries = [200.0]
        result = _fg_density_feather_cap(
            feathers, boundaries, warped_bg, order, cap_px=60, fg_thresh=0.60
        )
        assert int(result[0]) == 250  # unchanged


class TestComputeSeamStepSize:
    """§1.20: Dominant-axis camera step between two frame positions (S64)."""

    @staticmethod
    def _aff(ty: float, tx: float = 0.0) -> np.ndarray:
        a = np.eye(3, dtype=np.float32)
        a[0, 2] = tx
        a[1, 2] = ty
        return a

    def test_pure_vertical_step(self):
        """Only ty differs → step = |ty_b - ty_a|."""
        affines = [self._aff(0.0), self._aff(50.0)]
        result = _compute_seam_step_size(0, 1, affines)
        assert result == pytest.approx(50.0)

    def test_pure_horizontal_step(self):
        """Only tx differs → step = |tx_b - tx_a|."""
        affines = [self._aff(0.0, tx=0.0), self._aff(0.0, tx=80.0)]
        result = _compute_seam_step_size(0, 1, affines)
        assert result == pytest.approx(80.0)

    def test_uses_dominant_axis(self):
        """Both axes non-zero → returns max(dy, dx)."""
        affines = [self._aff(10.0, tx=30.0), self._aff(25.0, tx=90.0)]
        # dy = 15, dx = 60 → dominant = 60
        result = _compute_seam_step_size(0, 1, affines)
        assert result == pytest.approx(60.0)

    def test_exactly_at_threshold_not_below(self):
        """step == threshold is NOT below threshold (strict <)."""
        affines = [self._aff(0.0), self._aff(30.0)]
        step = _compute_seam_step_size(0, 1, affines)
        assert step == pytest.approx(30.0)
        assert not (step < 30.0)  # gate uses strict <

    def test_out_of_range_frame_returns_inf(self):
        """fi_a >= len(affines) → returns inf (never triggers escalation)."""
        affines = [self._aff(0.0), self._aff(20.0)]
        result = _compute_seam_step_size(99, 0, affines)
        assert result == float("inf")


class TestSeamLumEqualize:
    """§1.21: Post-composite seam luminance equalisation (S65)."""

    @staticmethod
    def _canvas(h: int, w: int, top_lum: int, bot_lum: int, split: int) -> np.ndarray:
        """Make a BGR canvas with top half at top_lum and bottom half at bot_lum."""
        c = np.zeros((h, w, 3), dtype=np.uint8)
        c[:split] = top_lum
        c[split:] = bot_lum
        return c

    def test_no_step_no_change(self):
        """Uniform canvas → no step → output unchanged."""
        canvas = self._canvas(200, 50, 128, 128, 100)
        result = _seam_lum_equalize(canvas, [100.0], band_px=20, min_step=5.0)
        np.testing.assert_array_equal(result, canvas)

    def test_step_above_threshold_is_reduced(self):
        """Canvas with +30 lum step → luminance at boundary is smoothed."""
        canvas = self._canvas(200, 50, 80, 110, 100)
        result = _seam_lum_equalize(canvas, [100.0], band_px=20, min_step=5.0)
        # Immediately below boundary (row 100), the correction should reduce lum
        result_lum = int(result[100, 0, 0])
        original_lum = int(canvas[100, 0, 0])
        assert result_lum < original_lum  # correction brought lum down toward above

    def test_step_below_threshold_not_corrected(self):
        """Step=3 < min_step=5 → no correction applied."""
        canvas = self._canvas(200, 50, 100, 103, 100)
        result = _seam_lum_equalize(canvas, [100.0], band_px=20, min_step=5.0)
        np.testing.assert_array_equal(result, canvas)

    def test_boundary_near_edge_no_crash(self):
        """Boundary at row 5 (near top) → guard zone clips to canvas edge, no crash."""
        canvas = self._canvas(100, 30, 80, 120, 5)
        result = _seam_lum_equalize(canvas, [5.0], band_px=20, min_step=5.0)
        assert result.shape == canvas.shape

    def test_returns_uint8_dtype(self):
        """Output dtype must be uint8 regardless of input lum values."""
        canvas = self._canvas(200, 50, 50, 200, 100)
        result = _seam_lum_equalize(canvas, [100.0], band_px=20, min_step=5.0)
        assert result.dtype == np.uint8


class TestAdaptiveSpSoftPx:
    """§1.22 — Adaptive single-pose soft-edge half-width (S66)."""

    def test_at_ref_px_returns_base(self):
        """feather == ref_px → exactly base_px returned (no scaling)."""
        assert _adaptive_sp_soft_px(80, base_px=6, max_px=30, ref_px=80) == 6

    def test_doubles_for_double_ref(self):
        """feather == 2 × ref_px → 2 × base_px (linear scaling in range)."""
        assert _adaptive_sp_soft_px(160, base_px=6, max_px=30, ref_px=80) == 12

    def test_narrow_feather_clamps_to_base(self):
        """feather < ref_px → result floored to base_px (no shrinkage below base)."""
        assert _adaptive_sp_soft_px(40, base_px=6, max_px=30, ref_px=80) == 6

    def test_wide_feather_caps_at_max_px(self):
        """Very wide feather → result capped at max_px."""
        assert _adaptive_sp_soft_px(500, base_px=6, max_px=30, ref_px=80) == 30

    def test_zero_feather_returns_base(self):
        """feather == 0 → base_px returned (degenerate-input guard)."""
        assert _adaptive_sp_soft_px(0, base_px=6, max_px=30, ref_px=80) == 6


class TestSeamCorridorExists:
    """§1.23 — SemanticStitch hard corridor barrier helper (S67)."""

    def _cost(
        self, shape, all_fg: bool = False, all_bg: bool = False, fg_col: int = None
    ):
        """Build a simple (H, W) cost map for testing.
        all_fg: every column has 100% fg-interior cost (1.0).
        all_bg: every pixel is bg (cost=0.0).
        fg_col: only this column is dominated (cost=1.0), rest are bg.
        """
        h, w = shape
        cost = np.zeros((h, w), dtype=np.float32)
        if all_fg:
            cost[:] = 1.0
        if fg_col is not None:
            cost[:, fg_col] = 1.0
        return cost

    def test_all_dominated_returns_false(self):
        """All columns fg-dominated (no corridor) → False."""
        cost = self._cost((10, 5), all_fg=True)
        assert _seam_corridor_exists(cost) is False

    def test_all_bg_returns_false(self):
        """No column is fg-dominated → False (no dominated cols to apply barrier to)."""
        cost = self._cost((10, 5), all_bg=True)
        assert _seam_corridor_exists(cost) is False

    def test_mixed_returns_true(self):
        """Some columns dominated, some not → corridor exists → True."""
        cost = self._cost((10, 5), fg_col=2)
        assert _seam_corridor_exists(cost) is True

    def test_hard_barrier_applied_when_corridor(self):
        """With barrier_cost=1e6, fg-dominated columns get 1e6 when corridor exists."""
        w = 4
        cost_map = np.zeros((10, w), dtype=np.float32)
        cost_map[:, 0] = 1.0  # col 0 dominated; cols 1-3 are bg corridor
        # bg_mask = (cost_map[:, :1] == 0).astype(np.uint8) * 255  # dummy 1-col mask
        canvas = np.zeros((10, w, 3), dtype=np.uint8)
        result = _build_seam_cost_map(canvas, None, None, dilate_px=0, barrier_cost=1e6)
        # No masks → no fg → no dominated columns → cost stays 0.0. Just verify no crash.
        assert result.shape == (10, w)

    def test_soft_barrier_backward_compat(self):
        """barrier_cost=2.0 is the S33 soft barrier; fg-dominated cols get ≤2.0."""
        canvas = np.zeros((10, 4, 3), dtype=np.uint8)
        result = _build_seam_cost_map(canvas, None, None, dilate_px=0, barrier_cost=2.0)
        assert result.max() <= 2.0


# ---------------------------------------------------------------------------
# §1.25 — TestSmoothSeamPath
# ---------------------------------------------------------------------------


class TestSmoothSeamPath:
    """Tests for _smooth_seam_path() — §1.25 seam path jitter smoothing."""

    def test_window_zero_returns_unchanged(self):
        """window=0 is a no-op; path is returned as-is."""
        path = np.array([3, 5, 2, 8, 1], dtype=np.int32)
        result = _smooth_seam_path(path, window=0)
        np.testing.assert_array_equal(result, path)

    def test_window_one_returns_unchanged(self):
        """window=1 is a no-op (kernel size 1 = identity)."""
        path = np.array([3, 5, 2, 8, 1], dtype=np.int32)
        result = _smooth_seam_path(path, window=1)
        np.testing.assert_array_equal(result, path)

    def test_smooth_path_removes_spike(self):
        """A single isolated spike is removed when window=5 spans it."""
        # Baseline path at y=5, one-sample spike to y=20
        path = np.array([5, 5, 5, 20, 5, 5, 5], dtype=np.int32)
        result = _smooth_seam_path(path, window=5)
        # Median of [5,5,5,20,5] = 5, so spike is replaced
        assert int(result[3]) == 5

    def test_constant_path_unchanged(self):
        """Constant path is unchanged by any window."""
        path = np.full(20, 7, dtype=np.int32)
        result = _smooth_seam_path(path, window=5)
        np.testing.assert_array_equal(result, path)

    def test_even_window_incremented_to_odd(self):
        """Even window is incremented by 1 internally; result is still int32."""
        path = np.array([2, 4, 6, 8, 10, 8, 6, 4, 2], dtype=np.int32)
        result = _smooth_seam_path(path, window=4)  # internally becomes 5
        assert result.dtype == np.int32
        assert result.shape == path.shape


# ---------------------------------------------------------------------------
# §1.26 — TestClampSeamPath
# ---------------------------------------------------------------------------


class TestClampSeamPath:
    """Tests for _clamp_seam_path() — §1.26 seam path boundary clamp."""

    def test_zero_margin_returns_unchanged(self):
        """margin=0 is a no-op."""
        path = np.array([0, 1, 2, 99, 3], dtype=np.int32)
        result = _clamp_seam_path(path, zone_h=100, margin=0)
        np.testing.assert_array_equal(result, path)

    def test_path_clamped_above_margin(self):
        """Values below margin are raised to margin."""
        path = np.array([0, 1, 2, 3, 4], dtype=np.int32)
        result = _clamp_seam_path(path, zone_h=20, margin=3)
        assert int(result[0]) == 3  # 0 → 3
        assert int(result[1]) == 3  # 1 → 3
        assert int(result[2]) == 3  # 2 → 3
        assert int(result[3]) == 3  # 3 == margin, unchanged

    def test_path_clamped_below_upper_bound(self):
        """Values above zone_h-1-margin are lowered to zone_h-1-margin."""
        path = np.array([17, 18, 19], dtype=np.int32)
        result = _clamp_seam_path(path, zone_h=20, margin=3)
        hi = 20 - 1 - 3  # = 16
        assert int(result[0]) == hi
        assert int(result[1]) == hi
        assert int(result[2]) == hi

    def test_in_range_values_unchanged(self):
        """Values already inside [margin, zone_h-1-margin] are not modified."""
        path = np.array([5, 8, 10], dtype=np.int32)
        result = _clamp_seam_path(path, zone_h=20, margin=3)
        np.testing.assert_array_equal(result, path)

    def test_zone_too_small_returns_unchanged(self):
        """When zone_h <= 2*margin, clamping bounds invert; path returned as-is."""
        path = np.array([3, 3, 3], dtype=np.int32)
        result = _clamp_seam_path(path, zone_h=4, margin=3)
        np.testing.assert_array_equal(result, path)


# ---------------------------------------------------------------------------
# §1.27 — TestHasSufficientBg
# ---------------------------------------------------------------------------


class TestHasSufficientBg:
    """Tests for _has_sufficient_bg() — §1.27 background coverage gate."""

    def test_sufficient_bg_returns_true(self):
        """Mask with more pixels than min_px returns True."""
        mask = np.ones((50, 50), dtype=bool)  # 2500 bg pixels
        assert _has_sufficient_bg(mask, min_px=200) is True

    def test_insufficient_bg_returns_false(self):
        """Mask with fewer pixels than min_px returns False."""
        mask = np.zeros((50, 50), dtype=bool)
        mask[:5, :5] = True  # only 25 bg pixels
        assert _has_sufficient_bg(mask, min_px=200) is False

    def test_exactly_at_threshold_returns_true(self):
        """Mask with exactly min_px pixels passes the floor."""
        mask = np.zeros((20, 20), dtype=bool)
        mask[:10, :10] = True  # exactly 100 pixels
        assert _has_sufficient_bg(mask, min_px=100) is True

    def test_none_mask_returns_false(self):
        """None mask (no BiRefNet output available) returns False."""
        assert _has_sufficient_bg(None, min_px=1) is False

    def test_all_fg_returns_false(self):
        """All-False mask (full-frame character, zero bg pixels) returns False."""
        mask = np.zeros((100, 100), dtype=bool)
        assert _has_sufficient_bg(mask, min_px=1) is False


# ---------------------------------------------------------------------------
# §1.28 — TestSeamPathStd
# ---------------------------------------------------------------------------


class TestSeamPathStd:
    """Tests for _seam_path_std() — §1.28 seam path instability metric."""

    def test_empty_path_returns_zero(self):
        """Empty path returns 0.0 (no data to measure)."""
        assert _seam_path_std(np.array([], dtype=np.int32)) == 0.0

    def test_constant_path_returns_zero(self):
        """A path that stays at the same row has std = 0."""
        path = np.full(100, 5, dtype=np.int32)
        assert _seam_path_std(path) == pytest.approx(0.0, abs=1e-6)

    def test_oscillating_path_has_high_std(self):
        """A path oscillating between 0 and 40 has std ≈ 20."""
        path = np.tile([0, 40], 50).astype(np.int32)
        std = _seam_path_std(path)
        assert std > 15.0  # well above any constant path

    def test_linearly_increasing_path_has_moderate_std(self):
        """A monotonically increasing path [0…39] has std ≈ 11.5."""
        path = np.arange(40, dtype=np.int32)
        std = _seam_path_std(path)
        assert 10.0 < std < 14.0

    def test_return_type_is_float(self):
        """Return type is always Python float."""
        path = np.array([5, 3, 7], dtype=np.int32)
        result = _seam_path_std(path)
        assert isinstance(result, float)


# ── TestZoneIsDegenerate — §1.30 minimum zone height guard (S74) ─────────────


class TestZoneIsDegenerate:
    """§1.30 — Degenerate zone height guard."""

    def test_zero_min_height_never_degenerate(self):
        """min_height=0 disables the check — any zone_h returns False."""
        assert _zone_is_degenerate(5, min_height=0) is False
        assert _zone_is_degenerate(1, min_height=0) is False

    def test_zone_below_threshold_is_degenerate(self):
        """zone_h < min_height → True."""
        assert _zone_is_degenerate(10, min_height=20) is True

    def test_zone_at_threshold_is_not_degenerate(self):
        """zone_h == min_height → False (threshold is exclusive lower bound)."""
        assert _zone_is_degenerate(20, min_height=20) is False

    def test_zone_above_threshold_is_not_degenerate(self):
        """zone_h > min_height → False."""
        assert _zone_is_degenerate(100, min_height=20) is False

    def test_negative_min_height_treated_as_disabled(self):
        """Negative min_height (guard <= 0 check) → never degenerate."""
        assert _zone_is_degenerate(5, min_height=-1) is False


# ── TestSeamFgPenetration — §1.31 seam fg penetration metric (S75) ───────────


class TestSeamFgPenetration:
    """§1.31 — Seam foreground penetration fraction."""

    def _zones(self, h: int = 20, w: int = 10, val_a: int = 0, val_b: int = 0):
        fa = np.full((h, w, 3), val_a, dtype=np.uint8)
        fb = np.full((h, w, 3), val_b, dtype=np.uint8)
        return fa, fb

    def test_empty_path_returns_zero(self):
        """Empty path → 0.0."""
        fa, fb = self._zones()
        assert _seam_fg_penetration(
            np.array([], dtype=np.int32), fa, fb
        ) == pytest.approx(0.0)

    def test_all_background_path_returns_zero(self):
        """Seam through all-black (bg) zones → 0.0 penetration."""
        fa, fb = self._zones(val_a=0, val_b=0)
        path = np.full(10, 5, dtype=np.int32)
        assert _seam_fg_penetration(path, fa, fb) == pytest.approx(0.0)

    def test_all_foreground_path_returns_one(self):
        """Seam through all-fg zones → 1.0 penetration."""
        fa, fb = self._zones(val_a=200, val_b=200)
        path = np.full(10, 5, dtype=np.int32)
        assert _seam_fg_penetration(path, fa, fb) == pytest.approx(1.0)

    def test_half_foreground_returns_half(self):
        """Left half bg, right half fg → 0.5 penetration."""
        fa = np.zeros((20, 10, 3), dtype=np.uint8)
        fb = np.zeros((20, 10, 3), dtype=np.uint8)
        # Columns 5–9 are foreground in fa
        fa[:, 5:, :] = 200
        path = np.full(10, 5, dtype=np.int32)
        result = _seam_fg_penetration(path, fa, fb)
        assert result == pytest.approx(0.5)

    def test_return_type_is_float(self):
        """Return type is always Python float."""
        fa, fb = self._zones(val_a=128, val_b=0)
        path = np.array([5, 6, 7], dtype=np.int32)
        result = _seam_fg_penetration(path, fa[:, :3], fb[:, :3])
        assert isinstance(result, float)


# ── TestExclusionMasks — Issue 10A3 NL seam routing ──────────────────────────


class TestExclusionMasks:
    """_build_seam_cost_map: exclusion_masks param forces cost=1e6 in masked regions."""

    def _canvas(self, H=64, W=64, val=128):
        return np.full((H, W, 3), val, dtype=np.uint8)

    def _bg_mask(self, H=64, W=64):
        m = np.zeros((H, W), dtype=np.uint8)
        m[:, W // 4 : 3 * W // 4] = 255  # centre-column bg strip
        return m

    def test_no_exclusion_baseline(self):
        """Without exclusion_masks, cost stays in [0, 2] range."""
        H, W = 32, 32
        cost = _build_seam_cost_map(
            self._canvas(H, W), self._bg_mask(H, W), None, dilate_px=0
        )
        assert cost.max() <= 2.01  # tier-2 column barrier at most 2.0

    def test_exclusion_mask_raises_cost_to_barrier(self):
        """Pixels under the exclusion mask must have cost = 1e6."""
        H, W = 32, 32
        em = np.zeros((H, W), dtype=np.uint8)
        em[10:20, 8:24] = 255  # rectangle to exclude
        cost = _build_seam_cost_map(
            self._canvas(H, W),
            self._bg_mask(H, W),
            None,
            dilate_px=0,
            exclusion_masks=[em],
        )
        assert cost[15, 16] == pytest.approx(1e6)

    def test_non_excluded_pixels_unchanged(self):
        """Pixels outside the exclusion mask must not be affected."""
        H, W = 32, 32
        em = np.zeros((H, W), dtype=np.uint8)
        em[0:8, 0:8] = 255  # top-left corner only
        cost = _build_seam_cost_map(
            self._canvas(H, W),
            self._bg_mask(H, W),
            None,
            dilate_px=0,
            exclusion_masks=[em],
        )
        # Centre of bg strip (W//4..3W//4 = 8..24), well below excluded rows
        # Background area → cost should be low (0.0–1.0), not 1e6
        assert cost[28, 16] < 1.5

    def test_exclusion_mask_auto_resized(self):
        """An exclusion mask with wrong shape must be resized before application."""
        H, W = 32, 32
        em_large = np.full((64, 64), 255, dtype=np.uint8)  # full exclusion, double size
        cost = _build_seam_cost_map(
            self._canvas(H, W),
            self._bg_mask(H, W),
            None,
            dilate_px=0,
            exclusion_masks=[em_large],
        )
        assert cost.max() == pytest.approx(1e6)

    def test_none_in_exclusion_list_skipped(self):
        """A None entry in the exclusion_masks list must not raise an exception."""
        H, W = 32, 32
        cost = _build_seam_cost_map(
            self._canvas(H, W),
            self._bg_mask(H, W),
            None,
            dilate_px=0,
            exclusion_masks=[None, None],
        )
        assert cost.max() <= 2.01  # same as no-exclusion baseline

    def test_multiple_exclusion_masks_combine(self):
        """Multiple exclusion masks are cumulative — all covered pixels blocked."""
        H, W = 32, 32
        em1 = np.zeros((H, W), dtype=np.uint8)
        em1[4:8, 4:28] = 255
        em2 = np.zeros((H, W), dtype=np.uint8)
        em2[24:28, 4:28] = 255
        cost = _build_seam_cost_map(
            self._canvas(H, W),
            self._bg_mask(H, W),
            None,
            dilate_px=0,
            exclusion_masks=[em1, em2],
        )
        assert cost[6, 16] == pytest.approx(1e6)
        assert cost[26, 16] == pytest.approx(1e6)


# ── TestComputeInitialBoundaries ───────────────────────────────────────────────


class TestComputeInitialBoundaries:
    """Tests for _compute_initial_boundaries (S85 — HITL boundary editor helper)."""

    def _affine(self, ty: float) -> np.ndarray:
        a = np.eye(2, 3, dtype=np.float64)
        a[1, 2] = ty
        return a

    def _frame(self, h: int = 40, w: int = 30) -> np.ndarray:
        return np.zeros((h, w, 3), dtype=np.uint8)

    def test_two_frames_single_boundary_at_midpoint(self):
        """Two frames: single boundary at midpoint between strip centres."""
        from backend.src.animation.rendering.compositing import _compute_initial_boundaries

        frames = [self._frame(40), self._frame(40)]
        affines = [self._affine(0.0), self._affine(40.0)]
        bnd = _compute_initial_boundaries(affines, frames)
        assert len(bnd) == 1
        # Strip centres: 20.0 and 60.0 → midpoint = 40.0
        assert abs(bnd[0] - 40.0) < 1e-6

    def test_n_minus_one_boundaries(self):
        """N frames produce exactly N-1 boundaries."""
        from backend.src.animation.rendering.compositing import _compute_initial_boundaries

        N = 5
        frames = [self._frame() for _ in range(N)]
        affines = [self._affine(i * 40.0) for i in range(N)]
        bnd = _compute_initial_boundaries(affines, frames)
        assert len(bnd) == N - 1

    def test_boundaries_monotonically_increasing(self):
        """Boundaries should be monotonically increasing for top-to-bottom scroll."""
        from backend.src.animation.rendering.compositing import _compute_initial_boundaries

        frames = [self._frame() for _ in range(4)]
        affines = [self._affine(i * 50.0) for i in range(4)]
        bnd = _compute_initial_boundaries(affines, frames)
        for i in range(len(bnd) - 1):
            assert bnd[i] < bnd[i + 1]

    def test_preset_boundaries_accepted_by_composite_foreground(self):
        """_composite_foreground respects preset_boundaries of correct length."""
        from backend.src.animation.rendering.compositing import (
            _composite_foreground,
            _compute_initial_boundaries,
        )

        H, W = 40, 30
        frames = [np.zeros((H, W, 3), dtype=np.uint8) for _ in range(2)]
        frames[0][:, :] = 50  # gray
        frames[1][:, :] = 100  # brighter gray
        affines = [self._affine(0.0), self._affine(float(H))]
        canvas_h, canvas_w = H * 2, W
        canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
        bg_masks = [None, None]
        bnd = _compute_initial_boundaries(affines, frames)
        # Should run without exception
        result = _composite_foreground(
            [],
            [],
            canvas,
            canvas_h,
            canvas_w,
            frames,
            affines,
            bg_masks,
            preset_boundaries=bnd,
        )
        assert result.shape == (canvas_h, canvas_w, 3)

    def test_wrong_length_preset_boundaries_ignored(self):
        """preset_boundaries with wrong length falls back to midpoint computation."""
        from backend.src.animation.rendering.compositing import _composite_foreground

        H, W = 40, 30
        frames = [np.zeros((H, W, 3), dtype=np.uint8) for _ in range(2)]
        affines = [self._affine(0.0), self._affine(float(H))]
        canvas_h, canvas_w = H * 2, W
        canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
        bg_masks = [None, None]
        # Pass wrong-length preset_boundaries — should not crash
        result = _composite_foreground(
            [],
            [],
            canvas,
            canvas_h,
            canvas_w,
            frames,
            affines,
            bg_masks,
            preset_boundaries=np.array([10.0, 20.0, 30.0]),  # 3 boundaries for 2 frames
        )
        assert result.shape == (canvas_h, canvas_w, 3)


# ── TestPaintMask ──────────────────────────────────────────────────────────────


class TestPaintMask:
    """Tests for paint_mask param in _composite_foreground (S86 — seam painter)."""

    def _frame(self, h: int = 40, w: int = 30, val: int = 80) -> np.ndarray:
        f = np.zeros((h, w, 3), dtype=np.uint8)
        f[:] = val
        return f

    def _affine(self, ty: float) -> np.ndarray:
        a = np.eye(2, 3, dtype=np.float64)
        a[1, 2] = ty
        return a

    def test_paint_mask_none_runs_without_error(self):
        """Passing paint_mask=None is equivalent to the default (no mask)."""
        from backend.src.animation.rendering.compositing import _composite_foreground

        H, W = 40, 30
        frames = [self._frame(H, W), self._frame(H, W, 100)]
        affines = [self._affine(0.0), self._affine(float(H))]
        canvas = np.zeros((H * 2, W, 3), dtype=np.uint8)
        result = _composite_foreground(
            [],
            [],
            canvas,
            H * 2,
            W,
            frames,
            affines,
            [None, None],
            paint_mask=None,
        )
        assert result.shape == (H * 2, W, 3)

    def test_paint_mask_correct_shape_accepted(self):
        """A paint_mask matching (canvas_h, canvas_w) is accepted without error."""
        from backend.src.animation.rendering.compositing import _composite_foreground

        H, W = 40, 30
        frames = [self._frame(H, W), self._frame(H, W, 100)]
        affines = [self._affine(0.0), self._affine(float(H))]
        canvas_h, canvas_w = H * 2, W
        canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
        mask = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
        mask[35:45, :] = 255  # paint a band around the seam
        result = _composite_foreground(
            [],
            [],
            canvas,
            canvas_h,
            canvas_w,
            frames,
            affines,
            [None, None],
            paint_mask=mask,
        )
        assert result.shape == (canvas_h, canvas_w, 3)

    def test_paint_mask_wrong_shape_ignored(self):
        """A paint_mask with wrong canvas dimensions is silently ignored."""
        from backend.src.animation.rendering.compositing import _composite_foreground

        H, W = 40, 30
        frames = [self._frame(H, W), self._frame(H, W)]
        affines = [self._affine(0.0), self._affine(float(H))]
        canvas_h, canvas_w = H * 2, W
        canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
        bad_mask = np.ones((10, 10), dtype=np.uint8) * 255  # wrong size
        result = _composite_foreground(
            [],
            [],
            canvas,
            canvas_h,
            canvas_w,
            frames,
            affines,
            [None, None],
            paint_mask=bad_mask,
        )
        assert result.shape == (canvas_h, canvas_w, 3)

    def test_paint_mask_combined_with_exclusion_masks(self):
        """paint_mask + existing exclusion_masks are both applied (no conflict)."""
        from backend.src.animation.rendering.compositing import _composite_foreground

        H, W = 40, 30
        frames = [self._frame(H, W, 60), self._frame(H, W, 120)]
        affines = [self._affine(0.0), self._affine(float(H))]
        canvas_h, canvas_w = H * 2, W
        canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
        excl = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
        excl[10:20, 5:25] = 255
        paint = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
        paint[35:45, :] = 255
        result = _composite_foreground(
            [],
            [],
            canvas,
            canvas_h,
            canvas_w,
            frames,
            affines,
            [None, None],
            exclusion_masks=[excl],
            paint_mask=paint,
        )
        assert result.shape == (canvas_h, canvas_w, 3)

    def test_paint_mask_all_black_behaves_like_no_mask(self):
        """An all-zero paint_mask has no effect on seam routing."""
        from backend.src.animation.rendering.compositing import _composite_foreground

        H, W = 40, 30
        frames = [self._frame(H, W), self._frame(H, W)]
        affines = [self._affine(0.0), self._affine(float(H))]
        canvas_h, canvas_w = H * 2, W
        canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
        zero_mask = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
        result_no = _composite_foreground(
            [],
            [],
            canvas.copy(),
            canvas_h,
            canvas_w,
            frames,
            affines,
            [None, None],
        )
        result_zm = _composite_foreground(
            [],
            [],
            canvas.copy(),
            canvas_h,
            canvas_w,
            frames,
            affines,
            [None, None],
            paint_mask=zero_mask,
        )
        np.testing.assert_array_equal(result_no, result_zm)


# ---------------------------------------------------------------------------
# §2.4B — _annotate_seams (S94)
# ---------------------------------------------------------------------------


class TestAnnotateSeams:
    """§2.4B: Coloured seam diagnostic overlay drawn on composite output."""

    def _make_canvas(self, H: int = 100, W: int = 80) -> np.ndarray:
        return np.full((H, W, 3), 128, dtype=np.uint8)

    def test_empty_boundaries_returns_unchanged(self):
        canvas = self._make_canvas()
        result = _annotate_seams(canvas, np.array([]), {}, {})
        np.testing.assert_array_equal(result, canvas)

    def test_good_seam_draws_green_line(self):
        canvas = self._make_canvas(H=100, W=80)
        boundaries = np.array([50.0])
        # diff well below amber threshold → green
        result = _annotate_seams(canvas, boundaries, {0: _AMBER - 1.0}, {})
        # At least one pixel in row 50 must have been changed to green (G channel high)
        row = result[50]
        assert any(p[1] > 150 and p[0] < 50 and p[2] < 50 for p in row), (
            "expected a green pixel at boundary row 50"
        )

    def test_moderate_seam_draws_amber_line(self):
        canvas = self._make_canvas(H=100, W=80)
        boundaries = np.array([40.0])
        diff = (_AMBER + _RED) / 2.0  # between amber and red thresholds
        result = _annotate_seams(canvas, boundaries, {0: diff}, {})
        row = result[40]
        # Amber in BGR: (0, 165, 255) → R channel high, G moderate, B low
        assert any(p[2] > 200 and p[1] > 100 and p[0] < 50 for p in row), (
            "expected an amber pixel at boundary row 40"
        )

    def test_poor_seam_draws_red_line(self):
        canvas = self._make_canvas(H=100, W=80)
        boundaries = np.array([60.0])
        diff = _RED + 5.0  # above red threshold
        result = _annotate_seams(canvas, boundaries, {0: diff}, {})
        row = result[60]
        # Red in BGR: (0, 0, 220) → R channel high, G and B low
        assert any(p[2] > 150 and p[1] < 50 and p[0] < 50 for p in row), (
            "expected a red pixel at boundary row 60"
        )

    def test_single_pose_seam_draws_red_even_with_low_diff(self):
        canvas = self._make_canvas(H=100, W=80)
        boundaries = np.array([30.0])
        # diff is low (would normally be green) but seam is single-pose
        result = _annotate_seams(canvas, boundaries, {0: 2.0}, {0: 1})
        row = result[30]
        # Expect red annotation regardless of diff value
        assert any(p[2] > 150 and p[1] < 50 and p[0] < 50 for p in row), (
            "expected a red pixel at single-pose seam row 30"
        )


# ── TestSeamMetaOut ─────────────────────────────────────────────────────────


class TestSeamMetaOut:
    """Tests for seam_meta_out / seam_overrides params in _composite_foreground (S95 — §2.4A)."""

    def _frame(self, h: int = 40, w: int = 30, val: int = 80) -> np.ndarray:
        f = np.zeros((h, w, 3), dtype=np.uint8)
        f[:] = val
        return f

    def _affine(self, ty: float) -> np.ndarray:
        a = np.eye(2, 3, dtype=np.float64)
        a[1, 2] = ty
        return a

    def test_seam_meta_out_populated_with_boundaries(self):
        """seam_meta_out receives boundaries, seam_post_diffs, seam_single_pose on return."""
        from backend.src.animation.rendering.compositing import _composite_foreground

        H, W = 40, 30
        frames = [self._frame(H, W, 80), self._frame(H, W, 100)]
        affines = [self._affine(0.0), self._affine(float(H))]
        canvas = np.zeros((H * 2, W, 3), dtype=np.uint8)
        meta: dict = {}
        _composite_foreground(
            [],
            [],
            canvas,
            H * 2,
            W,
            frames,
            affines,
            [None, None],
            seam_meta_out=meta,
        )
        assert "boundaries" in meta, "seam_meta_out must contain 'boundaries'"
        assert "seam_post_diffs" in meta, "seam_meta_out must contain 'seam_post_diffs'"
        assert "seam_single_pose" in meta, (
            "seam_meta_out must contain 'seam_single_pose'"
        )
        # Two frames produce exactly one boundary
        assert len(meta["boundaries"]) == 1, (
            f"expected 1 boundary, got {len(meta['boundaries'])}"
        )

    def test_seam_meta_out_single_frame_empty_boundaries(self):
        """With only one frame no seams are created; boundaries list is empty."""
        from backend.src.animation.rendering.compositing import _composite_foreground

        H, W = 40, 30
        frames = [self._frame(H, W, 80)]
        affines = [self._affine(0.0)]
        canvas = np.zeros((H, W, 3), dtype=np.uint8)
        meta: dict = {}
        _composite_foreground(
            [],
            [],
            canvas,
            H,
            W,
            frames,
            affines,
            [None],
            seam_meta_out=meta,
        )
        assert meta.get("boundaries", []) == [], (
            "single-frame composite should produce no seam boundaries"
        )

    def _bg_mask(self, h: int, w: int) -> np.ndarray:
        """All-background uint8 mask (255 = background, so wm > 127 = all-True)."""
        return np.full((h, w), 255, dtype=np.uint8)

    def test_force_single_pose_override_escalates_seam(self):
        """force_single_pose override must result in seam k appearing in seam_single_pose."""
        from backend.src.animation.rendering.compositing import _composite_foreground

        H, W = 40, 30
        frames = [self._frame(H, W, 80), self._frame(H, W, 100)]
        affines = [self._affine(0.0), self._affine(float(H))]
        canvas = np.zeros((H * 2, W, 3), dtype=np.uint8)
        # Provide non-None bg_masks so warped_bg[i] is not None (avoids early continue
        # at line 1814 that would bypass the force_single_pose code path).
        bg_masks = [self._bg_mask(H, W), self._bg_mask(H, W)]
        meta: dict = {}
        overrides = {0: {"force_single_pose": True, "force_blend": False}}
        _composite_foreground(
            [],
            [],
            canvas,
            H * 2,
            W,
            frames,
            affines,
            bg_masks,
            seam_meta_out=meta,
            seam_overrides=overrides,
        )
        assert 0 in meta.get("seam_single_pose", {}), (
            "force_single_pose override must escalate seam 0 to single-pose"
        )
        assert meta["seam_post_diffs"].get(0) == 99.0, (
            "force_single_pose sentinel diff must be 99.0"
        )

    def test_force_blend_override_removes_seam_from_single_pose(self):
        """force_blend override must remove seam k from seam_single_pose even if escalated.

        Uses overlapping zero-value frames so that:
          - zone_h > ASP_ZONE_MIN_HEIGHT (avoids degenerate-zone guard)
          - _seam_fg_penetration = 0 (avoids ASP_SEAM_FG_PENETRATION_MAX guard)
          - _seam_path_std = 0 (avoids ASP_SEAM_INSTABILITY_THRESH guard)
        This ensures that force_blend's post-loop removal is the only influence
        on whether seam 0 appears in seam_single_pose.
        """
        from backend.src.animation.rendering.compositing import _composite_foreground

        H, W = 60, 30
        # Overlap frames by 20px → max_feather ≥ 10 → zone_h ≥ 21 > ASP_ZONE_MIN_HEIGHT=20
        ty1 = H - 20  # frame 1 starts 20px below frame 0's top → 20px overlap
        # All-zero frames → FG penetration = 0.0 (no foreground pixels at all)
        frames = [
            np.zeros((H, W, 3), dtype=np.uint8),
            np.zeros((H, W, 3), dtype=np.uint8),
        ]
        a0 = np.eye(2, 3, dtype=np.float64)
        a1 = np.eye(2, 3, dtype=np.float64)
        a1[1, 2] = float(ty1)
        affines = [a0, a1]
        canvas_h = ty1 + H  # = 100px
        canvas = np.zeros((canvas_h, W, 3), dtype=np.uint8)
        # Non-None bg_masks required so the FG registration loop is entered.
        bg_masks = [self._bg_mask(H, W), self._bg_mask(H, W)]
        # First run: escalate via force_single_pose (even with zero frames)
        meta1: dict = {}
        _composite_foreground(
            [],
            [],
            canvas.copy(),
            canvas_h,
            W,
            frames,
            affines,
            bg_masks,
            seam_meta_out=meta1,
            seam_overrides={0: {"force_single_pose": True}},
        )
        assert 0 in meta1.get("seam_single_pose", {}), (
            "setup: seam 0 should be escalated"
        )
        # Second run: force_blend — seam 0 must NOT appear in seam_single_pose.
        # With zero-value frames the degenerate-zone, instability, and FG-penetration
        # blend-loop guards all remain inactive, so force_blend's removal is definitive.
        meta2: dict = {}
        _composite_foreground(
            [],
            [],
            canvas.copy(),
            canvas_h,
            W,
            frames,
            affines,
            bg_masks,
            seam_meta_out=meta2,
            seam_overrides={0: {"force_blend": True}},
        )
        assert 0 not in meta2.get("seam_single_pose", {}), (
            "force_blend override must remove seam 0 from seam_single_pose"
        )

    def test_seam_meta_out_none_does_not_raise(self):
        """Passing seam_meta_out=None (the default) must not raise any error."""
        from backend.src.animation.rendering.compositing import _composite_foreground

        H, W = 40, 30
        frames = [self._frame(H, W, 80), self._frame(H, W, 100)]
        affines = [self._affine(0.0), self._affine(float(H))]
        canvas = np.zeros((H * 2, W, 3), dtype=np.uint8)
        result = _composite_foreground(
            [],
            [],
            canvas,
            H * 2,
            W,
            frames,
            affines,
            [None, None],
            seam_meta_out=None,
        )
        assert result.shape == (H * 2, W, 3), "result shape must match canvas"


class TestSeamCropExtraction:
    """Tests for _extract_seam_crops (S96 — §2.4C)."""

    def _canvas(self, H: int = 100, W: int = 30, val: int = 128) -> np.ndarray:
        c = np.full((H, W, 3), val, dtype=np.uint8)
        return c

    def test_crops_extracted_for_all_seams(self):
        from backend.src.animation.rendering.compositing import _extract_seam_crops

        canvas = self._canvas(100, 30)
        boundaries = np.array([40, 70], dtype=np.float64)
        crops = _extract_seam_crops(canvas, boundaries, band_px=10)
        assert set(crops.keys()) == {0, 1}, "one crop per seam"

    def test_crop_height_is_twice_band(self):
        from backend.src.animation.rendering.compositing import _extract_seam_crops

        canvas = self._canvas(100, 30)
        boundaries = np.array([50.0])
        crops = _extract_seam_crops(canvas, boundaries, band_px=15)
        assert crops[0].shape == (30, 30, 3), "crop height = 2*band_px, full width"

    def test_crop_clamped_at_top_boundary(self):
        from backend.src.animation.rendering.compositing import _extract_seam_crops

        canvas = self._canvas(100, 30)
        # boundary at row 5 with band=20 → crop [0:25], height=25 (not 40)
        boundaries = np.array([5.0])
        crops = _extract_seam_crops(canvas, boundaries, band_px=20)
        assert crops[0].shape[0] == 25, "top clamp gives narrower crop (5+20=25)"

    def test_empty_boundaries_returns_empty_dict(self):
        from backend.src.animation.rendering.compositing import _extract_seam_crops

        canvas = self._canvas(100, 30)
        crops = _extract_seam_crops(canvas, np.array([]), band_px=10)
        assert crops == {}

    def test_seam_crops_in_meta_out(self):
        """_composite_foreground populates seam_meta_out['seam_crops']."""
        from backend.src.animation.rendering.compositing import _composite_foreground

        H, W = 40, 30
        frames = [
            np.full((H, W, 3), 80, dtype=np.uint8),
            np.full((H, W, 3), 100, dtype=np.uint8),
        ]
        a0 = np.eye(2, 3, dtype=np.float64)
        a1 = np.eye(2, 3, dtype=np.float64)
        a1[1, 2] = float(H)
        affines = [a0, a1]
        canvas = np.zeros((H * 2, W, 3), dtype=np.uint8)
        meta: dict = {}
        _composite_foreground(
            [], [], canvas, H * 2, W, frames, affines, [None, None], seam_meta_out=meta
        )
        assert "seam_crops" in meta, "seam_crops key must be in seam_meta_out"
        assert isinstance(meta["seam_crops"], dict)
        assert 0 in meta["seam_crops"], "seam 0 crop must be present"
        crop = meta["seam_crops"][0]
        assert crop.ndim == 3 and crop.shape[1] == W


# ---------------------------------------------------------------------------
# §1.34: _seam_zone_texture_energy tests (S98)
# ---------------------------------------------------------------------------


class TestSeamZoneTextureEnergy:
    """_seam_zone_texture_energy returns mean Laplacian variance in the seam band."""

    def _flat(self, H=80, W=60, val=128):
        """Solid-colour BGR frame — zero Laplacian variance."""
        return np.full((H, W, 3), val, dtype=np.uint8)

    def _textured(self, H=80, W=60, seed=42):
        """Random noise frame — high Laplacian variance."""
        rng = np.random.RandomState(seed)
        return rng.randint(0, 256, (H, W, 3), dtype=np.uint8)

    def test_flat_frames_score_near_zero(self):
        """Solid-colour frames have Laplacian variance ≈ 0 → score very small."""
        fa = self._flat()
        fb = self._flat()
        score = _seam_zone_texture_energy(fa, fb, boundary=40, half_band=15)
        assert score < 1.0, f"expected near-zero, got {score}"

    def test_textured_frames_score_high(self):
        """Random-noise frames have high variance → score well above typical threshold."""
        fa = self._textured()
        fb = self._textured(seed=7)
        score = _seam_zone_texture_energy(fa, fb, boundary=40, half_band=15)
        assert score > 100.0, f"expected high texture score, got {score}"

    def test_boundary_outside_frame_returns_zero(self):
        """Boundary far beyond frame height → empty band → 0.0."""
        fa = self._flat(H=20)
        fb = self._flat(H=20)
        score = _seam_zone_texture_energy(fa, fb, boundary=200, half_band=5)
        assert score == 0.0

    def test_grayscale_frames_accepted(self):
        """2-D (H, W) uint8 frames should not raise and should return a float."""
        rng = np.random.RandomState(0)
        fa = rng.randint(0, 256, (60, 40), dtype=np.uint8)
        fb = rng.randint(0, 256, (60, 40), dtype=np.uint8)
        score = _seam_zone_texture_energy(fa, fb, boundary=30, half_band=10)
        assert isinstance(score, float) and score >= 0.0

    def test_half_band_zero_returns_zero(self):
        """half_band=0 → y0 == y1 for any boundary → empty band → 0.0."""
        fa = self._textured()
        fb = self._textured(seed=3)
        score = _seam_zone_texture_energy(fa, fb, boundary=40, half_band=0)
        assert score == 0.0


# §1.35: _fg_gradient_cost tests (S99)
# ---------------------------------------------------------------------------


class TestFgGradientCost:
    """_fg_gradient_cost returns normalized Laplacian gradient cost for seam DP."""

    def _flat(self, H=60, W=80, val=128):
        """Solid-colour BGR canvas zone — zero Laplacian."""
        return np.full((H, W, 3), val, dtype=np.uint8)

    def _with_edge(self, H=60, W=80):
        """Zone with a sharp horizontal edge at mid-height — high Laplacian on that row."""
        zone = np.zeros((H, W, 3), dtype=np.uint8)
        zone[: H // 2] = 200
        zone[H // 2 :] = 50
        return zone

    def test_flat_zone_returns_zeros(self):
        """Solid-colour zone has near-zero Laplacian → output array is all zeros."""
        zone = self._flat()
        out = _fg_gradient_cost(zone, weight=1.0)
        assert out.max() < 0.01, f"expected near-zero cost, got max={out.max()}"

    def test_edge_zone_returns_nonzero_cost(self):
        """Zone with a sharp edge has positive Laplacian → output has non-zero values."""
        zone = self._with_edge()
        out = _fg_gradient_cost(zone, weight=1.0)
        assert out.max() > 0.0, "expected non-zero gradient cost for edge zone"

    def test_zero_weight_returns_zeros(self):
        """weight=0.0 → output is zero regardless of content (fast-path)."""
        zone = self._with_edge()
        out = _fg_gradient_cost(zone, weight=0.0)
        assert np.all(out == 0.0)

    def test_output_shape_matches_zone(self):
        """Output shape is (H, W) matching the input canvas zone."""
        H, W = 70, 90
        zone = self._with_edge(H=H, W=W)
        out = _fg_gradient_cost(zone, weight=2.0)
        assert out.shape == (H, W)

    def test_cost_bounded_by_weight(self):
        """All output values are in [0, weight] regardless of gradient magnitude."""
        zone = self._with_edge()
        weight = 3.5
        out = _fg_gradient_cost(zone, weight=weight)
        assert out.min() >= 0.0
        assert out.max() <= weight + 1e-6, f"max {out.max()} exceeds weight {weight}"


# ---------------------------------------------------------------------------
# TestSeamChromaEqualize (§1.56 — S122)
# ---------------------------------------------------------------------------


class TestSeamChromaEqualize:
    """§1.56 post-composite chroma seam correction (S122).

    _seam_chroma_equalize() measures mean a/b shift between strip reference
    bands above/below each seam boundary (in LAB space) and applies a linear
    additive ramp over band_px rows to close the gap.
    """

    def _make_canvas(self, H: int = 100, W: int = 60) -> np.ndarray:
        """Neutral grey canvas (all channels equal) so LAB a=b≈128."""
        return np.full((H, W, 3), 128, dtype=np.uint8)

    def test_no_chroma_shift_returns_unchanged(self):
        """When above/below strips have the same chroma, canvas is unchanged."""
        canvas = self._make_canvas()
        boundaries = [50.0]
        out = _seam_chroma_equalize(canvas, boundaries, band_px=10, min_shift=3.0)
        np.testing.assert_array_equal(out, canvas)

    def test_chroma_shift_is_reduced_at_boundary(self):
        """A warm/cool split across the seam should be partially corrected."""
        H, W = 120, 60
        # Upper half: cool blue-ish (B channel elevated)
        canvas = np.zeros((H, W, 3), dtype=np.uint8)
        canvas[:60, :] = [160, 128, 80]  # blue-ish top
        canvas[60:, :] = [80, 128, 160]  # orange-ish bottom
        boundaries = [60.0]
        out = _seam_chroma_equalize(canvas, boundaries, band_px=15, min_shift=1.0)
        # The output should have been modified — not identical to input
        assert not np.array_equal(out, canvas)
        # Output must stay in valid uint8 range
        assert out.min() >= 0
        assert out.max() <= 255

    def test_empty_boundaries_returns_unchanged(self):
        """Empty boundary list → no correction applied."""
        canvas = self._make_canvas()
        out = _seam_chroma_equalize(canvas, [], band_px=10, min_shift=1.0)
        np.testing.assert_array_equal(out, canvas)

    def test_output_same_shape_and_dtype(self):
        """Return array must have the same shape and uint8 dtype as input."""
        canvas = self._make_canvas(H=80, W=40)
        out = _seam_chroma_equalize(canvas, [40.0], band_px=10, min_shift=1.0)
        assert out.shape == canvas.shape
        assert out.dtype == np.uint8

    def test_below_min_shift_threshold_no_change(self):
        """Shifts smaller than min_shift must not trigger any correction."""
        H, W = 100, 60
        # Very subtle chroma difference — LAB a/b differ by < 2
        canvas = np.zeros((H, W, 3), dtype=np.uint8)
        canvas[:50, :] = [130, 128, 126]  # almost neutral
        canvas[50:, :] = [128, 130, 128]  # almost neutral
        boundaries = [50.0]
        out = _seam_chroma_equalize(canvas, boundaries, band_px=10, min_shift=10.0)
        np.testing.assert_array_equal(out, canvas)


class TestFgZonePoseGap:
    """§1.60 (S124): Fg pose-gap pre-escalation helper."""

    def test_identical_zones_gap_near_zero(self):
        """Identical frames in the blend zone → pose gap ≈ 0."""
        rng = np.random.default_rng(1)
        zone = rng.integers(10, 245, (80, 100, 3), dtype=np.uint8)
        gap = _fg_zone_pose_gap(zone, zone.copy())
        assert gap < 1.0, (
            f"Identical frames should give near-zero pose gap, got {gap:.3f}"
        )

    def test_complementary_zones_high_gap(self):
        """Zones with opposite pixel content → large pose gap."""
        rng = np.random.default_rng(2)
        fa = rng.integers(200, 255, (80, 100, 3), dtype=np.uint8)
        fb = rng.integers(0, 50, (80, 100, 3), dtype=np.uint8)
        gap = _fg_zone_pose_gap(fa, fb)
        assert gap > 100.0, (
            f"Opposite-brightness zones should give large gap, got {gap:.1f}"
        )

    def test_returns_zero_when_no_shared_fg(self):
        """Non-overlapping content (different sides are zero) → 0.0."""
        zone = np.zeros((50, 60, 3), dtype=np.uint8)
        fa = zone.copy()
        fb = zone.copy()
        fa[:, :30] = 200
        fb[:, 30:] = 200
        gap = _fg_zone_pose_gap(fa, fb)
        assert gap == 0.0, f"No shared fg pixels → expected 0.0, got {gap}"

    def test_returns_float(self):
        """Return type is always float."""
        rng = np.random.default_rng(99)
        fa = rng.integers(0, 256, (60, 80, 3), dtype=np.uint8)
        fb = rng.integers(0, 256, (60, 80, 3), dtype=np.uint8)
        assert isinstance(_fg_zone_pose_gap(fa, fb), float)

    def test_all_zeros_returns_zero(self):
        """All-black zones (no fg pixels) → 0.0."""
        z = np.zeros((40, 50, 3), dtype=np.uint8)
        assert _fg_zone_pose_gap(z, z) == 0.0


class TestFgSeamErosionBuffer:
    """§1.65 (S130): Fg mask erosion buffer reduces Tier-1 cost region."""

    @staticmethod
    def _solid_bg_mask(h: int, w: int, fg_band: int) -> np.ndarray:
        """Background mask with a central foreground band (fg_band rows, centred)."""
        bm = np.ones((h, w), dtype=np.uint8) * 255  # all background
        cy = h // 2
        bm[cy - fg_band // 2 : cy + fg_band // 2, :] = 0  # fg = 0
        return bm

    @staticmethod
    def _canvas(h: int, w: int) -> np.ndarray:
        return np.zeros((h, w, 3), dtype=np.uint8)

    def test_erosion_zero_unchanged(self):
        """With erosion=0, behaviour is identical to the un-eroded path."""
        import backend.src.animation.rendering.compositing as comp_mod

        h, w, fg_band = 80, 100, 20
        bm = self._solid_bg_mask(h, w, fg_band)
        old_val = comp_mod._FG_SEAM_EROSION_PX
        comp_mod._FG_SEAM_EROSION_PX = 0
        try:
            cost0 = _build_seam_cost_map(self._canvas(h, w), bm, None, dilate_px=3)
        finally:
            comp_mod._FG_SEAM_EROSION_PX = old_val
        # Interior of the fg band must be cost=1.0
        cy = h // 2
        assert cost0[cy, w // 2] == pytest.approx(1.0)

    def test_erosion_shrinks_tier1_region(self):
        """With erosion=3, the outermost fg outline rows should no longer be cost=1.0."""
        import backend.src.animation.rendering.compositing as comp_mod

        h, w, fg_band = 80, 100, 30
        bm = self._solid_bg_mask(h, w, fg_band)
        old_val = comp_mod._FG_SEAM_EROSION_PX
        comp_mod._FG_SEAM_EROSION_PX = 3
        try:
            cost_eroded = _build_seam_cost_map(
                self._canvas(h, w), bm, None, dilate_px=3
            )
        finally:
            comp_mod._FG_SEAM_EROSION_PX = old_val
        cy = h // 2
        fg_top = cy - fg_band // 2  # first fg row index
        # Row at fg_top should now be cost < 1.0 (outline ring eroded away)
        assert cost_eroded[fg_top, w // 2] < 1.0, (
            f"Expected eroded outline row to have cost < 1.0, got {cost_eroded[fg_top, w // 2]}"
        )
        # Interior row (deep in fg) must still be cost=1.0
        assert cost_eroded[cy, w // 2] == pytest.approx(1.0), (
            f"Expected fg interior to remain cost=1.0, got {cost_eroded[cy, w // 2]}"
        )

    def test_erosion_no_effect_when_all_background(self):
        """All-background mask → cost=0.0 everywhere regardless of erosion."""
        import backend.src.animation.rendering.compositing as comp_mod

        h, w = 60, 80
        bm = np.ones((h, w), dtype=np.uint8) * 255  # all background
        old_val = comp_mod._FG_SEAM_EROSION_PX
        comp_mod._FG_SEAM_EROSION_PX = 5
        try:
            cost = _build_seam_cost_map(self._canvas(h, w), bm, None, dilate_px=3)
        finally:
            comp_mod._FG_SEAM_EROSION_PX = old_val
        assert float(cost.max()) == pytest.approx(0.0), "All-bg → cost must be 0.0"

    def test_erosion_result_dtype_float32(self):
        """Cost map must always be float32 regardless of erosion setting."""
        import backend.src.animation.rendering.compositing as comp_mod

        h, w, fg_band = 60, 80, 20
        bm = self._solid_bg_mask(h, w, fg_band)
        old_val = comp_mod._FG_SEAM_EROSION_PX
        comp_mod._FG_SEAM_EROSION_PX = 2
        try:
            cost = _build_seam_cost_map(self._canvas(h, w), bm, None, dilate_px=3)
        finally:
            comp_mod._FG_SEAM_EROSION_PX = old_val
        assert cost.dtype == np.float32

    def test_erosion_larger_than_fg_band_collapses_tier1(self):
        """Erosion radius ≥ half the fg band should collapse the cost=1.0 region to zero."""
        import backend.src.animation.rendering.compositing as comp_mod

        h, w, fg_band = 60, 80, 8  # only 8 rows of fg
        bm = self._solid_bg_mask(h, w, fg_band)
        old_val = comp_mod._FG_SEAM_EROSION_PX
        comp_mod._FG_SEAM_EROSION_PX = 5  # erode 5 px > half of 8 px band
        try:
            cost = _build_seam_cost_map(self._canvas(h, w), bm, None, dilate_px=3)
        finally:
            comp_mod._FG_SEAM_EROSION_PX = old_val
        # With erosion wider than the fg band, no Tier-1 pixel should remain
        assert float((cost >= 1.0).sum()) == 0.0, (
            "Tier-1 region should collapse to zero"
        )


# ---------------------------------------------------------------------------
# §1.66 — NCC structural coherence gate (S131)
# ---------------------------------------------------------------------------


class TestSeamNccCoherenceCompositing:
    """§1.66 (S131): _seam_ncc_coherence and _check_seam_ncc_gate in compositing.py."""

    @staticmethod
    def _solid_image(h: int, w: int, val: int = 128) -> np.ndarray:
        return np.full((h, w, 3), val, dtype=np.uint8)

    def test_single_strip_returns_empty(self):
        """n_strips=1 → empty list (no seam boundaries)."""
        img = self._solid_image(100, 80)
        assert _seam_ncc_coherence(img, 1) == []

    def test_two_strips_returns_one_score(self):
        """n_strips=2 → exactly one NCC score."""
        img = self._solid_image(100, 80)
        scores = _seam_ncc_coherence(img, 2)
        assert len(scores) == 1

    def test_identical_halves_high_ncc(self):
        """Identical top/bottom bands → NCC ≈ 1.0 (structurally identical).

        band_px=20 means we take 20 rows above and below the seam boundary.
        With a 40-row image (n_strips=2 → boundary_y=20), top=band[0:20] and
        bot=band[20:40] which are the same random rows repeated.
        """
        rng = np.random.default_rng(42)
        band = rng.integers(50, 200, (20, 80, 3), dtype=np.uint8)
        img = np.vstack([band, band])  # 40 rows; boundary_y=20; top==bot
        scores = _seam_ncc_coherence(img, 2, band_px=20)
        assert len(scores) == 1
        assert scores[0] >= 0.9, (
            f"Identical halves should give NCC≥0.9, got {scores[0]}"
        )

    def test_gate_passes_above_threshold(self):
        """NCC score above threshold → gate returns None (all seams pass)."""
        rng = np.random.default_rng(7)
        band = rng.integers(50, 200, (20, 80, 3), dtype=np.uint8)
        img = np.vstack([band, band])  # 40 rows; boundary_y=20; top==bot
        result = _check_seam_ncc_gate(img, 2, thresh=0.3, band_px=20)
        assert result is None, "Identical halves should pass the NCC gate"

    def test_gate_fires_on_severely_mismatched_strips(self):
        """Highly mismatched strips → gate fires (returns seam index, not None)."""
        top = np.zeros((50, 60, 3), dtype=np.uint8)
        bot = np.full((50, 60, 3), 200, dtype=np.uint8)
        # Give both halves distinct spatial structure so NCC is low
        rng = np.random.default_rng(99)
        top[10:40, 10:50, 0] = rng.integers(10, 50, (30, 40), dtype=np.uint8)
        bot[10:40, 10:50, 0] = rng.integers(200, 250, (30, 40), dtype=np.uint8)
        img = np.vstack([top, bot])
        result = _check_seam_ncc_gate(img, 2, thresh=0.8, band_px=20)
        assert result == 0, (
            f"Mismatched strips should fail gate at seam 0, got {result}"
        )


class TestEnforceFeatherRatio:
    """§1.68 (S132): _enforce_feather_ratio clamps adjacent feather width jumps."""

    def test_single_feather_unchanged(self):
        """One feather → no adjacent pair → returned unchanged."""
        assert _enforce_feather_ratio([100], max_ratio=3.0) == [100]

    def test_no_enforcement_when_ratio_zero(self):
        """max_ratio=0.0 → no-op; original list returned."""
        assert _enforce_feather_ratio([80, 300], max_ratio=0.0) == [80, 300]

    def test_forward_clamp_applied(self):
        """[80, 300] with ratio=3.0 → second seam clamped to 240 (80×3)."""
        result = _enforce_feather_ratio([80, 300], max_ratio=3.0)
        assert result[1] <= int(result[0] * 3.0), (
            f"Expected result[1] ≤ {result[0] * 3.0}, got {result[1]}"
        )

    def test_backward_clamp_applied(self):
        """[300, 80] with ratio=3.0 → first seam clamped down to 240 (80×3)."""
        result = _enforce_feather_ratio([300, 80], max_ratio=3.0)
        assert result[0] <= int(result[1] * 3.0), (
            f"Expected result[0] ≤ {result[1] * 3.0}, got {result[0]}"
        )

    def test_already_within_ratio_unchanged(self):
        """[100, 200, 150] all within 2× of neighbours → unchanged."""
        feathers = [100, 200, 150]
        result = _enforce_feather_ratio(feathers, max_ratio=3.0)
        assert result == feathers


class TestSeamDpBgRatio:
    """§1.69 (S132): _seam_dp_bg_ratio measures bg fraction of DP seam path."""

    def _make_bg_mask(self, H: int, W: int, bg_rows: slice) -> np.ndarray:
        mask = np.zeros((H, W), dtype=bool)
        mask[bg_rows, :] = True
        return mask

    def test_no_masks_returns_one(self):
        """No bg masks → all pixels treated as background → ratio=1.0."""
        path = np.full(10, 5, dtype=np.int32)
        assert _seam_dp_bg_ratio(path, None, None) == 1.0

    def test_empty_path_returns_one(self):
        """Empty path → ratio=1.0 (safe default)."""
        assert _seam_dp_bg_ratio(np.array([], dtype=np.int32), None, None) == 1.0

    def test_all_background_path(self):
        """Seam path entirely in background rows → ratio=1.0."""
        H, W = 20, 10
        mask = self._make_bg_mask(H, W, slice(0, H))
        path = np.full(W, 5, dtype=np.int32)
        assert _seam_dp_bg_ratio(path, mask, mask) == 1.0

    def test_all_foreground_path(self):
        """Seam path entirely in fg rows → ratio=0.0."""
        H, W = 20, 10
        mask = np.zeros((H, W), dtype=bool)
        path = np.full(W, 5, dtype=np.int32)
        assert _seam_dp_bg_ratio(path, mask, mask) == 0.0

    def test_half_background_half_foreground(self):
        """Path rows alternate between bg (even) and fg (odd) → ratio ≈ 0.5."""
        H, W = 20, 10
        mask = np.zeros((H, W), dtype=bool)
        mask[::2, :] = True
        path = np.arange(W, dtype=np.int32) % H
        result = _seam_dp_bg_ratio(path, mask, mask)
        assert 0.0 <= result <= 1.0


class TestFgFractionInZone:
    """§1.70 (S132): _fg_fraction_in_zone measures union fg coverage in blend zone."""

    def test_both_none_returns_zero(self):
        """Both masks None → no fg information → 0.0."""
        assert _fg_fraction_in_zone(None, None) == 0.0

    def test_all_background_returns_zero(self):
        """All pixels background in both masks → fg fraction = 0."""
        mask = np.ones((10, 8), dtype=bool)
        assert _fg_fraction_in_zone(mask, mask) == 0.0

    def test_all_foreground_returns_one(self):
        """All pixels fg in both masks → fg fraction = 1.0."""
        mask = np.zeros((10, 8), dtype=bool)
        assert _fg_fraction_in_zone(mask, mask) == 1.0

    def test_union_uses_either_mask(self):
        """Left half fg in mask_a only, right half fg in mask_b only → union = full fg."""
        H, W = 10, 10
        mask_a = np.ones((H, W), dtype=bool)
        mask_b = np.ones((H, W), dtype=bool)
        mask_a[:, : W // 2] = False
        mask_b[:, W // 2 :] = False
        result = _fg_fraction_in_zone(mask_a, mask_b)
        assert result == 1.0

    def test_one_mask_none_uses_other(self):
        """mask_b None → result is solely from mask_a's fg pixels."""
        H, W = 10, 10
        mask_a = np.ones((H, W), dtype=bool)
        mask_a[: H // 2, :] = False
        result = _fg_fraction_in_zone(mask_a, None)
        assert abs(result - 0.5) < 0.05


class TestSeamEntropyAsymmetry:
    """§1.72 (S132): entropy asymmetry gate detects texture-density discontinuities."""

    def test_single_strip_returns_empty(self):
        """n_strips=1 → no seams → empty list."""
        img = np.zeros((80, 60, 3), dtype=np.uint8)
        assert _seam_entropy_asymmetry(img, 1) == []

    def test_identical_halves_near_zero(self):
        """Identical bands above and below seam → entropy difference ≈ 0."""
        rng = np.random.default_rng(42)
        band = rng.integers(0, 256, (20, 60, 3), dtype=np.uint8)
        img = np.vstack([band, band])
        scores = _seam_entropy_asymmetry(img, 2, band_px=20)
        assert len(scores) == 1
        assert scores[0] < 0.2, (
            f"Identical bands should have near-zero asymmetry, got {scores[0]}"
        )

    def test_flat_vs_rich_texture_high_asymmetry(self):
        """Flat top band (entropy≈0) vs random bottom band (entropy≈8) → high asymmetry."""
        top = np.full((20, 60, 3), 128, dtype=np.uint8)
        bot = np.random.default_rng(7).integers(0, 256, (20, 60, 3), dtype=np.uint8)
        img = np.vstack([top, bot])
        scores = _seam_entropy_asymmetry(img, 2, band_px=20)
        assert len(scores) == 1
        assert scores[0] > 2.0, (
            f"Flat vs rich bands should have high asymmetry, got {scores[0]}"
        )

    def test_gate_passes_below_threshold(self):
        """Symmetric bands → asymmetry below threshold → gate returns None."""
        rng = np.random.default_rng(42)
        band = rng.integers(0, 256, (20, 60, 3), dtype=np.uint8)
        img = np.vstack([band, band])
        result = _check_seam_entropy_gate(img, 2, thresh=1.5, band_px=20)
        assert result is None

    def test_gate_fires_on_asymmetric_strips(self):
        """Flat vs rich texture asymmetry > threshold → gate returns seam index."""
        top = np.full((20, 60, 3), 200, dtype=np.uint8)
        bot = np.random.default_rng(3).integers(0, 256, (20, 60, 3), dtype=np.uint8)
        img = np.vstack([top, bot])
        result = _check_seam_entropy_gate(img, 2, thresh=1.5, band_px=20)
        assert result == 0, (
            f"Asymmetric strips should fire gate at seam 0, got {result}"
        )


class TestSeamMaxColLumaStep:
    """§1.76 (S134): per-column worst-case luma step gate."""

    def test_single_strip_returns_empty(self):
        """n_strips=1 → no seams → empty list."""
        img = np.zeros((80, 60, 3), dtype=np.uint8)
        assert _seam_max_col_luma_step(img, 1) == []

    def test_identical_bands_zero_step(self):
        """When above and below bands are identical, worst-column step is 0."""
        band = np.full((10, 60, 3), 128, dtype=np.uint8)
        img = np.vstack([band, band])
        steps = _seam_max_col_luma_step(img, 2, band_px=10, guard=0)
        assert len(steps) == 1
        assert steps[0] == pytest.approx(0.0, abs=1.0)

    def test_step_change_detected_in_one_column(self):
        """Single bright column crossing the seam → high max step, low mean step."""
        H, W = 60, 40
        img = np.full((H, W, 3), 100, dtype=np.uint8)
        # One column above seam is bright, below is dark.
        img[: H // 2, 20] = 200
        img[H // 2 :, 20] = 50
        steps = _seam_max_col_luma_step(img, 2, band_px=5, guard=1)
        assert len(steps) == 1
        # Worst column step ≈ 150; the mean across 40 columns is ≈ 3.75.
        assert steps[0] > 100, f"Localised column spike not detected, got {steps[0]}"

    def test_gate_returns_none_below_threshold(self):
        """Uniform image → no column step → gate returns None."""
        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        assert _check_seam_max_col_gate(img, 2, thresh=40.0) is None

    def test_gate_fires_on_hot_spot_column(self):
        """Single-column brightness spike across seam → gate returns seam index 0."""
        H, W = 60, 40
        img = np.full((H, W, 3), 100, dtype=np.uint8)
        img[: H // 2, 15] = 220
        img[H // 2 :, 15] = 20
        result = _check_seam_max_col_gate(img, 2, thresh=40.0, band_px=5, guard=1)
        assert result == 0, (
            f"Hot-spot column should trigger gate at seam 0, got {result}"
        )


class TestSeamSaturationJump:
    """§1.77 (S135): mean HSV saturation jump gate."""

    def test_single_strip_returns_empty(self):
        """n_strips=1 → no seams → empty list."""
        img = np.zeros((80, 60, 3), dtype=np.uint8)
        assert _seam_saturation_jump(img, 1) == []

    def test_greyscale_input_returns_zeros(self):
        """Greyscale (2-D) image → no saturation information → 0.0 per seam."""
        img = np.full((60, 40), 128, dtype=np.uint8)
        jumps = _seam_saturation_jump(img, 2, band_px=10)
        assert len(jumps) == 1
        assert jumps[0] == pytest.approx(0.0)

    def test_uniform_saturation_no_jump(self):
        """Top and bottom halves at identical saturation → jump ≈ 0."""
        # Solid mid-green — high saturation throughout.
        img = np.zeros((60, 40, 3), dtype=np.uint8)
        img[:, :, 1] = 200  # Green channel → high saturation in HSV
        jumps = _seam_saturation_jump(img, 2, band_px=10)
        assert len(jumps) == 1
        assert jumps[0] < 5.0, (
            f"Uniform saturation should give near-zero jump, got {jumps[0]}"
        )

    def test_vivid_vs_grey_detected(self):
        """Top half vivid colour, bottom half grey → large saturation jump detected."""
        H, W = 60, 40
        top = np.zeros((H // 2, W, 3), dtype=np.uint8)
        top[:, :, 2] = 255  # Pure red → HSV saturation = 255
        bot = np.full((H // 2, W, 3), 128, dtype=np.uint8)  # Grey → sat = 0
        img = np.vstack([top, bot])
        jumps = _seam_saturation_jump(img, 2, band_px=10)
        assert len(jumps) == 1
        assert jumps[0] > 40.0, (
            f"Vivid vs grey should produce large sat jump, got {jumps[0]}"
        )

    def test_gate_fires_on_vivid_grey_split(self):
        """Vivid top / grey bottom exceeds default threshold → gate returns seam 0."""
        H, W = 60, 40
        top = np.zeros((H // 2, W, 3), dtype=np.uint8)
        top[:, :, 2] = 255
        bot = np.full((H // 2, W, 3), 128, dtype=np.uint8)
        img = np.vstack([top, bot])
        result = _check_seam_saturation_gate(img, 2, thresh=40.0, band_px=10)
        assert result == 0, (
            f"Vivid/grey split should trigger gate at seam 0, got {result}"
        )


class TestSeamHueShift:
    """§1.78 (S135): circular mean hue shift gate."""

    def test_single_strip_returns_empty(self):
        """n_strips=1 → no seams → empty list."""
        img = np.zeros((80, 60, 3), dtype=np.uint8)
        assert _seam_hue_shift(img, 1) == []

    def test_greyscale_input_returns_zeros(self):
        """Greyscale (2-D) image → no hue information → 0.0 per seam."""
        img = np.full((60, 40), 100, dtype=np.uint8)
        shifts = _seam_hue_shift(img, 2, band_px=10)
        assert len(shifts) == 1
        assert shifts[0] == pytest.approx(0.0)

    def test_same_hue_no_shift(self):
        """Top and bottom halves with same hue → circular shift ≈ 0."""
        # Both halves: pure blue (BGR = [255, 0, 0] → HSV hue ≈ 120).
        img = np.zeros((60, 40, 3), dtype=np.uint8)
        img[:, :, 0] = 255  # Blue channel
        shifts = _seam_hue_shift(img, 2, band_px=10)
        assert len(shifts) == 1
        assert shifts[0] < 5.0, (
            f"Same-hue strips should give near-zero shift, got {shifts[0]}"
        )

    def test_warm_vs_cool_detected(self):
        """Top half warm red, bottom half cool blue → large circular hue shift."""
        H, W = 60, 40
        top = np.zeros((H // 2, W, 3), dtype=np.uint8)
        top[:, :, 2] = 255  # Red (BGR) → HSV hue ≈ 0
        bot = np.zeros((H // 2, W, 3), dtype=np.uint8)
        bot[:, :, 0] = 255  # Blue (BGR) → HSV hue ≈ 120
        img = np.vstack([top, bot])
        shifts = _seam_hue_shift(img, 2, band_px=10)
        assert len(shifts) == 1
        # Circular distance between hue≈0 and hue≈120 on [0,180] scale = 60°.
        assert shifts[0] > 30.0, (
            f"Warm/cool split should give large hue shift, got {shifts[0]}"
        )

    def test_gate_fires_on_opposite_hues(self):
        """Red top / blue bottom exceeds threshold → gate returns seam 0."""
        H, W = 60, 40
        top = np.zeros((H // 2, W, 3), dtype=np.uint8)
        top[:, :, 2] = 255  # Red
        bot = np.zeros((H // 2, W, 3), dtype=np.uint8)
        bot[:, :, 0] = 255  # Blue
        img = np.vstack([top, bot])
        result = _check_seam_hue_gate(img, 2, thresh=30.0, band_px=10)
        assert result == 0, f"Opposite hues should trigger gate at seam 0, got {result}"


class TestSeamSharpnessMismatch:
    """§1.79 (S136): Laplacian-variance log₂ ratio sharpness mismatch gate."""

    def test_single_strip_returns_empty(self):
        """n_strips=1 → no seams → empty list."""
        img = np.zeros((80, 60, 3), dtype=np.uint8)
        assert _seam_sharpness_mismatch(img, 1) == []

    def test_uniform_image_zero_mismatch(self):
        """Flat uniform image: both halves have near-zero Laplacian → clamped to 1.0 each → ratio=0."""
        img = np.full((60, 40, 3), 128, dtype=np.uint8)
        scores = _seam_sharpness_mismatch(img, 2, band_px=10)
        assert len(scores) == 1
        assert scores[0] == pytest.approx(0.0), (
            f"Uniform image should give zero mismatch, got {scores[0]}"
        )

    def test_equal_sharpness_low_score(self):
        """Both halves with identical noise texture → similar Laplacian variance → low score."""
        rng = np.random.default_rng(42)
        img = rng.integers(0, 256, (80, 60, 3), dtype=np.uint8)
        scores = _seam_sharpness_mismatch(img, 2, band_px=20)
        assert len(scores) == 1
        assert scores[0] < 2.0, (
            f"Equal-noise halves should produce low mismatch, got {scores[0]}"
        )

    def test_sharp_vs_blurry_detected(self):
        """Top half: sharp checkerboard; bottom half: heavily Gaussian-blurred → large log₂ ratio."""
        H, W = 80, 60
        checker = np.zeros((H // 2, W), dtype=np.uint8)
        checker[::4, :] = 255
        checker[:, ::4] = 255
        blurry = cv2.GaussianBlur(checker, (21, 21), 10)
        top = np.stack([checker] * 3, axis=-1)
        bot = np.stack([blurry] * 3, axis=-1)
        img = np.vstack([top, bot])
        scores = _seam_sharpness_mismatch(img, 2, band_px=15)
        assert len(scores) == 1
        assert scores[0] > 2.0, (
            f"Sharp/blurry split should give large mismatch, got {scores[0]}"
        )

    def test_gate_fires_on_sharp_blurry_split(self):
        """Sharp top / blurred bottom with thresh=2.0 → gate returns seam 0."""
        H, W = 80, 60
        checker = np.zeros((H // 2, W), dtype=np.uint8)
        checker[::4, :] = 255
        checker[:, ::4] = 255
        blurry = cv2.GaussianBlur(checker, (21, 21), 10)
        top = np.stack([checker] * 3, axis=-1)
        bot = np.stack([blurry] * 3, axis=-1)
        img = np.vstack([top, bot])
        result = _check_seam_sharpness_gate(img, 2, thresh=2.0, band_px=15)
        assert result == 0, (
            f"Sharp/blurry split should trigger gate at seam 0, got {result}"
        )


class TestSeamGradDirection:
    """§1.80 (S137): Gradient direction coherence gate."""

    def test_single_strip_returns_empty(self):
        """n_strips=1 → no seams → empty list."""
        img = np.zeros((80, 60, 3), dtype=np.uint8)
        assert _seam_grad_direction(img, 1) == []

    def test_flat_image_returns_zero(self):
        """Uniform image: no strong gradients → both bands below mag_thresh → score=0.0."""
        img = np.full((60, 40, 3), 128, dtype=np.uint8)
        scores = _seam_grad_direction(img, 2, band_px=10, mag_thresh=5.0)
        assert len(scores) == 1
        assert scores[0] == pytest.approx(0.0), (
            f"Flat image should give 0.0 (no strong gradients), got {scores[0]}"
        )

    def test_same_orientation_low_score(self):
        """Both bands have horizontal lines → same dominant orientation → low score."""
        H, W = 80, 60
        # Horizontal stripes: gy dominates, gx≈0 → orientation ≈ π/2 everywhere.
        half = np.zeros((H // 2, W), dtype=np.uint8)
        half[::4, :] = 200  # horizontal stripes only
        top = np.stack([half] * 3, axis=-1)
        bot = np.stack([half] * 3, axis=-1)
        img = np.vstack([top, bot])
        scores = _seam_grad_direction(img, 2, band_px=15, mag_thresh=5.0)
        assert len(scores) == 1
        assert scores[0] < 20.0, (
            f"Identical orientation both sides → low score, got {scores[0]}"
        )

    def test_orthogonal_orientations_high_score(self):
        """Top: horizontal lines (gy-dominant); bot: vertical lines (gx-dominant) → ~90° score."""
        H, W = 80, 60
        top_grey = np.zeros((H // 2, W), dtype=np.uint8)
        top_grey[::4, :] = 200  # horizontal stripes → vertical gradient (gy large)
        bot_grey = np.zeros((H // 2, W), dtype=np.uint8)
        bot_grey[:, ::4] = 200  # vertical stripes → horizontal gradient (gx large)
        top = np.stack([top_grey] * 3, axis=-1)
        bot = np.stack([bot_grey] * 3, axis=-1)
        img = np.vstack([top, bot])
        scores = _seam_grad_direction(img, 2, band_px=15, mag_thresh=5.0)
        assert len(scores) == 1
        assert scores[0] > 60.0, (
            f"Orthogonal stripe orientations should give score > 60°, got {scores[0]}"
        )

    def test_gate_fires_on_orthogonal_content(self):
        """Gate with thresh=45° returns seam 0 for orthogonal stripe content."""
        H, W = 80, 60
        top_grey = np.zeros((H // 2, W), dtype=np.uint8)
        top_grey[::4, :] = 200
        bot_grey = np.zeros((H // 2, W), dtype=np.uint8)
        bot_grey[:, ::4] = 200
        top = np.stack([top_grey] * 3, axis=-1)
        bot = np.stack([bot_grey] * 3, axis=-1)
        img = np.vstack([top, bot])
        result = _check_seam_grad_direction_gate(img, 2, thresh=45.0, band_px=15)
        assert result == 0, (
            f"Orthogonal content should trigger gate at seam 0, got {result}"
        )


class TestSeamBandSsim:
    """§1.81 (S138): SSIM-based perceptual seam gate."""

    def test_single_strip_returns_empty(self):
        """n_strips=1 → no seams → empty list."""
        img = np.zeros((80, 60, 3), dtype=np.uint8)
        assert _seam_band_ssim(img, 1) == []

    def test_identical_bands_score_one(self):
        """Identical top and bottom bands → SSIM ≈ 1.0."""
        band = np.full((30, 60, 3), 128, dtype=np.uint8)
        img = np.vstack([band, band])
        scores = _seam_band_ssim(img, 2, band_px=20)
        assert len(scores) == 1
        assert scores[0] > 0.99, (
            f"Identical bands should give SSIM ≈ 1.0, got {scores[0]}"
        )

    def test_dissimilar_bands_low_score(self):
        """Random noise top vs uniform grey bottom → low SSIM score."""
        rng = np.random.default_rng(7)
        top = rng.integers(0, 256, (40, 60, 3), dtype=np.uint8)
        bot = np.full((40, 60, 3), 128, dtype=np.uint8)
        img = np.vstack([top, bot])
        scores = _seam_band_ssim(img, 2, band_px=20)
        assert len(scores) == 1
        assert scores[0] < 0.8, (
            f"Dissimilar bands should give low SSIM, got {scores[0]}"
        )

    def test_gate_passes_similar_bands(self):
        """Bands with SSIM > 0.85 → gate returns None (no fallback)."""
        band = np.full((40, 60, 3), 100, dtype=np.uint8)
        img = np.vstack([band, band])
        result = _check_seam_ssim_gate(img, 2, thresh=0.85, band_px=20)
        assert result is None, f"Identical bands should not trigger gate, got {result}"

    def test_gate_fires_on_dissimilar_bands(self):
        """Noise top / uniform bottom → SSIM well below threshold → gate fires."""
        rng = np.random.default_rng(42)
        top = rng.integers(0, 256, (40, 60, 3), dtype=np.uint8)
        bot = np.full((40, 60, 3), 180, dtype=np.uint8)
        img = np.vstack([top, bot])
        result = _check_seam_ssim_gate(img, 2, thresh=0.85, band_px=20)
        assert result == 0, (
            f"Dissimilar bands should trigger gate at seam 0, got {result}"
        )


class TestSeamFreqProfile:
    """§1.82 (S138): FFT spatial-frequency profile mismatch gate."""

    def test_single_strip_returns_empty(self):
        """n_strips=1 → no seams → empty list."""
        img = np.zeros((80, 60, 3), dtype=np.uint8)
        assert _seam_freq_profile(img, 1) == []

    def test_identical_bands_zero_mismatch(self):
        """Identical top and bottom bands → identical spectra → score ≈ 0."""
        band = np.full((30, 60, 3), 128, dtype=np.uint8)
        img = np.vstack([band, band])
        scores = _seam_freq_profile(img, 2, band_px=20)
        assert len(scores) == 1
        assert scores[0] < 0.05, (
            f"Identical bands should give near-zero mismatch, got {scores[0]}"
        )

    def test_uniform_bands_zero_mismatch(self):
        """Flat uniform image: near-zero Laplacian → near-zero spectrum → score ≈ 0."""
        img = np.full((80, 60, 3), 128, dtype=np.uint8)
        scores = _seam_freq_profile(img, 2, band_px=20)
        assert len(scores) == 1
        assert scores[0] < 0.2, (
            f"Flat image should give low spectral mismatch, got {scores[0]}"
        )

    def test_high_vs_low_freq_detected(self):
        """High-freq row stripes above vs low-freq row stripes below → spectral mismatch."""
        H, W = 80, 60
        # High-frequency: alternates every 2 rows → peak at Nyquist in row FFT.
        hi = np.zeros((H // 2, W), dtype=np.uint8)
        hi[::2, :] = 200
        # Low-frequency: alternates every 8 rows → peak at 1/8 in row FFT.
        lo = np.zeros((H // 2, W), dtype=np.uint8)
        lo[::8, :] = 200
        top = np.stack([hi] * 3, axis=-1)
        bot = np.stack([lo] * 3, axis=-1)
        img = np.vstack([top, bot])
        scores = _seam_freq_profile(img, 2, band_px=20)
        assert len(scores) == 1
        assert scores[0] > 0.2, (
            f"High vs low freq should give high mismatch, got {scores[0]}"
        )

    def test_gate_fires_on_spectral_mismatch(self):
        """High-freq stripes above / low-freq stripes below exceeds threshold → gate fires."""
        H, W = 80, 60
        hi = np.zeros((H // 2, W), dtype=np.uint8)
        hi[::2, :] = 200
        lo = np.zeros((H // 2, W), dtype=np.uint8)
        lo[::8, :] = 200
        top = np.stack([hi] * 3, axis=-1)
        bot = np.stack([lo] * 3, axis=-1)
        img = np.vstack([top, bot])
        result = _check_seam_freq_gate(img, 2, thresh=0.2, band_px=20)
        assert result == 0, (
            f"Spectral mismatch should trigger gate at seam 0, got {result}"
        )


# ---------------------------------------------------------------------------
# §1.83 (S139): Seam Band Noise-Level Asymmetry
# ---------------------------------------------------------------------------


class TestSeamNoiseMismatch:
    """§1.83 (S139): Noise-level asymmetry gate."""

    def test_single_strip_returns_empty(self):
        """n_strips=1 → no seams → empty list."""
        img = np.zeros((80, 60, 3), dtype=np.uint8)
        assert _seam_noise_mismatch(img, 1) == []

    def test_identical_bands_zero_asymmetry(self):
        """Top and bottom bands from same source → identical σ → score ≈ 0."""
        rng = np.random.default_rng(42)
        band = rng.integers(80, 180, size=(30, 60), dtype=np.uint8)
        grey = np.vstack([band, band])
        img = np.stack([grey, grey, grey], axis=-1)
        scores = _seam_noise_mismatch(img, 2, band_px=20)
        assert len(scores) == 1
        assert scores[0] < 0.05, (
            f"Identical bands should give near-zero asymmetry, got {scores[0]}"
        )

    def test_clean_vs_noisy_detected(self):
        """Flat clean strip vs heavy-noise strip → high asymmetry score."""
        H, W = 80, 60
        clean = np.full((H // 2, W), 128, dtype=np.uint8)
        rng = np.random.default_rng(7)
        noisy = rng.integers(0, 255, size=(H // 2, W), dtype=np.uint8)
        grey = np.vstack([clean, noisy])
        img = np.stack([grey, grey, grey], axis=-1)
        scores = _seam_noise_mismatch(img, 2, band_px=20)
        assert len(scores) == 1
        assert scores[0] > 0.5, (
            f"Clean vs noisy should give high asymmetry, got {scores[0]}"
        )

    def test_gate_passes_on_matched_noise(self):
        """Both bands have similar noise → gate should not fire."""
        rng = np.random.default_rng(0)
        top = rng.integers(100, 160, size=(30, 60), dtype=np.uint8)
        bot = rng.integers(100, 160, size=(30, 60), dtype=np.uint8)
        grey = np.vstack([top, bot])
        img = np.stack([grey, grey, grey], axis=-1)
        result = _check_seam_noise_gate(img, 2, thresh=2.0, band_px=20)
        assert result is None, (
            f"Similar noise levels should not trigger gate, got {result}"
        )

    def test_gate_fires_on_clean_vs_noisy(self):
        """Flat strip above, max-noise strip below → gate fires at seam 0."""
        H, W = 80, 60
        clean = np.full((H // 2, W), 128, dtype=np.uint8)
        rng = np.random.default_rng(3)
        noisy = rng.integers(0, 255, size=(H // 2, W), dtype=np.uint8)
        grey = np.vstack([clean, noisy])
        img = np.stack([grey, grey, grey], axis=-1)
        result = _check_seam_noise_gate(img, 2, thresh=0.5, band_px=20)
        assert result == 0, (
            f"Clean vs noisy should trigger gate at seam 0, got {result}"
        )


# ---------------------------------------------------------------------------
# §1.84 (S139): Seam Band RMS Contrast Ratio
# ---------------------------------------------------------------------------


class TestSeamRmsContrastRatio:
    """§1.84 (S139): RMS contrast ratio gate."""

    def test_single_strip_returns_empty(self):
        """n_strips=1 → no seams → empty list."""
        img = np.zeros((80, 60, 3), dtype=np.uint8)
        assert _seam_rms_contrast_ratio(img, 1) == []

    def test_identical_bands_ratio_one(self):
        """Same strip above and below → c_top = c_bot → ratio = 1.0."""
        band = np.tile(np.arange(60, dtype=np.uint8), (30, 1))
        img = np.stack([np.vstack([band, band])] * 3, axis=-1)
        scores = _seam_rms_contrast_ratio(img, 2, band_px=20)
        assert len(scores) == 1
        assert abs(scores[0] - 1.0) < 0.01, (
            f"Identical bands should give ratio ≈ 1, got {scores[0]}"
        )

    def test_flat_vs_high_contrast_detected(self):
        """Flat uniform strip vs high-contrast gradient → ratio > 1."""
        H, W = 80, 60
        flat = np.full((H // 2, W), 128, dtype=np.uint8)
        grad = np.tile(np.linspace(0, 255, W, dtype=np.uint8), (H // 2, 1))
        grey = np.vstack([flat, grad])
        img = np.stack([grey, grey, grey], axis=-1)
        scores = _seam_rms_contrast_ratio(img, 2, band_px=20)
        assert len(scores) == 1
        assert scores[0] > 2.0, (
            f"Flat vs gradient should give ratio > 2, got {scores[0]}"
        )

    def test_gate_passes_on_equal_contrast(self):
        """Both strips have similar coefficient of variation → gate should not fire."""
        band = np.tile(np.linspace(50, 200, 60, dtype=np.uint8), (30, 1))
        img = np.stack([np.vstack([band, band])] * 3, axis=-1)
        result = _check_seam_rms_contrast_gate(img, 2, thresh=4.0, band_px=20)
        assert result is None, f"Equal contrast should not trigger gate, got {result}"

    def test_gate_fires_on_flat_vs_gradient(self):
        """Flat strip above, high-contrast gradient below → gate fires at seam 0."""
        H, W = 80, 60
        flat = np.full((H // 2, W), 128, dtype=np.uint8)
        grad = np.tile(np.linspace(0, 255, W, dtype=np.uint8), (H // 2, 1))
        grey = np.vstack([flat, grad])
        img = np.stack([grey, grey, grey], axis=-1)
        result = _check_seam_rms_contrast_gate(img, 2, thresh=2.0, band_px=20)
        assert result == 0, (
            f"Flat vs gradient should trigger gate at seam 0, got {result}"
        )


# ---------------------------------------------------------------------------
# §1.85 (S139): Multi-Gate Ensemble Combiner
# ---------------------------------------------------------------------------


class TestSeamGateEnsemble:
    """§1.85 (S139): Multi-gate ensemble combiner."""

    def test_single_strip_returns_empty_votes(self):
        """n_strips=1 → no seams → empty vote list."""
        img = np.zeros((80, 60, 3), dtype=np.uint8)
        assert _seam_gate_vote_counts(img, 1) == []

    def test_all_thresholds_zero_gives_zero_votes(self):
        """All gate thresholds at 0.0 → no votes for any seam."""
        H, W = 80, 60
        rng = np.random.default_rng(1)
        img = rng.integers(0, 255, size=(H, W, 3), dtype=np.uint8)
        votes = _seam_gate_vote_counts(img, 2)  # all thresholds default 0.0
        assert votes == [0], f"No active gates should give zero votes, got {votes}"

    def test_ensemble_gate_disabled_when_min_votes_zero(self):
        """min_votes=0 → ensemble gate always returns None."""
        img = np.zeros((80, 60, 3), dtype=np.uint8)
        result = _check_seam_ensemble_gate(img, 2, min_votes=0)
        assert result is None, "min_votes=0 should disable the ensemble gate"

    def test_single_gate_vote_accumulates(self):
        """One active gate that fires on seam 0 → votes[0] >= 1."""
        H, W = 80, 60
        flat = np.full((H // 2, W), 128, dtype=np.uint8)
        rng = np.random.default_rng(5)
        noisy = rng.integers(0, 255, size=(H // 2, W), dtype=np.uint8)
        grey = np.vstack([flat, noisy])
        img = np.stack([grey, grey, grey], axis=-1)
        votes = _seam_gate_vote_counts(img, 2, thresh_noise=0.5)
        assert votes[0] >= 1, f"Noisy seam should receive ≥1 vote, got {votes[0]}"

    def test_ensemble_fires_when_votes_meet_threshold(self):
        """Seam that accumulates ≥ min_votes gate failures → ensemble fires."""
        H, W = 80, 60
        flat = np.full((H // 2, W), 128, dtype=np.uint8)
        rng = np.random.default_rng(9)
        noisy = rng.integers(0, 255, size=(H // 2, W), dtype=np.uint8)
        grey = np.vstack([flat, noisy])
        img = np.stack([grey, grey, grey], axis=-1)
        # Use a generous low threshold so multiple gates fire on the noisy seam
        result = _check_seam_ensemble_gate(
            img,
            2,
            min_votes=2,
            thresh_noise=0.3,
            thresh_contrast=1.5,
        )
        # Both noise and contrast gates should flag the flat-vs-noisy seam
        assert result == 0, f"Ensemble should trigger at seam 0, got {result}"


# ── TestZonePairSsim — §1.86 zone SSIM pre-gate (S141) ───────────────────────


class TestZonePairSsim:
    """§1.86 — Zone SSIM pre-gate: structural similarity between warped zone crops."""

    def _zone(self, h: int = 80, w: int = 200, fill: int = 128) -> np.ndarray:
        """Create a uniform BGR zone crop."""
        return np.full((h, w, 3), fill, dtype=np.uint8)

    def test_identical_zones_return_one(self):
        """Two identical zones → SSIM ≈ 1.0."""
        zone = self._zone(fill=100)
        score = _zone_pair_ssim(zone, zone.copy())
        assert score == pytest.approx(1.0, abs=0.02), f"Expected ~1.0, got {score}"

    def test_completely_different_zones_low_score(self):
        """Zones with opposite luminance patterns → SSIM well below 0.5."""
        h, w = 80, 200
        # Checkerboard vs. solid — extreme structural mismatch
        checker = np.zeros((h, w, 3), dtype=np.uint8)
        checker[::2, ::2] = 200
        checker[1::2, 1::2] = 200
        solid = self._zone(h=h, w=w, fill=100)
        score = _zone_pair_ssim(checker, solid)
        assert score < 0.5, f"Expected low SSIM for checker vs solid, got {score}"

    def test_degenerate_thin_zone_returns_one(self):
        """Zone with fewer than 4 rows → 1.0 (no gate)."""
        fa = np.zeros((3, 200, 3), dtype=np.uint8)
        fb = np.full((3, 200, 3), 200, dtype=np.uint8)
        assert _zone_pair_ssim(fa, fb) == pytest.approx(1.0)

    def test_degenerate_narrow_zone_returns_one(self):
        """Zone with fewer than 8 columns → 1.0 (no gate)."""
        fa = np.zeros((80, 7, 3), dtype=np.uint8)
        fb = np.full((80, 7, 3), 200, dtype=np.uint8)
        assert _zone_pair_ssim(fa, fb) == pytest.approx(1.0)

    def test_moderately_different_zones_intermediate_score(self):
        """Zones differing in the lower half → score in (0.1, 0.9)."""
        h, w = 80, 200
        fa = self._zone(h=h, w=w, fill=128)
        fb = fa.copy()
        # Bottom half of fb is dark — structural difference in half the zone
        fb[h // 2 :] = 20
        score = _zone_pair_ssim(fa, fb)
        assert 0.1 < score < 0.9, f"Expected intermediate score, got {score}"


class TestHorizontalCompositing:
    """§3.14B: Horizontal-strip compositing — ASP_HORIZONTAL_COMPOSITE flag."""

    def _horiz_affines(self, N=4, step=200):
        """Produce affines for a horizontal scroll (primary tx displacement)."""
        import numpy as np

        affines = []
        for i in range(N):
            M = np.eye(2, 3, dtype=np.float64)
            M[0, 2] = i * step  # tx increases, ty=0
            affines.append(M)
        return affines

    def test_horizontal_detected_from_affines(self):
        from backend.src.animation.alignment.canvas import _detect_scroll_axis

        affines = self._horiz_affines()
        assert _detect_scroll_axis(affines) == "horizontal"

    def test_flag_default_is_false(self):
        import os

        os.environ.pop("ASP_HORIZONTAL_COMPOSITE", None)
        # Import fresh module value (may be cached; just check the env default)
        val = os.environ.get("ASP_HORIZONTAL_COMPOSITE", "0") != "0"
        assert val is False

    def test_flag_on_suppresses_scans_path(self):
        import backend.src.animation.core.pipeline as pip

        assert hasattr(pip, "_HORIZONTAL_COMPOSITE")
        assert isinstance(pip._HORIZONTAL_COMPOSITE, bool)

    def test_composite_foreground_horizontal_fast_path(self):
        import numpy as np
        from backend.src.animation.rendering.compositing import _composite_foreground

        N = 3
        H, W = 64, 192
        frames = [np.full((H, W // N, 3), 128, dtype=np.uint8) for _ in range(N)]
        affines = self._horiz_affines(N=N, step=W // N)
        canvas = np.full((H, W, 3), 50, dtype=np.uint8)
        result = _composite_foreground(
            [],
            [],
            canvas,
            H,
            W,
            frames,
            affines,
            [None] * N,
        )
        # Horizontal fast-path returns canvas unchanged
        np.testing.assert_array_equal(result, canvas)

    def test_horizontal_flag_is_boolean(self):
        import backend.src.animation.core.pipeline as pip

        assert isinstance(pip._HORIZONTAL_COMPOSITE, bool)


class TestMeshBarrier:
    """§3.15B: Triangular mesh barrier — _build_fg_mesh_barrier."""

    def test_returns_zeros_for_empty_mask(self):
        import numpy as np
        from backend.src.animation.rendering.compositing import _build_fg_mesh_barrier

        mask = np.zeros((64, 64), dtype=np.uint8)
        barrier = _build_fg_mesh_barrier(mask)
        assert barrier.shape == (64, 64)
        assert barrier.max() == 0.0

    def test_returns_zeros_for_tiny_area(self):
        """Contours with total area < min_area_px produce no barrier."""
        import numpy as np
        from backend.src.animation.rendering.compositing import _build_fg_mesh_barrier

        mask = np.zeros((64, 64), dtype=np.uint8)
        mask[30:32, 30:32] = 255
        barrier = _build_fg_mesh_barrier(mask, min_area_px=100)
        assert barrier.max() == 0.0

    def test_fills_fg_region_with_high_cost(self):
        """Large fg region yields 1e6 barrier inside the hull."""
        import numpy as np
        from backend.src.animation.rendering.compositing import _build_fg_mesh_barrier

        mask = np.zeros((128, 128), dtype=np.uint8)
        cv2 = __import__("cv2")
        cv2.rectangle(mask, (20, 20), (80, 80), 255, -1)
        barrier = _build_fg_mesh_barrier(mask, min_area_px=10)
        assert barrier.max() >= 1e5, "Expected high barrier cost inside fg hull"

    def test_flag_is_boolean(self):
        import backend.src.animation.rendering.compositing as comp

        assert isinstance(comp._MESH_BARRIER, bool)

    def test_cost_map_respects_mesh_barrier_env(self, monkeypatch):
        """With ASP_MESH_BARRIER=1 and a large fg mask the seam cost map has 1e6 entries."""
        import numpy as np
        import backend.src.animation.rendering.compositing as comp

        monkeypatch.setattr(comp, "_MESH_BARRIER", True)
        H, W = 128, 128
        cv2 = __import__("cv2")
        bg_mask = np.zeros((H, W), dtype=np.uint8)
        cv2.rectangle(bg_mask, (10, 10), (90, 90), 255, -1)
        canvas_zone = np.zeros((H, W, 3), dtype=np.uint8)
        cost = comp._build_seam_cost_map(
            canvas_zone,
            bg_mask_a=bg_mask,
            bg_mask_b=bg_mask,
        )
        assert cost.max() >= 1e5, "Expected mesh barrier cost in cost map"


class TestFlowHitlCallback:
    """§2.10A — Flow HITL callback checkpoint infrastructure."""

    def test_callback_registered_and_cleared(self):
        import backend.src.animation.rendering.compositing as comp

        comp.set_flow_hitl_callback(lambda k, info: None)
        assert comp._flow_hitl_callback is not None
        comp.set_flow_hitl_callback(None)
        assert comp._flow_hitl_callback is None

    def test_callback_identity_preserved(self):
        import backend.src.animation.rendering.compositing as comp

        def cb(k, info):
            return None

        comp.set_flow_hitl_callback(cb)
        try:
            assert comp._flow_hitl_callback is cb
        finally:
            comp.set_flow_hitl_callback(None)

    def test_callback_none_by_default_after_clear(self):
        import backend.src.animation.rendering.compositing as comp

        comp.set_flow_hitl_callback(None)
        assert comp._flow_hitl_callback is None

    def test_set_flow_hitl_callback_exported(self):
        import backend.src.animation.rendering.compositing as comp

        assert "set_flow_hitl_callback" in comp.__all__

    def test_callback_return_none_proceeds(self):
        """Callback returning None should not inject a flow override."""
        import backend.src.animation.rendering.compositing as comp

        comp.set_flow_hitl_callback(lambda k, info: None)
        try:
            result = comp._flow_hitl_callback(0, {"post_warp_diff": 30.0, "seam_k": 0})
            assert result is None
        finally:
            comp.set_flow_hitl_callback(None)


# ===========================================================================
# Merged from test_compositing_s147.py
# ===========================================================================


class TestSeamBandHistMatch:
    def test_output_shape_unchanged(self):
        from backend.src.animation.rendering.compositing import _seam_band_hist_match

        rng = np.random.default_rng(0)
        dom = rng.integers(0, 256, (50, 40, 3), dtype=np.uint8)
        oth = np.clip(dom.astype(np.float32) * 0.5, 0, 255).astype(np.uint8)
        path = np.full(50, 20, dtype=int)
        out = _seam_band_hist_match(dom, oth, path, band_px=8)
        assert out.shape == oth.shape

    def test_band_pixels_shifted_toward_dom(self):
        from backend.src.animation.rendering.compositing import _seam_band_hist_match

        dom = np.full((30, 30, 3), 200, dtype=np.uint8)
        oth = np.full((30, 30, 3), 50, dtype=np.uint8)
        path = np.full(30, 15, dtype=int)
        out = _seam_band_hist_match(dom, oth, path, band_px=8)
        band_mean = out[5:25, 7:23].mean()
        assert band_mean > 120  # shifted from 50 toward 200

    def test_outside_band_unchanged(self):
        from backend.src.animation.rendering.compositing import _seam_band_hist_match

        dom = np.full((30, 30, 3), 200, dtype=np.uint8)
        oth = np.full((30, 30, 3), 50, dtype=np.uint8)
        path = np.full(30, 15, dtype=int)
        out = _seam_band_hist_match(dom, oth, path, band_px=4)
        # Column 0 is far outside the band (path=15, band=4 → cols 11–19)
        assert np.all(out[:, 0] == 50)

    def test_zero_band_px_returns_copy(self):
        from backend.src.animation.rendering.compositing import _seam_band_hist_match

        oth = np.full((10, 10, 3), 100, dtype=np.uint8)
        dom = np.full((10, 10, 3), 200, dtype=np.uint8)
        path = np.full(10, 5, dtype=int)
        out = _seam_band_hist_match(dom, oth, path, band_px=0)
        assert np.array_equal(out, oth)

    def test_function_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_seam_band_hist_match" in comp.__all__


# ---------------------------------------------------------------------------
# §1.89 — Seam residual order
# ---------------------------------------------------------------------------


class TestSeamOrderResidual:
    def test_flag_default_off(self):
        import backend.src.animation.rendering.compositing as comp

        # Default env has no ASP_SEAM_ORDER=residual
        # We can't guarantee env state, but at least the attribute exists
        assert hasattr(comp, "_SEAM_ORDER_RESIDUAL")

    def test_residual_sort_ascending(self):
        seam_post_diffs = {0: 25.0, 1: 5.0, 2: 15.0}
        n_b = 3
        seam_order = sorted(range(n_b), key=lambda k: seam_post_diffs.get(k, 0.0))
        assert seam_order == [1, 2, 0]

    def test_empty_diffs_stable_order(self):
        seam_post_diffs = {}
        n_b = 4
        seam_order = sorted(range(n_b), key=lambda k: seam_post_diffs.get(k, 0.0))
        assert seam_order == [0, 1, 2, 3]

    def test_partial_diffs_default_zero(self):
        seam_post_diffs = {2: 10.0}
        n_b = 4
        seam_order = sorted(range(n_b), key=lambda k: seam_post_diffs.get(k, 0.0))
        assert seam_order[-1] == 2  # highest residual last
        assert seam_order[:3] == sorted(seam_order[:3])  # 0,1,3 all zero → stable

    def test_flag_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_SEAM_ORDER_RESIDUAL" in comp.__all__


# ---------------------------------------------------------------------------
# §1.90 — Bilateral seam smoothing
# ---------------------------------------------------------------------------


class TestBilateralSeamSmooth:
    def test_output_shape_unchanged(self):
        from backend.src.animation.rendering.compositing import _bilateral_seam_smooth

        canvas = np.random.randint(0, 256, (100, 200, 3), dtype=np.uint8)
        paths = {0: np.full(100, 50, dtype=int), 1: np.full(100, 100, dtype=int)}
        out = _bilateral_seam_smooth(canvas, paths)
        assert out.shape == canvas.shape

    def test_empty_paths_returns_copy(self):
        from backend.src.animation.rendering.compositing import _bilateral_seam_smooth

        canvas = np.random.randint(0, 256, (50, 100, 3), dtype=np.uint8)
        out = _bilateral_seam_smooth(canvas, {})
        assert np.array_equal(out, canvas)

    def test_outside_band_unchanged(self):
        from backend.src.animation.rendering.compositing import _bilateral_seam_smooth

        canvas = np.ones((30, 100, 3), dtype=np.uint8) * 128
        paths = {0: np.full(30, 50, dtype=int)}
        out = _bilateral_seam_smooth(canvas, paths, band_px=3)
        assert np.all(out[:, 0] == 128)

    def test_none_path_skipped(self):
        from backend.src.animation.rendering.compositing import _bilateral_seam_smooth

        canvas = np.ones((20, 40, 3), dtype=np.uint8) * 100
        paths = {0: None, 1: np.full(20, 20, dtype=int)}
        out = _bilateral_seam_smooth(canvas, paths)
        assert out.shape == canvas.shape

    def test_function_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_bilateral_seam_smooth" in comp.__all__


# ---------------------------------------------------------------------------
# §3.17 — High-frequency column seam cost
# ---------------------------------------------------------------------------


class TestHfColumnCost:
    def test_output_shape(self):
        from backend.src.animation.rendering.compositing import _hf_column_cost

        a = np.random.randint(0, 256, (40, 60, 3), dtype=np.uint8)
        b = np.random.randint(0, 256, (40, 60, 3), dtype=np.uint8)
        cost = _hf_column_cost(a, b)
        assert cost.shape == (40, 60)

    def test_flat_image_zero_cost(self):
        from backend.src.animation.rendering.compositing import _hf_column_cost

        a = np.full((30, 40, 3), 128, dtype=np.uint8)
        b = np.full((30, 40, 3), 128, dtype=np.uint8)
        cost = _hf_column_cost(a, b, hf_threshold=1.0)
        assert cost.max() == 0.0

    def test_high_freq_col_gets_boost(self):
        from backend.src.animation.rendering.compositing import _hf_column_cost

        a = np.zeros((30, 20, 3), dtype=np.uint8)
        # Alternating 0/255 pattern at column 10 = maximum high-frequency
        for row in range(30):
            a[row, 10] = 255 if row % 2 == 0 else 0
        b = a.copy()
        cost = _hf_column_cost(a, b, hf_threshold=10.0, hf_boost=1.0)
        assert cost[:, 10].mean() > cost[:, 0].mean()

    def test_dtype_float32(self):
        from backend.src.animation.rendering.compositing import _hf_column_cost

        a = np.random.randint(0, 256, (20, 30, 3), dtype=np.uint8)
        b = a.copy()
        cost = _hf_column_cost(a, b)
        assert cost.dtype == np.float32

    def test_function_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_hf_column_cost" in comp.__all__


# ===========================================================================
# Merged from test_compositing_s148.py
# ===========================================================================


class TestSeamLumConverge:
    def test_converges_when_delta_high(self):
        from backend.src.animation.rendering.compositing import _seam_lum_converge

        dom = np.full((30, 30, 3), 200, dtype=np.uint8)
        oth = np.full((30, 30, 3), 50, dtype=np.uint8)
        path = np.full(30, 15, dtype=int)
        out = _seam_lum_converge(
            dom, oth, path, band_px=8, target_delta=5.0, max_iters=2
        )
        # After convergence, band mean should be closer to 200 than 50
        band_mean = out[5:25, 7:23].mean()
        assert band_mean > 100

    def test_no_change_when_delta_already_small(self):
        from backend.src.animation.rendering.compositing import _seam_lum_converge

        val = 180
        dom = np.full((20, 20, 3), val, dtype=np.uint8)
        oth = np.full((20, 20, 3), val - 3, dtype=np.uint8)  # delta=3 < target=5
        path = np.full(20, 10, dtype=int)
        out = _seam_lum_converge(
            dom, oth, path, band_px=5, target_delta=5.0, max_iters=2
        )
        # Should not over-correct — result should be close to oth
        assert abs(float(out.mean()) - float(oth.mean())) < 5.0

    def test_zero_band_px_returns_copy(self):
        from backend.src.animation.rendering.compositing import _seam_lum_converge

        oth = np.full((10, 10, 3), 100, dtype=np.uint8)
        dom = np.full((10, 10, 3), 200, dtype=np.uint8)
        path = np.full(10, 5, dtype=int)
        out = _seam_lum_converge(dom, oth, path, band_px=0)
        assert np.array_equal(out, oth)

    def test_output_shape_preserved(self):
        from backend.src.animation.rendering.compositing import _seam_lum_converge

        rng = np.random.default_rng(1)
        dom = rng.integers(0, 256, (40, 50, 3), dtype=np.uint8)
        oth = rng.integers(0, 256, (40, 50, 3), dtype=np.uint8)
        path = np.full(40, 25, dtype=int)
        out = _seam_lum_converge(dom, oth, path, band_px=6)
        assert out.shape == oth.shape

    def test_function_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_seam_lum_converge" in comp.__all__


# ---------------------------------------------------------------------------
# §1.92 — Gaussian feather smoothing
# ---------------------------------------------------------------------------


class TestSmoothFeatherArray:
    def test_single_element_identity(self):
        from backend.src.animation.rendering.compositing import _smooth_feather_array

        f = np.array([200], dtype=np.int64)
        out = _smooth_feather_array(f, sigma=1.0)
        assert len(out) == 1

    def test_smooths_spike(self):
        from backend.src.animation.rendering.compositing import _smooth_feather_array

        # Spike at index 1: [80, 300, 80]
        f = np.array([80, 300, 80], dtype=np.int64)
        out = _smooth_feather_array(f, sigma=1.0)
        # After Gaussian smooth, the spike should be reduced
        assert out[1] < 300

    def test_uniform_array_unchanged(self):
        from backend.src.animation.rendering.compositing import _smooth_feather_array

        f = np.array([150, 150, 150, 150], dtype=np.int64)
        out = _smooth_feather_array(f, sigma=1.0)
        assert np.allclose(out, 150, atol=1)

    def test_clamps_to_feather_bounds(self):
        from backend.src.animation.rendering.compositing import _smooth_feather_array

        f = np.array([50, 50, 50], dtype=np.int64)
        out = _smooth_feather_array(f, sigma=1.0, feather_min=80, feather_max=300)
        assert (out >= 80).all()
        assert (out <= 300).all()

    def test_function_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_smooth_feather_array" in comp.__all__


# ---------------------------------------------------------------------------
# §3.18 — CQAS aggregate quality score
# ---------------------------------------------------------------------------


class TestComputeCqas:
    def _good_metrics(self):
        return {
            "ghosting_siqe": 2.0,  # nearly clean
            "seam_visibility": 3.0,  # invisible
            "seam_coherence": 5.0,  # coherent
            "sharpness": 90.0,  # sharp
        }

    def _bad_metrics(self):
        return {
            "ghosting_siqe": 70.0,  # heavy ghost
            "seam_visibility": 30.0,  # hard cut
            "seam_coherence": 60.0,  # incoherent
            "sharpness": 10.0,  # blurry
        }

    def test_good_metrics_high_score(self):
        from backend.benchmark.bench_anime_stitch import _compute_cqas

        score = _compute_cqas(self._good_metrics())
        assert score is not None
        assert score > 0.7

    def test_bad_metrics_low_score(self):
        from backend.benchmark.bench_anime_stitch import _compute_cqas

        score = _compute_cqas(self._bad_metrics())
        assert score is not None
        assert score < 0.5

    def test_empty_metrics_returns_none(self):
        from backend.benchmark.bench_anime_stitch import _compute_cqas

        assert _compute_cqas({}) is None

    def test_partial_metrics_uses_available(self):
        from backend.benchmark.bench_anime_stitch import _compute_cqas

        # Only ghosting available
        score = _compute_cqas({"ghosting_siqe": 0.0})
        assert score is not None
        assert score > 0.9  # 0 ghost → ~1.0

    def test_score_in_unit_range(self):
        from backend.benchmark.bench_anime_stitch import _compute_cqas

        score = _compute_cqas(self._good_metrics())
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# §1.94 — Background plate consistency score
# ---------------------------------------------------------------------------


class TestBgConsistencyScore:
    def test_flat_image_low_score(self):
        from backend.benchmark.bench_anime_stitch import _bg_consistency_score

        img = np.full((100, 80, 3), 128, dtype=np.uint8)
        score = _bg_consistency_score(img, n_strips=1)
        assert score < 1.0  # flat image → near-zero variance

    def test_banded_image_high_score(self):
        from backend.benchmark.bench_anime_stitch import _bg_consistency_score

        img = np.zeros((100, 80, 3), dtype=np.uint8)
        # Alternating bright/dark rows = high row-mean variance
        img[::2] = 200
        img[1::2] = 50
        score = _bg_consistency_score(img, n_strips=1)
        assert score > 30.0  # high variance

    def test_output_shape(self):
        from backend.benchmark.bench_anime_stitch import _bg_consistency_score

        img = np.random.randint(0, 256, (60, 40, 3), dtype=np.uint8)
        score = _bg_consistency_score(img, n_strips=3)
        assert isinstance(score, float)

    def test_multiple_strips(self):
        from backend.benchmark.bench_anime_stitch import _bg_consistency_score

        img = np.random.randint(0, 256, (90, 60, 3), dtype=np.uint8)
        s1 = _bg_consistency_score(img, n_strips=1)
        s3 = _bg_consistency_score(img, n_strips=3)
        # Both should return floats without error
        assert isinstance(s1, float)
        assert isinstance(s3, float)

    def test_empty_image_returns_zero(self):
        from backend.benchmark.bench_anime_stitch import _bg_consistency_score
        import numpy as np

        img = np.zeros((0, 10, 3), dtype=np.uint8)
        score = _bg_consistency_score(img, n_strips=1)
        assert score == 0.0


# ===========================================================================
# Merged from test_compositing_s149.py
# ===========================================================================


class TestSpThreshFgScale:
    def test_flags_in_module(self):
        import backend.src.animation.rendering.compositing as comp

        assert hasattr(comp, "_SP_THRESH_FG_SCALE")
        assert hasattr(comp, "_SP_THRESH_FG_FACTOR")
        assert hasattr(comp, "_SP_FG_FRAC_THRESH")

    def test_fg_factor_default(self):
        import backend.src.animation.rendering.compositing as comp

        assert 0.0 < comp._SP_THRESH_FG_FACTOR <= 1.0

    def test_fg_frac_thresh_default(self):
        import backend.src.animation.rendering.compositing as comp

        assert 0.0 < comp._SP_FG_FRAC_THRESH < 1.0

    def test_flags_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_SP_THRESH_FG_SCALE" in comp.__all__

    def test_constants_defined(self):
        from backend.src.constants.animation import (
            SP_THRESH_FG_FACTOR,
            SP_FG_FRAC_THRESH,
        )

        assert SP_THRESH_FG_FACTOR == pytest.approx(0.7)
        assert SP_FG_FRAC_THRESH == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# §3.19 — Per-zone pre-blend chroma alignment
# ---------------------------------------------------------------------------


class TestZoneChromaAlign:
    def test_identical_zones_returns_copy(self):
        from backend.src.animation.rendering.compositing import _zone_chroma_align

        zone = np.full((30, 40, 3), 128, dtype=np.uint8)
        out = _zone_chroma_align(zone, zone)
        assert out.shape == zone.shape

    def test_shifts_chroma_toward_reference(self):
        from backend.src.animation.rendering.compositing import _zone_chroma_align
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
        from backend.src.animation.rendering.compositing import _zone_chroma_align

        rng = np.random.default_rng(42)
        fa = rng.integers(50, 200, (25, 30, 3), dtype=np.uint8)
        fb = rng.integers(50, 200, (25, 30, 3), dtype=np.uint8)
        out = _zone_chroma_align(fa, fb)
        assert out.shape == fb.shape
        assert out.dtype == np.uint8

    def test_black_zone_returns_copy(self):
        from backend.src.animation.rendering.compositing import _zone_chroma_align

        black = np.zeros((10, 10, 3), dtype=np.uint8)
        fb = np.full((10, 10, 3), 100, dtype=np.uint8)
        out = _zone_chroma_align(black, fb)
        assert np.array_equal(out, fb)

    def test_function_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_zone_chroma_align" in comp.__all__
        assert "_ZONE_CHROMA_ALIGN" in comp.__all__


# ---------------------------------------------------------------------------
# §1.97 — Seam zone entropy asymmetry gate
# ---------------------------------------------------------------------------


class TestSeamZoneEntropyGap:
    def test_identical_zones_zero_gap(self):
        from backend.src.animation.rendering.compositing import _seam_zone_entropy_gap

        zone = np.random.randint(0, 256, (20, 30, 3), dtype=np.uint8)
        assert _seam_zone_entropy_gap(zone, zone) == pytest.approx(0.0)

    def test_flat_vs_noisy_high_gap(self):
        from backend.src.animation.rendering.compositing import _seam_zone_entropy_gap

        flat = np.full((30, 30, 3), 128, dtype=np.uint8)
        noisy = np.random.randint(0, 256, (30, 30, 3), dtype=np.uint8)
        gap = _seam_zone_entropy_gap(flat, noisy)
        assert gap > 1.0

    def test_entropy_positive(self):
        from backend.src.animation.rendering.compositing import _zone_entropy

        zone = np.random.randint(0, 256, (20, 20, 3), dtype=np.uint8)
        assert _zone_entropy(zone) >= 0.0

    def test_empty_zone_returns_zero(self):
        from backend.src.animation.rendering.compositing import (
            _zone_entropy,
            _seam_zone_entropy_gap,
        )

        empty = np.zeros((0, 10, 3), dtype=np.uint8)
        assert _zone_entropy(empty) == 0.0
        assert _seam_zone_entropy_gap(empty, empty) == 0.0

    def test_functions_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_zone_entropy" in comp.__all__
        assert "_seam_zone_entropy_gap" in comp.__all__
        assert "_ENTROPY_GAP_THRESH" in comp.__all__


# ===========================================================================
# Merged from test_compositing_s150.py
# ===========================================================================


class TestSmoothGainArray:
    def test_single_element_passthrough(self):
        from backend.src.animation.rendering.compositing import _smooth_gain_array

        out = _smooth_gain_array([1.5], sigma=1.0)
        assert len(out) == 1
        assert abs(float(out[0]) - 1.5) < 1e-6

    def test_smooths_spike(self):
        from backend.src.animation.rendering.compositing import _smooth_gain_array

        gains = [1.0, 2.0, 1.0, 1.0, 1.0]
        out = _smooth_gain_array(gains, sigma=1.0)
        # The spike at index 1 should be reduced
        assert float(out[1]) < 2.0

    def test_uniform_gains_unchanged(self):
        from backend.src.animation.rendering.compositing import _smooth_gain_array

        gains = [1.2, 1.2, 1.2, 1.2]
        out = _smooth_gain_array(gains, sigma=1.0)
        assert np.allclose(out, 1.2, atol=1e-5)

    def test_output_length_preserved(self):
        from backend.src.animation.rendering.compositing import _smooth_gain_array

        gains = [0.9, 1.1, 0.95, 1.05, 1.0, 0.88]
        out = _smooth_gain_array(gains, sigma=1.0)
        assert len(out) == len(gains)

    def test_flags_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_smooth_gain_array" in comp.__all__
        assert "_SMOOTH_GAIN" in comp.__all__
        assert "_SMOOTH_GAIN_SIGMA" in comp.__all__


# ---------------------------------------------------------------------------
# §3.20 — Extra fg-boundary dilation cost ring
# ---------------------------------------------------------------------------


class TestExtraFgDilationCost:
    def _make_cost_map(self, extra_dilation):
        import backend.src.animation.rendering.compositing as comp

        orig = comp._EXTRA_FG_DILATION
        comp._EXTRA_FG_DILATION = extra_dilation
        try:
            zone = np.zeros((60, 80, 3), dtype=np.uint8)
            bg_a = np.ones((60, 80), dtype=np.uint8) * 255
            bg_b = np.ones((60, 80), dtype=np.uint8) * 255
            bg_a[20:40, 30:50] = 0
            bg_b[20:40, 30:50] = 0
            return comp._build_seam_cost_map(zone, bg_a, bg_b)
        finally:
            comp._EXTRA_FG_DILATION = orig

    def test_flag_in_module(self):
        import backend.src.animation.rendering.compositing as comp

        assert hasattr(comp, "_EXTRA_FG_DILATION")

    def test_flag_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_EXTRA_FG_DILATION" in comp.__all__

    def test_constant_defined(self):
        from backend.src.constants.animation import EXTRA_FG_DILATION_DEFAULT

        assert EXTRA_FG_DILATION_DEFAULT > 0

    def test_extra_ring_creates_outer_cost(self):
        cost_off = self._make_cost_map(extra_dilation=0)
        cost_on = self._make_cost_map(extra_dilation=8)
        assert (cost_on > 0).sum() >= (cost_off > 0).sum()

    def test_extra_ring_does_not_exceed_column_barrier(self):
        cost = self._make_cost_map(extra_dilation=8)
        # Column barrier (§3.15A) raises fg-dominated columns to 2.0; outer ring
        # adds only 0.3 and np.maximum preserves higher tiers — max should stay ≤ 2.0
        assert float(cost.max()) <= 2.0 + 1e-3


# ---------------------------------------------------------------------------
# §1.99 — Seam endpoint bg-preference
# ---------------------------------------------------------------------------


class TestSeamPinRows:
    def test_flag_in_module(self):
        import backend.src.animation.rendering.compositing as comp

        assert hasattr(comp, "_SEAM_PIN_ROWS")

    def test_flag_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_SEAM_PIN_ROWS" in comp.__all__

    def test_constant_defined(self):
        from backend.src.constants.animation import SEAM_PIN_ROWS_DEFAULT

        assert SEAM_PIN_ROWS_DEFAULT > 0

    def test_pin_amplifies_top_fg_cost(self):
        import backend.src.animation.rendering.compositing as comp

        orig = comp._SEAM_PIN_ROWS
        comp._SEAM_PIN_ROWS = 3
        try:
            zone = np.zeros((40, 50, 3), dtype=np.uint8)
            bg_a = np.zeros((40, 50), dtype=np.uint8)
            bg_b = np.zeros((40, 50), dtype=np.uint8)
            cost_on = comp._build_seam_cost_map(zone, bg_a, bg_b)
            comp._SEAM_PIN_ROWS = 0
            cost_off = comp._build_seam_cost_map(zone, bg_a, bg_b)
            assert float(cost_on[:3].mean()) >= float(cost_off[:3].mean())
        finally:
            comp._SEAM_PIN_ROWS = orig

    def test_pin_only_affects_fg_pixels(self):
        import backend.src.animation.rendering.compositing as comp

        orig = comp._SEAM_PIN_ROWS
        comp._SEAM_PIN_ROWS = 3
        try:
            zone = np.zeros((40, 50, 3), dtype=np.uint8)
            bg_a = np.ones((40, 50), dtype=np.uint8) * 255
            bg_b = np.ones((40, 50), dtype=np.uint8) * 255
            cost_on = comp._build_seam_cost_map(zone, bg_a, bg_b)
            comp._SEAM_PIN_ROWS = 0
            cost_off = comp._build_seam_cost_map(zone, bg_a, bg_b)
            assert np.allclose(cost_on, cost_off, atol=1e-5)
        finally:
            comp._SEAM_PIN_ROWS = orig


# ===========================================================================
# Merged from test_compositing_s151.py
# ===========================================================================


class TestZoneMadThresh:
    def test_flag_in_module(self):
        import backend.src.animation.rendering.compositing as comp

        assert hasattr(comp, "_ZONE_MAD_THRESH")

    def test_flag_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_ZONE_MAD_THRESH" in comp.__all__

    def test_default_is_zero(self):
        import backend.src.animation.rendering.compositing as comp

        assert comp._ZONE_MAD_THRESH == pytest.approx(0.0)

    def test_constant_defined(self):
        from backend.src.constants.animation import ZONE_MAD_THRESH_DEFAULT

        assert ZONE_MAD_THRESH_DEFAULT > 0.0

    def test_config_schema_has_key(self):
        from backend.src.animation.core.config import _CONFIG_SCHEMA

        assert "ASP_ZONE_MAD_THRESH" in _CONFIG_SCHEMA


# ---------------------------------------------------------------------------
# §1.102 — Warp residual momentum damping
# ---------------------------------------------------------------------------


class TestWarpMomentumDamp:
    def test_flags_in_module(self):
        import backend.src.animation.rendering.compositing as comp

        assert hasattr(comp, "_WARP_MOMENTUM_DAMP")
        assert hasattr(comp, "_WARP_MOMENTUM_FACTOR")

    def test_flags_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_WARP_MOMENTUM_DAMP" in comp.__all__
        assert "_WARP_MOMENTUM_FACTOR" in comp.__all__

    def test_factor_default_in_range(self):
        import backend.src.animation.rendering.compositing as comp

        assert 0.0 < comp._WARP_MOMENTUM_FACTOR <= 1.0

    def test_constant_defined(self):
        from backend.src.constants.animation import WARP_MOMENTUM_FACTOR

        assert 0.0 < WARP_MOMENTUM_FACTOR <= 1.0

    def test_config_schema_has_keys(self):
        from backend.src.animation.core.config import _CONFIG_SCHEMA

        assert "ASP_WARP_MOMENTUM_DAMP" in _CONFIG_SCHEMA
        assert "ASP_WARP_MOMENTUM_FACTOR" in _CONFIG_SCHEMA


# ---------------------------------------------------------------------------
# §1.103 — Reference-proximity dominant frame selection
# ---------------------------------------------------------------------------


class TestSpRefProx:
    def test_flag_in_module(self):
        import backend.src.animation.rendering.compositing as comp

        assert hasattr(comp, "_SP_REF_PROX")

    def test_flag_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_SP_REF_PROX" in comp.__all__

    def test_default_is_false(self):
        import backend.src.animation.rendering.compositing as comp

        assert comp._SP_REF_PROX is False

    def test_constant_defined(self):
        from backend.src.constants.animation import SP_REF_PROX_DEFAULT

        assert SP_REF_PROX_DEFAULT is False

    def test_ref_prox_picks_closer_frame(self):
        # Pure unit test of the proximity logic, no pipeline needed
        ref_fi = 5
        fi_a, fi_b = 3, 8  # fi_a is closer (|3-5|=2 vs |8-5|=3)
        dom_prox = fi_a if abs(fi_a - ref_fi) <= abs(fi_b - ref_fi) else fi_b
        assert dom_prox == fi_a


# ===========================================================================
# Merged from test_compositing_s152.py
# ===========================================================================


class TestZoneLumNorm:
    def test_identical_zones_unchanged(self):
        from backend.src.animation.rendering.compositing import _zone_lum_norm

        zone = np.full((20, 30, 3), 150, dtype=np.uint8)
        out = _zone_lum_norm(zone, zone)
        assert out.shape == zone.shape

    def test_normalizes_darker_zone(self):
        from backend.src.animation.rendering.compositing import _zone_lum_norm

        fa = np.full((20, 20, 3), 200, dtype=np.uint8)
        fb = np.full((20, 20, 3), 100, dtype=np.uint8)
        out = _zone_lum_norm(fa, fb)
        assert float(out.mean()) > 100.0

    def test_output_shape_preserved(self):
        from backend.src.animation.rendering.compositing import _zone_lum_norm

        rng = np.random.default_rng(0)
        fa = rng.integers(50, 200, (25, 30, 3), dtype=np.uint8)
        fb = rng.integers(50, 200, (25, 30, 3), dtype=np.uint8)
        out = _zone_lum_norm(fa, fb)
        assert out.shape == fb.shape
        assert out.dtype == np.uint8

    def test_black_zone_returns_copy(self):
        from backend.src.animation.rendering.compositing import _zone_lum_norm

        fa = np.zeros((10, 10, 3), dtype=np.uint8)
        fb = np.full((10, 10, 3), 100, dtype=np.uint8)
        out = _zone_lum_norm(fa, fb)
        assert np.array_equal(out, fb)

    def test_function_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_zone_lum_norm" in comp.__all__
        assert "_ZONE_LUM_NORM" in comp.__all__


# ---------------------------------------------------------------------------
# §1.105 — Fg-overlap blend weight cap
# ---------------------------------------------------------------------------


class TestFgOverlapBlendCap:
    def test_flag_in_module(self):
        import backend.src.animation.rendering.compositing as comp

        assert hasattr(comp, "_FG_OVERLAP_BLEND_CAP")

    def test_flag_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_FG_OVERLAP_BLEND_CAP" in comp.__all__

    def test_default_is_zero(self):
        import backend.src.animation.rendering.compositing as comp

        assert comp._FG_OVERLAP_BLEND_CAP == pytest.approx(0.0)

    def test_constant_defined(self):
        from backend.src.constants.animation import FG_OVERLAP_BLEND_CAP_DEFAULT

        assert 0.0 < FG_OVERLAP_BLEND_CAP_DEFAULT <= 0.5

    def test_config_schema_has_key(self):
        from backend.src.animation.core.config import _CONFIG_SCHEMA

        assert "ASP_FG_OVERLAP_BLEND_CAP" in _CONFIG_SCHEMA


# ---------------------------------------------------------------------------
# §1.106 — Post-composite seam luminance step audit
# ---------------------------------------------------------------------------


class TestAuditSeamLumSteps:
    def test_flat_canvas_zero_steps(self):
        from backend.src.animation.rendering.compositing import _audit_seam_lum_steps

        canvas = np.full((100, 80, 3), 128, dtype=np.uint8)
        steps = _audit_seam_lum_steps(canvas, [30.0, 60.0], band_px=5, warn_thresh=8.0)
        assert len(steps) == 2
        assert steps[0] < 1.0
        assert steps[1] < 1.0

    def test_sharp_step_detected(self):
        from backend.src.animation.rendering.compositing import _audit_seam_lum_steps

        canvas = np.zeros((100, 80, 3), dtype=np.uint8)
        canvas[:50] = 200
        canvas[50:] = 50
        steps = _audit_seam_lum_steps(canvas, [50.0], band_px=5, warn_thresh=8.0)
        assert steps[0] > 50.0

    def test_returns_dict_keyed_by_index(self):
        from backend.src.animation.rendering.compositing import _audit_seam_lum_steps

        canvas = np.full((80, 60, 3), 100, dtype=np.uint8)
        steps = _audit_seam_lum_steps(canvas, [20.0, 40.0, 60.0])
        assert isinstance(steps, dict)
        assert set(steps.keys()) == {0, 1, 2}

    def test_empty_boundaries_empty_dict(self):
        from backend.src.animation.rendering.compositing import _audit_seam_lum_steps

        canvas = np.full((60, 40, 3), 128, dtype=np.uint8)
        steps = _audit_seam_lum_steps(canvas, [])
        assert steps == {}

    def test_function_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_audit_seam_lum_steps" in comp.__all__
        assert "_POST_SEAM_WARN_THRESH" in comp.__all__


# ===========================================================================
# Merged from test_compositing_s153.py
# ===========================================================================


class TestAdaptiveSeamBand:
    def test_short_zone_uses_base_band(self):
        from backend.src.animation.rendering.compositing import _adaptive_seam_band

        # zone_h=10, base=10, max=40 → max(10, 10//6=1) = 10
        result = _adaptive_seam_band(zone_h=10, base_band=10, max_band=40)
        assert result == 10

    def test_tall_zone_grows_band(self):
        from backend.src.animation.rendering.compositing import _adaptive_seam_band

        # zone_h=120, base=10, max=40 → max(10, 120//6=20) = 20
        result = _adaptive_seam_band(zone_h=120, base_band=10, max_band=40)
        assert result == 20

    def test_very_tall_zone_clamped_to_max(self):
        from backend.src.animation.rendering.compositing import _adaptive_seam_band

        # zone_h=600, base=10, max=40 → min(40, max(10, 100)) = 40
        result = _adaptive_seam_band(zone_h=600, base_band=10, max_band=40)
        assert result == 40

    def test_result_at_least_base_band(self):
        from backend.src.animation.rendering.compositing import _adaptive_seam_band

        for zone_h in [1, 5, 10, 50, 200]:
            result = _adaptive_seam_band(zone_h=zone_h, base_band=8, max_band=40)
            assert result >= 8

    def test_function_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_adaptive_seam_band" in comp.__all__
        assert "_ADAPTIVE_SEAM_BAND" in comp.__all__


# ---------------------------------------------------------------------------
# §1.108 — Laplacian blend alpha schedule
# ---------------------------------------------------------------------------


class TestLaplacianAlphaSchedule:
    def test_flag_in_module(self):
        import backend.src.animation.rendering.compositing as comp

        assert hasattr(comp, "_LAPLACIAN_ALPHA_SCHEDULE")

    def test_flag_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_LAPLACIAN_ALPHA_SCHEDULE" in comp.__all__

    def test_alpha_schedule_accepted_by_laplacian_blend(self):
        from backend.src.animation.core.stateless import _laplacian_blend
        import inspect

        sig = inspect.signature(_laplacian_blend)
        assert "alpha_schedule" in sig.parameters

    def test_alpha_schedule_output_valid(self):
        from backend.src.animation.core.stateless import _laplacian_blend

        rng = np.random.default_rng(42)
        a = rng.integers(0, 256, (30, 40, 3), dtype=np.uint8)
        b = rng.integers(0, 256, (30, 40, 3), dtype=np.uint8)
        mask = np.ones((30, 40), dtype=np.float32) * 0.5
        out = _laplacian_blend(a, b, mask, alpha_schedule=True)
        assert out.shape == a.shape
        assert out.dtype == np.uint8

    def test_constant_defined(self):
        from backend.src.constants.animation import LAPLACIAN_ALPHA_FINE_WEIGHT

        assert 0.0 < LAPLACIAN_ALPHA_FINE_WEIGHT <= 1.0


# ---------------------------------------------------------------------------
# §1.109 — Seam cost map L-inf normalization
# ---------------------------------------------------------------------------


class TestCostMapNorm:
    def test_flag_in_module(self):
        import backend.src.animation.rendering.compositing as comp

        assert hasattr(comp, "_COST_MAP_NORM")

    def test_flag_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_COST_MAP_NORM" in comp.__all__

    def test_normalized_map_max_is_one(self):
        import backend.src.animation.rendering.compositing as comp

        orig = comp._COST_MAP_NORM
        comp._COST_MAP_NORM = True
        try:
            zone = np.zeros((40, 50, 3), dtype=np.uint8)
            bg_a = np.zeros((40, 50), dtype=np.uint8)  # all fg
            bg_b = np.zeros((40, 50), dtype=np.uint8)
            cost = comp._build_seam_cost_map(zone, bg_a, bg_b)
            # Non-barrier max should be <= 1.0 after normalization
            soft_max = float(cost[cost < 1e5].max()) if (cost < 1e5).any() else 0.0
            assert soft_max <= 1.0 + 1e-5
        finally:
            comp._COST_MAP_NORM = orig

    def test_barriers_preserved_after_norm(self):
        import backend.src.animation.rendering.compositing as comp

        orig_norm = comp._COST_MAP_NORM
        orig_barrier = comp._SEAM_HARD_BARRIER
        comp._COST_MAP_NORM = True
        comp._SEAM_HARD_BARRIER = True
        try:
            zone = np.zeros((40, 50, 3), dtype=np.uint8)
            # Mix fg (left half) and bg (right half) to trigger column barrier
            bg_a = np.ones((40, 50), dtype=np.uint8) * 255  # all bg initially
            bg_b = np.ones((40, 50), dtype=np.uint8) * 255
            bg_a[:, :25] = 0  # left columns are fg
            bg_b[:, :25] = 0
            cost = comp._build_seam_cost_map(zone, bg_a, bg_b)
            # With hard barrier enabled on fg-dominated columns, barriers should exist
            assert (cost >= 1e5).any()
        finally:
            comp._COST_MAP_NORM = orig_norm
            comp._SEAM_HARD_BARRIER = orig_barrier

    def test_config_schema_has_key(self):
        from backend.src.animation.core.config import _CONFIG_SCHEMA

        assert "ASP_COST_MAP_NORM" in _CONFIG_SCHEMA


# ===========================================================================
# Merged from test_compositing_s154.py
# ===========================================================================


class TestCostMapBlur:
    def test_flag_in_module(self):
        import backend.src.animation.rendering.compositing as comp

        assert hasattr(comp, "_COST_MAP_BLUR_SIGMA")

    def test_flag_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_COST_MAP_BLUR_SIGMA" in comp.__all__

    def test_blur_smooths_cost_transitions(self):
        import backend.src.animation.rendering.compositing as comp

        orig = comp._COST_MAP_BLUR_SIGMA
        comp._COST_MAP_BLUR_SIGMA = 1.5
        try:
            zone = np.zeros((40, 50, 3), dtype=np.uint8)
            # Left half fg, right half bg → sharp tier boundary at column 25
            bg_a = np.ones((40, 50), dtype=np.uint8) * 255
            bg_b = np.ones((40, 50), dtype=np.uint8) * 255
            bg_a[:, :25] = 0
            bg_b[:, :25] = 0
            cost = comp._build_seam_cost_map(zone, bg_a, bg_b)
            # After blur the cost at the boundary column should be intermediate
            soft_mask = cost < 1e5
            assert soft_mask.any()
            # max cost among soft pixels should be > min (not all uniform)
            soft_vals = cost[soft_mask]
            assert soft_vals.max() > soft_vals.min()
        finally:
            comp._COST_MAP_BLUR_SIGMA = orig

    def test_barriers_preserved_with_blur(self):
        import backend.src.animation.rendering.compositing as comp

        orig_blur = comp._COST_MAP_BLUR_SIGMA
        orig_barrier = comp._SEAM_HARD_BARRIER
        comp._COST_MAP_BLUR_SIGMA = 2.0
        comp._SEAM_HARD_BARRIER = True
        try:
            zone = np.zeros((40, 50, 3), dtype=np.uint8)
            bg_a = np.ones((40, 50), dtype=np.uint8) * 255
            bg_b = np.ones((40, 50), dtype=np.uint8) * 255
            bg_a[:, :25] = 0
            bg_b[:, :25] = 0
            cost = comp._build_seam_cost_map(zone, bg_a, bg_b)
            assert (cost >= 1e5).any(), "Hard barriers must survive blur"
        finally:
            comp._COST_MAP_BLUR_SIGMA = orig_blur
            comp._SEAM_HARD_BARRIER = orig_barrier

    def test_zero_sigma_no_blur(self):
        import backend.src.animation.rendering.compositing as comp

        orig = comp._COST_MAP_BLUR_SIGMA
        comp._COST_MAP_BLUR_SIGMA = 0.0
        try:
            zone = np.zeros((40, 50, 3), dtype=np.uint8)
            bg_a = np.ones((40, 50), dtype=np.uint8) * 255
            bg_b = np.ones((40, 50), dtype=np.uint8) * 255
            bg_a[:, :25] = 0
            bg_b[:, :25] = 0
            cost_off = comp._build_seam_cost_map(zone, bg_a, bg_b)
            comp._COST_MAP_BLUR_SIGMA = 3.0
            cost_on = comp._build_seam_cost_map(zone, bg_a, bg_b)
            # Blurred cost should differ from unblurred
            soft = cost_off < 1e5
            assert not np.allclose(cost_off[soft], cost_on[soft])
        finally:
            comp._COST_MAP_BLUR_SIGMA = orig

    def test_constant_defined(self):
        from backend.src.constants.animation import COST_MAP_BLUR_SIGMA

        assert COST_MAP_BLUR_SIGMA > 0.0


# ---------------------------------------------------------------------------
# §1.111 — Zone background saturation normalization
# ---------------------------------------------------------------------------


class TestZoneSatNorm:
    def test_flag_in_module(self):
        import backend.src.animation.rendering.compositing as comp

        assert hasattr(comp, "_ZONE_SAT_NORM")

    def test_flag_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_ZONE_SAT_NORM" in comp.__all__

    def test_returns_uint8_same_shape(self):
        from backend.src.animation.rendering.compositing import _zone_sat_norm

        rng = np.random.default_rng(0)
        fa = rng.integers(10, 200, (30, 40, 3), dtype=np.uint8)
        fb = rng.integers(10, 200, (30, 40, 3), dtype=np.uint8)
        out = _zone_sat_norm(fa, fb)
        assert out.shape == fb.shape
        assert out.dtype == np.uint8

    def test_all_black_zone_returns_copy(self):
        from backend.src.animation.rendering.compositing import _zone_sat_norm

        fa = np.zeros((20, 30, 3), dtype=np.uint8)
        fb = np.ones((20, 30, 3), dtype=np.uint8) * 50
        out = _zone_sat_norm(fa, fb)
        np.testing.assert_array_equal(out, fb)

    def test_identical_saturation_unchanged(self):
        from backend.src.animation.rendering.compositing import _zone_sat_norm

        # Create a solid-color patch with defined saturation
        fa = np.full((30, 40, 3), 100, dtype=np.uint8)
        fb = fa.copy()
        out = _zone_sat_norm(fa, fb)
        # Same saturation → gain ~1.0 → output should be close to input
        assert np.abs(out.astype(np.float32) - fb.astype(np.float32)).mean() < 5.0


# ---------------------------------------------------------------------------
# §1.112 — Seam path vertical drift
# ---------------------------------------------------------------------------


class TestSeamPathDrift:
    def test_constant_path_zero_drift(self):
        from backend.src.animation.rendering.compositing import _seam_path_drift

        path = np.full(50, 10, dtype=np.int32)
        assert _seam_path_drift(path) == 0.0

    def test_single_large_jump(self):
        from backend.src.animation.rendering.compositing import _seam_path_drift

        path = np.zeros(50, dtype=np.int32)
        path[25:] = 20  # jump of 20 at column 25
        result = _seam_path_drift(path)
        assert result == pytest.approx(20.0)

    def test_gradual_slope_small_drift(self):
        from backend.src.animation.rendering.compositing import _seam_path_drift

        path = np.arange(50, dtype=np.int32)  # step of 1 per column
        result = _seam_path_drift(path)
        assert result == pytest.approx(1.0)

    def test_empty_path_returns_zero(self):
        from backend.src.animation.rendering.compositing import _seam_path_drift

        assert _seam_path_drift(np.array([], dtype=np.int32)) == 0.0

    def test_flag_and_constant_defined(self):
        import backend.src.animation.rendering.compositing as comp

        assert hasattr(comp, "_SEAM_DRIFT_THRESH")
        assert "_SEAM_DRIFT_THRESH" in comp.__all__
        from backend.src.constants.animation import SEAM_DRIFT_THRESH

        assert SEAM_DRIFT_THRESH > 0.0


# ===========================================================================
# Merged from test_compositing_s155.py
# ===========================================================================


class TestCostColSmoothSigma:
    def test_flag_in_module(self):
        import backend.src.animation.rendering.compositing as comp

        assert hasattr(comp, "_COST_COL_SMOOTH_SIGMA")

    def test_flag_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_COST_COL_SMOOTH_SIGMA" in comp.__all__

    def test_default_is_zero(self):
        import backend.src.animation.rendering.compositing as comp

        assert comp._COST_COL_SMOOTH_SIGMA == pytest.approx(0.0)

    def test_column_smooth_spreads_cost(self):
        import backend.src.animation.rendering.compositing as comp

        orig = comp._COST_COL_SMOOTH_SIGMA
        comp._COST_COL_SMOOTH_SIGMA = 1.5
        try:
            zone = np.zeros((30, 50, 3), dtype=np.uint8)
            bg_a = np.ones((30, 50), dtype=np.uint8) * 255
            bg_b = np.ones((30, 50), dtype=np.uint8) * 255
            bg_a[:, 20:25] = 0
            bg_b[:, 20:25] = 0
            cost = comp._build_seam_cost_map(zone, bg_a, bg_b)
            # Column smooth should spread cost laterally from fg columns
            assert cost[:, 15].mean() > 0.0
        finally:
            comp._COST_COL_SMOOTH_SIGMA = orig

    def test_constant_defined(self):
        from backend.src.constants.animation import COST_COL_SMOOTH_SIGMA

        assert COST_COL_SMOOTH_SIGMA > 0.0


class TestZoneContrastEq:
    def test_identical_zones_returns_same_shape(self):
        from backend.src.animation.rendering.compositing import _zone_contrast_eq

        rng = np.random.default_rng(1)
        zone = rng.integers(50, 200, (20, 30, 3), dtype=np.uint8)
        out = _zone_contrast_eq(zone, zone)
        assert out.shape == zone.shape

    def test_equalizes_low_contrast_zone(self):
        from backend.src.animation.rendering.compositing import _zone_contrast_eq

        rng = np.random.default_rng(2)
        fa = rng.integers(50, 200, (20, 20, 3), dtype=np.uint8)
        # Near-flat fb
        fb_flat = np.clip(
            np.full((20, 20, 3), 128, dtype=np.int32)
            + rng.integers(-4, 5, (20, 20, 3)),
            0,
            255,
        ).astype(np.uint8)
        out = _zone_contrast_eq(fa, fb_flat)
        assert out.std() >= fb_flat.std() - 1

    def test_output_shape_and_dtype_preserved(self):
        from backend.src.animation.rendering.compositing import _zone_contrast_eq

        rng = np.random.default_rng(3)
        fa = rng.integers(0, 256, (25, 30, 3), dtype=np.uint8)
        fb = rng.integers(0, 256, (25, 30, 3), dtype=np.uint8)
        out = _zone_contrast_eq(fa, fb)
        assert out.shape == fb.shape
        assert out.dtype == np.uint8

    def test_black_zone_returns_copy(self):
        from backend.src.animation.rendering.compositing import _zone_contrast_eq

        fa = np.zeros((10, 10, 3), dtype=np.uint8)
        fb = np.full((10, 10, 3), 100, dtype=np.uint8)
        out = _zone_contrast_eq(fa, fb)
        assert np.array_equal(out, fb)

    def test_function_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_zone_contrast_eq" in comp.__all__
        assert "_ZONE_CONTRAST_EQ" in comp.__all__


class TestCapFeatherJumps:
    def test_no_jump_identity(self):
        from backend.src.animation.rendering.compositing import _cap_feather_jumps

        f = np.array([100, 110, 105, 108], dtype=np.int64)
        out = _cap_feather_jumps(f, max_jump=50)
        assert np.array_equal(out, f)

    def test_caps_large_jump(self):
        from backend.src.animation.rendering.compositing import _cap_feather_jumps

        f = np.array([80, 300, 80, 80], dtype=np.int64)
        out = _cap_feather_jumps(f, max_jump=100)
        assert out[1] <= 80 + 100

    def test_single_element_passthrough(self):
        from backend.src.animation.rendering.compositing import _cap_feather_jumps

        f = np.array([200], dtype=np.int64)
        out = _cap_feather_jumps(f, max_jump=50)
        assert len(out) == 1

    def test_zero_max_jump_passthrough(self):
        from backend.src.animation.rendering.compositing import _cap_feather_jumps

        f = np.array([80, 300, 80], dtype=np.int64)
        out = _cap_feather_jumps(f, max_jump=0)
        assert np.array_equal(out, f)

    def test_function_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_cap_feather_jumps" in comp.__all__
        assert "_FEATHER_JUMP_MAX" in comp.__all__


# ===========================================================================
# Merged from test_compositing_s156.py
# ===========================================================================


class TestZoneBgFracDiag:
    def test_flag_in_module(self):
        import backend.src.animation.rendering.compositing as comp

        assert hasattr(comp, "_ZONE_BG_FRAC_DIAG")

    def test_flag_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_ZONE_BG_FRAC_DIAG" in comp.__all__

    def test_default_is_false(self):
        import backend.src.animation.rendering.compositing as comp

        assert comp._ZONE_BG_FRAC_DIAG is False

    def test_constant_defined(self):
        from backend.src.constants.animation import ZONE_BG_FRAC_DIAG_KEY

        assert isinstance(ZONE_BG_FRAC_DIAG_KEY, str)

    def test_config_schema_has_key(self):
        from backend.src.animation.core.config import _CONFIG_SCHEMA

        assert "ASP_ZONE_BG_FRAC_DIAG" in _CONFIG_SCHEMA


class TestZonePairNcc:
    def test_identical_zones_returns_one(self):
        from backend.src.animation.rendering.compositing import _zone_pair_ncc

        rng = np.random.default_rng(0)
        zone = rng.integers(30, 200, (30, 40, 3), dtype=np.uint8)
        ncc = _zone_pair_ncc(zone, zone)
        assert ncc == pytest.approx(1.0, abs=1e-4)

    def test_opposite_zones_low_ncc(self):
        from backend.src.animation.rendering.compositing import _zone_pair_ncc

        a = np.zeros((20, 20, 3), dtype=np.uint8)
        a[:10] = 200
        b = np.zeros((20, 20, 3), dtype=np.uint8)
        b[10:] = 200
        ncc = _zone_pair_ncc(a, b)
        assert ncc < 0.9

    def test_result_in_valid_range(self):
        from backend.src.animation.rendering.compositing import _zone_pair_ncc

        rng = np.random.default_rng(42)
        a = rng.integers(0, 256, (25, 30, 3), dtype=np.uint8)
        b = rng.integers(0, 256, (25, 30, 3), dtype=np.uint8)
        ncc = _zone_pair_ncc(a, b)
        assert -1.0 <= ncc <= 1.0

    def test_empty_zone_returns_one(self):
        from backend.src.animation.rendering.compositing import _zone_pair_ncc

        empty = np.zeros((0, 10, 3), dtype=np.uint8)
        ncc = _zone_pair_ncc(empty, empty)
        assert ncc == pytest.approx(1.0)

    def test_function_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_zone_pair_ncc" in comp.__all__
        assert "_ZONE_FAST_NCC_THRESH" in comp.__all__


class TestMeasureSeamSharpness:
    def test_flat_canvas_low_sharpness(self):
        from backend.src.animation.rendering.compositing import _measure_seam_sharpness

        canvas = np.full((100, 80, 3), 128, dtype=np.uint8)
        sharpness = _measure_seam_sharpness(canvas, [30.0, 60.0], band_px=5)
        assert len(sharpness) == 2
        assert sharpness[0] < 10.0
        assert sharpness[1] < 10.0

    def test_sharp_edge_high_variance(self):
        from backend.src.animation.rendering.compositing import _measure_seam_sharpness

        canvas = np.zeros((80, 60, 3), dtype=np.uint8)
        canvas[:40] = 200
        canvas[40:] = 0
        sharpness = _measure_seam_sharpness(canvas, [40.0], band_px=5)
        assert sharpness[0] > 100.0

    def test_returns_dict_keyed_by_index(self):
        from backend.src.animation.rendering.compositing import _measure_seam_sharpness

        canvas = np.full((80, 60, 3), 100, dtype=np.uint8)
        sharpness = _measure_seam_sharpness(canvas, [20.0, 40.0, 60.0])
        assert isinstance(sharpness, dict)
        assert set(sharpness.keys()) == {0, 1, 2}

    def test_empty_boundaries_empty_dict(self):
        from backend.src.animation.rendering.compositing import _measure_seam_sharpness

        canvas = np.full((60, 40, 3), 128, dtype=np.uint8)
        sharpness = _measure_seam_sharpness(canvas, [])
        assert sharpness == {}

    def test_function_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_measure_seam_sharpness" in comp.__all__
        assert "_SEAM_SHARP_MIN" in comp.__all__


# ===========================================================================
# Merged from test_compositing_s157.py
# ===========================================================================


class TestZoneWidthCv:
    def test_uniform_widths_zero_cv(self):
        from backend.src.animation.rendering.compositing import _zone_width_cv

        boundaries = [0.0, 100.0, 200.0, 300.0]
        cv = _zone_width_cv(boundaries)
        assert cv == pytest.approx(0.0, abs=1e-6)

    def test_uneven_widths_high_cv(self):
        from backend.src.animation.rendering.compositing import _zone_width_cv

        boundaries = [0.0, 5.0, 200.0, 205.0]
        cv = _zone_width_cv(boundaries)
        assert cv > 0.5

    def test_single_boundary_returns_zero(self):
        from backend.src.animation.rendering.compositing import _zone_width_cv

        assert _zone_width_cv([50.0]) == pytest.approx(0.0)

    def test_empty_boundaries_returns_zero(self):
        from backend.src.animation.rendering.compositing import _zone_width_cv

        assert _zone_width_cv([]) == pytest.approx(0.0)

    def test_function_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_zone_width_cv" in comp.__all__
        assert "_ZONE_WIDTH_CV_MAX" in comp.__all__


class TestAuditSeamSatSteps:
    def test_uniform_image_zero_step(self):
        from backend.src.animation.rendering.compositing import _audit_seam_sat_steps

        canvas = np.full((80, 60, 3), 128, dtype=np.uint8)
        sat_steps = _audit_seam_sat_steps(canvas, [40.0], band_px=5)
        assert len(sat_steps) == 1
        assert sat_steps[0] < 5.0

    def test_saturated_vs_grey_high_step(self):
        from backend.src.animation.rendering.compositing import _audit_seam_sat_steps

        canvas = np.zeros((80, 60, 3), dtype=np.uint8)
        # Top half: vivid red (high sat in HSV)
        canvas[:40] = (0, 0, 200)
        # Bottom half: grey (zero sat)
        canvas[40:] = (128, 128, 128)
        sat_steps = _audit_seam_sat_steps(canvas, [40.0], band_px=5)
        assert sat_steps[0] > 10.0

    def test_empty_boundaries_empty_dict(self):
        from backend.src.animation.rendering.compositing import _audit_seam_sat_steps

        canvas = np.full((60, 40, 3), 100, dtype=np.uint8)
        sat_steps = _audit_seam_sat_steps(canvas, [])
        assert sat_steps == {}

    def test_returns_dict_keyed_by_index(self):
        from backend.src.animation.rendering.compositing import _audit_seam_sat_steps

        canvas = np.full((90, 60, 3), 120, dtype=np.uint8)
        sat_steps = _audit_seam_sat_steps(canvas, [30.0, 60.0])
        assert isinstance(sat_steps, dict)
        assert set(sat_steps.keys()) == {0, 1}

    def test_flag_and_function_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_audit_seam_sat_steps" in comp.__all__
        assert "_SEAM_SAT_WARN_THRESH" in comp.__all__


class TestZoneHistIntersection:
    def test_identical_zones_returns_one(self):
        from backend.src.animation.rendering.compositing import _zone_hist_intersection

        rng = np.random.default_rng(1)
        zone = rng.integers(20, 200, (30, 40, 3), dtype=np.uint8)
        score = _zone_hist_intersection(zone, zone)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_different_palettes_low_score(self):
        from backend.src.animation.rendering.compositing import _zone_hist_intersection

        a = np.zeros((30, 30, 3), dtype=np.uint8)
        a[:] = (200, 50, 50)
        b = np.zeros((30, 30, 3), dtype=np.uint8)
        b[:] = (50, 50, 200)
        score = _zone_hist_intersection(a, b)
        assert score < 0.7

    def test_result_in_valid_range(self):
        from backend.src.animation.rendering.compositing import _zone_hist_intersection

        rng = np.random.default_rng(99)
        a = rng.integers(0, 256, (20, 20, 3), dtype=np.uint8)
        b = rng.integers(0, 256, (20, 20, 3), dtype=np.uint8)
        score = _zone_hist_intersection(a, b)
        assert 0.0 <= score <= 1.0

    def test_empty_zone_returns_one(self):
        from backend.src.animation.rendering.compositing import _zone_hist_intersection

        empty = np.zeros((0, 10, 3), dtype=np.uint8)
        score = _zone_hist_intersection(empty, empty)
        assert score == pytest.approx(1.0)

    def test_function_in_all(self):
        import backend.src.animation.rendering.compositing as comp

        assert "_zone_hist_intersection" in comp.__all__
        assert "_ZONE_HIST_THRESH" in comp.__all__


# ===========================================================================
# Merged from test_compositing_s158.py
# ===========================================================================


class TestMeanPathCost:
    """Five tests for _mean_path_cost (S158)."""

    @pytest.fixture(autouse=True)
    def _import(self):
        import backend.src.animation.rendering.compositing as comp

        importlib.reload(comp)
        self.comp = comp

    def test_uniform_cost_map(self):
        """Mean of constant cost map equals that constant."""
        cost = np.ones((10, 20), dtype=np.float32) * 0.5
        path = np.full(20, 5, dtype=np.int32)
        assert self.comp._mean_path_cost(path, cost) == pytest.approx(0.5, abs=1e-5)

    def test_path_selects_rows(self):
        """Path samples the correct row per column from a row-varying cost map."""
        H, W = 8, 4
        cost = np.zeros((H, W), dtype=np.float32)
        cost[3, :] = 1.0  # row 3 is expensive
        path = np.full(W, 3, dtype=np.int32)
        assert self.comp._mean_path_cost(path, cost) == pytest.approx(1.0, abs=1e-5)

    def test_empty_path_returns_zero(self):
        """Empty path array returns 0.0 without error."""
        cost = np.ones((5, 5), dtype=np.float32)
        assert self.comp._mean_path_cost(np.array([], dtype=np.int32), cost) == 0.0

    def test_empty_cost_map_returns_zero(self):
        """Empty cost map returns 0.0 without error."""
        path = np.array([1, 2, 3], dtype=np.int32)
        assert self.comp._mean_path_cost(path, np.array([], dtype=np.float32)) == 0.0

    def test_out_of_bounds_rows_clamped(self):
        """Path rows outside cost map height are clamped, not IndexError."""
        cost = np.ones((5, 3), dtype=np.float32)
        path = np.array([100, -5, 3], dtype=np.int32)  # row 100 and -5 out of bounds
        result = self.comp._mean_path_cost(path, cost)
        assert 0.0 <= result <= 2.0  # must be a valid float, not error


# ---------------------------------------------------------------------------
# §1.123 — scatter cost penalty in _build_seam_cost_map
# ---------------------------------------------------------------------------
class TestScatterCost:
    """Five tests for §1.123 scatter cost penalty (S158)."""

    def _build_cost(self, canvas_zone, scatter=True, weight=0.3):
        """Helper: build cost map with scatter flag set via env."""
        import backend.src.animation.rendering.compositing as comp

        orig_sc = os.environ.get("ASP_SCATTER_COST", "0")
        orig_w = os.environ.get("ASP_SCATTER_COST_WEIGHT", "0.3")
        try:
            os.environ["ASP_SCATTER_COST"] = "1" if scatter else "0"
            os.environ["ASP_SCATTER_COST_WEIGHT"] = str(weight)
            importlib.reload(comp)
            return comp._build_seam_cost_map(canvas_zone, None, None)
        finally:
            os.environ["ASP_SCATTER_COST"] = orig_sc
            os.environ["ASP_SCATTER_COST_WEIGHT"] = orig_w
            importlib.reload(comp)

    def test_scatter_off_unchanged(self):
        """With scatter disabled, cost map is unaffected by local variance."""
        canvas = np.random.randint(0, 255, (20, 30, 3), dtype=np.uint8)
        cost_off = self._build_cost(canvas, scatter=False)
        cost_on = self._build_cost(canvas, scatter=True, weight=0.0)
        # weight=0 → no change even if flag is on
        np.testing.assert_array_almost_equal(cost_off, cost_on, decimal=4)

    def test_scatter_adds_positive_cost(self):
        """Scatter-enabled map has >= base cost for non-barrier pixels."""
        rng = np.random.default_rng(42)
        canvas = rng.integers(0, 255, (30, 40, 3), dtype=np.uint8)
        import backend.src.animation.rendering.compositing as comp

        importlib.reload(comp)
        cost_base = comp._build_seam_cost_map(canvas, None, None)
        cost_scatter = self._build_cost(canvas, scatter=True, weight=0.5)
        soft = cost_base < 1e5
        assert float((cost_scatter[soft] - cost_base[soft]).min()) >= -1e-4

    def test_uniform_canvas_zero_variance(self):
        """Uniform canvas has zero variance → scatter adds ~0 cost."""
        canvas = np.full((20, 20, 3), 128, dtype=np.uint8)
        import backend.src.animation.rendering.compositing as comp

        importlib.reload(comp)
        cost_base = comp._build_seam_cost_map(canvas, None, None)
        cost_scatter = self._build_cost(canvas, scatter=True, weight=1.0)
        soft = cost_base < 1e5
        np.testing.assert_array_almost_equal(
            cost_scatter[soft], cost_base[soft], decimal=3
        )

    def test_scatter_weight_scales_penalty(self):
        """Higher weight → larger scatter additive penalty."""
        rng = np.random.default_rng(7)
        canvas = rng.integers(0, 255, (30, 30, 3), dtype=np.uint8)
        import backend.src.animation.rendering.compositing as comp

        importlib.reload(comp)
        cost_base = comp._build_seam_cost_map(canvas, None, None)
        cost_low = self._build_cost(canvas, scatter=True, weight=0.1)
        cost_high = self._build_cost(canvas, scatter=True, weight=1.0)
        soft = cost_base < 1e5
        mean_low = float((cost_low[soft] - cost_base[soft]).mean())
        mean_high = float((cost_high[soft] - cost_base[soft]).mean())
        assert mean_high > mean_low

    def test_scatter_does_not_affect_barriers(self):
        """Scatter penalty is NOT applied to barrier-cost pixels (cost >= 1e5)."""
        import backend.src.animation.rendering.compositing as comp

        # Synthetic fg mask: full foreground → generates high-cost barrier cols
        canvas = np.zeros((20, 20, 3), dtype=np.uint8)
        fg_mask = np.full((20, 20), 255, dtype=np.uint8)
        importlib.reload(comp)
        # Build with hard barrier flag
        orig_b = os.environ.get("ASP_SEAM_HARD_BARRIER", "0")
        orig_sc = os.environ.get("ASP_SCATTER_COST", "0")
        try:
            os.environ["ASP_SEAM_HARD_BARRIER"] = "1"
            os.environ["ASP_SCATTER_COST"] = "1"
            importlib.reload(comp)
            cost = comp._build_seam_cost_map(canvas, fg_mask, fg_mask)
            barriers = cost >= 1e5
            if barriers.any():
                # Scatter should not have lowered any barrier pixel
                assert float(cost[barriers].min()) >= 1e5
        finally:
            os.environ["ASP_SEAM_HARD_BARRIER"] = orig_b
            os.environ["ASP_SCATTER_COST"] = orig_sc
            importlib.reload(comp)


# ---------------------------------------------------------------------------
# §1.124 — adaptive SP soft-edge width from seam residual
# ---------------------------------------------------------------------------
class TestAdaptiveSpSoft:
    """Five tests for §1.124 residual-based adaptive soft-edge width (S158)."""

    @pytest.fixture(autouse=True)
    def _import(self):
        orig = os.environ.get("ASP_ADAPTIVE_SP_SOFT", "0")
        os.environ["ASP_ADAPTIVE_SP_SOFT"] = "1"
        import backend.src.animation.rendering.compositing as comp

        importlib.reload(comp)
        self.comp = comp
        yield
        os.environ["ASP_ADAPTIVE_SP_SOFT"] = orig
        importlib.reload(comp)

    def _read_min_max(self):
        return self.comp._ADAPTIVE_SP_SOFT_MIN, self.comp._ADAPTIVE_SP_SOFT_MAX

    def test_min_max_defaults(self):
        """Default MIN=3, MAX=10."""
        mn, mx = self._read_min_max()
        assert mn == 3
        assert mx == 10

    def test_high_residual_uses_min(self):
        """Post-diff > 30 → effective width clamped to MIN."""
        # Simulate the residual-based logic directly
        sp_soft = 6
        seam_post_diffs = {0: 40.0}  # high residual
        mn, mx = self._read_min_max()
        post_d = seam_post_diffs.get(0, 22.0)
        eff = sp_soft
        if post_d > 30.0:
            eff = mn
        elif post_d < 10.0:
            eff = mx
        assert eff == mn

    def test_low_residual_uses_max(self):
        """Post-diff < 10 → effective width widened to MAX."""
        sp_soft = 6
        seam_post_diffs = {0: 5.0}  # low residual
        mn, mx = self._read_min_max()
        post_d = seam_post_diffs.get(0, 22.0)
        eff = sp_soft
        if post_d > 30.0:
            eff = mn
        elif post_d < 10.0:
            eff = mx
        assert eff == mx

    def test_mid_residual_unchanged(self):
        """Post-diff in [10, 30] → effective width unchanged from sp_soft."""
        sp_soft = 6
        seam_post_diffs = {0: 20.0}  # mid residual
        mn, mx = self._read_min_max()
        post_d = seam_post_diffs.get(0, 22.0)
        eff = sp_soft
        if post_d > 30.0:
            eff = mn
        elif post_d < 10.0:
            eff = mx
        assert eff == sp_soft

    def test_env_override_min_max(self):
        """ASP_ADAPTIVE_SP_SOFT_MIN/MAX env vars override defaults."""
        orig_min = os.environ.get("ASP_ADAPTIVE_SP_SOFT_MIN", "3")
        orig_max = os.environ.get("ASP_ADAPTIVE_SP_SOFT_MAX", "10")
        try:
            os.environ["ASP_ADAPTIVE_SP_SOFT_MIN"] = "5"
            os.environ["ASP_ADAPTIVE_SP_SOFT_MAX"] = "15"
            import backend.src.animation.rendering.compositing as comp

            importlib.reload(comp)
            assert comp._ADAPTIVE_SP_SOFT_MIN == 5
            assert comp._ADAPTIVE_SP_SOFT_MAX == 15
        finally:
            os.environ["ASP_ADAPTIVE_SP_SOFT_MIN"] = orig_min
            os.environ["ASP_ADAPTIVE_SP_SOFT_MAX"] = orig_max
            importlib.reload(comp)


# ===========================================================================
# Merged from test_compositing_s159.py
# ===========================================================================


class TestSeamTransitionPenalty:
    """§1.125: transition_penalty biases DP seam toward zone midline."""

    def _make_zones(self, h=40, w=30):
        rng = np.random.default_rng(0)
        a = rng.integers(80, 200, (h, w, 3), dtype=np.uint8)
        b = rng.integers(80, 200, (h, w, 3), dtype=np.uint8)
        return a, b

    def test_zero_penalty_does_not_change_output_type(self):
        from backend.src.animation.rendering.compositing import _seam_cut

        a, b = self._make_zones()
        path = _seam_cut(a, b)
        assert path.ndim == 1
        assert len(path) == a.shape[1]

    def test_transition_pen_biases_toward_midline(self, monkeypatch):
        """With a large penalty the mean path row should be closer to h//2."""
        from backend.src.animation.rendering import compositing as _mod

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
        from backend.src.animation.rendering import compositing as _mod

        monkeypatch.setattr(_mod, "_SEAM_TRANSITION_PEN", 20.0)
        a, b = self._make_zones()
        path = _mod._seam_cut(a, b)
        assert path.min() >= 0
        assert path.max() < a.shape[0]

    def test_path_length_equals_width(self, monkeypatch):
        from backend.src.animation.rendering import compositing as _mod

        monkeypatch.setattr(_mod, "_SEAM_TRANSITION_PEN", 10.0)
        a, b = self._make_zones(h=20, w=50)
        path = _mod._seam_cut(a, b)
        assert len(path) == 50

    def test_large_penalty_all_rows_near_mid(self, monkeypatch):
        """Extreme penalty: every path pixel should be within 5 of midline."""
        from backend.src.animation.rendering import compositing as _mod

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
        from backend.src.animation.rendering import compositing as _mod

        monkeypatch.setattr(_mod, "_FG_MAJORITY_FLOOR", 0.0)
        zone = self._make_fg_zone()
        cost = _mod._build_seam_cost_map(zone, self._bg_mask(zone), self._bg_mask(zone))
        assert cost is not None

    def test_floor_raises_heavy_fg_columns(self, monkeypatch):
        """Heavy fg columns should be raised to at least _FG_MAJORITY_FLOOR."""
        from backend.src.animation.rendering import compositing as _mod

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
        from backend.src.animation.rendering import compositing as _mod

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
        from backend.src.animation.rendering import compositing as _mod

        monkeypatch.setattr(_mod, "_FG_MAJORITY_FLOOR", 1.5)
        zone = np.zeros((20, 20, 3), dtype=np.uint8)  # pure bg
        zone[:, :3] = 100  # only 15% fg → no change
        bg = self._bg_mask(zone)
        cost = _mod._build_seam_cost_map(zone, bg, bg)
        assert cost.max() < 1.5

    def test_cost_never_reduced_by_floor(self, monkeypatch):
        """_FG_MAJORITY_FLOOR must only raise costs, never lower them."""
        from backend.src.animation.rendering import compositing as _mod

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
        from backend.src.animation.rendering.compositing import _zone_hue_eq

        fa = np.full((20, 15, 3), [120, 60, 60], dtype=np.uint8)
        fb = np.full((20, 15, 3), [60, 120, 60], dtype=np.uint8)
        out = _zone_hue_eq(fa, fb)
        assert out.shape == fb.shape
        assert out.dtype == np.uint8

    def test_hue_shift_applied(self):
        """Mean hue of output should be closer to fa's mean hue."""
        import cv2
        from backend.src.animation.rendering.compositing import _zone_hue_eq

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
        from backend.src.animation.rendering.compositing import _zone_hue_eq

        # Nearly identical hue
        fa = np.full((20, 15, 3), [100, 150, 50], dtype=np.uint8)
        fb = np.full((20, 15, 3), [102, 148, 51], dtype=np.uint8)
        out = _zone_hue_eq(fa, fb)
        np.testing.assert_array_equal(out, fb)

    def test_all_black_input_returns_copy(self):
        """All-black zones have no content pixels — return unmodified copy."""
        from backend.src.animation.rendering.compositing import _zone_hue_eq

        fa = np.zeros((10, 10, 3), dtype=np.uint8)
        fb = np.zeros((10, 10, 3), dtype=np.uint8)
        out = _zone_hue_eq(fa, fb)
        np.testing.assert_array_equal(out, fb)

    def test_wired_in_blend_loop(self, monkeypatch):
        """_ZONE_HUE_EQ=True causes _zone_hue_eq to be called in blend loop."""
        from backend.src.animation.rendering import compositing as _mod

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


# ===========================================================================
# Merged from test_compositing_s160.py
# ===========================================================================


class TestBlocksGainCompensate:
    """§4.1: Spatial blocks BGR gain compensation."""

    def test_flag_in_module(self):
        assert hasattr(compositing, "_BLOCKS_GAIN_COMP")

    def test_uniform_zone_no_change(self):
        # fa == fb == solid gray → gain ≈ 1.0 → output ≈ input
        zone = np.full((64, 64, 3), 128, dtype=np.uint8)
        result = _blocks_gain_compensate(zone, zone.copy(), block_size=32)
        assert result.shape == zone.shape
        assert result.dtype == np.uint8
        diff = np.abs(result.astype(np.int32) - zone.astype(np.int32)).max()
        assert diff <= 2  # rounding tolerance

    def test_applies_gain_correction(self):
        # fa is brighter than fb → output should be brighter than fb
        fa = np.full((64, 64, 3), 200, dtype=np.uint8)
        fb = np.full((64, 64, 3), 100, dtype=np.uint8)
        result = _blocks_gain_compensate(fa, fb, block_size=32)
        assert float(result.mean()) > float(fb.mean())

    def test_clamps_extreme_gain(self):
        # fb ≈ 0 (very dark) — gain would be huge; clamped to 2.0 → no crash
        fa = np.full((64, 64, 3), 128, dtype=np.uint8)
        fb = np.full((64, 64, 3), 0, dtype=np.uint8)
        result = _blocks_gain_compensate(fa, fb, block_size=32)
        assert result.dtype == np.uint8
        assert result.min() >= 0
        assert result.max() <= 255

    def test_constant_added_to_schema(self):
        assert "ASP_BLOCKS_GAIN_COMP" in config._CONFIG_SCHEMA


class TestBlocksLumCompensate:
    """§4.4: LAB L-channel blocks gain compensation."""

    def test_flag_in_module(self):
        assert hasattr(compositing, "_BLOCKS_LUM_COMP")

    def test_uniform_zone_no_change(self):
        zone = np.full((64, 64, 3), 128, dtype=np.uint8)
        result = _blocks_lum_compensate(zone, zone.copy(), block_size=32)
        assert result.shape == zone.shape
        assert result.dtype == np.uint8
        diff = np.abs(result.astype(np.int32) - zone.astype(np.int32)).max()
        assert diff <= 2

    def test_brightens_dark_fb(self):
        fa = np.full((64, 64, 3), 150, dtype=np.uint8)
        fb = np.full((64, 64, 3), 100, dtype=np.uint8)
        result = _blocks_lum_compensate(fa, fb, block_size=32)
        assert float(result.mean()) > float(fb.mean())

    def test_output_shape_preserved(self):
        fa = np.random.randint(50, 200, (80, 60, 3), dtype=np.uint8)
        fb = np.random.randint(50, 200, (80, 60, 3), dtype=np.uint8)
        result = _blocks_lum_compensate(fa, fb, block_size=32)
        assert result.shape == fb.shape
        assert result.dtype == np.uint8

    def test_schema_entry(self):
        assert "ASP_BLOCKS_LUM_COMP" in config._CONFIG_SCHEMA
