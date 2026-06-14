"""
Tests for bg_complete.py — §5A/C background zero-coverage fill.

1. _nn_fill_zero_bg: single-column gap filled with nearest known pixel
2. _nn_fill_zero_bg: all-unknown column left as-is (no known anchor)
3. _nn_fill_zero_bg: gap at top of column filled with first known below
4. complete_background: returns unchanged canvas when zero rows < min_rows
5. complete_background: fills gap when zero rows >= min_rows
"""

import numpy as np
import pytest

from backend.src.anim.bg_complete import _nn_fill_zero_bg, _linear_interp_zero_bg, complete_background


class TestNnFillZeroBg:
    def _canvas(self, H=10, W=4):
        canvas = np.zeros((H, W, 3), dtype=np.uint8)
        canvas[:, :] = [30, 60, 90]
        return canvas

    def test_single_column_gap_filled_with_nearest_known(self):
        canvas = self._canvas(H=6, W=2)
        canvas[:, 0] = [10, 10, 10]
        # rows 2-3 in column 1 are zero (gap)
        canvas[0, 1] = [200, 200, 200]
        canvas[1, 1] = [200, 200, 200]
        canvas[2, 1] = [0, 0, 0]
        canvas[3, 1] = [0, 0, 0]
        canvas[4, 1] = [150, 150, 150]
        canvas[5, 1] = [150, 150, 150]
        zero_mask = np.zeros((6, 2), dtype=bool)
        zero_mask[2:4, 1] = True

        out = _nn_fill_zero_bg(canvas, zero_mask)

        # Rows 2 and 3 should be filled with nearest known (above=200 or below=150)
        # Row 2: nearest known above is row 1 (distance 1), below is row 4 (distance 2)
        assert out[2, 1, 0] == 200
        # Row 3: nearest known below is row 4 (distance 1), above is row 1 (distance 2)
        assert out[3, 1, 0] == 150
        # Column 0 unchanged
        assert out[0, 0, 0] == 10

    def test_all_unknown_column_left_unchanged(self):
        canvas = self._canvas(H=4, W=2)
        canvas[:, 0] = [50, 50, 50]
        canvas[:, 1] = [0, 0, 0]
        zero_mask = np.zeros((4, 2), dtype=bool)
        zero_mask[:, 1] = True  # all rows unknown in col 1

        out = _nn_fill_zero_bg(canvas, zero_mask)

        # No known pixel in column 1 → all rows remain 0
        assert out[:, 1, 0].tolist() == [0, 0, 0, 0]

    def test_gap_at_top_filled_with_first_known_below(self):
        canvas = np.zeros((5, 1, 3), dtype=np.uint8)
        canvas[0, 0] = [0, 0, 0]
        canvas[1, 0] = [0, 0, 0]
        canvas[2, 0] = [99, 99, 99]
        canvas[3, 0] = [99, 99, 99]
        canvas[4, 0] = [99, 99, 99]
        zero_mask = np.zeros((5, 1), dtype=bool)
        zero_mask[0:2, 0] = True

        out = _nn_fill_zero_bg(canvas, zero_mask)

        assert out[0, 0, 0] == 99
        assert out[1, 0, 0] == 99
        assert out[2, 0, 0] == 99  # unchanged

    def test_no_gap_returns_identical_canvas(self):
        canvas = self._canvas(H=4, W=3)
        zero_mask = np.zeros((4, 3), dtype=bool)

        out = _nn_fill_zero_bg(canvas, zero_mask)

        np.testing.assert_array_equal(out, canvas)


class TestCompleteBackground:
    def _make_canvas_and_mask(self, H=20, W=4, n_zero_rows=5):
        canvas = np.ones((H, W, 3), dtype=np.uint8) * 100
        valid = np.ones((H, W), dtype=np.uint8) * 255
        valid[:n_zero_rows, :] = 0
        canvas[:n_zero_rows, :] = 0
        return canvas, valid

    def test_skips_when_too_few_zero_rows(self):
        canvas, valid = self._make_canvas_and_mask(H=20, n_zero_rows=3)
        out = complete_background(canvas, valid, min_rows=5)
        # Should return the unchanged canvas (3 < 5)
        np.testing.assert_array_equal(out, canvas)

    def test_fills_when_enough_zero_rows(self):
        canvas, valid = self._make_canvas_and_mask(H=20, W=4, n_zero_rows=6)
        out = complete_background(canvas, valid, min_rows=5)
        # Zero rows should be filled (non-zero after fill)
        assert out[:6, :, 0].max() > 0


class TestLinearInterpZeroBg:
    """§1.42: Linear interpolation bg fill."""

    def _canvas(self, H: int, W: int = 1) -> np.ndarray:
        return np.zeros((H, W, 3), dtype=np.uint8)

    def test_midpoint_interpolated_between_boundaries(self):
        """Gap at row 2 between row-0 (value 0) and row-4 (value 100) → row 2 ≈ 50."""
        H, W = 5, 1
        canvas = self._canvas(H, W)
        canvas[0, 0] = [0, 0, 0]
        canvas[4, 0] = [100, 100, 100]
        zero_mask = np.array([False, True, True, True, False]).reshape(H, W)
        out = _linear_interp_zero_bg(canvas, zero_mask)
        # row 2 is the midpoint (t=0.5) → expected ≈ 50
        assert int(out[2, 0, 0]) == pytest.approx(50, abs=2)

    def test_top_boundary_gap_falls_back_to_nn(self):
        """Gap at top rows with no known pixel above → filled with nearest below."""
        H, W = 5, 1
        canvas = self._canvas(H, W)
        canvas[3, 0] = [200, 200, 200]
        canvas[4, 0] = [200, 200, 200]
        zero_mask = np.array([True, True, True, False, False]).reshape(H, W)
        out = _linear_interp_zero_bg(canvas, zero_mask)
        # Rows 0–2 should all be filled with the nearest known (row 3 = 200)
        assert int(out[0, 0, 0]) == 200
        assert int(out[2, 0, 0]) == 200

    def test_no_gap_returns_identical_canvas(self):
        """Fully covered canvas → output equals input."""
        canvas = np.random.randint(0, 255, (8, 4, 3), dtype=np.uint8)
        zero_mask = np.zeros((8, 4), dtype=bool)
        out = _linear_interp_zero_bg(canvas, zero_mask)
        np.testing.assert_array_equal(out, canvas)

    def test_all_unknown_column_left_unchanged(self):
        """Column with no known pixels → remains black (no anchor to fill from)."""
        canvas = self._canvas(H=6, W=1)
        zero_mask = np.ones((6, 1), dtype=bool)
        out = _linear_interp_zero_bg(canvas, zero_mask)
        assert out[:, 0, 0].max() == 0

    def test_interpolated_value_monotone_between_boundaries(self):
        """Gap rows between value 0 and 200 → strictly increasing fill."""
        H, W = 6, 1
        canvas = self._canvas(H, W)
        canvas[0, 0] = [0, 0, 0]
        canvas[5, 0] = [200, 200, 200]
        zero_mask = np.array([False, True, True, True, True, False]).reshape(H, W)
        out = _linear_interp_zero_bg(canvas, zero_mask)
        vals = [int(out[r, 0, 0]) for r in range(1, 5)]
        assert vals == sorted(vals), f"fill should be monotone, got {vals}"
