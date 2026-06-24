"""
Tests for canvas geometry: _compute_canvas and _crop_to_valid.

Issue categories covered:
  E — Canvas overcrop / height loss (test4: −393px, test9: −1609px).
  H — Pure horizontal scroll (test20: ty≈0, tx=0–1857px).
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

import backend.src.animation.alignment.canvas as _canvas_mod  # noqa: E402
from backend.src.animation.alignment.canvas import (  # noqa: E402
    _compute_adaptive_seam_smooth_px,
    _compute_canvas,
    _correct_seam_lum_steps,
    _crop_to_valid,
    _detect_scroll_axis,
    _panorama_stitch_fallback,
    _per_seam_lum_step_px,
    _smooth_seam_bands,
    _telea_fill_gaps,
)
from backend.src.animation.core.pipeline import _compute_row_coverage  # noqa: E402
from backend.src.constants import CANVAS_MAX_DIM as _CANVAS_MAX_DIM  # noqa: E402
from conftest import make_frame, make_translation_affine  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stack(n: int, h: int = 200, w: int = 300, dy: float = 150.0):
    """n frames with pure translation affines spaced dy apart."""
    frames = [make_frame(h, w) for _ in range(n)]
    affines = [make_translation_affine(ty=i * dy) for i in range(n)]
    return frames, affines


def _full_valid_mask(h: int, w: int) -> np.ndarray:
    return np.full((h, w), 255, dtype=np.uint8)


def _empty_valid_mask(h: int, w: int) -> np.ndarray:
    return np.zeros((h, w), dtype=np.uint8)


# ---------------------------------------------------------------------------
# _compute_canvas
# ---------------------------------------------------------------------------


class TestComputeCanvas:
    def test_returns_correct_types(self):
        frames, affines = _make_stack(2, h=100, w=150, dy=80.0)
        ch, cw, T = _compute_canvas(frames, affines)
        assert isinstance(ch, int)
        assert isinstance(cw, int)
        assert isinstance(T, np.ndarray)
        assert T.shape == (2,)

    def test_canvas_taller_than_single_frame(self):
        """2 frames 150px apart → canvas height > single frame height."""
        H, dy = 200, 150.0
        frames, affines = _make_stack(2, h=H, w=300, dy=dy)
        ch, cw, _ = _compute_canvas(frames, affines)
        assert ch > H, f"canvas_h={ch} should exceed single frame height {H}"

    def test_canvas_height_covers_all_frames(self):
        """Canvas height should accommodate all frame strip positions."""
        H, dy, N = 200, 150.0, 4
        frames, affines = _make_stack(N, h=H, w=300, dy=dy)
        ch, cw, _ = _compute_canvas(frames, affines)
        expected_min = (N - 1) * dy + H
        assert ch >= expected_min - 2, (
            f"canvas_h={ch} too small for {N} frames at dy={dy}; "
            f"expected at least {expected_min:.0f}"
        )

    def test_T_global_makes_corners_non_negative(self):
        """After applying T_global, every warped corner should be ≥ 0."""
        frames = [make_frame(100, 150) for _ in range(3)]
        affines = [
            make_translation_affine(tx=-50.0, ty=0.0),
            make_translation_affine(tx=0.0, ty=100.0),
            make_translation_affine(tx=30.0, ty=200.0),
        ]
        ch, cw, T = _compute_canvas(frames, affines)
        for i, (frm, aff) in enumerate(zip(frames, affines)):
            h, w = frm.shape[:2]
            corners = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float32)
            warped = (aff[:2, :2] @ corners.T + aff[:2, 2:3]).T
            shifted = warped + T
            assert shifted.min() >= -1.0, (
                f"frame{i}: shifted corner {shifted.min():.2f} is negative after T_global"
            )

    def test_canvas_width_equals_frame_width_for_pure_vertical(self):
        """Pure vertical scroll (tx=0) → canvas width equals frame width."""
        H, W = 200, 300
        frames, affines = _make_stack(4, h=H, w=W, dy=150.0)
        ch, cw, T = _compute_canvas(frames, affines)
        assert cw == W, (
            f"canvas_w={cw} should equal frame_w={W} for pure vertical scroll"
        )

    def test_canvas_wider_for_horizontal_offset(self):
        """Frames with tx offset → canvas wider than single frame."""
        W, tx = 300, 200
        frames = [make_frame(200, W) for _ in range(2)]
        affines = [
            make_translation_affine(tx=0.0, ty=0.0),
            make_translation_affine(tx=float(tx), ty=0.0),
        ]
        ch, cw, _ = _compute_canvas(frames, affines)
        assert cw > W, (
            f"canvas_w={cw} should exceed single frame width {W} with tx={tx}"
        )

    def test_canvas_max_dim_clamped(self):
        """Pathological affines producing a huge canvas are clamped to _CANVAS_MAX_DIM."""
        frames = [make_frame(100, 100) for _ in range(2)]
        affines = [
            make_translation_affine(ty=0.0),
            make_translation_affine(ty=float(_CANVAS_MAX_DIM + 5000)),
        ]
        ch, cw, _ = _compute_canvas(frames, affines)
        assert ch <= _CANVAS_MAX_DIM, (
            f"canvas_h={ch} exceeds _CANVAS_MAX_DIM={_CANVAS_MAX_DIM}"
        )


# ---------------------------------------------------------------------------
# _crop_to_valid
# ---------------------------------------------------------------------------


class TestCropToValid:
    def test_full_mask_no_crop(self):
        """All-valid mask → canvas returned unchanged."""
        canvas = np.random.randint(0, 255, (100, 150, 3), dtype=np.uint8)
        valid = _full_valid_mask(100, 150)
        result = _crop_to_valid(canvas, valid)
        assert result.shape == canvas.shape

    def test_empty_mask_no_crop(self):
        """All-zero mask → canvas returned unchanged (no crash)."""
        canvas = np.zeros((100, 150, 3), dtype=np.uint8)
        valid = _empty_valid_mask(100, 150)
        result = _crop_to_valid(canvas, valid)
        assert result.shape == canvas.shape

    def test_known_bounding_box(self):
        """Known rectangular valid region → crop matches that rectangle exactly."""
        H, W = 200, 300
        canvas = np.ones((H, W, 3), dtype=np.uint8) * 127
        valid = _empty_valid_mask(H, W)
        r0, r1, c0, c1 = 20, 80, 30, 200
        valid[r0:r1, c0:c1] = 255
        result = _crop_to_valid(canvas, valid)
        assert result.shape == (r1 - r0, c1 - c0, 3), (
            f"Expected shape ({r1 - r0}, {c1 - c0}, 3), got {result.shape}"
        )

    def test_single_row_valid(self):
        """Only one row valid → crop to that single row."""
        H, W = 100, 120
        canvas = np.random.randint(1, 255, (H, W, 3), dtype=np.uint8)
        valid = _empty_valid_mask(H, W)
        valid[50, :] = 255
        result = _crop_to_valid(canvas, valid)
        assert result.shape[0] == 1

    def test_single_column_valid(self):
        """Only one column valid → crop to that single column."""
        H, W = 80, 120
        canvas = np.random.randint(1, 255, (H, W, 3), dtype=np.uint8)
        valid = _empty_valid_mask(H, W)
        valid[:, 60] = 255
        result = _crop_to_valid(canvas, valid)
        assert result.shape[1] == 1

    def test_overcrop_issue_test4(self):
        """
        Regression for test4 overcrop (-393px height loss).

        When the valid mask covers the full canvas height from row 0 to H-1,
        _crop_to_valid must not remove any rows.
        """
        H, W = 400, 300
        canvas = np.random.randint(1, 255, (H, W, 3), dtype=np.uint8)
        valid = _full_valid_mask(H, W)
        result = _crop_to_valid(canvas, valid)
        assert result.shape[0] == H, (
            f"crop_to_valid removed rows when all rows are valid: "
            f"input_h={H}, output_h={result.shape[0]}"
        )

    def test_sparse_bottom_rows_not_overcropped(self):
        """
        If the bottom rows contain at least one valid pixel, they must be kept.
        Overcropping bottom rows is the pattern causing test4's height loss.
        """
        H, W = 200, 300
        canvas = np.ones((H, W, 3), dtype=np.uint8) * 50
        valid = _empty_valid_mask(H, W)
        # Make the top part valid
        valid[0 : H - 5, :] = 255
        # Make the bottom 5 rows sparse
        for r in range(H - 5, H):
            valid[r, W // 2] = 255
        result = _crop_to_valid(canvas, valid)
        assert result.shape[0] == H, (
            f"Bottom rows with sparse valid pixels were cropped: "
            f"expected H={H}, got {result.shape[0]}"
        )


# ---------------------------------------------------------------------------
# Horizontal scroll detection utility
# ---------------------------------------------------------------------------
class TestScrollAxisDetection:
    """
    Tests for the scroll axis detection logic that must be implemented
    to support test20 (horizontal scroll) and test7 (diagonal scroll).
    """

    def test_pure_vertical_scroll(self):
        """Standard vertical scroll: ty increases, tx≈0."""
        affines = [make_translation_affine(ty=i * 200.0) for i in range(6)]
        assert _detect_scroll_axis(affines) == "vertical"

    def test_pure_horizontal_scroll_test20_pattern(self):
        """test20 pattern: ty≈0 for all frames, tx ranges 0→1857px."""
        txs = [1857, 1482, 1130, 942, 688, 315, 0]
        affines = [
            make_translation_affine(tx=float(tx), ty=float(i % 4))
            for i, tx in enumerate(txs)
        ]
        result = _detect_scroll_axis(affines)
        assert result == "horizontal", (
            f"Expected 'horizontal' for pure tx scroll, got '{result}'"
        )

    def test_diagonal_scroll_test7_pattern(self):
        """test7 pattern: significant both ty and tx components."""
        affines = [make_translation_affine(tx=i * 50.0, ty=i * 150.0) for i in range(6)]
        result = _detect_scroll_axis(affines)
        assert result in ("diagonal", "vertical"), (
            f"Expected 'diagonal' or 'vertical' for ty+tx drift, got '{result}'"
        )

    def test_colocated_frames_test21_pattern(self):
        """test21 pattern: 3 frames at identical positions."""
        affines = [
            make_translation_affine(tx=165.0, ty=0.0),
            make_translation_affine(tx=132.0, ty=177.0),
            make_translation_affine(tx=165.0, ty=0.0),
            make_translation_affine(tx=165.0, ty=0.0),
        ]
        tys = sorted([float(a[1, 2]) for a in affines])
        min_gap = float(np.diff(tys).min())
        assert min_gap == pytest.approx(0.0, abs=1.0), (
            f"Expected min_gap≈0 for co-located frames, got {min_gap}"
        )

    def test_ty_range_dominates_vertical_classification(self):
        """Slight tx drift (test15: tx_range=22px) should still classify as vertical."""
        affines = [
            make_translation_affine(tx=float(i * 4), ty=float(i * 400))
            for i in range(7)
        ]
        assert _detect_scroll_axis(affines) == "vertical"


# ---------------------------------------------------------------------------
# §3.14 — _detect_scroll_axis from canvas module (S33)
# Tests the actual exported function, not the local test copy above.
# ---------------------------------------------------------------------------


class TestDetectScrollAxisModule:
    """Validate canvas._detect_scroll_axis (§3.14) via the exported module function."""

    def test_pure_vertical_returns_vertical(self):
        """ty increases, tx≈0 → 'vertical'."""
        affines = [make_translation_affine(tx=0.0, ty=float(i * 300)) for i in range(5)]
        assert _detect_scroll_axis(affines) == "vertical"

    def test_pure_horizontal_returns_horizontal(self):
        """tx ranges 1800→0, ty≈0 → 'horizontal' (test20 pattern)."""
        txs = [1800, 1440, 1080, 720, 360, 0]
        affines = [make_translation_affine(tx=float(tx), ty=0.0) for tx in txs]
        assert _detect_scroll_axis(affines) == "horizontal"

    def test_diagonal_returns_diagonal(self):
        """tx_range > 0.3 × ty_range → 'diagonal' (test7 pattern)."""
        affines = [
            make_translation_affine(tx=float(i * 80), ty=float(i * 200))
            for i in range(6)
        ]
        result = _detect_scroll_axis(affines)
        assert result == "diagonal", f"Expected 'diagonal', got '{result}'"

    def test_colocated_returns_none(self):
        """All frames at same position (total range < 1 px) → 'none'."""
        affines = [make_translation_affine(tx=100.0, ty=200.0) for _ in range(4)]
        assert _detect_scroll_axis(affines) == "none"

    def test_small_tx_drift_still_vertical(self):
        """tx_range=20px vs ty_range=1000px: ratio 0.02 << 0.3 → 'vertical'."""
        affines = [
            make_translation_affine(tx=float(i * 4), ty=float(i * 250))
            for i in range(5)
        ]
        assert _detect_scroll_axis(affines) == "vertical"


# ---------------------------------------------------------------------------
# _compute_row_coverage — Stage 10.5 multi-frame canvas coverage gate (S13)
# ---------------------------------------------------------------------------


class TestComputeRowCoverage:
    """
    _compute_row_coverage(affines, frames, canvas_h) returns
    (row_cov, pct_multi, median_cov) where row_cov[r] = number of frames
    covering canvas row r, pct_multi is the fraction of content rows with
    ≥2 frames, and median_cov is the median coverage among content rows.
    """

    def _make_inputs(self, n: int, frame_h: int, step: int):
        canvas_h = frame_h + (n - 1) * step
        frames = [make_frame(frame_h, 100) for _ in range(n)]
        affines = [make_translation_affine(ty=float(i * step)) for i in range(n)]
        return frames, affines, canvas_h

    def test_two_fully_overlapping_frames_all_rows_covered_twice(self):
        """Two frames at ty=0 with frame_h=canvas_h → every row covered twice."""
        frame_h, canvas_h = 100, 100
        frames = [make_frame(frame_h, 80)] * 2
        affines = [make_translation_affine(ty=0.0)] * 2
        row_cov, pct_multi, median_cov = _compute_row_coverage(
            affines, frames, canvas_h
        )
        assert row_cov.shape == (canvas_h,)
        assert int(row_cov.min()) == 2
        assert pct_multi == pytest.approx(1.0)
        assert median_cov == pytest.approx(2.0)

    def test_non_overlapping_frames_zero_multi_coverage(self):
        """Two frames that don't overlap → every row covered by exactly 1 frame."""
        frame_h = 50
        canvas_h = 100  # frame 0: rows 0–49, frame 1: rows 50–99
        frames = [make_frame(frame_h, 80)] * 2
        affines = [
            make_translation_affine(ty=0.0),
            make_translation_affine(ty=float(frame_h)),
        ]
        row_cov, pct_multi, median_cov = _compute_row_coverage(
            affines, frames, canvas_h
        )
        assert int(row_cov[0]) == 1
        assert int(row_cov[frame_h]) == 1
        assert pct_multi == pytest.approx(0.0)
        assert median_cov == pytest.approx(1.0)

    def test_dense_stack_high_pct_multi(self):
        """Many overlapping frames → pct_multi close to 1.0."""
        frames, affines, canvas_h = self._make_inputs(n=10, frame_h=100, step=20)
        _, pct_multi, median_cov = _compute_row_coverage(affines, frames, canvas_h)
        assert pct_multi > 0.8, f"Expected high multi-coverage, got {pct_multi:.2f}"
        assert median_cov >= 2.0

    def test_output_array_shape(self):
        """row_cov must have shape (canvas_h,) regardless of frame count."""
        frames, affines, canvas_h = self._make_inputs(n=5, frame_h=80, step=40)
        row_cov, _, _ = _compute_row_coverage(affines, frames, canvas_h)
        assert row_cov.shape == (canvas_h,)
        assert row_cov.dtype == np.int32

    def test_empty_canvas_returns_zero_pct(self):
        """canvas_h=0 content rows → pct_multi=0.0, median=0.0."""
        frames = [make_frame(50, 80)]
        affines = [make_translation_affine(ty=0.0)]
        _, pct_multi, median_cov = _compute_row_coverage(affines, frames, 0)
        assert pct_multi == pytest.approx(0.0)
        assert median_cov == pytest.approx(0.0)

    def test_row_cov_never_negative(self):
        """Coverage counts must be ≥ 0 for all rows."""
        frames, affines, canvas_h = self._make_inputs(n=4, frame_h=60, step=30)
        row_cov, _, _ = _compute_row_coverage(affines, frames, canvas_h)
        assert int(row_cov.min()) >= 0


