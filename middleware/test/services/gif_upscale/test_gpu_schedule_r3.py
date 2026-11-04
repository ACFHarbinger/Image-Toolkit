"""R3 (#1172): CUDA out-of-memory shrinks the batch and retries the same card.

No device is used. ``OutOfMemoryError`` is a stand-in for ``torch.cuda.OutOfMemoryError``
(same class name). Output order is exact for these fakes, not an approximate tolerance.
"""

from __future__ import annotations

import threading

import numpy as np
from middleware.src.services.media.gif_upscale.gpu_schedule import schedule_gif_frames
from middleware.src.services.media.gif_upscale.io import GifClip
from middleware.src.services.media.gif_upscale.pipeline import (
    _finish_message,
    _path_record,
    _resample_gif_in_memory_gpu,
    _resample_gif_stream,
    _stage_timings,
)

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
    def __init__(self, batch_size: int, fail_when, error: type[Exception] = OutOfMemoryError) -> None:
        self.device_index = 0
        self.device_name = "cuda:0"
        self.batch_size = batch_size
        self.fail_when = fail_when
        self.error = error
        self.cache_frees = 0
        self.batches: list[list[int]] = []
        self.attempted: list[list[int]] = []
        self.closed = False

    def release_cached_memory(self) -> None:
        self.cache_frees += 1

    def scale_and_index_batch(self, frames: list[np.ndarray]):
        ids = [int(frame.reshape(-1)[0]) for frame in frames]
        self.attempted.append(ids)
        if self.fail_when(ids):
            raise self.error("injected")
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


def test_repeated_shrink_splits_a_queued_tail() -> None:
    """A tail queued at the old limit must be split before it runs at the new limit.

    Batch 4 OOMs, shrinks to 2, and queues a 2-frame tail. The head OOMs and
    shrinks to 1. Executing that tail whole counts as a batch-size-1 failure
    and retires the card.
    """
    session = _Session(4, lambda ids: len(ids) > 1)
    writer = _Writer()
    opts: dict = {}

    def fallback(frames, op):
        del frames, op
        raise AssertionError("CPU fallback should not run when batch size 1 fits")

    schedule_gif_frames([session], _frames(4), [40] * 4, writer, opts=opts, cpu_fallback=fallback)
    assert writer.frames == [0, 1, 2, 3]
    assert session.batch_size == 1
    assert getattr(session, "retired", False) is False
    assert session.attempted == [[0, 1, 2, 3], [0, 1], [0], [1], [2], [3]]
    assert session.batches == [[0], [1], [2], [3]]
    assert "fell back to CPU" not in _message(opts)


class _GatedSession(_Session):
    """Block the worker's batch-size read until another card has requeued."""

    def __init__(self, batch_size: int, fail_when, gate: threading.Event) -> None:
        self._size = batch_size
        self._reads = 0
        self._gate = gate
        super().__init__(batch_size, fail_when)
        self.device_index = 1
        self.device_name = "cuda:1"

    @property
    def batch_size(self) -> int:
        self._reads += 1
        # Scheduler construction reads every session once. The next read is the pull.
        if self._reads > 1 and not self._gate.wait(5):
            raise TimeoutError("the other card did not requeue before the pull")
        return self._size

    @batch_size.setter
    def batch_size(self, value: int) -> None:
        self._size = int(value)


def test_retry_from_another_card_is_split_to_the_receiver_limit() -> None:
    """A 4-frame failure handed to a card whose limit is 1 must not run whole."""
    from middleware.src.services.media.gif_upscale import gpu_schedule as sched

    released = threading.Event()
    donor = _Session(4, lambda ids: True, error=RuntimeError)
    receiver = _GatedSession(1, lambda ids: len(ids) > 1, released)
    writer = _Writer()
    original = sched._FrameScheduler._fail_device

    def fail_device(self, session, job, exc) -> None:
        original(self, session, job, exc)
        if session is donor:
            released.set()

    sched._FrameScheduler._fail_device = fail_device
    try:
        schedule_gif_frames(
            [donor, receiver],
            _frames(4),
            [40] * 4,
            writer,
            cpu_fallback=lambda frames, op: (_ for _ in ()).throw(AssertionError("cpu")),
        )
    finally:
        sched._FrameScheduler._fail_device = original
    assert donor.attempted == [[0, 1, 2, 3]]
    assert receiver.attempted == [[0], [1], [2], [3]]
    assert writer.frames == [0, 1, 2, 3]
    assert getattr(donor, "retired", False) is True
    assert getattr(receiver, "retired", False) is False


