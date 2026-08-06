"""Crash-contained execution boundary for native-heavy solver operations."""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import time
import traceback
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from threading import Event, Lock
from typing import Any, Protocol

import numpy as np

DEFAULT_DIAGNOSTIC_MAX_BYTES = 20 * 1024 * 1024
DEFAULT_DIAGNOSTIC_MAX_AGE_DAYS = 7


def default_diagnostics_path() -> Path:
    """Return the local XDG-compatible diagnostics path without creating it."""
    state_root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return state_root / "cel-shaded-generator" / "diagnostics.jsonl"


class Operation(StrEnum):
    """Stable operation identifiers shared by desktop and plugin hosts."""

    SCRIBBLE_COLORIZE = "scribble_colorize"
    REFERENCE_COLORIZE = "reference_colorize"
    TEMPORAL_COLORIZE = "temporal_colorize"
    ARAP_DEFORM = "arap_deform"
    HEALTH_CHECK = "health_check"
    _TEST_CRASH = "_test_crash"
    _TEST_HANG = "_test_hang"


@dataclass(slots=True)
class JobRequest:
    """Serializable, GUI-independent native job contract."""

    operation: Operation
    inputs: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)


class WorkerFailure(RuntimeError):
    """Base class for isolated-worker failures."""


class WorkerCrashed(WorkerFailure):
    """Raised when a native worker exits without returning a result."""


class JobTimedOut(WorkerFailure):
    """Raised after the adaptive, user-capped timeout expires."""


class JobCancelled(WorkerFailure):
    """Raised when the host requests cancellation."""


class _StoppableProcess(Protocol):
    def terminate(self) -> None: ...

    def kill(self) -> None: ...

    def join(self, timeout: float | None = None) -> None: ...

    def is_alive(self) -> bool: ...


def adaptive_timeout(request: JobRequest, maximum_seconds: float) -> float:
    """Estimate an operation timeout from input size, capped by user policy."""
    pixels = sum(
        int(value.size) for value in request.inputs.values() if isinstance(value, np.ndarray)
    )
    base = {
        Operation.SCRIBBLE_COLORIZE: 5.0,
        Operation.REFERENCE_COLORIZE: 8.0,
        Operation.TEMPORAL_COLORIZE: 15.0,
        Operation.ARAP_DEFORM: 5.0,
    }.get(request.operation, 2.0)
    return min(maximum_seconds, base + pixels / 250_000)


def _dispatch(request: JobRequest) -> Any:
    from cel_shaded_generator import (
        arap_deform,
        colorize_reference,
        colorize_scribble,
        colorize_scribble_sequence,
    )

    if request.operation == Operation.SCRIBBLE_COLORIZE:
        return colorize_scribble(**request.inputs, **request.options)
    if request.operation == Operation.REFERENCE_COLORIZE:
        return colorize_reference(**request.inputs, **request.options)
    if request.operation == Operation.TEMPORAL_COLORIZE:
        return colorize_scribble_sequence(**request.inputs, **request.options)
    if request.operation == Operation.ARAP_DEFORM:
        return arap_deform(**request.inputs, **request.options)
    if request.operation == Operation.HEALTH_CHECK:
        return "ok"
    if request.operation == Operation._TEST_CRASH:
        os._exit(86)
    if request.operation == Operation._TEST_HANG:
        time.sleep(60)
    raise ValueError(f"unsupported operation: {request.operation}")


def _worker(connection: Any, request: JobRequest) -> None:
    try:
        connection.send((True, _dispatch(request)))
    except BaseException as error:
        connection.send(
            (
                False,
                {
                    "type": type(error).__name__,
                    "message": str(error),
                    "traceback": traceback.format_exc(),
                },
            )
        )
    finally:
        connection.close()


def _persistent_worker(connection: Any) -> None:
    try:
        while True:
            request = connection.recv()
            if request is None:
                return
            try:
                connection.send((True, _dispatch(request)))
            except BaseException as error:
                connection.send(
                    (
                        False,
                        {
                            "type": type(error).__name__,
                            "message": str(error),
                            "traceback": traceback.format_exc(),
                        },
                    )
                )
    finally:
        connection.close()


def _dimensions(request: JobRequest) -> dict[str, list[int]]:
    return {
        name: list(value.shape)
        for name, value in request.inputs.items()
        if isinstance(value, np.ndarray)
    }


