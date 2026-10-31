"""Process-pool GIF LZW (task D1, #1163). workers=1 stays in-process."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
from middleware.src.services.media.gif_upscale.base import AlgorithmError
from middleware.src.services.media.gif_upscale.encode import IndexedGifWriter
from middleware.src.services.media.gif_upscale.encode_pool import _limit_worker_threads
from PIL import Image

_THREAD_KEYS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "OPENCV_NUM_THREADS")


def _palette() -> np.ndarray:
    return np.repeat(np.arange(256)[:, None], 3, axis=1)


def _patterns(count: int, size: int = 8) -> list[np.ndarray]:
    frames = []
    for number in range(count):
        frame = np.full((size, size), number + 1, dtype=np.uint8)
        frame[0, :] = 100 + number
        frame[:, 0] = 150 + number
        frames.append(frame)
    return frames


def _durations(count: int) -> list[int]:
    return [40 * (index + 1) for index in range(count)]


def _spawn_main_children() -> set[int]:
    parent = os.getpid()
    found: set[int] = set()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text()
            command = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        tail = stat.rsplit(")", 1)
        if len(tail) != 2 or b"spawn_main" not in command:
            continue
        ppid = int(tail[1].split()[1])
        if ppid == parent:
            found.add(int(entry.name))
    return found


def _write(
    path: Path,
    frames: list[np.ndarray],
    *,
    workers: int,
    use_pillow_lzw: bool = True,
) -> IndexedGifWriter:
    height, width = frames[0].shape
    writer = IndexedGifWriter(
        str(path),
        width,
        height,
        _palette(),
        loop=2,
        transparent=False,
        use_pillow_lzw=use_pillow_lzw,
        workers=workers,
    )
    try:
        for frame, duration in zip(frames, _durations(len(frames)), strict=True):
            writer.add_frame(frame, duration)
    finally:
        writer.close()
    return writer


def _assert_decoded(path: Path, frames: list[np.ndarray]) -> None:
    durations = _durations(len(frames))
    with Image.open(path) as gif:
        assert gif.n_frames == len(frames)
        assert gif.size == (frames[0].shape[1], frames[0].shape[0])
        assert gif.info.get("loop") == 2
        for index, frame in enumerate(frames):
            gif.seek(index)
            assert gif.info.get("duration") == durations[index]
            np.testing.assert_array_equal(np.asarray(gif), frame)


@pytest.mark.parametrize("use_pillow_lzw", [True, False])
def test_workers_one_matches_default_and_does_not_spawn(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, use_pillow_lzw: bool
) -> None:
    import middleware.src.services.media.gif_upscale.encode_pool as encode_pool

    def forbid_pool(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("workers=1 started a process pool")

    monkeypatch.setattr(encode_pool.multiprocessing, "get_context", forbid_pool)
    frames = _patterns(2)
    default_path = tmp_path / "default.gif"
    explicit_path = tmp_path / "workers-1.gif"
    before = _spawn_main_children()
    omitted = IndexedGifWriter(
        str(default_path), 8, 8, _palette(), loop=2, transparent=False, use_pillow_lzw=use_pillow_lzw
    )
    try:
        for frame, duration in zip(frames, _durations(2), strict=True):
            omitted.add_frame(frame, duration)
    finally:
        omitted.close()
    writer = IndexedGifWriter(
        str(explicit_path),
        8,
        8,
        _palette(),
        loop=2,
        transparent=False,
        use_pillow_lzw=use_pillow_lzw,
        workers=1,
    )
    assert writer._pool is None
    try:
        for frame, duration in zip(frames, _durations(2), strict=True):
            writer.add_frame(frame, duration)
            assert writer._pool is None
    finally:
        writer.close()
    assert writer._pool is None
    assert _spawn_main_children() == before
    assert default_path.read_bytes() == explicit_path.read_bytes()
    _assert_decoded(explicit_path, frames)


@pytest.mark.parametrize("use_pillow_lzw", [True, False])
def test_workers_two_matches_in_process_frames(tmp_path: Path, use_pillow_lzw: bool) -> None:
    frames = _patterns(4)
    parent_env = {key: os.environ.get(key) for key in _THREAD_KEYS}
    before = _spawn_main_children()
    single = tmp_path / "workers-1.gif"
    pooled = tmp_path / "workers-2.gif"
    _write(single, frames, workers=1, use_pillow_lzw=use_pillow_lzw)
    writer = IndexedGifWriter(
        str(pooled),
        8,
        8,
        _palette(),
        loop=2,
        transparent=False,
        use_pillow_lzw=use_pillow_lzw,
        workers=2,
    )
    try:
        writer.add_frame(frames[0], _durations(4)[0])
        assert writer._pool is not None
        assert writer._pool._mp is not None
        assert writer._pool._mp._initializer is _limit_worker_threads
        assert writer._pool._mp._processes == 2
        for frame, duration in zip(frames[1:], _durations(4)[1:], strict=True):
            writer.add_frame(frame, duration)
    finally:
        writer.close()
    assert {key: os.environ.get(key) for key in _THREAD_KEYS} == parent_env
    assert _spawn_main_children() == before
    assert pooled.read_bytes() == single.read_bytes()
    _assert_decoded(pooled, frames)


def test_failed_worker_does_not_write_past_the_gap(tmp_path: Path) -> None:
    frames = _patterns(4)
    frames[2] = np.zeros((frames[0].shape[0],), dtype=np.uint8)
    path = tmp_path / "gap.gif"
    before = _spawn_main_children()
    writer = IndexedGifWriter(str(path), 8, 8, _palette(), loop=2, transparent=False, workers=2)
    try:
        with pytest.raises(AlgorithmError, match="Expected 2D indexed frame"):
            for frame, duration in zip(frames, _durations(len(frames)), strict=True):
                writer.add_frame(frame, duration)
            writer.close()
    finally:
        writer.close()
    assert _spawn_main_children() == before
    _assert_decoded(path, _patterns(2))
