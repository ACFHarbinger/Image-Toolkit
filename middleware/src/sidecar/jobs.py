"""In-memory jobs capability for the W0-12 sidecar.

This is the bridge-level job registry used by the conformance suite. Feature
services replace the executor behind the same contract; they do not change the
wire semantics.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from middleware.src.bridge import BridgeAppError, CancelRegistry, Catalog, catalog, job_event

TERMINAL_JOB_STATES = frozenset({"completed", "failed", "cancelled", "capped"})


@dataclass
class JobRecord:
    job_id: str
    kind: str
    spec: dict[str, Any]
    state: str = "queued"
    progress: dict[str, int] | None = None
    error: dict[str, Any] | None = None

    def status(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "job_id": self.job_id,
            "kind": self.kind,
            "state": self.state,
        }
        if self.progress is not None:
            result["progress"] = dict(self.progress)
        if self.error is not None:
            result["error"] = dict(self.error)
        return result


class JobRegistry:
    """Contract-valid jobs routed through ``jobs.*`` methods."""

    def __init__(
        self,
        *,
        table: Catalog | None = None,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.table = table or catalog()
        self._event_sink = event_sink
        self._cancel = CancelRegistry()
        self._jobs: dict[str, JobRecord] = {}
        self._seq = 0
        self._mu = threading.Lock()

    def submit(self, params: dict[str, Any]) -> dict[str, Any]:
        self._validate_params("jobs.submit", params)
        job_id = uuid.uuid4().hex
        with self._mu:
            self._cancel.register(job_id)
            self._jobs[job_id] = JobRecord(
                job_id=job_id,
                kind=str(params["kind"]),
                spec=dict(params["spec"]),
            )
        self._emit(job_id, "queued")
        return {"job_id": job_id}

    def status(self, params: dict[str, Any]) -> dict[str, Any]:
        self._validate_params("jobs.status", params)
        job_id = str(params["job_id"])
        with self._mu:
            job = self._jobs.get(job_id)
            if job is None:
                raise self._not_found(job_id)
            return job.status()

    def list(self, params: dict[str, Any]) -> dict[str, Any]:
        self._validate_params("jobs.list", params)
        states = params.get("states")
        limit = params.get("limit")
        with self._mu:
            jobs = list(self._jobs.values())
        if states is not None:
            wanted = set(states)
            jobs = [job for job in jobs if job.state in wanted]
        if limit is not None:
            jobs = jobs[: int(limit)]
        return {"jobs": [job.status() for job in jobs]}

    def cancel(self, params: dict[str, Any]) -> dict[str, Any]:
        self._validate_params("jobs.cancel", params)
        job_id = str(params["job_id"])
        with self._mu:
            job = self._jobs.get(job_id)
            if job is None:
                raise self._not_found(job_id)
            result = self._cancel.cancel(job_id)
            if job.state not in TERMINAL_JOB_STATES:
                job.state = "cancelled"
                self._cancel.mark_terminal(job_id)
                terminal = True
            else:
                terminal = False
        if terminal:
            self._emit(job_id, "cancelled")
        return result

    def _emit(self, job_id: str, state: str) -> None:
        if self._event_sink is None:
            return
        with self._mu:
            self._seq += 1
            seq = self._seq
        self._event_sink(job_event(job_id, state, seq=seq, table=self.table))

    def _validate_params(self, method: str, params: dict[str, Any]) -> None:
        errors = self.table.validate_params(method, params)
        if errors:
            raise BridgeAppError(
                "bridge.invalid_params",
                retryable=True,
                details={"errors": [str(error) for error in errors]},
            )

    @staticmethod
    def _not_found(job_id: str) -> BridgeAppError:
        return BridgeAppError("jobs.not_found", details={"job_id": job_id})
