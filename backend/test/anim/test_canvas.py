"""
Tests for canvas geometry: _compute_canvas and _crop_to_valid.

Issue categories covered:
  E — Canvas overcrop / height loss (test4: −393px, test9: −1609px).
  H — Pure horizontal scroll (test20: ty≈0, tx=0–1857px).
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

from backend.src.anim.canvas import _compute_canvas, _crop_to_valid  # noqa: E402
from backend.src.constants import _CANVAS_MAX_DIM  # noqa: E402
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
        assert cw == W, f"canvas_w={cw} should equal frame_w={W} for pure vertical scroll"

    def test_canvas_wider_for_horizontal_offset(self):
        """Frames with tx offset → canvas wider than single frame."""
        W, tx = 300, 200
        frames = [make_frame(200, W) for _ in range(2)]
        affines = [
            make_translation_affine(tx=0.0, ty=0.0),
            make_translation_affine(tx=float(tx), ty=0.0),
        ]
        ch, cw, _ = _compute_canvas(frames, affines)
        assert cw > W, f"canvas_w={cw} should exceed single frame width {W} with tx={tx}"

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
        valid[0:H-5, :] = 255
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


def _detect_scroll_axis(affines: list) -> str:
    """
    Classify the scroll direction of a set of affines as:
    - 'vertical'    : ty_range >> tx_range (normal case)
    - 'horizontal'  : tx_range >> ty_range (test20 pattern)
    - 'diagonal'    : both ty and tx significant (test7 pattern)
    - 'none'        : all frames co-located
    """
    tys = np.array([float(a[1, 2]) for a in affines])
    txs = np.array([float(a[0, 2]) for a in affines])
    ty_range = float(tys.max() - tys.min())
    tx_range = float(txs.max() - txs.min())
    total = ty_range + tx_range
    if total < 1.0:
        return "none"
    if tx_range > 0 and ty_range / max(tx_range, 1.0) < 0.1:
        return "horizontal"
    if ty_range > 0 and tx_range / max(ty_range, 1.0) > 0.3:
        return "diagonal"
    return "vertical"


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
            make_translation_affine(tx=float(i * 4), ty=float(i * 400)) for i in range(7)
        ]
        assert _detect_scroll_axis(affines) == "vertical"
