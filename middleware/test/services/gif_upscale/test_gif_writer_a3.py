"""Tests for Task A3 (#1150): Pillow C LZW encoder in IndexedGifWriter."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from middleware.src.services.media.gif_upscale.base import AlgorithmError
from middleware.src.services.media.gif_upscale.encode import (
    IndexedGifWriter,
    _encode_lzw_subblocks,
)
from middleware.src.services.media.gif_upscale.io import decode_gif


def _make_palette(seed: int = 101) -> np.ndarray:
    rng = np.random.default_rng(seed)
    pal = rng.integers(0, 256, size=(256, 3), dtype=np.uint8).astype(np.float32)
    pal[0] = [0.0, 0.0, 0.0]
    return pal


@pytest.mark.parametrize("transparent", [False, True])
@pytest.mark.parametrize("shape", [(47, 73), (64, 64)])
def test_pillow_lzw_matches_pure_python_lzw_decoded_pixels(
    tmp_path: Path, transparent: bool, shape: tuple[int, int]
) -> None:
    """Pillow C LZW (default) and pure-Python _lzw decode to 100% bit-identical RGBA frames and metadata."""
    rng = np.random.default_rng(2026)
    height, width = shape
    palette = _make_palette()
    frames_idx = [rng.integers(0, 256, size=(height, width), dtype=np.uint8) for _ in range(5)]
    if transparent:
        for idx in frames_idx:
            idx[:5, :7] = 0
    durations = [40, 70, 100, 30, 60]
    loop = 3

    path_c = tmp_path / "c_lzw.gif"
    path_py = tmp_path / "py_lzw.gif"

    writer_c = IndexedGifWriter(str(path_c), width, height, palette, loop, transparent=transparent, use_pillow_lzw=True)
    writer_py = IndexedGifWriter(
        str(path_py), width, height, palette, loop, transparent=transparent, use_pillow_lzw=False
    )
    try:
        for idx, dur in zip(frames_idx, durations, strict=True):
            writer_c.add_frame(idx, dur)
            writer_py.add_frame(idx, dur)
    finally:
        writer_c.close()
        writer_py.close()

    clip_c = decode_gif(str(path_c))
    clip_py = decode_gif(str(path_py))
    frames_c, durs_c, loop_c = clip_c.frames, clip_c.durations, clip_c.loop
    frames_py, durs_py, loop_py = clip_py.frames, clip_py.durations, clip_py.loop

    assert loop_c == loop
    assert loop_py == loop
    assert durs_c == durations
    assert durs_py == durations
    assert len(frames_c) == len(frames_idx)
    for fc, fpy, idx in zip(frames_c, frames_py, frames_idx, strict=True):
        np.testing.assert_array_equal(fc, fpy)
        expected_rgb = palette[idx].astype(np.uint8)
        if transparent:
            opaque_mask = idx != 0
            np.testing.assert_array_equal(fc[:, :, :3][opaque_mask], expected_rgb[opaque_mask])
            np.testing.assert_array_equal(fc[:, :, 3] == 0, ~opaque_mask)
        else:
            np.testing.assert_array_equal(fc[:, :, :3], expected_rgb)
            assert int(fc[:, :, 3].min()) == 255


def test_non_interlaced_row_order_preserved(tmp_path: Path) -> None:
    """Verify interlace=False is enforced so row indices 0..H-1 do not get scrambled."""
    height, width = 33, 19
    palette = np.zeros((256, 3), dtype=np.float32)
    for i in range(height):
        palette[i] = [i * 7 % 256, i * 13 % 256, i * 29 % 256]
    # Each row r has constant index r
    index = np.broadcast_to(np.arange(height, dtype=np.uint8)[:, None], (height, width)).copy()
    out = tmp_path / "row_order.gif"
    writer = IndexedGifWriter(str(out), width, height, palette, 0, transparent=False)
    try:
        writer.add_frame(index, 50)
    finally:
        writer.close()

    clip = decode_gif(str(out))
    expected_rgb = palette[index].astype(np.uint8)
    np.testing.assert_array_equal(clip.frames[0][:, :, :3], expected_rgb)


def test_add_compressed_frame_matches_add_frame(tmp_path: Path) -> None:
    """Pre-compressed LZW subblocks written via add_compressed_frame match add_frame byte-for-byte."""
    rng = np.random.default_rng(77)
    height, width = 24, 32
    palette = _make_palette(77)
    indices = [rng.integers(0, 256, size=(height, width), dtype=np.uint8) for _ in range(3)]
    p1 = tmp_path / "direct.gif"
    p2 = tmp_path / "precompressed.gif"
    w1 = IndexedGifWriter(str(p1), width, height, palette, 0, transparent=True)
    w2 = IndexedGifWriter(str(p2), width, height, palette, 0, transparent=True)
    try:
        for idx in indices:
            w1.add_frame(idx, 50)
            w2.add_compressed_frame(_encode_lzw_subblocks(idx, use_pillow=True), 50)
    finally:
        w1.close()
        w2.close()
    assert p1.read_bytes() == p2.read_bytes()


def test_encode_lzw_subblocks_rejects_non_2d() -> None:
    with pytest.raises(AlgorithmError, match="Expected 2D indexed frame"):
        _encode_lzw_subblocks(np.zeros((10,), dtype=np.uint8))
