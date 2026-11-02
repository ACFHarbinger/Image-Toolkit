"""R3 (#1172): CUDA out-of-memory shrinks the batch and retries the same card.

No device is used. ``OutOfMemoryError`` is a stand-in for ``torch.cuda.OutOfMemoryError``
(same class name). Output order is exact for these fakes, not an approximate tolerance.
"""

from __future__ import annotations

import numpy as np
from middleware.src.services.media.gif_upscale.gpu_schedule import schedule_gif_frames
from middleware.src.services.media.gif_upscale.pipeline import _finish_message, _path_record

_STAGES = ("decode", "palette", "scale", "index", "lzw")


class OutOfMemoryError(Exception):
    pass


class _Writer:
    def __init__(self) -> None:
        self.frames: list[int] = []

    def add_frame(self, index: np.ndarray, duration_ms: int) -> None:
        del duration_ms
        self.frames.append(int(np.asarray(index).reshape(-1)[0]))


class _Session:
    def __init__(self, batch_size: int, fail_when) -> None:
        self.device_index = 0
        self.device_name = "cuda:0"
        self.batch_size = batch_size
        self.fail_when = fail_when
        self.cache_frees = 0
        self.batches: list[list[int]] = []
        self.closed = False

    def release_cached_memory(self) -> None:
        self.cache_frees += 1

    def scale_and_index_batch(self, frames: list[np.ndarray]):
        ids = [int(frame.reshape(-1)[0]) for frame in frames]
        if self.fail_when(ids):
            raise OutOfMemoryError("injected")
        self.batches.append(ids)
        stacked = np.stack([np.full((1, 1), frame_id, dtype=np.uint8) for frame_id in ids])
        return stacked, 0.01, 0.02

    def close(self) -> None:
        self.closed = True


def _frames(count: int) -> list[np.ndarray]:
    return [np.array([[[frame_id, 0, 0, 255]]], dtype=np.uint8) for frame_id in range(count)]


def _message(opts: dict) -> str:
    return _finish_message(
        1,
        1,
        "out.gif",
        _path_record(opts, "lanczos3-dering", "mediancut"),
        dict.fromkeys(_STAGES, 0.0),
        opts.get("_gpu_fallback"),
    )


def test_oom_halves_batch_and_keeps_the_device() -> None:
    session = _Session(4, lambda ids: len(ids) > 2)
    writer = _Writer()
    opts: dict = {}

    def fallback(frames, op):
        del frames, op
        raise AssertionError("CPU fallback should not run when the smaller batch fits")

    schedule_gif_frames([session], _frames(4), [40] * 4, writer, opts=opts, cpu_fallback=fallback)
    assert writer.frames == [0, 1, 2, 3]
    assert session.batch_size == 2
    assert session.cache_frees == 1
    assert getattr(session, "retired", False) is False
    assert session.batches == [[0, 1], [2, 3]]
    message = _message(opts)
    assert "halved from 4 to 2" in message
    assert "cuda:0" in message


def test_one_oom_at_batch_size_one_retries_without_retiring() -> None:
    failed = {"n": 0}

    def fail_once(ids: list[int]) -> bool:
        del ids
        failed["n"] += 1
        return failed["n"] == 1

    session = _Session(1, fail_once)
    writer = _Writer()
    opts: dict = {}
    schedule_gif_frames(
        [session],
        _frames(1),
        [40],
        writer,
        opts=opts,
        cpu_fallback=lambda frames, op: (_ for _ in ()).throw(AssertionError("cpu")),
    )
    assert writer.frames == [0]
    assert getattr(session, "retired", False) is False
    assert session.cache_frees == 1
    assert "retrying the same batch on cuda:0" in _message(opts)


def test_repeated_oom_at_batch_size_one_retires_and_keeps_order() -> None:
    session = _Session(2, lambda ids: True)
    writer = _Writer()
    opts: dict = {}
    seen: list[list[int]] = []

    def fallback(frames, op):
        del op
        ids = [int(frame.reshape(-1)[0]) for frame in frames]
        seen.append(ids)
        return np.stack([np.full((1, 1), frame_id, dtype=np.uint8) for frame_id in ids])

    schedule_gif_frames([session], _frames(2), [40, 40], writer, opts=opts, cpu_fallback=fallback)
    assert writer.frames == [0, 1]
    assert session.batch_size == 1
    assert session.retired is True
    assert session.cache_frees >= 1
    assert seen == [[0], [1]]
    message = _message(opts)
    assert "halved from 2 to 1" in message
    assert "retiring cuda:0" in message
    assert "device=cpu" in message
