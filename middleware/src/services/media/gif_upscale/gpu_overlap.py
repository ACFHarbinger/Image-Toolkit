"""Bounded overlap for one GPU's GIF resample batches (#1157).

The caller thread drives the device. This module does not start a process
pool or a thread pool, and it does not change OpenBLAS or OpenCV thread counts.

Pinned host memory and CUDA streams are used only when ``session.device`` is a
real CUDA device and ``torch.cuda.is_available()`` is true. That path keeps a
copy stream and a compute stream, a pinned upload buffer, and a pinned buffer
for the uint8 index download. ``GpuResampleSession`` does not take a stream,
so compute is still ``scale_batch_uint8`` then ``index_batch_uint8``. The next
batch's pinned host-to-device prefetch is queued on the copy stream before
that download runs, which is the overlap. At most ``queue_depth`` batches are
allocated.

A fake session, or any session without a CUDA device, runs those two calls in
order on this thread and does not pin memory.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable, Sequence
from typing import Any

import numpy as np

_Batch = tuple[Any, Sequence[np.ndarray]]


class _Slot:
    """One in-flight batch. Storage is reused so the queue stays bounded."""

    __slots__ = ("batch_id", "device_up", "frames", "h2d_event", "pinned_down", "pinned_up")

    def __init__(self) -> None:
        self.batch_id: Any = None
        self.pinned_up: Any = None
        self.pinned_down: Any = None
        self.device_up: Any = None
        self.h2d_event: Any = None
        self.frames: Sequence[np.ndarray] | None = None


def run_device_pipeline(
    session: Any,
    batches: Iterable[_Batch],
    *,
    queue_depth: int = 2,
    cancel: Callable[[], None] | None = None,
) -> list[tuple[Any, np.ndarray]]:
    """Run batches on one device with overlap.

    session: GpuResampleSession or a test double.
    batches: sequence of (batch_id, frames) where frames is a list of HxWx4 uint8 or float arrays.
    Returns a list of (batch_id, indices) in completion order (NOT sorted).
    queue_depth is the max number of batches in flight (H2D + compute + D2H).
    cancel: optional zero-arg callable; if it raises, stop launching and reraise
    after in-flight work is joined. Nothing new is launched after it raises.

    Pinned uploads, pinned index downloads, and CUDA streams run only when
    ``session.device`` is a real CUDA device. Otherwise scale then index run
    in order on this thread and memory is not pinned.
    """
    depth = int(queue_depth)
    if depth < 1:
        raise ValueError("queue_depth must be at least 1")
    if _cuda_streams_available(session):
        return _run_cuda(session, batches, depth, cancel)
    return _run_sequential(session, batches, cancel)


def _check_cancel(cancel: Callable[[], None] | None) -> None:
    if cancel is not None:
        cancel()


def _run_sequential(
    session: Any,
    batches: Iterable[_Batch],
    cancel: Callable[[], None] | None,
) -> list[tuple[Any, np.ndarray]]:
    """One batch at a time. That is inside ``queue_depth`` and does not pin."""
    results: list[tuple[Any, np.ndarray]] = []
    for batch_id, frames in batches:
        _check_cancel(cancel)
        scaled = session.scale_batch_uint8(frames)
        indices = session.index_batch_uint8(scaled)
        results.append((batch_id, np.ascontiguousarray(indices)))
    return results


def _cuda_streams_available(session: Any) -> bool:
    device = getattr(session, "device", None)
    if getattr(device, "type", None) != "cuda":
        return False
    try:
        import torch
    except ImportError:
        return False
    return bool(torch.cuda.is_available() and isinstance(device, torch.device))


def _run_cuda(
    session: Any,
    batches: Iterable[_Batch],
    depth: int,
    cancel: Callable[[], None] | None,
) -> list[tuple[Any, np.ndarray]]:
    import torch

    device = session.device
    copy_stream = torch.cuda.Stream(device=device)
    compute_stream = torch.cuda.Stream(device=device)
    try:
        return _drive_cuda(session, batches, depth, cancel, torch, device, copy_stream, compute_stream)
    finally:
        # Join copies still queued when cancel or a session error unwinds.
        # The steady state does not device-synchronize; that would serialize
        # the copy stream with compute and remove the overlap.
        copy_stream.synchronize()
        compute_stream.synchronize()


def _drive_cuda(
    session: Any,
    batches: Iterable[_Batch],
    depth: int,
    cancel: Callable[[], None] | None,
    torch: Any,
    device: Any,
    copy_stream: Any,
    compute_stream: Any,
) -> list[tuple[Any, np.ndarray]]:
    free: list[_Slot] = []
    window: deque[_Slot] = deque()
    created = 0
    results: list[tuple[Any, np.ndarray]] = []
    pending = iter(batches)
    exhausted = False
    cancel_exc: Exception | None = None
    while True:
        while len(window) < depth and not exhausted and cancel_exc is None:
            try:
                _check_cancel(cancel)
            except Exception as exc:
                cancel_exc = exc
                break
            try:
                batch_id, frames = next(pending)
            except StopIteration:
                exhausted = True
                break
            slot, created = _acquire_slot(free, created, depth)
            _prefetch_slot(slot, torch, device, copy_stream, batch_id, frames)
            window.append(slot)
        if not window:
            break
        # Oldest first. Its index download overlaps H2D prefetches already queued.
        slot = window.popleft()
        indices = _compute_slot(session, slot, torch, compute_stream)
        results.append((slot.batch_id, indices))
        free.append(slot)
    if cancel_exc is not None:
        raise cancel_exc
    return results


def _acquire_slot(free: list[_Slot], created: int, depth: int) -> tuple[_Slot, int]:
    if free:
        return free.pop(), created
    if created >= depth:
        raise RuntimeError("refusing to allocate past queue_depth")
    return _Slot(), created + 1


def _stack_frames(frames: Sequence[np.ndarray]) -> np.ndarray:
    return np.ascontiguousarray(np.stack(list(frames), axis=0))


def _reusable_pinned(torch: Any, existing: Any, array: np.ndarray) -> Any:
    needed = torch.from_numpy(np.empty((), dtype=array.dtype)).dtype
    shape = tuple(int(dim) for dim in array.shape)
    if existing is None or existing.dtype != needed or tuple(existing.shape) != shape or not existing.is_pinned():
        existing = torch.empty(shape, dtype=needed, pin_memory=True)
    existing.copy_(torch.from_numpy(array))
    return existing


def _prefetch_slot(
    slot: _Slot,
    torch: Any,
    device: Any,
    copy_stream: Any,
    batch_id: Any,
    frames: Sequence[np.ndarray],
) -> None:
    """Queue a pinned H2D of this batch without calling into the session yet."""
    slot.batch_id = batch_id
    stacked = _stack_frames(frames)
    slot.pinned_up = _reusable_pinned(torch, slot.pinned_up, stacked)
    with torch.cuda.stream(copy_stream):
        # Keep ``device_up`` alive until compute waits on ``h2d_event``.
        slot.device_up = slot.pinned_up.to(device, non_blocking=True)
        slot.h2d_event = copy_stream.record_event()
    host = slot.pinned_up.numpy()
    slot.frames = [host[index] for index in range(host.shape[0])]


def _compute_slot(session: Any, slot: _Slot, torch: Any, compute_stream: Any) -> np.ndarray:
    """Run the session on the compute stream, then stage indices in pinned memory.

    Waiting on this batch's copy event does not drain other prefetches. A
    device-wide synchronize would.
    """
    if slot.h2d_event is not None:
        compute_stream.wait_event(slot.h2d_event)
    frames = slot.frames if slot.frames is not None else []
    with torch.cuda.stream(compute_stream):
        scaled = session.scale_batch_uint8(frames)
        indices = session.index_batch_uint8(scaled)
    staged = np.ascontiguousarray(indices, dtype=np.uint8)
    slot.pinned_down = _reusable_pinned(torch, slot.pinned_down, staged)
    # Own the bytes. The slot reuses ``pinned_down`` for a later batch.
    out = slot.pinned_down.numpy().copy()
    slot.device_up = None
    slot.frames = None
    slot.h2d_event = None
    return out
