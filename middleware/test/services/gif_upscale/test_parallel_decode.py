"""Parallel GIF decode must match the sequential decoder frame for frame."""

from __future__ import annotations

import multiprocessing
import struct

import numpy as np
import pytest
from middleware.src.services.media.gif_upscale.io import iter_gif_frames
from middleware.src.services.media.gif_upscale.parallel_decode import (
    _proven_equivalent,
    iter_gif_frames_parallel,
    scan_gif,
)
from PIL import Image


def _palette() -> bytes:
    rng = np.random.default_rng(7)
    return rng.integers(0, 256, 768, dtype=np.uint8).tobytes()


def _payload(tmp_path, index: np.ndarray, palette: bytes) -> bytes:
    """Pillow's LZW image data for an index array (non-interlaced), reusing the block scanner."""
    image = Image.fromarray(index, "P")
    image.putpalette(palette)
    path = tmp_path / "one.gif"
    image.save(path, format="GIF", optimize=False, interlace=False)
    _info, records = scan_gif(str(path))
    return path.read_bytes()[records[0].start : records[0].end]


def _assemble(tmp_path, width, height, frames, palette, loop=0) -> str:
    """frames: (left, top, index_array, disposal, transparent_index_or_None, delay_cs)."""
    out = bytearray(b"GIF89a" + struct.pack("<HH", width, height) + bytes([0xF7, 0, 0]) + palette)
    out += b"\x21\xff\x0bNETSCAPE2.0\x03\x01" + struct.pack("<H", loop) + b"\x00"
    for left, top, index, disposal, transparent, delay in frames:
        packed = (disposal << 2) | (1 if transparent is not None else 0)
        out += b"\x21\xf9\x04" + bytes([packed]) + struct.pack("<H", delay) + bytes([transparent or 0, 0])
        h, w = index.shape
        out += b"\x2c" + struct.pack("<HHHH", left, top, w, h) + b"\x00"
        out += _payload(tmp_path, index, palette)
    out += b"\x3b"
    path = tmp_path / "built.gif"
    path.write_bytes(bytes(out))
    return str(path)


def _same(path: str, workers: int = 2) -> int:
    expected = list(iter_gif_frames(path))
    got = list(iter_gif_frames_parallel(path, workers))
    assert len(got) == len(expected)
    for i, ((a, da, la), (b, db, lb)) in enumerate(zip(expected, got, strict=True)):
        assert np.array_equal(a, b), f"frame {i} differs"
        assert (da, la) == (db, lb), f"frame {i} duration/loop differs"
    return len(got)


@pytest.mark.parametrize("disposal", [0, 1, 2, 3])
def test_pillow_made_gif_matches(tmp_path, disposal):
    base = Image.new("RGB", (40, 24), (10, 200, 30))
    frames = []
    for step in range(6):
        frame = base.copy()
        frame.paste((255 - step * 30, step * 40, 90), (step * 4, 2, step * 4 + 10, 14))
        frames.append(frame)
    path = tmp_path / "p.gif"
    frames[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=[30, 40, 50, 60, 70, 80],
        loop=3,
        disposal=disposal,
    )
    assert _same(str(path)) == 6


def test_partial_transparent_frames_with_variable_delays(tmp_path):
    rng = np.random.default_rng(1)
    pal = _palette()
    full = rng.integers(1, 200, (30, 50), dtype=np.uint8)
    patch = rng.integers(1, 200, (8, 12), dtype=np.uint8)
    holes = rng.integers(0, 3, (10, 14), dtype=np.uint8)  # index 0 is transparent
    frames = [
        (0, 0, full, 1, 0, 4),
        (5, 6, patch, 1, 0, 9),
        (20, 10, holes, 1, 0, 2),
        (0, 0, np.zeros((30, 50), np.uint8), 1, 0, 7),  # fully transparent frame keeps the canvas
    ]
    path = _assemble(tmp_path, 50, 30, frames, pal, loop=3)
    assert _same(path) == 4
    info, records = scan_gif(path)
    assert info.loop == 3 and [r.delay_cs for r in records] == [4, 9, 2, 7]


def test_restore_previous_and_clear_to_transparent(tmp_path):
    rng = np.random.default_rng(2)
    pal = _palette()
    base = rng.integers(1, 200, (24, 36), dtype=np.uint8)
    over = rng.integers(1, 200, (10, 10), dtype=np.uint8)
    frames = [
        (0, 0, base, 1, 0, 5),
        (4, 4, over, 3, 0, 5),  # disposal 3: the next frame sees the canvas without this patch
        (20, 8, over, 2, 0, 5),  # disposal 2 with a transparent index clears its rectangle
        (0, 0, np.zeros((24, 36), np.uint8), 1, 0, 5),
    ]
    assert _same(_assemble(tmp_path, 36, 24, frames, pal)) == 4


