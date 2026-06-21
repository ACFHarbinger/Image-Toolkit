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
from unittest.mock import patch, MagicMock

from backend.src.anim.bg_complete import (
    _nn_fill_zero_bg,
    _linear_interp_zero_bg,
    _masked_median_bg,
    _propainter_complete_frames,
    complete_background,
)


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


# ---------------------------------------------------------------------------
# §3.13 TestProPainterCompleteFrames
# ---------------------------------------------------------------------------


class TestProPainterCompleteFrames:
    """§3.13: _propainter_complete_frames — multi-frame ProPainter with NN fallback."""

    def _frames(self, n=3, H=8, W=8):
        return [np.full((H, W, 3), 100 + i * 10, dtype=np.uint8) for i in range(n)]

    def _bg_masks(self, n=3, H=8, W=8, fg_rows=2):
        masks = []
        for _ in range(n):
            m = np.ones((H, W), dtype=np.uint8) * 255
            m[:fg_rows, :] = 0  # top rows are fg
            masks.append(m)
        return masks

    def test_none_mask_frames_returned_unchanged(self):
        """Frame with None mask (all-bg) is returned unchanged."""
        frames = self._frames(n=1)
        out = _propainter_complete_frames(frames, [None], device="cpu")
        assert len(out) == 1
        np.testing.assert_array_equal(out[0], frames[0])

    def test_return_length_matches_input(self):
        """Output length always equals input length."""
        frames = self._frames(n=4)
        masks = self._bg_masks(n=4)
        out = _propainter_complete_frames(frames, masks, device="cpu")
        assert len(out) == 4

    def test_nn_fallback_fills_fg_pixels(self):
        """Without ProPainter, NN fill replaces fg-masked pixels with nearby bg."""
        frames = [np.zeros((6, 4, 3), dtype=np.uint8)]
        frames[0][2:, :] = 180  # bg rows = value 180
        mask = np.zeros((6, 4), dtype=np.uint8)
        mask[2:, :] = 255  # top 2 rows are fg (0)
        out = _propainter_complete_frames(frames, [mask], device="cpu")
        # fg rows (0,1) should be filled with nearest bg value (≥1)
        assert int(out[0][0, 0, 0]) >= 1

    def test_propainter_used_when_available(self):
        """When ProPainterInference is available, it's called with RGB frames and fg masks."""
        frames = self._frames(n=2, H=4, W=4)
        masks = self._bg_masks(n=2, H=4, W=4, fg_rows=1)
        rgb_out = [np.full((4, 4, 3), 55, dtype=np.uint8) for _ in range(2)]
        mock_model = MagicMock()
        mock_model.inpaint.return_value = rgb_out
        MockClass = MagicMock(return_value=mock_model)
        import backend.src.anim.bg_complete as bm
        with patch.object(bm, "ProPainterInference", MockClass):
            result = _propainter_complete_frames(frames, masks, device="cpu")
        assert len(result) == 2
        mock_model.inpaint.assert_called_once()
        call_kwargs = mock_model.inpaint.call_args
        assert len(call_kwargs.kwargs.get("frames", call_kwargs.args[0] if call_kwargs.args else [])) == 2

    def test_fallback_on_propainter_exception(self):
        """If ProPainterInference.inpaint() raises, NN fill is used instead."""
        frames = [np.full((4, 4, 3), 120, dtype=np.uint8)]
        mask = np.ones((4, 4), dtype=np.uint8) * 255
        mock_model = MagicMock()
        mock_model.inpaint.side_effect = RuntimeError("GPU OOM")
        MockClass = MagicMock(return_value=mock_model)
        import backend.src.anim.bg_complete as bm
        with patch.object(bm, "ProPainterInference", MockClass):
            result = _propainter_complete_frames(frames, [mask], device="cpu")
        # NN fallback: all-bg mask → frame returned unchanged
        assert len(result) == 1
        np.testing.assert_array_equal(result[0], frames[0])


class TestMaskedMedianBg:
    def _make_stack(self, N=4, H=6, W=8, C=3):
        rng = np.random.default_rng(0)
        return rng.integers(0, 256, (N, H, W, C), dtype=np.uint8).astype(np.float32)

    def test_all_bg_returns_plain_median(self):
        stack = self._make_stack()
        N, H, W, C = stack.shape
        fg = np.zeros((N, H, W), dtype=bool)
        result = _masked_median_bg(stack, fg)
        expected = np.median(stack, axis=0)
        np.testing.assert_allclose(result, expected, atol=1.0)

    def test_fg_pixels_excluded_from_median(self):
        N, H, W, C = 3, 4, 4, 3
        stack = np.ones((N, H, W, C), dtype=np.float32) * 100.0
        stack[0, :, :, :] = 200.0  # frame 0 has fg pixels that differ
        fg = np.zeros((N, H, W), dtype=bool)
        fg[0, :, :] = True  # mask frame 0 everywhere
        result = _masked_median_bg(stack, fg)
        # Only frames 1,2 contribute → should be 100 everywhere
        np.testing.assert_allclose(result, 100.0, atol=0.5)

    def test_all_fg_falls_back_to_unconstrained_median(self):
        N, H, W, C = 3, 2, 2, 1
        stack = np.array(
            [[[50.0, 100.0], [150.0, 200.0]],
             [[60.0, 110.0], [160.0, 210.0]],
             [[70.0, 120.0], [170.0, 220.0]]],
            dtype=np.float32,
        ).reshape(N, H, W, C)
        fg = np.ones((N, H, W), dtype=bool)  # all fg
        result = _masked_median_bg(stack, fg)
        expected = np.median(stack, axis=0)
        np.testing.assert_allclose(result, expected, atol=0.5)

    def test_partial_fg_mixed_coverage(self):
        N, H, W, C = 4, 2, 4, 1
        stack = np.zeros((N, H, W, C), dtype=np.float32)
        stack[:, :, :2, 0] = 80.0   # left half: bg in all frames
        stack[:, :, 2:, 0] = 200.0  # right half: will be masked as fg
        fg = np.zeros((N, H, W), dtype=bool)
        fg[:, :, 2:] = True  # right half all fg → unconstrained fallback
        result = _masked_median_bg(stack, fg)
        np.testing.assert_allclose(result[:, :2, 0], 80.0, atol=0.5)
        np.testing.assert_allclose(result[:, 2:, 0], 200.0, atol=0.5)

    def test_output_shape_matches_input(self):
        N, H, W, C = 5, 10, 12, 3
        stack = np.zeros((N, H, W, C), dtype=np.float32)
        fg = np.zeros((N, H, W), dtype=bool)
        result = _masked_median_bg(stack, fg)
        assert result.shape == (H, W, C)