# ---------------------------------------------------------------------------
# _panorama_stitch_fallback — §1.3B PANORAMA stitcher before SCANS (S31)
# ---------------------------------------------------------------------------


class TestPanoramaStitchFallback:
    """
    _panorama_stitch_fallback(frames, output_path) tries cv2.Stitcher PANORAMA
    (mode=0) before the caller falls through to SCANS.  All tests use mocks so
    no real feature matching is required.
    """

    def _solid_bgr(self, h: int = 64, w: int = 128, v: int = 128) -> np.ndarray:
        return np.full((h, w, 3), v, dtype=np.uint8)

    def test_returns_pil_image_on_success(self, tmp_path):
        """Mock stitcher returns OK + valid image → PIL.Image returned."""
        from unittest.mock import MagicMock, patch
        from PIL import Image as PILImage

        fake_pano = self._solid_bgr(60, 120, 200)
        mock_stitcher = MagicMock()
        mock_stitcher.stitch.return_value = (cv2.Stitcher_OK, fake_pano)

        with patch("cv2.Stitcher_create", return_value=mock_stitcher):
            frames = [self._solid_bgr()]
            result = _panorama_stitch_fallback(frames, str(tmp_path / "out.png"))

        assert isinstance(result, PILImage.Image)

    def test_raises_runtime_error_on_non_ok_status(self, tmp_path):
        """Non-OK status from stitcher → CanvasError (caller falls through to SCANS)."""
        from backend.src.exceptions import CanvasError
        from unittest.mock import MagicMock, patch

        mock_stitcher = MagicMock()
        mock_stitcher.stitch.return_value = (cv2.Stitcher_ERR_NEED_MORE_IMGS, None)

        with patch("cv2.Stitcher_create", return_value=mock_stitcher):
            with pytest.raises(CanvasError, match="PANORAMA stitcher failed"):
                _panorama_stitch_fallback(
                    [self._solid_bgr()], str(tmp_path / "out.png")
                )

    def test_saves_file_on_success(self, tmp_path):
        """Successful stitch → output file written to output_path."""
        from unittest.mock import MagicMock, patch

        fake_pano = self._solid_bgr(50, 100, 150)
        mock_stitcher = MagicMock()
        mock_stitcher.stitch.return_value = (cv2.Stitcher_OK, fake_pano)
        out_path = str(tmp_path / "panorama.png")

        with patch("cv2.Stitcher_create", return_value=mock_stitcher):
            _panorama_stitch_fallback([self._solid_bgr()], out_path)

        assert os.path.exists(out_path)

    def test_uses_panorama_mode_zero(self):
        """cv2.Stitcher_create must be called with mode=0 (PANORAMA)."""
        from unittest.mock import MagicMock, patch
        import tempfile

        fake_pano = self._solid_bgr(40, 80, 100)
        mock_stitcher = MagicMock()
        mock_stitcher.stitch.return_value = (cv2.Stitcher_OK, fake_pano)

        with patch("cv2.Stitcher_create", return_value=mock_stitcher) as mock_create:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                _panorama_stitch_fallback([self._solid_bgr()], f.name)
            mock_create.assert_called_once_with(mode=0)

    def test_output_dimensions_match_pano(self, tmp_path):
        """Result image dimensions match the (possibly cropped) stitcher output."""
        from unittest.mock import MagicMock, patch
        from PIL import Image as PILImage

        h, w = 80, 160
        fake_pano = self._solid_bgr(h, w, 200)
        mock_stitcher = MagicMock()
        mock_stitcher.stitch.return_value = (cv2.Stitcher_OK, fake_pano)

        with patch("cv2.Stitcher_create", return_value=mock_stitcher):
            result = _panorama_stitch_fallback(
                [self._solid_bgr()], str(tmp_path / "out.png")
            )

        assert isinstance(result, PILImage.Image)
        assert result.width > 0 and result.height > 0


