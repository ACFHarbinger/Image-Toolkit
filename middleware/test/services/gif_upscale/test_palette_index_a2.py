"""Tests for #1149 A2: exact BLAS palette lookup and 7-bit (128^3) LUT with precomputed Bayer grid."""

from __future__ import annotations

import numpy as np
import pytest
from middleware.src.services.media.gif_upscale.base import AlgorithmError
from middleware.src.services.media.gif_upscale.encode import (
    _BAYER_8,
    _bayer_grid,
    _indexes,
    _shared_palette,
    build_palette_lut,
    index_frame,
)


def _reference_indexes(rgb: np.ndarray, palette: np.ndarray, dither: str) -> np.ndarray:
    """Today's brute-force chunked Euclidean distance lookup."""
    adjusted = rgb.astype(np.float32)
    if dither == "ordered":
        height, width = rgb.shape[:2]
        yy, xx = np.mgrid[0:height, 0:width]
        threshold = (_BAYER_8[yy % 8, xx % 8] + 0.5) / 64.0 - 0.5
        adjusted = adjusted + threshold[:, :, None] * 24.0
    flat = adjusted.reshape(-1, 3)
    chosen = np.empty(flat.shape[0], dtype=np.uint8)
    step = 8192
    for start in range(0, flat.shape[0], step):
        chunk = flat[start : start + step]
        distance = ((chunk[:, None, :] - palette[None, :, :]) ** 2).sum(axis=2)
        chosen[start : start + step] = distance.argmin(axis=1).astype(np.uint8)
    return chosen.reshape(rgb.shape[:2])


def test_exact_blas_matches_reference_bit_for_bit() -> None:
    rng = np.random.default_rng(42)
    for height, width in ((7, 5), (16, 24), (65, 97)):
        rgba = rng.integers(0, 256, (height, width, 4), dtype=np.uint8)
        palette = rng.integers(0, 256, (256, 3), dtype=np.uint8).astype(np.float32)
        for dither in ("ordered", "none"):
            expected = _reference_indexes(rgba[:, :, :3], palette, dither)
            actual = _indexes(rgba[:, :, :3], palette, dither, quality="exact")
            assert np.array_equal(actual, expected)

        # Check transparent index_frame shifting and alpha masking
        rgba_trans = rgba.copy()
        rgba_trans[::2, ::3, 3] = 0
        rgba_trans[1::2, ::3, 3] = 255
        expected_trans = _reference_indexes(rgba_trans[:, :, :3], palette[1:], "ordered") + 1
        expected_trans[rgba_trans[:, :, 3] < 128] = 0
        actual_trans = index_frame(rgba_trans, palette, transparent=True, dither="ordered", quality="exact")
        assert np.array_equal(actual_trans, expected_trans)


def test_deterministic_tie_breaking_picks_lowest_index() -> None:
    # Palette entries 1 and 3 are identical; entry 0 and 2 are equidistant from (15, 0, 0).
    palette = np.array(
        [
            [10.0, 0.0, 0.0],
            [100.0, 100.0, 100.0],
            [20.0, 0.0, 0.0],
            [100.0, 100.0, 100.0],
        ],
        dtype=np.float32,
    )
    rgb = np.array([[[15, 0, 0], [100, 100, 100]]], dtype=np.uint8)
    exact_out = _indexes(rgb, palette, "none", quality="exact")
    lut_out = _indexes(rgb, palette, "none", quality="balanced")
    assert exact_out[0, 0] == 0
    assert exact_out[0, 1] == 1
    assert lut_out[0, 1] == 1


def test_lut_and_bayer_grid_cache_and_accuracy() -> None:
    rng = np.random.default_rng(7)
    yy, xx = np.mgrid[0:64, 0:96]
    grad = np.zeros((64, 96, 4), dtype=np.uint8)
    grad[..., 0] = (xx * 255 // 95).astype(np.uint8)
    grad[..., 1] = (yy * 255 // 63).astype(np.uint8)
    grad[..., 2] = ((xx + yy) * 255 // 158).astype(np.uint8)
    grad[..., 3] = 255
    noisy = np.clip(grad.astype(np.int16) + rng.integers(-8, 9, grad.shape, dtype=np.int16), 0, 255).astype(np.uint8)
    noisy[..., 3] = 255

    palette = _shared_palette([grad, noisy], 256, "mediancut")
    lut1 = build_palette_lut(palette)
    lut2 = build_palette_lut(palette.copy())
    assert lut1 is lut2
    assert lut1.shape == (128**3,)
    assert lut1.dtype == np.uint8

    grid1 = _bayer_grid(64, 96)
    grid2 = _bayer_grid(64, 96)
    assert grid1 is grid2

    exact_idx = index_frame(noisy, palette, transparent=False, dither="ordered", quality="exact")
    balanced_idx = index_frame(noisy, palette, transparent=False, dither="ordered", quality="balanced")
    fast_idx = index_frame(noisy, palette, transparent=False, dither="ordered", quality="fast")
    default_idx = index_frame(noisy, palette, transparent=False, dither="ordered")

    # Default is balanced; fast and balanced share the 7-bit LUT and are temporally deterministic.
    assert np.array_equal(balanced_idx, default_idx)
    assert np.array_equal(balanced_idx, fast_idx)
    agreement = float((balanced_idx == exact_idx).mean())
    assert agreement >= 0.88

    # Decoded-color error between exact and 7-bit LUT is tiny.
    exact_rgb = palette[exact_idx]
    balanced_rgb = palette[balanced_idx]
    rmse = float(np.sqrt(np.mean((exact_rgb - balanced_rgb) ** 2)))
    assert rmse < 2.5


def test_unknown_quality_raises_algorithm_error() -> None:
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    palette = np.zeros((16, 3), dtype=np.float32)
    with pytest.raises(AlgorithmError, match="Unknown palette indexing quality"):
        _indexes(rgb, palette, "ordered", quality="ultra")
