"""
Tests for the Stage 11 Laplacian-blend composite (compositing.py).

Issue categories covered:
  A — Seam blending: feather zone, boundary search, Laplacian pyramid blend.

All tests run without GPU — no BiRefNet or LoFTR dependencies.
"""

from __future__ import annotations

import os
import sys

import cv2
import numpy as np
import pytest

_repo_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, _repo_root)

from backend.src.anim.compositing import (  # noqa: E402
    _adaptive_gain_clamp,
    _apply_bg_histogram_match,
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
)
from backend.src.constants import (  # noqa: E402
    FEATHER_MAX as _FEATHER_MAX,
    FEATHER_MIN as _FEATHER_MIN,
    FEATHER_TABLE as _FEATHER_TABLE,
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
        z = np.clip(z.astype(np.int32) + rng.integers(-noise, noise + 1, z.shape), 0, 255)
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
        assert int(diffs.max()) <= 1, f"Path not 3-connected: max step={int(diffs.max())}"


# ---------------------------------------------------------------------------
# 4. Parallel seam pre-computation (_precomp_paths) — S12 integration
# ---------------------------------------------------------------------------


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
        affines = [make_translation_affine(ty=i * float(frame_h) * 0.9) for i in range(n)]
        canvas_h = int((n - 1) * frame_h * 0.9 + frame_h)
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
        return _composite_foreground([], [], canvas, canvas_h, W, frames, affines, [None] * n)

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
        affines = [make_translation_affine(ty=i * float(frame_h) * 0.9) for i in range(n)]
        canvas_h = int((n - 1) * frame_h * 0.9 + frame_h)
        canvas = np.zeros((canvas_h, W, 3), dtype=np.uint8)
        result = _composite_foreground([], [], canvas, canvas_h, W, frames, affines, [None] * n)
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
        apply = np.zeros((H, W), dtype=bool)   # nothing applied
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
        assert int(seam_row) == dom_lum, f"Band pixel should equal dom_lum={dom_lum}, got {seam_row}"

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
        dom[:, :, 0] = 50   # B=50, G=0, R=0
        dom[:, :, 1] = 100  # B=50, G=100, R=0
        dom[:, :, 2] = 150  # B=50, G=100, R=150
        oth = np.full((H, W, 3), 200, dtype=np.uint8)  # B=G=R=200
        path = self._path(W, seam_y)
        out = _seam_color_match(dom, oth, path, band_px)
        # delta per channel: B=50-200=-150, G=100-200=-100, R=150-200=-50
        # band pixel after shift: B=clip(200-150,0,255)=50, G=100, R=150
        band_px_val = out[seam_y, 0]
        assert int(band_px_val[0]) == 50,  f"B channel: expected 50, got {band_px_val[0]}"
        assert int(band_px_val[1]) == 100, f"G channel: expected 100, got {band_px_val[1]}"
        assert int(band_px_val[2]) == 150, f"R channel: expected 150, got {band_px_val[2]}"


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
        assert float(out[0].mean()) > 0.95, f"Top row weight: {float(out[0].mean()):.3f}"

    def test_weight_zero_far_below_seam(self):
        """Far below the seam, weight should be ~0.0 (all fb)."""
        H, W, seam_y = 100, 80, 50
        fa = self._uniform(H, W, 128)
        fb = self._uniform(H, W, 50)
        path = self._path(W, seam_y)
        out = _soft_seam_weight(fa, fb, path, H, W)
        # Last row is far below seam_y=50 → weight should be ~0.0
        assert float(out[-1].mean()) < 0.05, f"Bottom row weight: {float(out[-1].mean()):.3f}"

    def test_high_similarity_gives_wider_blend_than_low(self):
        """Identical frames (high sim) must produce a wider blend than very different frames (low sim)."""
        H, W, seam_y = 80, 60, 40
        fa_similar = self._uniform(H, W, 128)
        fb_similar = self._uniform(H, W, 130)   # Δ=2 → very similar

        fa_diff = self._uniform(H, W, 50)
        fb_diff = self._uniform(H, W, 200)      # Δ=150 → very different

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
        out_fg_mask = _soft_seam_weight(fa, fb, path, H, W, bg_mask_a=bg_all_fg, bg_mask_b=bg_all_fg)

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
        lo_dark = _adaptive_gain_clamp(50.0, 10000.0)   # forced to lo
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
        assert result[0] is True   # frame 0 in bad pair
        assert result[1] is True   # frame 1 in bad pair
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
        lums = [105.0, 110.0, 100.0]   # lum[0]=105, lum[1]=110, lum[2]=100
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
            f"row just past fg boundary should be edge-buffer=0.5, got {cost[22,10]:.3f}"
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
        assert result[0] is False and result[1] is False and result[3] is False and result[4] is False

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
        h, w = 300, 100
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
        bot_warm[:, :, 0] = 28   # B
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
        bot_warm[:, :, 0] = 28   # B
        bot_warm[:, :, 1] = 128  # G
        bot_warm[:, :, 2] = 166  # R  → luma ≈ 128
        img = np.vstack([top_grey, bot_warm])
        grey_result = _check_seam_color_gate(img, n_strips=2, thresh=0.55, use_bgr=False)
        bgr_result  = _check_seam_color_gate(img, n_strips=2, thresh=0.55, use_bgr=True)
        assert grey_result is None, "Greyscale gate should not fire on same-luma hue shift"
        assert bgr_result == 0, "BGR gate should return seam 0 for hue-shifted bands"

    def test_band_too_small_returns_one(self):
        """band_px too large for image height → trivially thin bands → score 1.0."""
        img = self._bgr(10, 50, 0, 0, 255)
        score = _seam_color_similarity_bgr(img, k=0, n_strips=2, band_px=100)
        assert score == pytest.approx(1.0, abs=1e-6)