class _ProductionSession:
    """One leased card. Batches longer than one frame report out of memory."""

    def __init__(self, gate: threading.Event | None = None) -> None:
        self.device_index = 0
        self.device_name = "cuda:0"
        self._size = 4
        self._reads = 0
        self._gate = gate
        self.attempted: list[int] = []
        self.cache_frees = 0
        self.closed = False

    @property
    def batch_size(self) -> int:
        self._reads += 1
        entered = getattr(self, "_entered", None)
        waiting = self._gate is not None and entered is not None and entered.is_set() and self._reads > 1
        if waiting and not self._gate.wait(5):
            raise TimeoutError("the stream decode did not finish before the pull")
        return self._size

    @batch_size.setter
    def batch_size(self, value: int) -> None:
        self._size = int(value)

    def _touch(self, frames) -> None:
        self.attempted.append(len(frames))
        if len(frames) > 1:
            raise OutOfMemoryError("injected")

    def scale_batch_uint8(self, frames):
        self._touch(frames)
        return [np.zeros((2, 2, 4), dtype=np.uint8) for _frame in frames]

    def index_batch_uint8(self, frames):
        self._touch(frames)
        return np.zeros((len(frames), 2, 2), dtype=np.uint8)

    def scale_and_index_batch(self, frames):
        self._touch(frames)
        return np.zeros((len(frames), 2, 2), dtype=np.uint8), 0.0, 0.0

    def prepare_palette(self, palette, transparent: bool, dither: str, quality: str) -> None:
        del palette, transparent, dither, quality

    def release_cached_memory(self) -> None:
        self.cache_frees += 1

    def close(self) -> None:
        self.closed = True


def _install_acquire(session: _ProductionSession):
    from middleware.src.services.media.gif_upscale import gpu_schedule as sched

    original = sched.acquire_gpu_sessions

    def acquire(**kwargs):
        del kwargs
        return [session], None

    sched.acquire_gpu_sessions = acquire
    return sched, original


def test_in_memory_entry_shrinks_one_session(tmp_path) -> None:
    session = _ProductionSession()
    sched, original = _install_acquire(session)
    clip = GifClip([np.zeros((2, 2, 4), dtype=np.uint8) for _ in range(4)], [40] * 4, 0)
    output = tmp_path / "memory.gif"
    params = {"algorithm": "lanczos3-dering", "encoder": "temporal", "factor": 1, "workers": 1}
    try:
        result = _resample_gif_in_memory_gpu(clip, str(output), params, _stage_timings(), None)
    finally:
        sched.acquire_gpu_sessions = original
    assert result is not None and result["success"] is True
    assert session.attempted[:6] == [4, 2, 1, 1, 1, 1]
    assert all(size == 1 for size in session.attempted[2:])
    assert session.batch_size == 1
    assert getattr(session, "retired", False) is False
    assert "fell back to CPU" not in result["message"]
    assert output.read_bytes().startswith(b"GIF89a")


def test_stream_entry_shrinks_one_session(tmp_path) -> None:
    from middleware.src.services.media.gif_upscale import gpu_schedule as sched
    from PIL import Image

    source = tmp_path / "source.gif"
    frames = [Image.new("RGB", (2, 2), (index * 40, 0, 0)) for index in range(4)]
    frames[0].save(source, save_all=True, append_images=frames[1:], duration=40, loop=0, disposal=2)
    # The worker waits only after schedule_gif_frames has started, and only until
    # that scheduler's decode thread has queued every frame. The old one-session
    # loop never enters the scheduler, so it must not sit on this gate.
    entered = threading.Event()
    decoded = threading.Event()
    original_decode = sched._FrameScheduler._decode_loop
    original_schedule = sched.schedule_gif_frames

    def decode_loop(self) -> None:
        try:
            original_decode(self)
        finally:
            decoded.set()

    def schedule(*args, **kwargs):
        entered.set()
        return original_schedule(*args, **kwargs)

    session = _ProductionSession(gate=decoded)
    session._entered = entered
    sched_module, original_acquire = _install_acquire(session)
    sched_module._FrameScheduler._decode_loop = decode_loop
    sched_module.schedule_gif_frames = schedule
    output = tmp_path / "stream.gif"
    params = {"algorithm": "lanczos3-dering", "encoder": "temporal", "factor": 1, "workers": 1}
    try:
        result = _resample_gif_stream(str(source), str(output), params, None)
    finally:
        sched_module.acquire_gpu_sessions = original_acquire
        sched_module._FrameScheduler._decode_loop = original_decode
        sched_module.schedule_gif_frames = original_schedule
    assert result["success"] is True
    # Palette sampling scales one frame at a time. The encode batch is the full clip.
    assert 4 in session.attempted
    assert session.batch_size == 1
    assert getattr(session, "retired", False) is False
    assert "fell back to CPU" not in result["message"]
    assert "halved" in result["message"]
    assert output.read_bytes().startswith(b"GIF89a")