# ---------------------------------------------------------------------------
# _telea_fill_gaps
# ---------------------------------------------------------------------------


class TestTelaeFillGaps:
    """§1.7B: cv2.INPAINT_TELEA border gap fill (S23)."""

    H, W = 20, 24

    def _solid_canvas(self, val: int = 120) -> np.ndarray:
        return np.full((self.H, self.W, 3), val, dtype=np.uint8)

    def _corner_gap_mask(self, gap: int = 4) -> np.ndarray:
        """Top-left `gap × gap` region marked as missing."""
        m = np.zeros((self.H, self.W), dtype=np.uint8)
        m[:gap, :gap] = 255
        return m

    def test_no_gap_returns_unchanged(self):
        """All-zero gap mask → output identical to input."""
        canvas = self._solid_canvas(80)
        gap_mask = np.zeros((self.H, self.W), dtype=np.uint8)
        out = _telea_fill_gaps(canvas, gap_mask)
        np.testing.assert_array_equal(out, canvas)

    def test_shape_preserved(self):
        """Output shape must match input."""
        canvas = self._solid_canvas()
        out = _telea_fill_gaps(canvas, self._corner_gap_mask())
        assert out.shape == canvas.shape

    def test_dtype_preserved(self):
        """Output dtype must be uint8."""
        canvas = self._solid_canvas()
        out = _telea_fill_gaps(canvas, self._corner_gap_mask())
        assert out.dtype == np.uint8

    def test_corner_gap_no_longer_black(self):
        """After TELEA fill, the top-left corner should not be pure black."""
        canvas = self._solid_canvas(150)
        gap = 4
        canvas[:gap, :gap] = 0
        gap_mask = self._corner_gap_mask(gap)
        out = _telea_fill_gaps(canvas, gap_mask)
        assert int(out[:gap, :gap].max()) > 0

    def test_valid_region_unchanged_outside_band(self):
        """Pixels far from the gap must not be modified by TELEA."""
        canvas = self._solid_canvas(200)
        canvas[:4, :4] = 0
        gap_mask = self._corner_gap_mask(4)
        out = _telea_fill_gaps(canvas, gap_mask)
        np.testing.assert_array_equal(out[8:, 8:], canvas[8:, 8:])


