"""Task B3 (#1156): work-stealing GPU schedule with fake sessions. No torch."""

from __future__ import annotations

import threading
from types import SimpleNamespace

import numpy as np
import pytest
from middleware.src.core.gpu_lease_arbiter import GpuLeaseArbiter
from middleware.src.services.media.gif_upscale.base import ResampleCancelled
from middleware.src.services.media.gif_upscale.gpu_schedule import (
    acquire_gpu_sessions,
    schedule_gif_frames,
)


class _Writer:
    def __init__(self) -> None:
        self.frames: list[int] = []
        self.durations: list[int] = []

    def add_frame(self, index: np.ndarray, duration_ms: int) -> None:
        self.frames.append(int(index.reshape(-1)[0]))
        self.durations.append(int(duration_ms))


class _Session:
    def __init__(self, index: int, *, slow: bool = False, fail_once: bool = False) -> None:
        self.device_index = index
        self.device_name = f"cuda:{index}"
        self.batch_size = 2
        self.slow = slow
        self.fail_once = fail_once
        self.batches: list[list[int]] = []
        self.prepared = False
        self.closed = False
        self._first = True

    def prepare_palette(self, palette: np.ndarray, **kwargs: object) -> None:
        del palette, kwargs
        self.prepared = True

    def scale_batch_uint8(self, frames: list[np.ndarray]) -> list[np.ndarray]:
        ids = [int(frame.reshape(-1)[0]) for frame in frames]
        if self._first:
            self._first = False
            _sync_first_batch(self)
        elif not self.slow:
            _release_slow()
        if self.fail_once:
            self.fail_once = False
            self.batches.append(ids)
            raise RuntimeError("gpu down")
        self.batches.append(ids)
        return list(frames)

    def index_batch_uint8(self, frames: list[np.ndarray]) -> np.ndarray:
        ids = [int(frame.reshape(-1)[0]) for frame in frames]
        return np.stack([np.full((1, 1), frame_id, dtype=np.uint8) for frame_id in ids])

    def close(self) -> None:
        self.closed = True


_BARRIER: threading.Barrier | None = None
_RELEASE = threading.Event()


def _sync_first_batch(session: _Session) -> None:
    if _BARRIER is None:
        return
    _BARRIER.wait(10)
    if session.slow and not _RELEASE.wait(10):
        raise TimeoutError("slow device was not released")


def _release_slow() -> None:
    _RELEASE.set()


def _frames(count: int = 5) -> list[np.ndarray]:
    return [np.array([[[frame_id, 0, 0, 255]]], dtype=np.uint8) for frame_id in range(count)]


def test_faster_device_steals_more_batches_and_writer_stays_ordered() -> None:
    global _BARRIER, _RELEASE
    _BARRIER = threading.Barrier(2)
    _RELEASE = threading.Event()
    fast = _Session(0)
    slow = _Session(1, slow=True)
    writer = _Writer()
    opts: dict = {}
    try:
        result = schedule_gif_frames(
            [fast, slow],
            _frames(),
            [40] * 5,
            writer,
            palette=np.zeros((2, 3), dtype=np.float32),
            opts=opts,
        )
    finally:
        _BARRIER = None
    assert writer.frames == [0, 1, 2, 3, 4]
    assert writer.durations == [40] * 5
    assert len(fast.batches) > len(slow.batches)
    assert fast.prepared and slow.prepared
    assert fast.closed and slow.closed
    assert result["devices"] == ("cuda:0", "cuda:1")
    assert opts["_scale_path"] == "gpu-schedule cuda:0,cuda:1"
    covered: list[int] = []
    for batch in fast.batches + slow.batches:
        covered.extend(batch)
    assert sorted(covered) == [0, 1, 2, 3, 4]


def test_failed_device_retries_elsewhere_without_a_gap() -> None:
    global _BARRIER
    _BARRIER = None
    flaky = _Session(0, fail_once=True)
    other = _Session(1)
    writer = _Writer()
    schedule_gif_frames([flaky, other], _frames(), [40] * 5, writer, hold_batches=1)
    assert writer.frames == [0, 1, 2, 3, 4]
    assert flaky.closed and other.closed
    retried = [frame_id for batch in flaky.batches for frame_id in batch]
    elsewhere = [frame_id for batch in other.batches for frame_id in batch]
    assert retried
    assert set(retried) <= set(elsewhere)


def test_cancel_raises_and_closes_every_session() -> None:
    global _BARRIER
    _BARRIER = None
    sessions = [_Session(0), _Session(1)]

    def progress(stage: str, done: int, total: int) -> None:
        del stage, total
        if done >= 1:
            raise ResampleCancelled

    with pytest.raises(ResampleCancelled):
        schedule_gif_frames(sessions, _frames(), [40] * 5, _Writer(), progress=progress)
    assert all(session.closed for session in sessions)


