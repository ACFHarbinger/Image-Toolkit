"""Multi-GPU frame scheduler for GIF resample (#1156, D11, D12, D13, D16).

Each allow-listed device with free VRAM gets its own session and batch size.
A free device pulls the next unstarted frames (work stealing). Results may
finish out of order; one writer thread emits the next frame index only.
The default lease is the process shared lease. An injected arbiter stays
the test and caller path. ``gpu_overlap.run_device_pipeline`` replaces the
per-batch scale+index calls when that module exists and the session has no
fused scale-and-index (lane B4). This module does not create it.
"""

from __future__ import annotations

import contextlib
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from middleware.src.core.gpu_lease_arbiter import GpuLeaseArbiter, cuda_device_table
from middleware.src.services.media.gif_upscale.base import AlgorithmError, ResampleCancelled
from middleware.src.services.media.gif_upscale.classical._resize import _LANCZOS_DERING
from middleware.src.services.media.gif_upscale.gpu_batch import acquire_gpu_session, resolve_gif_arbiter

_HOLD_BATCHES = 8
CpuFallback = Callable[[Sequence[Any], str], Any]


@dataclass
class _Job:
    start: int
    frames: list[Any]
    durations: list[int]
    retries: int
    device_index: int
    scale_s: float
    index_s: float