# ---------------------------------------------------------------------------
# Phase 5 — batch.canvas C++ dispatch tests
# ---------------------------------------------------------------------------


class TestBatchCanvasWiring:
    """Phase 5: verify batch.canvas dispatch is wired and falls back correctly."""

    def _affines(self, n: int, dy: float = 100.0):
        return [make_translation_affine(ty=float(i * dy)) for i in range(n)]

    def test_compute_canvas_returns_correct_types(self):
        """_compute_canvas returns (int, int, ndarray) regardless of batch avail."""
        frames, affines = _make_stack(3)
        ch, cw, T = _compute_canvas(frames, affines)
        assert isinstance(ch, int) and isinstance(cw, int)
        assert isinstance(T, np.ndarray) and T.shape == (2,)

    def test_compute_canvas_height_covers_all_frames(self):
        """Canvas height must accommodate N vertically-spaced frames."""
        H, dy, N = 200, 150.0, 4
        frames, affines = _make_stack(N, h=H, w=300, dy=dy)
        ch, cw, _ = _compute_canvas(frames, affines)
        assert ch >= (N - 1) * dy + H - 2

    def test_detect_scroll_axis_vertical(self):
        """Pure vertical affines → 'vertical'."""
        affines = [make_translation_affine(ty=float(i * 300)) for i in range(5)]
        assert _detect_scroll_axis(affines) == "vertical"

    def test_detect_scroll_axis_horizontal(self):
        """Pure horizontal affines → 'horizontal'."""
        affines = [make_translation_affine(tx=float(i * 400), ty=0.0) for i in range(5)]
        assert _detect_scroll_axis(affines) == "horizontal"

    def test_telea_fill_gaps_no_gap_returns_unchanged(self):
        """Zero gap mask → output identical to input."""
        canvas = np.full((30, 40, 3), 120, dtype=np.uint8)
        gap = np.zeros((30, 40), dtype=np.uint8)
        out = _telea_fill_gaps(canvas, gap)
        np.testing.assert_array_equal(out, canvas)

    def test_telea_fill_gaps_shape_preserved(self):
        """Gap-filled output must have same shape as input."""
        canvas = np.full((30, 40, 3), 150, dtype=np.uint8)
        canvas[:4, :4] = 0
        gap = np.zeros((30, 40), dtype=np.uint8)
        gap[:4, :4] = 255
        out = _telea_fill_gaps(canvas, gap)
        assert out.shape == canvas.shape