def test_zero_devices_returns_the_cpu_reason() -> None:
    arbiter = GpuLeaseArbiter(
        devices=(
            {"index": 0, "total_gb": 24.0, "free_gb": 0.0},
            {"index": 1, "total_gb": 24.0, "free_gb": 0.0},
        )
    )
    opts: dict = {"params": {"gpu_arbiter": arbiter}}
    sessions, reason = acquire_gpu_sessions(
        src_h=4,
        src_w=4,
        dst_h=8,
        dst_w=8,
        opts=opts,
        arbiter=arbiter,
    )
    assert sessions == []
    assert reason is not None
    assert "fell back to cpu" in reason.lower()
    assert opts["_device"] == "cpu"
    assert opts["_gpu_fallback"] == reason


def test_each_allow_listed_device_is_requested_once(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    owners: list[str] = []

    def fake_acquire(**kwargs: object) -> tuple[SimpleNamespace | None, str | None]:
        call_opts = kwargs["opts"]
        assert isinstance(call_opts, dict)
        device = str(call_opts["params"]["device"])
        seen.append(device)
        owners.append(str(kwargs["owner"]))
        index = int(device.split(":")[1])
        if index == 1:
            return None, "GPU admission is held by other. Fell back to CPU"
        return SimpleNamespace(device_index=index, device_name=device), None

    monkeypatch.setattr(
        "middleware.src.services.media.gif_upscale.gpu_schedule.acquire_gpu_session",
        fake_acquire,
    )
    arbiter = GpuLeaseArbiter(
        devices=(
            {"index": 0, "total_gb": 24.0, "free_gb": 10.0},
            {"index": 1, "total_gb": 24.0, "free_gb": 8.0},
            {"index": 2, "total_gb": 24.0, "free_gb": 4.0},
        ),
        allow_devices=(0, 1),
    )
    opts: dict = {"params": {}}
    sessions, reason = acquire_gpu_sessions(
        src_h=4,
        src_w=4,
        dst_h=8,
        dst_w=8,
        opts=opts,
        arbiter=arbiter,
    )
    assert seen == ["cuda:0", "cuda:1"]
    assert len(set(owners)) == 2
    assert reason is None
    assert len(sessions) == 1
    assert "cuda:1" in opts["_gpu_fallback"] or "held by other" in opts["_gpu_fallback"]


def test_streaming_source_writes_frames_in_order() -> None:
    global _BARRIER
    _BARRIER = None
    writer = _Writer()

    def jobs() -> object:
        yield from ((frame, 40) for frame in _frames())

    schedule_gif_frames([_Session(0), _Session(1)], jobs(), None, writer, total=5)
    assert writer.frames == [0, 1, 2, 3, 4]


def test_overlap_runner_replaces_session_scale_and_index(monkeypatch: pytest.MonkeyPatch) -> None:
    global _BARRIER
    _BARRIER = None
    called: list[int] = []

    def run_device_pipeline(session: _Session, batches, **_kwargs: object) -> list[tuple[int, np.ndarray]]:
        called.append(session.device_index)
        batch_id, frames = batches[0]
        ids = [int(frame.reshape(-1)[0]) for frame in frames]
        session.batches.append(ids)
        indices = np.stack([np.full((1, 1), frame_id, dtype=np.uint8) for frame_id in ids])
        return [(batch_id, indices)]

    monkeypatch.setattr(
        "middleware.src.services.media.gif_upscale.gpu_schedule._overlap_pipeline",
        lambda: run_device_pipeline,
    )
    only = _Session(0)

    def forbid_scale(frames: list[np.ndarray]) -> list[np.ndarray]:
        del frames
        raise AssertionError("scale_batch_uint8 should not run when overlap is present")

    only.scale_batch_uint8 = forbid_scale  # type: ignore[method-assign]
    writer = _Writer()
    schedule_gif_frames([only], _frames(2), [40, 40], writer)
    assert writer.frames == [0, 1]
    assert called == [0]


def test_fused_scale_index_keeps_intermediate_on_device():
    class FusedSession(_Session):
        def scale_and_index_batch(self, frames):
            ids = [int(frame.reshape(-1)[0]) for frame in frames]
            return np.array(ids, dtype=np.uint8).reshape(-1, 1, 1), 0.1, 0.2

        def scale_batch_uint8(self, frames):
            raise AssertionError("RGBA host round trip")

    writer = _Writer()
    schedule_gif_frames(
        [FusedSession(0)], _frames(), [30] * 5, writer=writer,
        palette=np.zeros((256, 3), dtype=np.float32),
    )
    assert writer.frames == list(range(5))
