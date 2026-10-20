"""Idempotent cooperative cancel with escalation (W0-11, #875).

One ``jobs.cancel`` for the whole bridge (roadmap Cancel): safe to retry,
safe to call on a terminal job. The bridge layer owns the semantics — a
registry of per-job tokens, cooperative checks inside the running work
and an escalation hook the owning service supplies. Cancelling an unknown
job fails with the contract's ``jobs.not_found``.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from .envelope import BridgeAppError

# Terminal states per contracts/schemas/capability/jobs.json $defs/JobState.
TERMINAL_JOB_STATES = frozenset({"completed", "failed", "cancelled", "capped"})


class Cancelled(Exception):
    """Raised inside service work at a cooperative checkpoint."""


class CancelToken:
    """Cooperative cancellation for one job.

    The service checks ``raise_if_cancelled()`` (or ``cancelled``) at
    checkpoints; ``on_escalate`` runs once if the grace period elapses
    after cancel was requested — the owning service decides what
    escalation means (drop the job, SIGKILL the worker, ...).
    """

    def __init__(self, job_id: str, grace_seconds: float = 5.0) -> None:
        self.job_id = job_id
        self.grace_seconds = grace_seconds
        self._cancelled = False
        self._escalated = False
        self._cancelled_at: float | None = None
        self.on_escalate: Callable[[CancelToken], None] | None = None

    @property
    def cancelled(self) -> bool:
        if self._cancelled and not self._escalated:
            self._check_escalation()
        return self._cancelled

    def cancel(self) -> None:
        """Request cancellation; idempotent."""
        if self._cancelled:
            return
        self._cancelled = True
        self._cancelled_at = time.monotonic()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise Cancelled(self.job_id)

    def _check_escalation(self) -> None:
        if self._escalated or self._cancelled_at is None:
            return
        if time.monotonic() - self._cancelled_at >= self.grace_seconds:
            self._escalated = True
            if self.on_escalate is not None:
                self.on_escalate(self)


class CancelRegistry:
    """Per-job tokens with the bridge's cancel semantics.

    Jobs stay registered after reaching a terminal state so a repeat
    cancel on a finished job is a successful no-op (idempotent), while an
    unknown id fails with ``jobs.not_found`` per methods.toml.
    """

    def __init__(self, grace_seconds: float = 5.0) -> None:
        self.grace_seconds = grace_seconds
        self._tokens: dict[str, CancelToken] = {}
        self._terminal: set[str] = set()

    def register(self, job_id: str) -> CancelToken:
        token = CancelToken(job_id, grace_seconds=self.grace_seconds)
        self._tokens[job_id] = token
        self._terminal.discard(job_id)
        return token

    def mark_terminal(self, job_id: str) -> None:
        if job_id not in self._tokens:
            raise BridgeAppError("jobs.not_found", details={"job_id": job_id})
        self._terminal.add(job_id)

    def token(self, job_id: str) -> CancelToken:
        token = self._tokens.get(job_id)
        if token is None:
            raise BridgeAppError("jobs.not_found", details={"job_id": job_id})
        return token

    def cancel(self, job_id: str) -> dict[str, Any]:
        """Idempotent ``jobs.cancel``: returns ``{"ok": true}`` or raises."""
        token = self._tokens.get(job_id)
        if token is None:
            raise BridgeAppError("jobs.not_found", details={"job_id": job_id})
        if job_id in self._terminal:
            return {"ok": True}
        token.cancel()
        return {"ok": True}
