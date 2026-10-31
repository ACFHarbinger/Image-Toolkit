"""Process pool that LZW-compresses GIF frames outside the parent's GIL.

Pillow's GIF encoder holds the GIL, so extra threads do not speed it up. The
parent process stays the only writer and emits frames in sequence order.
"""

from __future__ import annotations

import multiprocessing
import os
from collections.abc import Callable
from typing import Any

import numpy as np

# Set in worker processes only. A worker must not start another encode pool.
_IN_ENCODE_WORKER = False


def _limit_worker_threads() -> None:
    """Cap native thread pools inside one encode process."""
    global _IN_ENCODE_WORKER
    _IN_ENCODE_WORKER = True
    # The child inherits the parent's environment, then overrides these.
    # Assignments here do not change the parent process.
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["OPENCV_NUM_THREADS"] = "1"


def encode_indexed_frame(index: np.ndarray, use_pillow_lzw: bool) -> bytes:
    """Picklable pool entry. Same LZW sub-blocks as the in-process encoder."""
    from middleware.src.services.media.gif_upscale.encode import _encode_lzw_subblocks

    return _encode_lzw_subblocks(index, use_pillow=bool(use_pillow_lzw))


class FrameEncodePool:
    """Compress frames in ``workers`` processes. Completed blocks stay ordered.

    At most ``workers`` frames are running or waiting out of order. The caller
    writes a frame only when it is the next sequence number, so a later result
    cannot pass a failed one.
    """

    def __init__(self, workers: int) -> None:
        if _IN_ENCODE_WORKER:
            raise RuntimeError("GIF encode worker cannot start another process pool")
        if workers < 2:
            raise ValueError(f"FrameEncodePool requires workers >= 2, got {workers}.")
        self._workers = int(workers)
        self._next_submit = 0
        self._next_write = 0
        self._pending: dict[int, Any] = {}
        self._ready: dict[int, bytes] = {}
        self._failed: dict[int, BaseException] = {}
        self._durations: dict[int, int] = {}
        self._mp = None
        # spawn: the parent may already own a CUDA context. fork would copy it.
        ctx = multiprocessing.get_context("spawn")
        self._mp = ctx.Pool(processes=self._workers, initializer=_limit_worker_threads)

    def push(
        self,
        index: np.ndarray,
        use_pillow_lzw: bool,
        duration_ms: int,
        emit: Callable[[bytes, int], None],
    ) -> None:
        """Encode one frame. ``emit`` runs on this process, in frame order."""
        self._wait_for_capacity(emit)
        # Copy before the worker runs. Callers reuse the index buffer.
        array = np.array(index, dtype=np.uint8, copy=True, order="C")
        seq = self._next_submit
        self._next_submit += 1
        self._durations[seq] = duration_ms
        pool = self._mp
        if pool is None:
            raise RuntimeError("GIF encode pool is closed.")
        self._pending[seq] = pool.apply_async(encode_indexed_frame, (array, bool(use_pillow_lzw)))
        self._harvest(block=False)
        self._emit(emit)

    def finish(self, emit: Callable[[bytes, int], None]) -> None:
        """Write every submitted frame in order, then join the workers."""
        try:
            while self._pending or self._next_write in self._ready or self._next_write in self._failed:
                self._harvest(block=bool(self._pending))
                self._emit(emit)
            self._shutdown(terminate=False)
        except BaseException:
            self._shutdown(terminate=True)
            raise

    def abort(self) -> None:
        """Drop leftover jobs. Used when a frame already failed or close is early."""
        self._shutdown(terminate=True)

    def _occupied(self) -> int:
        return len(self._pending) + len(self._ready) + len(self._failed)

    def _wait_for_capacity(self, emit: Callable[[bytes, int], None]) -> None:
        # Cap equals the pool size: do not queue an unbounded backlog.
        while self._occupied() >= self._workers:
            if not self._pending:
                self._emit(emit)
                if self._occupied() >= self._workers:
                    raise RuntimeError("GIF encode buffer is full and no frame is running")
                continue
            self._harvest(block=True)
            self._emit(emit)

    def _harvest(self, *, block: bool) -> None:
        if block and self._pending:
            self._resolve(min(self._pending))
        finished = [seq for seq, result in self._pending.items() if result.ready()]
        for seq in finished:
            self._resolve(seq)

    def _resolve(self, seq: int) -> None:
        result = self._pending.pop(seq)
        try:
            self._ready[seq] = result.get()
        except Exception as exc:
            self._failed[seq] = exc
        except BaseException as exc:
            self._failed[seq] = exc
            raise

    def _emit(self, emit: Callable[[bytes, int], None]) -> None:
        while True:
            seq = self._next_write
            failed = self._failed.get(seq)
            if failed is not None:
                raise failed
            payload = self._ready.pop(seq, None)
            if payload is None:
                return
            duration = self._durations.pop(seq)
            self._next_write = seq + 1
            emit(payload, duration)

    def _shutdown(self, *, terminate: bool) -> None:
        pool = self._mp
        if pool is None:
            return
        self._mp = None
        if terminate:
            pool.terminate()
        else:
            pool.close()
        pool.join()