def _device_label(session: Any) -> str:
    name = getattr(session, "device_name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    return f"cuda:{int(session.device_index)}"


def _label_sort_key(label: str) -> tuple[int, str]:
    if label.startswith("cuda:"):
        tail = label.split(":", 1)[1]
        if tail.isdigit():
            return int(tail), label
    return 1_000_000, label


def _safe_close(session: Any) -> None:
    close = getattr(session, "close", None)
    if callable(close):
        with contextlib.suppress(Exception):
            close()


def _batch_size_of(session: Any) -> int:
    try:
        size = int(getattr(session, "batch_size", 1))
    except (TypeError, ValueError):
        return 1
    return max(1, size)


def _overlap_pipeline() -> Callable[..., Any] | None:
    """B4 seam. Missing module means call the session scale and index methods."""
    try:
        from middleware.src.services.media.gif_upscale.gpu_overlap import run_device_pipeline
    except ImportError:
        return None
    return run_device_pipeline


def _params_of(opts: dict[str, Any]) -> dict[str, Any]:
    params = opts.get("params")
    return params if isinstance(params, dict) else {}


def _pinned_index(params: dict[str, Any]) -> int | None | str:
    """Return a device index, ``'cpu'``, or None when the caller did not pin one."""
    requested = str(params.get("device") or "").strip().lower()
    if not requested:
        return None
    if requested == "cpu":
        return "cpu"
    tail = requested.split(":", 1)[1] if requested.startswith("cuda:") else requested
    if tail.isdigit():
        return int(tail)
    return None


def _allow_set(arbiter: GpuLeaseArbiter) -> set[int] | None:
    configured = arbiter.allow_indexes()
    if configured is None:
        return None
    if isinstance(configured, str):
        return set()
    return {int(index) for index in configured}


def _candidate_indexes(arbiter: GpuLeaseArbiter, opts: dict[str, Any]) -> list[int] | None:
    indexes = arbiter.device_indexes()
    if not indexes:
        return None
    allow = _allow_set(arbiter)
    chosen = list(indexes) if allow is None else [index for index in indexes if index in allow]
    raw = _params_of(opts).get("allow_devices")
    if isinstance(raw, (list, tuple)) and raw:
        try:
            wanted = {int(index) for index in raw}
        except (TypeError, ValueError):
            return []
        chosen = [index for index in chosen if index in wanted]
    return chosen


def _visible_device_table() -> tuple[dict[str, float | int], ...] | None:
    """Import torch the way ``acquire_gpu_session`` does, then read the device table.

    ``cuda_device_table`` stays empty until torch is already imported.
    """
    try:
        import torch
    except ImportError:
        return None
    cuda = getattr(torch, "cuda", None)
    if cuda is None or not bool(getattr(cuda, "is_available", lambda: False)()):
        return None
    table = cuda_device_table()
    return table or None


def _remember_standalone(opts: dict[str, Any], source: str) -> None:
    opts["_gpu_lease"] = source
    if source != "standalone":
        return
    note = "Shared GPU lease is unavailable; using a standalone lease"
    previous = opts.get("_gpu_fallback")
    opts["_gpu_fallback"] = f"{previous}; {note}" if isinstance(previous, str) and previous else note


def _arbiter_for(opts: dict[str, Any], arbiter: GpuLeaseArbiter | None) -> GpuLeaseArbiter | None:
    if isinstance(arbiter, GpuLeaseArbiter):
        opts.setdefault("_gpu_lease", "explicit")
        return arbiter
    params = _params_of(opts)
    named = params.get("gpu_arbiter")
    if isinstance(named, GpuLeaseArbiter):
        opts.setdefault("_gpu_lease", "explicit")
        return named
    table = _visible_device_table()
    if not table:
        return None
    allow = params.get("allow_devices")
    allow_tuple = tuple(int(index) for index in allow) if isinstance(allow, (list, tuple)) and allow else None
    resolved, source = resolve_gif_arbiter(table, allow_devices=allow_tuple)
    _remember_standalone(opts, source)
    return resolved


def _one_session(
    *,
    opts: dict[str, Any],
    arbiter: GpuLeaseArbiter | None,
    src_h: int,
    src_w: int,
    dst_h: int,
    dst_w: int,
    algorithm_id: str,
    owner: str | None,
) -> tuple[list[Any], str | None]:
    session, reason = acquire_gpu_session(
        src_h=src_h,
        src_w=src_w,
        dst_h=dst_h,
        dst_w=dst_w,
        opts=opts,
        algorithm_id=algorithm_id,
        arbiter=arbiter,
        owner=owner,
    )
    if session is None:
        return [], reason
    return [session], None


def _opts_for_device(opts: dict[str, Any], index: int) -> dict[str, Any]:
    # acquire_gpu_session reads params["device"] and passes it to try_acquire(device=).
    call_opts = dict(opts)
    call_opts["params"] = dict(_params_of(opts))
    call_opts["params"]["device"] = f"cuda:{index}"
    return call_opts


def _adopt_single(session: Any, opts: dict[str, Any]) -> None:
    opts["_device"] = _device_label(session)
    scale_path = getattr(session, "scale_path", None)
    if isinstance(scale_path, str) and scale_path:
        opts["_scale_path"] = scale_path
    if hasattr(session, "opts"):
        session.opts = opts
    update = getattr(session, "_update_opts_metadata", None)
    if callable(update):
        update()


def _remember_skips(opts: dict[str, Any], refusals: list[str]) -> None:
    if not refusals:
        return
    note = "; ".join(refusals)
    previous = opts.get("_gpu_fallback")
    opts["_gpu_fallback"] = f"{previous}; {note}" if isinstance(previous, str) and previous else note


def _lease_each(
    *,
    opts: dict[str, Any],
    arbiter: GpuLeaseArbiter,
    indexes: list[int],
    src_h: int,
    src_w: int,
    dst_h: int,
    dst_w: int,
    algorithm_id: str,
    owner: str | None,
) -> tuple[list[Any], str | None]:
    base = owner or f"gif_upscale_{uuid.uuid4().hex[:8]}"
    sessions: list[Any] = []
    refusals: list[str] = []
    try:
        for index in indexes:
            session, reason = acquire_gpu_session(
                src_h=src_h,
                src_w=src_w,
                dst_h=dst_h,
                dst_w=dst_w,
                opts=_opts_for_device(opts, index),
                algorithm_id=algorithm_id,
                arbiter=arbiter,
                owner=f"{base}_d{index}",
            )
            if session is None:
                refusals.append(reason or f"cuda:{index} refused")
                continue
            sessions.append(session)
    except Exception:
        for session in sessions:
            _safe_close(session)
        raise
    if not sessions:
        reason = refusals[0] if len(refusals) == 1 else "; ".join(refusals)
        opts["_device"] = "cpu"
        if reason:
            opts["_gpu_fallback"] = reason
        return [], reason
    if len(sessions) == 1:
        _adopt_single(sessions[0], opts)
    _remember_skips(opts, refusals)
    return sessions, None


def acquire_gpu_sessions(
    *,
    src_h: int,
    src_w: int,
    dst_h: int,
    dst_w: int,
    opts: dict[str, Any],
    algorithm_id: str = _LANCZOS_DERING,
    arbiter: GpuLeaseArbiter | None = None,
    owner: str | None = None,
) -> tuple[list[Any], str | None]:
    """Lease every allow-listed device that accepts a session.

    One device matches ``acquire_gpu_session`` (same opts object and lease).
    Two or more devices each get ``device=`` so the arbiter does not hand out
    the same card twice. A refusal is skipped and recorded on ``opts``. No
    session means the existing CPU fallback reason.
    """
    if algorithm_id != _LANCZOS_DERING:
        return [], None
    params = _params_of(opts)
    pinned = _pinned_index(params)
    if pinned == "cpu":
        opts["_device"] = "cpu"
        return [], None
    active = _arbiter_for(opts, arbiter)
    lease = {
        "opts": opts,
        "arbiter": active,
        "src_h": src_h,
        "src_w": src_w,
        "dst_h": dst_h,
        "dst_w": dst_w,
        "algorithm_id": algorithm_id,
        "owner": owner,
    }
    if isinstance(pinned, int):
        if not isinstance(active, GpuLeaseArbiter):
            return _one_session(**lease)
        return _lease_each(indexes=[pinned], **lease)
    if not isinstance(active, GpuLeaseArbiter):
        return _one_session(**lease)
    indexes = _candidate_indexes(active, opts)
    if not indexes or len(indexes) == 1:
        return _one_session(**lease)
    return _lease_each(indexes=indexes, **lease)


def _call_progress(progress: Any, stage: str, done: int, total: int) -> None:
    if progress is None:
        return
    progress(stage, int(done), int(total))


class _FrameScheduler:
    """Pull-based batches plus one ordered writer. Not a process pool."""

    def __init__(
        self,
        sessions: Sequence[Any],
        frames: Any,
        durations: Sequence[int] | None,
        writer: Any,
        *,
        total: int | None,
        op: str,
        palette: np.ndarray | None,
        transparent: bool,
        dither: str,
        quality: str,
        progress: Any,
        progress_stage: str,
        timings: dict[str, float] | None,
        opts: dict[str, Any] | None,
        cpu_fallback: CpuFallback | None,
        hold_batches: int,
        close_sessions: bool,
    ) -> None:
        self._all_sessions = list(sessions)
        self._sessions = list(sessions)
        self._frames = frames
        self._durations = durations
        self._writer = writer
        self._op = op
        self._palette = palette
        self._transparent = transparent
        self._dither = dither
        self._quality = quality
        self._progress = progress
        self._stage = progress_stage
        self._timings = timings
        self._opts = opts
        self._cpu_fallback = cpu_fallback
        self._hold_limit = max(1, int(hold_batches))
        self._close_sessions = close_sessions
        self._random = _is_random_access(frames, durations)
        self._total = _job_total(frames, durations, total, self._random)
        self._lock = threading.RLock()
        self._cv = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._claimed = 0
        self._written = 0
        self._hold = 0
        self._pulling = False
        self._retry: deque[_Job] = deque()
        self._pending: dict[int, tuple[_Job, Any]] = {}
        self._decoded: deque[tuple[Any, int]] = deque()
        self._decode_done = self._random
        self._decode_limit = self._hold_limit * max((_batch_size_of(session) for session in sessions), default=1)
        self._producers_done = False
        self._error: BaseException | None = None
        self._batch_devices: list[tuple[int, int]] = []
        self._cpu_notes: list[str] = []
        self._labels = {int(session.device_index): _device_label(session) for session in sessions}
        self._alive: dict[int, Any] = {id(session): session for session in sessions}
        self._scaled: list[Any] = [None] * self._total
        self._threads: list[threading.Thread] = []
        self._writer_thread: threading.Thread | None = None

    def run(self) -> dict[str, Any]:
        try:
            self._prepare_palette()
            self._start_writer()
            if self._sessions:
                self._start_workers()
            self._join_workers()
            if self._error is None and not self._stop.is_set():
                self._drain_cpu()
            self._mark_producers_done()
            self._join_writer()
            if self._error is not None:
                raise self._error
            return self._result()
        finally:
            self._cleanup()

    def _prepare_palette(self) -> None:
        if self._palette is None:
            return
        kept: list[Any] = []
        for session in self._sessions:
            try:
                session.prepare_palette(
                    self._palette,
                    transparent=self._transparent,
                    dither=self._dither,
                    quality=self._quality,
                )
            except ResampleCancelled:
                raise
            except Exception as exc:
                _safe_close(session)
                self._alive.pop(id(session), None)
                self._cpu_notes.append(f"{_device_label(session)} palette init failed ({exc}); skipped")
                continue
            kept.append(session)
        self._sessions = kept

    def _start_writer(self) -> None:
        if self._total == 0:
            return
        self._writer_thread = threading.Thread(target=self._writer_thread_main, name="gif-gpu-writer")
        self._writer_thread.start()

    def _start_workers(self) -> None:
        if not self._random and self._total > 0:
            decoder = threading.Thread(target=self._decode_loop, name="gif-gpu-decode")
            decoder.start()
            self._threads.append(decoder)
        for session in self._sessions:
            worker = threading.Thread(
                target=self._worker_thread_main,
                args=(session,),
                name=f"gif-gpu-{_device_label(session)}",
            )
            worker.start()
            self._threads.append(worker)

    def _writer_thread_main(self) -> None:
        try:
            self._writer_loop()
        except Exception as exc:
            self._store_error(exc)

    def _worker_thread_main(self, session: Any) -> None:
        try:
            self._worker_loop(session)
        except Exception as exc:
            self._store_error(exc)

    def _writer_loop(self) -> None:
        while self._written < self._total:
            job, payload = self._pop_next()
            if job is None:
                return
            self._emit(job, payload)
            with self._lock:
                self._written += len(job.durations)
                self._cv.notify_all()

    def _pop_next(self) -> tuple[_Job | None, Any]:
        with self._lock:
            while self._written not in self._pending and not self._stop.is_set() and not self._producers_done:
                self._cv.wait()
            if self._written not in self._pending:
                if not self._stop.is_set() and self._written < self._total:
                    self._store_error(AlgorithmError("GPU schedule ended before every frame was written."))
                return None, None
            job, payload = self._pending.pop(self._written)
            self._hold -= 1
            self._add_time_locked("scale", job.scale_s)
            self._add_time_locked("index", job.index_s)
            self._cv.notify_all()
            return job, payload

    def _emit(self, job: _Job, payload: Any) -> None:
        count = len(job.durations)
        for offset in range(count):
            _call_progress(self._progress, self._stage, job.start + offset + 1, self._total)
            item = payload[offset]
            if self._op == "scale":
                self._scaled[job.start + offset] = item
                continue
            started = time.perf_counter()
            self._writer.add_frame(item, job.durations[offset])
            self._add_time("lzw", time.perf_counter() - started)

    def _worker_loop(self, session: Any) -> None:
        while not self._stop.is_set():
            job = self._pull(_batch_size_of(session))
            if job is None:
                return
            try:
                payload, scale_s, index_s = self._execute(session, job.frames)
            except ResampleCancelled:
                raise
            except Exception as exc:
                self._fail_device(session, job, exc)
                return
            job.device_index = int(session.device_index)
            job.scale_s += scale_s
            job.index_s += index_s
            self._submit(job, payload)

    def _fail_device(self, session: Any, job: _Job, exc: Exception) -> None:
        others = self._retire(session)
        label = _device_label(session)
        if job.retries < 1 and others:
            job.retries += 1
            self._note(f"{label} failed ({exc}); batch retried on another device")
            with self._lock:
                self._retry.appendleft(job)
                self._cv.notify_all()
            return
        self._note(f"{label} failed ({exc}); batch retried on CPU")
        self._cpu_job(job)
        if not others:
            self._drain_cpu()

    def _retire(self, session: Any) -> list[Any]:
        _safe_close(session)
        with self._lock:
            self._alive.pop(id(session), None)
            return list(self._alive.values())

    def _cpu_job(self, job: _Job) -> None:
        if self._cpu_fallback is None:
            raise AlgorithmError(f"GPU batch at frame {job.start} failed and no CPU path is available.")
        started = time.perf_counter()
        payload = self._cpu_fallback(job.frames, self._op)
        elapsed = time.perf_counter() - started
        if self._op == "index":
            job.index_s += elapsed
        else:
            job.scale_s += elapsed
        job.device_index = -1
        self._submit(job, payload)

    def _drain_cpu(self) -> None:
        if self._cpu_fallback is None or self._stop.is_set():
            return
        while not self._stop.is_set():
            job = self._pull(1)
            if job is None:
                return
            self._note(f"frames {job.start} retried on CPU")
            self._cpu_job(job)

    def _execute(self, session: Any, frames: Sequence[Any]) -> tuple[Any, float, float]:
        if self._op == "scale":
            started = time.perf_counter()
            return session.scale_batch_uint8(frames), time.perf_counter() - started, 0.0
        if self._op == "index":
            started = time.perf_counter()
            return session.index_batch_uint8(frames), 0.0, time.perf_counter() - started
        # Keep scaled pixels on-device; the legacy overlap adapter round-trips RGBA.
        fused = getattr(session, "scale_and_index_batch", None)
        if callable(fused):
            return fused(frames)
        runner = _overlap_pipeline()
        if runner is not None:
            # B4 takes (batch_id, frames) pairs and returns (batch_id, indices).
            # One scheduler batch is one overlapped unit. Time is not split.
            started = time.perf_counter()
            results = runner(session, [(0, frames)])
            elapsed = time.perf_counter() - started
            if len(results) != 1:
                raise AlgorithmError("GPU overlap returned an unexpected batch count.")
            _batch_id, indices = results[0]
            return indices, elapsed, 0.0
        started = time.perf_counter()
        scaled = session.scale_batch_uint8(frames)
        scale_s = time.perf_counter() - started
        started = time.perf_counter()
        indexed = session.index_batch_uint8(scaled)
        return indexed, scale_s, time.perf_counter() - started

    def _pull(self, batch_size: int) -> _Job | None:
        with self._lock:
            while True:
                if self._stop.is_set():
                    return None
                if self._pulling:
                    self._cv.wait()
                    continue
                if self._retry:
                    return self._retry.popleft()
                if self._claimed >= self._total:
                    return None
                if self._hold_blocks_new_work():
                    self._cv.wait()
                    continue
                self._pulling = True
                try:
                    return self._take_batch(batch_size)
                finally:
                    self._pulling = False
                    self._cv.notify_all()

    def _hold_blocks_new_work(self) -> bool:
        # New frames wait when the out-of-order hold is full, unless this pull is
        # the frame the writer is blocked on (nothing in flight ahead of it).
        # Retries are taken above, before this check.
        return self._hold >= self._hold_limit and self._claimed != self._written

    def _take_batch(self, batch_size: int) -> _Job | None:
        want = min(max(1, batch_size), self._total - self._claimed)
        if self._random:
            return self._take_random(want)
        return self._take_decoded(want)

    def _take_random(self, want: int) -> _Job:
        start = self._claimed
        assert self._durations is not None
        taken = list(self._frames[start : start + want])
        durations = [int(value) for value in self._durations[start : start + want]]
        self._claimed += len(taken)
        return _Job(start, taken, durations, 0, -1, 0.0, 0.0)

    def _take_decoded(self, want: int) -> _Job | None:
        frames: list[Any] = []
        durations: list[int] = []
        while len(frames) < want and not self._stop.is_set():
            if not self._wait_decoded():
                break
            frame, duration = self._decoded.popleft()
            frames.append(frame)
            durations.append(duration)
            self._cv.notify_all()
        if not frames:
            return None
        start = self._claimed
        self._claimed += len(frames)
        return _Job(start, frames, durations, 0, -1, 0.0, 0.0)

    def _wait_decoded(self) -> bool:
        while not self._decoded and not self._decode_done and not self._stop.is_set():
            self._cv.wait()
        return bool(self._decoded) and not self._stop.is_set()

    def _submit(self, job: _Job, payload: Any) -> None:
        with self._lock:
            if self._stop.is_set():
                return
            # Finished work always lands. New pulls block once ``_hold`` is full,
            # so a slow card cannot add batches, and the writer cannot deadlock
            # behind a submit that is waiting for the frame only a retry can produce.
            self._pending[job.start] = (job, payload)
            self._hold += 1
            self._batch_devices.append((job.start, job.device_index))
            self._cv.notify_all()

    def _decode_loop(self) -> None:
        source = iter(self._frames)
        produced = 0
        try:
            while produced < self._total and not self._stop.is_set():
                started = time.perf_counter()
                item = next(source)
                elapsed = time.perf_counter() - started
                frame, duration = item[0], int(item[1])
                with self._lock:
                    self._add_time_locked("decode", elapsed)
                    while len(self._decoded) >= self._decode_limit and not self._stop.is_set():
                        self._cv.wait()
                    if self._stop.is_set():
                        return
                    self._decoded.append((frame, duration))
                    self._cv.notify_all()
                produced += 1
        except StopIteration:
            pass
        except Exception as exc:
            self._store_error(exc)
            return
        with self._lock:
            self._decode_done = True
            self._cv.notify_all()

    def _mark_producers_done(self) -> None:
        with self._lock:
            self._producers_done = True
            self._cv.notify_all()

    def _join_workers(self) -> None:
        for thread in self._threads:
            thread.join()

    def _join_writer(self) -> None:
        if self._writer_thread is not None:
            self._writer_thread.join()

    def _cleanup(self) -> None:
        self._stop.set()
        with self._lock:
            self._cv.notify_all()
        self._join_workers()
        self._join_writer()
        if self._close_sessions:
            for session in self._all_sessions:
                _safe_close(session)

    def _note(self, text: str) -> None:
        with self._lock:
            self._cpu_notes.append(text)

    def _store_error(self, exc: BaseException) -> None:
        with self._lock:
            if self._error is None:
                self._error = exc
            self._stop.set()
            self._cv.notify_all()

    def _add_time(self, stage: str, seconds: float) -> None:
        if self._timings is None or seconds == 0.0:
            return
        with self._lock:
            self._add_time_locked(stage, seconds)

    def _add_time_locked(self, stage: str, seconds: float) -> None:
        if self._timings is None or seconds == 0.0:
            return
        self._timings[stage] = self._timings.get(stage, 0.0) + seconds

    def _result(self) -> dict[str, Any]:
        labels = {
            "cpu" if index < 0 else self._labels.get(index, f"cuda:{index}")
            for _start, index in self._batch_devices
        }
        devices = tuple(sorted(labels, key=_label_sort_key))
        self._publish_path(devices)
        frames = None
        if self._op == "scale":
            if any(frame is None for frame in self._scaled):
                raise AlgorithmError("GPU schedule left a gap in scaled frames.")
            frames = self._scaled
        return {
            "frames": frames,
            "batch_devices": tuple(sorted(self._batch_devices)),
            "devices": devices,
        }

    def _publish_path(self, devices: tuple[str, ...]) -> None:
        if self._opts is None:
            return
        gpu_labels = {label for label in devices if label != "cpu"}
        existing = self._opts.get("_scale_path")
        if isinstance(existing, str) and existing.startswith("gpu-schedule "):
            prior = existing.removeprefix("gpu-schedule ").split(",")
            gpu_labels.update(part for part in prior if part and part != "cpu")
        if gpu_labels:
            joined = ",".join(sorted(gpu_labels, key=_label_sort_key))
            self._opts["_device"] = joined
            self._opts["_scale_path"] = f"gpu-schedule {joined}"
        notes = "; ".join(self._cpu_notes)
        if not notes:
            return
        previous = self._opts.get("_gpu_fallback")
        self._opts["_gpu_fallback"] = f"{previous}; {notes}" if isinstance(previous, str) and previous else notes


def _is_random_access(frames: Any, durations: Sequence[int] | None) -> bool:
    return isinstance(frames, Sequence) and not isinstance(frames, (str, bytes)) and durations is not None


def _job_total(frames: Any, durations: Sequence[int] | None, total: int | None, random_access: bool) -> int:
    if random_access:
        assert durations is not None
        if len(durations) != len(frames):
            raise AlgorithmError("GPU schedule durations do not match the frame count.")
        return len(frames)
    if total is None:
        raise AlgorithmError("GPU schedule needs a frame total for a streaming source.")
    return int(total)


def schedule_gif_frames(
    sessions: Sequence[Any],
    frames: Any,
    durations: Sequence[int] | None,
    writer: Any = None,
    *,
    total: int | None = None,
    op: str = "scale_index",
    palette: np.ndarray | None = None,
    transparent: bool = True,
    dither: str = "ordered",
    quality: str = "balanced",
    progress: Any = None,
    progress_stage: str = "scale_encode",
    timings: dict[str, float] | None = None,
    opts: dict[str, Any] | None = None,
    cpu_fallback: CpuFallback | None = None,
    hold_batches: int = _HOLD_BATCHES,
    close_sessions: bool = True,
) -> dict[str, Any]:
    """Run ``frames`` on whichever session is free and write indexes in order.

    ``op`` is ``scale`` (ordered uint8 frames, no writer), ``index`` (palette
    indexes for frames that are already scaled), or ``scale_index``. A shared
    ``palette`` is uploaded with ``prepare_palette`` on every session that
    accepts it. Sessions close before return unless ``close_sessions`` is false.
    """
    if op not in {"scale", "index", "scale_index"}:
        raise AlgorithmError(f"Unknown GPU schedule op {op!r}.")
    if op != "scale" and writer is None:
        raise AlgorithmError("GPU schedule needs a writer.")
    scheduler = _FrameScheduler(
        sessions,
        frames,
        durations,
        writer,
        total=total,
        op=op,
        palette=palette,
        transparent=transparent,
        dither=dither,
        quality=quality,
        progress=progress,
        progress_stage=progress_stage,
        timings=timings,
        opts=opts,
        cpu_fallback=cpu_fallback,
        hold_batches=hold_batches,
        close_sessions=close_sessions,
    )
    return scheduler.run()


__all__ = ["acquire_gpu_sessions", "schedule_gif_frames"]