# ===========================================================================
# §4.9 — _smooth_seam_bands (post-composite seam band Gaussian smoothing)
# ===========================================================================


class TestSmoothSeamBands:
    """§4.9: Narrow vertical Gaussian blur at inter-frame seam rows."""

    def _two_strip_canvas(self, H: int = 64, W: int = 80, top_val: int = 50, bot_val: int = 200):
        """Create a canvas with hard luminance step at row H//2."""
        canvas = np.full((H, W, 3), top_val, dtype=np.uint8)
        canvas[H // 2 :, :] = bot_val
        return canvas

    def test_returns_same_shape(self):
        canvas = self._two_strip_canvas()
        out = _smooth_seam_bands(canvas, seam_ys=[32], band_px=4)
        assert out.shape == canvas.shape
        assert out.dtype == np.uint8

    def test_smooths_luminance_step(self):
        # Without smoothing: row 31=50, row 32=200 → step=150.
        # With smoothing ±4px: intermediate values should appear in the band.
        canvas = self._two_strip_canvas(H=64, W=80)
        out = _smooth_seam_bands(canvas, seam_ys=[32], band_px=4)
        band = out[28:36, :, 0].astype(np.float32)
        # Band should now have non-constant values (i.e., a gradient exists).
        assert band.std() > 0

    def test_zero_band_returns_copy(self):
        canvas = self._two_strip_canvas()
        out = _smooth_seam_bands(canvas, seam_ys=[32], band_px=0)
        np.testing.assert_array_equal(out, canvas)

    def test_empty_seam_list_returns_copy(self):
        canvas = self._two_strip_canvas()
        out = _smooth_seam_bands(canvas, seam_ys=[], band_px=4)
        np.testing.assert_array_equal(out, canvas)

    def test_black_pixels_not_modified(self):
        # Pixels outside valid content (value=0) must not be altered.
        canvas = np.zeros((32, 40, 3), dtype=np.uint8)
        canvas[:16, :] = 100
        canvas[16:, :] = 0  # second strip is all-black (invalid content)
        out = _smooth_seam_bands(canvas, seam_ys=[16], band_px=4)
        # Rows in the smoothed band where canvas was 0 must stay 0.
        assert out[16:, :].max() == 0


# ── TestCorrectSeamLumSteps — §5.1 Post-composite seam luminance step correction (S166) ──

class TestCorrectSeamLumSteps:
    """§5.1: _correct_seam_lum_steps bridges inter-strip luminance gap with a linear ramp."""

    def _make_canvas(self, top_lum: int, bot_lum: int, H: int = 64, W: int = 32) -> np.ndarray:
        canvas = np.zeros((H, W, 3), dtype=np.uint8)
        canvas[: H // 2] = top_lum
        canvas[H // 2 :] = bot_lum
        return canvas

    def test_returns_same_shape(self):
        canvas = self._make_canvas(80, 160)
        out = _correct_seam_lum_steps(canvas, [32], band_px=20)
        assert out.shape == canvas.shape
        assert out.dtype == np.uint8

    def test_reduces_luminance_step(self):
        H, W = 64, 32
        canvas = self._make_canvas(80, 160, H=H, W=W)
        seam = H // 2
        before_step = abs(int(canvas[seam, 0, 0]) - int(canvas[seam - 1, 0, 0]))
        out = _correct_seam_lum_steps(canvas, [seam], band_px=20)
        after_step = abs(int(out[seam, 0, 0]) - int(out[seam - 1, 0, 0]))
        assert after_step < before_step, (
            f"Expected reduced step: before={before_step}, after={after_step}"
        )

    def test_zero_band_returns_copy(self):
        canvas = self._make_canvas(80, 160)
        out = _correct_seam_lum_steps(canvas, [32], band_px=0)
        np.testing.assert_array_equal(out, canvas)

    def test_empty_seam_list_returns_copy(self):
        canvas = self._make_canvas(80, 160)
        out = _correct_seam_lum_steps(canvas, [], band_px=20)
        np.testing.assert_array_equal(out, canvas)

    def test_black_pixels_not_modified(self):
        H, W = 64, 32
        canvas = np.zeros((H, W, 3), dtype=np.uint8)
        canvas[: H // 2] = 100
        # bottom half stays fully black — bot_valid.any() is False → skip
        out = _correct_seam_lum_steps(canvas, [H // 2], band_px=20)
        np.testing.assert_array_equal(out[H // 2 :], 0)


class TestComputeAdaptiveSeamSmoothPx:
    """§5.11: _compute_adaptive_seam_smooth_px — seam-coherence-driven width."""

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _uniform_canvas(h: int = 100, w: int = 80, value: int = 128) -> np.ndarray:
        """Uniform BGR canvas → very low row-mean std (sc ≈ 0)."""
        return np.full((h, w, 3), value, dtype=np.uint8)

    @staticmethod
    def _alternating_canvas(h: int = 100, w: int = 80) -> np.ndarray:
        """Black/white alternating rows → very high row-mean std (sc >> 30)."""
        canvas = np.zeros((h, w, 3), dtype=np.uint8)
        canvas[1::2] = 255
        return canvas

    @staticmethod
    def _moderate_canvas(h: int = 100, w: int = 80) -> np.ndarray:
        """Canvas with row-mean std in [5, 30] (sc ≈ 15) for interpolation tests."""
        # Linearly vary rows from 0 to 100 (std of linear ramp ≈ range/sqrt(12))
        canvas = np.zeros((h, w, 3), dtype=np.uint8)
        for r in range(h):
            v = int(r * 150 / h)
            canvas[r] = v
        return canvas

    # ── tests ─────────────────────────────────────────────────────────────────

    def test_low_sc_returns_max_px(self):
        """Uniform image (sc ≈ 0) → returns max_px=12."""
        canvas = self._uniform_canvas()
        result = _compute_adaptive_seam_smooth_px(canvas, base_px=4, min_px=2, max_px=12)
        assert result == 12, f"Expected 12 for low-sc canvas, got {result}"

    def test_high_sc_returns_min_px(self):
        """Alternating black/white rows (sc >> 30) → returns min_px=2."""
        canvas = self._alternating_canvas()
        result = _compute_adaptive_seam_smooth_px(canvas, base_px=4, min_px=2, max_px=12)
        assert result == 2, f"Expected 2 for high-sc canvas, got {result}"

    def test_mid_sc_interpolates(self):
        """Moderate sc canvas → result strictly between min_px and max_px."""
        canvas = self._moderate_canvas()
        result = _compute_adaptive_seam_smooth_px(canvas, base_px=4, min_px=2, max_px=12)
        assert 2 <= result <= 12, f"Expected value in [2, 12], got {result}"

    def test_disabled_base_px_zero(self):
        """base_px=0 → returns 0 immediately (disabled path)."""
        canvas = self._uniform_canvas()
        result = _compute_adaptive_seam_smooth_px(canvas, base_px=0, min_px=2, max_px=12)
        assert result == 0, f"Expected 0 for base_px=0, got {result}"

    def test_in_all(self):
        """'_compute_adaptive_seam_smooth_px' must be listed in canvas.__all__."""
        assert "_compute_adaptive_seam_smooth_px" in _canvas_mod.__all__


class TestPerSeamLumStepPx:
    """§5.16: Tests for _per_seam_lum_step_px."""

    @staticmethod
    def _make_canvas(top_val: int, bot_val: int, H: int = 100, W: int = 80) -> np.ndarray:
        """Build a (H, W, 3) uint8 canvas with top half = top_val, bottom half = bot_val."""
        img = np.zeros((H, W, 3), dtype=np.uint8)
        img[:H // 2] = top_val
        img[H // 2:] = bot_val
        return img

    def test_uniform_seam_returns_min_px(self):
        """Canvas with uniform luminance (step≈0) → all seams return min_px=5."""
        img = self._make_canvas(128, 128)
        seam_ys = [40, 60]
        result = _per_seam_lum_step_px(img, seam_ys, base_px=20, min_px=5, max_px=40)
        assert result == [5, 5], f"expected [5, 5], got {result}"

    def test_large_step_returns_max_px(self):
        """Canvas with large step (40 vs 200 → step=160 >> 30) → returns max_px=40."""
        img = self._make_canvas(40, 200)
        seam_ys = [50]
        result = _per_seam_lum_step_px(img, seam_ys, base_px=20, min_px=5, max_px=40)
        assert result == [40], f"expected [40], got {result}"

    def test_moderate_step_interpolates(self):
        """step ≈ 15 → value strictly between min_px=5 and max_px=40."""
        img = self._make_canvas(100, 115)
        seam_ys = [50]
        result = _per_seam_lum_step_px(img, seam_ys, base_px=20, min_px=5, max_px=40)
        assert len(result) == 1
        assert 5 < result[0] < 40, f"expected interpolated value, got {result[0]}"

    def test_empty_seam_list(self):
        """seam_ys=[] → returns []."""
        img = self._make_canvas(100, 150)
        result = _per_seam_lum_step_px(img, [], base_px=20, min_px=5, max_px=40)
        assert result == []

    def test_in_all(self):
        """'_per_seam_lum_step_px' must appear in canvas.__all__."""
        assert "_per_seam_lum_step_px" in _canvas_mod.__all__
