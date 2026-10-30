"""Overlap tiles with a feather blend, and shrink the tile after a memory error."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

TileFn = Callable[[np.ndarray], np.ndarray]


def process_tiled(
    frame: np.ndarray,
    function: TileFn,
    *,
    tile: int = 256,
    overlap: int = 16,
    min_tile: int = 32,
) -> np.ndarray:
    """Run ``function`` on tiles. ``MemoryError`` retries with a tile half as wide."""
    if tile < 1 or min_tile < 1:
        raise ValueError("tile size must be positive")
    size = tile
    while True:
        try:
            return _stitch(frame, function, size, overlap)
        except MemoryError:
            if size <= min_tile:
                raise
            size = max(min_tile, size // 2)


def _stitch(frame: np.ndarray, function: TileFn, tile: int, overlap: int) -> np.ndarray:
    height, width = frame.shape[:2]
    accumulator = np.zeros_like(frame, dtype=np.float32)
    weights = np.zeros((height, width, 1), dtype=np.float32)
    step = max(1, tile - overlap)
    for top in range(0, height, step):
        for left in range(0, width, step):
            bottom = min(height, top + tile)
            right = min(width, left + tile)
            piece = function(frame[top:bottom, left:right])
            if piece.shape[:2] != (bottom - top, right - left):
                raise ValueError("tiled function changed the tile shape")
            window = _feather(piece.shape[0], piece.shape[1], overlap, top == 0, left == 0, bottom == height, right == width)
            accumulator[top:bottom, left:right] += piece.astype(np.float32) * window
            weights[top:bottom, left:right] += window
    return (accumulator / np.maximum(weights, 1e-6)).astype(frame.dtype, copy=False)


def _feather(
    height: int,
    width: int,
    overlap: int,
    top_edge: bool,
    left_edge: bool,
    bottom_edge: bool,
    right_edge: bool,
) -> np.ndarray:
    weight_y = _fade(height, overlap, top_edge, bottom_edge)
    weight_x = _fade(width, overlap, left_edge, right_edge)
    return (weight_y[:, None] * weight_x[None, :])[:, :, None]


def _fade(length: int, overlap: int, start_edge: bool, end_edge: bool) -> np.ndarray:
    """Ramp only across the pixels this tile actually has.

    A trailing tile can be narrower than ``overlap``. Using the full ramp
    there raises a broadcasting error.
    """
    weights = np.ones(length, dtype=np.float32)
    if overlap <= 0 or length <= 0:
        return weights
    span = min(overlap, length)
    ramp = np.linspace(0.0, 1.0, span, endpoint=False, dtype=np.float32)
    if not start_edge:
        weights[:span] *= ramp
    if not end_edge:
        weights[-span:] *= ramp[::-1]
    return weights