def test_first_frame_with_transparent_pixels_keeps_their_colour(tmp_path):
    rng = np.random.default_rng(4)
    pal = _palette()
    first = rng.integers(0, 4, (18, 26), dtype=np.uint8)  # many index-0 (transparent) pixels
    later = rng.integers(0, 4, (18, 26), dtype=np.uint8)
    frames = [(0, 0, first, 1, 0, 3), (0, 0, later, 1, 0, 3), (0, 0, first, 2, 0, 3), (0, 0, later, 1, 0, 3)]
    assert _same(_assemble(tmp_path, 26, 18, frames, pal)) == 4


def test_partial_first_frame_uses_the_sequential_decoder(tmp_path):
    rng = np.random.default_rng(5)
    pal = _palette()
    frames = [
        (2, 2, rng.integers(1, 200, (8, 8), dtype=np.uint8), 1, 0, 3),
        (0, 0, rng.integers(1, 200, (16, 16), dtype=np.uint8), 1, 0, 3),
    ]
    path = _assemble(tmp_path, 16, 16, frames, pal)
    info, records = scan_gif(path)
    assert not _proven_equivalent(info, records)
    assert _same(path) == 2


def test_background_disposal_without_transparency_uses_the_sequential_decoder(tmp_path):
    rng = np.random.default_rng(3)
    pal = _palette()
    frames = [
        (0, 0, rng.integers(0, 200, (20, 20), dtype=np.uint8), 2, None, 5),
        (3, 3, rng.integers(0, 200, (6, 6), dtype=np.uint8), 2, None, 5),
        (0, 0, rng.integers(0, 200, (20, 20), dtype=np.uint8), 0, None, 5),
    ]
    path = _assemble(tmp_path, 20, 20, frames, pal)
    info, records = scan_gif(path)
    assert not _proven_equivalent(info, records)
    assert _same(path) == 3


def test_one_worker_never_starts_a_pool(tmp_path, monkeypatch):
    import middleware.src.services.media.gif_upscale.parallel_decode as module

    def boom(*_a, **_k):
        raise AssertionError("pool started")

    monkeypatch.setattr(module, "ProcessPoolExecutor", boom)
    base = Image.new("RGB", (16, 16), (1, 2, 3))
    other = Image.new("RGB", (16, 16), (200, 2, 3))
    path = tmp_path / "w1.gif"
    base.save(path, format="GIF", save_all=True, append_images=[other], duration=20)
    assert _same(str(path), workers=1) == 2


def test_closing_the_generator_stops_the_pool(tmp_path):
    frames = [Image.new("RGB", (32, 32), (i * 5 % 256, 40, 90)) for i in range(40)]
    path = tmp_path / "many.gif"
    frames[0].save(path, format="GIF", save_all=True, append_images=frames[1:], duration=20)
    generator = iter_gif_frames_parallel(str(path), 2)
    next(generator)
    next(generator)
    generator.close()
    assert multiprocessing.active_children() == []


def test_pipeline_workers_key_selects_the_parallel_decoder(tmp_path, monkeypatch):
    import middleware.src.services.media.gif_upscale.pipeline as pipeline

    calls = []
    real = pipeline._iter_rgba

    def spy(path, workers=1):
        calls.append(workers)
        return real(path, workers)

    monkeypatch.setattr(pipeline, "_iter_rgba", spy)
    frames = [Image.new("RGB", (24, 16), (i * 40 % 256, 30, 90)) for i in range(5)]
    path = tmp_path / "w.gif"
    frames[0].save(path, format="GIF", save_all=True, append_images=frames[1:], duration=20)
    assert pipeline._workers({}) == 1
    assert pipeline._workers({"workers": "3"}) == 3
    assert pipeline._workers({"workers": "bad"}) == 1
    clip = pipeline._decode_clip(str(path), {"workers": 2})
    assert calls == [2] and len(clip.frames) == 5
    sequential = pipeline._decode_clip(str(path), {})
    assert all(np.array_equal(a, b) for a, b in zip(clip.frames, sequential.frames, strict=True))
    assert clip.durations == sequential.durations and clip.loop == sequential.loop


def test_resample_gif_with_workers_matches_workers_one(tmp_path):
    from middleware.src.services.media.gif_upscale.pipeline import resample_gif

    frames = []
    for i in range(6):
        frame = Image.new("RGB", (32, 20), (10, 120, 30))
        frame.paste((250 - i * 30, i * 40, 90), (i * 3, 2, i * 3 + 9, 12))
        frames.append(frame)
    source = tmp_path / "s.gif"
    frames[0].save(source, format="GIF", save_all=True, append_images=frames[1:], duration=30, loop=0)
    base = {"mode": "factor", "factor": 2, "algorithm": "bicubic"}
    one = resample_gif(str(source), str(tmp_path / "one.gif"), {**base, "workers": 1})
    many = resample_gif(str(source), str(tmp_path / "many.gif"), {**base, "workers": 2})
    assert one["success"] and many["success"]
    assert [f[0] for f in iter_gif_frames(str(tmp_path / "one.gif"))].__len__() == 6
    for (a, _da, _la), (b, _db, _lb) in zip(
        iter_gif_frames(str(tmp_path / "one.gif")), iter_gif_frames(str(tmp_path / "many.gif")), strict=True
    ):
        assert np.array_equal(a, b)
