"""Cancellable optimization-job contract shared by exact and metaheuristic solvers.

Every long-running solver call (seam routing, GNC alignment, color
harmonization, PSO, DE...) is wrapped as a `Job` so the GUI/pipeline layer can
report progress, inspect intermediate proposals, and cancel without killing
the whole worker thread. This mirrors the product decision recorded in
`.agent/cache/chat/hie_product_decisions_20260812.md`: optimization/ML
assistance must be explicit and inspectable, never an opaque background
mutation.

Cancellation is always *cooperative* — there is no way to forcibly kill a C++
call already in flight, so solver bodies must poll `CancelToken` between
iterations (see `exact_dp.py` / `metaheuristics.py` for the pattern).
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class JobProgress:
    """A single progress sample emitted by a running job."""

    fraction: float  # 0.0-1.0, expected monotonic non-decreasing
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


class JobCancelled(Exception):  # noqa: N818 - deliberately not an "Error": expected control flow
    """Raised inside a job body (via ``CancelToken.raise_if_cancelled()``) to unwind cleanly."""


class CancelToken:
    """Cooperative cancellation flag passed into every job body."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self._event.is_set():
            raise JobCancelled()


@dataclass
class JobResult(Generic[T]):
    """Terminal outcome of a job — a success value XOR an error, never both."""

    status: JobStatus
    value: T | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status is JobStatus.SUCCEEDED


ReportFn = Callable[[JobProgress], None]
JobBody = Callable[[CancelToken, ReportFn], T]


class JobHandle(Generic[T]):
    """Handle to a job running on a background thread.

    Usage::

        handle = submit_job(lambda token, report: run_pso(token, report, ...))
        result = handle.result(timeout=30)
        if result.ok:
            ...
    """

    def __init__(self, job_id: str, body: JobBody[T]) -> None:
        self.job_id = job_id
        self._token = CancelToken()
        self._progress_lock = threading.Lock()
        self._progress: list[JobProgress] = []
        self._result: JobResult[T] | None = None
        self._done_event = threading.Event()
        self._status = JobStatus.PENDING
        self._thread = threading.Thread(target=self._run, args=(body,), daemon=True)

    def start(self) -> JobHandle[T]:
        self._status = JobStatus.RUNNING
        self._thread.start()
        return self

    def _report(self, progress: JobProgress) -> None:
        with self._progress_lock:
            self._progress.append(progress)

    def _run(self, body: JobBody[T]) -> None:
        try:
            value = body(self._token, self._report)
            result = (
                JobResult(JobStatus.CANCELLED)
                if self._token.cancelled
                else JobResult(JobStatus.SUCCEEDED, value=value)
            )
        except JobCancelled:
            result = JobResult(JobStatus.CANCELLED)
        except Exception as exc:  # noqa: BLE001 - convert to an inspectable result, never crash the worker thread
            result = JobResult(JobStatus.FAILED, error=str(exc))
        self._result = result
        self._status = result.status
        self._done_event.set()

    def cancel(self) -> None:
        """Request cancellation. Cooperative — has no effect until the body next polls the token."""
        self._token.cancel()

    @property
    def status(self) -> JobStatus:
        return self._status

    @property
    def done(self) -> bool:
        return self._done_event.is_set()

    def latest_progress(self) -> JobProgress | None:
        with self._progress_lock:
            return self._progress[-1] if self._progress else None

    def drain_progress(self) -> list[JobProgress]:
        """Return and clear all progress samples recorded since the last drain."""
        with self._progress_lock:
            drained, self._progress = self._progress, []
        return drained

    def result(self, timeout: float | None = None) -> JobResult[T]:
        """Block until the job reaches a terminal state and return its result."""
        if not self._done_event.wait(timeout):
            raise TimeoutError(f"job {self.job_id} did not complete within {timeout}s")
        assert self._result is not None  # noqa: S101 - guaranteed set before _done_event fires
        return self._result


def submit_job(body: JobBody[T], *, job_id: str | None = None) -> JobHandle[T]:
    """Start `body` on a background thread and return a handle immediately."""
    handle: JobHandle[T] = JobHandle(job_id or str(uuid.uuid4()), body)
    return handle.start()