class IsolatedRunner:
    """Runs each native job in a fresh spawned process for crash containment."""

    def __init__(
        self,
        maximum_timeout_seconds: float = 300,
        diagnostics_path: str | Path | None = None,
        diagnostics_enabled: bool = True,
        diagnostic_max_bytes: int = DEFAULT_DIAGNOSTIC_MAX_BYTES,
        diagnostic_max_age_days: int = DEFAULT_DIAGNOSTIC_MAX_AGE_DAYS,
    ):
        if maximum_timeout_seconds <= 0:
            raise ValueError("maximum_timeout_seconds must be positive")
        self.maximum_timeout_seconds = maximum_timeout_seconds
        self.diagnostics_path = (
            (Path(diagnostics_path) if diagnostics_path else default_diagnostics_path())
            if diagnostics_enabled
            else None
        )
        self.diagnostic_max_bytes = diagnostic_max_bytes
        self.diagnostic_max_age_days = diagnostic_max_age_days
        self._context = mp.get_context("spawn")

    def _rotate_diagnostics(self) -> None:
        path = self.diagnostics_path
        if path is None or not path.exists():
            return
        too_large = path.stat().st_size >= self.diagnostic_max_bytes
        too_old = time.time() - path.stat().st_mtime >= self.diagnostic_max_age_days * 86400
        if too_large or too_old:
            os.replace(path, path.with_suffix(".jsonl.previous"))

    def _log(
        self, request: JobRequest, outcome: str, elapsed: float, detail: str | None = None
    ) -> None:
        if self.diagnostics_path is None:
            return
        self._rotate_diagnostics()
        record = {
            "operation": request.operation.value,
            "dimensions": _dimensions(request),
            "elapsed_ms": round(elapsed * 1000, 3),
            "outcome": outcome,
            "detail": detail,
        }
        self.diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
        with self.diagnostics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    @staticmethod
    def _stop(process: _StoppableProcess) -> None:
        """Terminate a worker, escalating to SIGKILL after a bounded grace period."""
        process.terminate()
        process.join(0.5)
        if process.is_alive():
            process.kill()
            process.join(0.5)

    def run(self, request: JobRequest, cancel: Event | None = None) -> Any:
        """Execute one request, terminating its process on cancel or timeout."""
        parent, child = self._context.Pipe(duplex=False)
        process = self._context.Process(target=_worker, args=(child, request), daemon=True)
        started = time.monotonic()
        process.start()
        child.close()
        timeout = adaptive_timeout(request, self.maximum_timeout_seconds)
        try:
            while process.is_alive():
                elapsed = time.monotonic() - started
                if cancel is not None and cancel.is_set():
                    self._stop(process)
                    self._log(request, "cancelled", elapsed)
                    raise JobCancelled(f"{request.operation.value} was cancelled")
                if elapsed >= timeout:
                    self._stop(process)
                    self._log(request, "timeout", elapsed)
                    raise JobTimedOut(f"{request.operation.value} exceeded {timeout:.2f}s")
                process.join(0.01)
            elapsed = time.monotonic() - started
            if parent.poll():
                try:
                    ok, payload = parent.recv()
                except EOFError:
                    self._log(request, "crashed", elapsed, f"exit code {process.exitcode}")
                    raise WorkerCrashed(
                        f"{request.operation.value} worker exited with code {process.exitcode}"
                    ) from None
                if ok:
                    self._log(request, "ok", elapsed)
                    return payload
                self._log(request, "error", elapsed, payload["traceback"])
                raise WorkerFailure(f"{payload['type']}: {payload['message']}")
            self._log(request, "crashed", elapsed, f"exit code {process.exitcode}")
            raise WorkerCrashed(
                f"{request.operation.value} worker exited with code {process.exitcode}"
            )
        finally:
            parent.close()


class PersistentIsolatedRunner(IsolatedRunner):
    """Reuse one isolated worker for latency-sensitive serial operations."""

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self._connection: Any | None = None
        self._process: Any | None = None
        self._run_lock = Lock()

    @property
    def worker_pid(self) -> int | None:
        """Return the current worker PID for diagnostics and lifecycle tests."""
        return self._process.pid if self._process is not None else None

    def _start(self) -> None:
        if self._process is not None and self._process.is_alive():
            return
        parent, child = self._context.Pipe(duplex=True)
        process = self._context.Process(target=_persistent_worker, args=(child,), daemon=True)
        process.start()
        child.close()
        self._connection = parent
        self._process = process

    def _discard(self, stop: bool = False) -> None:
        if stop and self._process is not None and self._process.is_alive():
            self._stop(self._process)
        if self._connection is not None:
            self._connection.close()
        self._connection = None
        self._process = None

    def run(self, request: JobRequest, cancel: Event | None = None) -> Any:
        """Run one serial request, restarting the persistent worker after failure."""
        with self._run_lock:
            self._start()
            connection, process = self._connection, self._process
            assert connection is not None and process is not None
            started = time.monotonic()
            connection.send(request)
            timeout = adaptive_timeout(request, self.maximum_timeout_seconds)
            while True:
                elapsed = time.monotonic() - started
                if connection.poll(0.01):
                    try:
                        ok, payload = connection.recv()
                    except EOFError:
                        self._discard()
                        self._log(request, "crashed", elapsed, f"exit code {process.exitcode}")
                        raise WorkerCrashed(
                            f"{request.operation.value} worker exited with code {process.exitcode}"
                        ) from None
                    if ok:
                        self._log(request, "ok", elapsed)
                        return payload
                    self._log(request, "error", elapsed, payload["traceback"])
                    raise WorkerFailure(f"{payload['type']}: {payload['message']}")
                if not process.is_alive():
                    self._discard()
                    self._log(request, "crashed", elapsed, f"exit code {process.exitcode}")
                    raise WorkerCrashed(
                        f"{request.operation.value} worker exited with code {process.exitcode}"
                    )
                if cancel is not None and cancel.is_set():
                    self._discard(stop=True)
                    self._log(request, "cancelled", elapsed)
                    raise JobCancelled(f"{request.operation.value} was cancelled")
                if elapsed >= timeout:
                    self._discard(stop=True)
                    self._log(request, "timeout", elapsed)
                    raise JobTimedOut(f"{request.operation.value} exceeded {timeout:.2f}s")

    def close(self) -> None:
        """Gracefully stop the persistent worker."""
        with self._run_lock:
            if self._connection is not None and self._process is not None:
                if self._process.is_alive():
                    self._connection.send(None)
                    self._process.join(0.5)
                self._discard(stop=True)

    def __enter__(self) -> PersistentIsolatedRunner:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
