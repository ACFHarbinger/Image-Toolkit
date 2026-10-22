"""Reference ``jobs.*`` handlers: minimal in-memory job registry.

The spec is opaque at the bridge layer (contracts/jobs.json); the owning
service validates it in a later wave. Skeleton semantics: a submitted job
stays ``queued`` until cancelled — no executor runs yet. Cancel is the
bridge's idempotent cooperative cancel (#875): terminal jobs are a no-op,
unknown ids fail with ``jobs.not_found``.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from middleware.src.bridge.cancel import TERMINAL_JOB_STATES, CancelRegistry
from middleware.src.bridge.envelope import BridgeAppError


class JobRegistry:
    """In-memory jobs + cancel tokens; emits ``job_event`` via ``emit``."""

    def __init__(self, emit: Callable[[str, str], None], cancels: CancelRegistry | None = None) -> None:
        self._emit = emit  # (job_id, state) -> None; writes a jobs-channel event
        self._cancels = cancels or CancelRegistry()
        self._jobs: dict[str, dict[str, Any]] = {}

    def submit(self, params: dict[str, Any]) -> dict[str, Any]:
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        self._cancels.register(job_id)
        self._jobs[job_id] = {
            "job_id": job_id,
            "kind": params["kind"],
            "state": "queued",
            "spec": params["spec"],
        }
        self._emit(job_id, "queued")
        return {"job_id": job_id}

    def status(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._status(self._lookup(params["job_id"]))

    def list(self, params: dict[str, Any]) -> dict[str, Any]:
        states = set(params.get("states", []))
        limit = params.get("limit", 500)
        jobs = [
            self._status(job)
            for job in self._jobs.values()
            if not states or job["state"] in states
        ]
        return {"jobs": jobs[:limit]}

    def cancel(self, params: dict[str, Any]) -> dict[str, Any]:
        job_id = params["job_id"]
        self._lookup(job_id)  # unknown id -> jobs.not_found before any cancel state
        self._cancels.cancel(job_id)  # idempotent; terminal job is a no-op
        job = self._jobs[job_id]
        if job["state"] not in TERMINAL_JOB_STATES:
            job["state"] = "cancelled"
            self._cancels.mark_terminal(job_id)
            self._emit(job_id, "cancelled")
        return {"ok": True}

    def _lookup(self, job_id: str) -> dict[str, Any]:
        job = self._jobs.get(job_id)
        if job is None:
            raise BridgeAppError("jobs.not_found", details={"job_id": job_id})
        return job

    @staticmethod
    def _status(job: dict[str, Any]) -> dict[str, Any]:
        return {"job_id": job["job_id"], "kind": job["kind"], "state": job["state"]}
