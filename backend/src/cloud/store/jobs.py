"""Jobs, attempts, shards and the append-only event log (#827)."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from ..adapter import ResourceRef, resource_from_dict, resource_to_dict
from ..spec import JobSpec
from ..state import (
    TERMINAL,
    AttemptView,
    CancelRequest,
    JobState,
    JobView,
    Outcome,
    ShardView,
    check_transition,
)
from .db import transaction


class UnknownJob(KeyError):
    pass


@dataclass(frozen=True)
class AttemptRow:
    attempt_id: str
    job_id: str
    attempt_no: int
    provider: str
    region: str
    mode: str
    idempotency_key: str
    shards: Tuple[int, ...]
    submitted: bool
    submit_unknown: bool
    resources: Tuple[ResourceRef, ...]
    teardown_done: bool
    cost_usd: float
    started_at: float
    ended_at: Optional[float]

    def view(self) -> AttemptView:
        return AttemptView(self.attempt_id, self.attempt_no, self.provider, self.started_at,
                           self.resources, self.submit_unknown, self.submitted)


_ATTEMPT_COLS = ("attempt_id, job_id, attempt_no, provider, region, mode, idempotency_key, "
                 "shards_json, submitted, submit_unknown, resources_json, teardown_done, "
                 "cost_usd, started_at, ended_at")


def _attempt(row: Sequence[Any]) -> AttemptRow:
    return AttemptRow(
        row[0], row[1], int(row[2]), row[3], row[4], row[5], row[6],
        tuple(json.loads(row[7])), bool(row[8]), bool(row[9]),
        tuple(resource_from_dict(r) for r in json.loads(row[10])), bool(row[11]),
        float(row[12]), float(row[13]), row[14],
    )


class JobRepo:
    def __init__(self, db: Any, clock: Callable[[], float] = time.time):
        self._db = db
        self._clock = clock

    # --- jobs ---------------------------------------------------------------

    def create(self, spec: JobSpec, capability_override: bool = False) -> str:
        spec.validate()
        now = self._clock()
        with transaction(self._db):
            self._db.execute(
                "INSERT INTO jobs(job_id, kind, title, spec_json, state, capability_override, "
                "scheduled_at, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (spec.job_id, spec.kind.value, spec.title, spec.to_json(), JobState.QUEUED.value,
                 int(capability_override), spec.scheduled_at, now, now),
            )
            self._db.executemany(
                "INSERT INTO shards(job_id, idx) VALUES (?, ?)",
                [(spec.job_id, s.index) for s in spec.shards],
            )
            self.event(spec.job_id, "created", {"kind": spec.kind.value,
                                                "provider": spec.placement.provider,
                                                "shards": len(spec.shards)})
        return spec.job_id

    def spec(self, job_id: str) -> JobSpec:
        rows = self._db.query("SELECT spec_json FROM jobs WHERE job_id = ?", (job_id,))
        if not rows:
            raise UnknownJob(job_id)
        return JobSpec.from_json(rows[0][0])

    def replace_spec(self, spec: JobSpec) -> None:
        self._db.execute("UPDATE jobs SET spec_json = ?, updated_at = ? WHERE job_id = ?",
                         (spec.to_json(), self._clock(), spec.job_id))

    def created_at(self, job_id: str) -> float:
        rows = self._db.query("SELECT created_at FROM jobs WHERE job_id = ?", (job_id,))
        if not rows:
            raise UnknownJob(job_id)
        return float(rows[0][0])

    def accepted_record(self, job_id: str) -> Dict[str, Any]:
        rows = self._db.query("SELECT data_json FROM job_events WHERE job_id = ? AND type = 'accepted' "
                              "ORDER BY id LIMIT 1", (job_id,))
        return json.loads(rows[0][0]) if rows else {}

    def state(self, job_id: str) -> JobState:
        rows = self._db.query("SELECT state FROM jobs WHERE job_id = ?", (job_id,))
        if not rows:
            raise UnknownJob(job_id)
        return JobState(rows[0][0])

    def job_ids(self, states: Optional[Iterable[JobState]] = None) -> List[str]:
        if states is None:
            rows = self._db.query("SELECT job_id FROM jobs ORDER BY created_at", ())
        else:
            vals = [s.value for s in states]
            marks = ",".join("?" * len(vals))
            rows = self._db.query(
                f"SELECT job_id FROM jobs WHERE state IN ({marks}) ORDER BY created_at", vals)
        return [r[0] for r in rows]

    def needing_work(self) -> List[str]:
        """Non-terminal jobs, plus terminal ones whose teardown is still owed."""
        terminal = [s.value for s in TERMINAL]
        marks = ",".join("?" * len(terminal))
        rows = self._db.query(
            f"SELECT job_id FROM jobs WHERE state NOT IN ({marks}) OR teardown_pending = 1 "
            "ORDER BY created_at", terminal)
        return [r[0] for r in rows]

    def transition(self, job_id: str, to: JobState, reason: str = "") -> None:
        with transaction(self._db):
            src = self.state(job_id)
            if src is to:
                return
            check_transition(src, to)
            self._db.execute("UPDATE jobs SET state = ?, updated_at = ? WHERE job_id = ?",
                             (to.value, self._clock(), job_id))
            self.event(job_id, "state", {"from": src.value, "to": to.value, "reason": reason})

    def set_outcome(self, job_id: str, outcome: Outcome, reason: str) -> None:
        self._db.execute("UPDATE jobs SET outcome = ?, outcome_reason = ?, updated_at = ? WHERE job_id = ?",
                         (outcome.value, reason, self._clock(), job_id))
        self.event(job_id, "outcome", {"outcome": outcome.value, "reason": reason})

    def request_cancel(self, job_id: str, request: CancelRequest) -> None:
        if self.state(job_id) in TERMINAL:
            return
        self._db.execute("UPDATE jobs SET cancel_request = ?, updated_at = ? WHERE job_id = ?",
                         (request.value, self._clock(), job_id))
        self.event(job_id, "cancel_requested", {"request": request.value})

    def set_teardown_pending(self, job_id: str, pending: bool) -> None:
        self._db.execute("UPDATE jobs SET teardown_pending = ? WHERE job_id = ?", (int(pending), job_id))

    def note_fallback(self, job_id: str, target: str) -> None:
        rows = self._db.query("SELECT fallback_used_json FROM jobs WHERE job_id = ?", (job_id,))
        used = json.loads(rows[0][0]) + [target]
        self._db.execute("UPDATE jobs SET fallback_used_json = ? WHERE job_id = ?",
                         (json.dumps(used), job_id))

    # --- attempts -----------------------------------------------------------

    def begin_attempt(self, job_id: str, shards: Sequence[int]) -> AttemptRow:
        """Persist intent + idempotency key *before* the provider is called."""
        spec = self.spec(job_id)
        with transaction(self._db):
            n = int(self._db.query("SELECT attempts_used FROM jobs WHERE job_id = ?", (job_id,))[0][0]) + 1
            attempt_id = f"{job_id}-a{n}-{uuid.uuid4().hex[:6]}"
            pl = spec.placement
            self._db.execute(
                f"INSERT INTO attempts({_ATTEMPT_COLS}) VALUES (?,?,?,?,?,?,?,?,0,0,'[]',0,0,?,NULL)",
                (attempt_id, job_id, n, pl.provider, pl.region, pl.mode.value,
                 spec.idempotency_key(n), json.dumps(list(shards)), self._clock()),
            )
            self._db.execute("UPDATE jobs SET attempts_used = ?, updated_at = ? WHERE job_id = ?",
                             (n, self._clock(), job_id))
            self.event(job_id, "attempt", {"attempt_id": attempt_id, "n": n,
                                           "provider": pl.provider, "shards": list(shards)})
        return self.attempt(attempt_id)

    def attempt(self, attempt_id: str) -> AttemptRow:
        rows = self._db.query(f"SELECT {_ATTEMPT_COLS} FROM attempts WHERE attempt_id = ?", (attempt_id,))
        return _attempt(rows[0])

    def attempts(self, job_id: str) -> List[AttemptRow]:
        rows = self._db.query(
            f"SELECT {_ATTEMPT_COLS} FROM attempts WHERE job_id = ? ORDER BY attempt_no", (job_id,))
        return [_attempt(r) for r in rows]

    def current_attempt(self, job_id: str) -> Optional[AttemptRow]:
        rows = self._db.query(
            f"SELECT {_ATTEMPT_COLS} FROM attempts WHERE job_id = ? ORDER BY attempt_no DESC LIMIT 1",
            (job_id,))
        return _attempt(rows[0]) if rows else None

    def mark_submitted(self, attempt_id: str, resources: Sequence[ResourceRef]) -> None:
        self._db.execute(
            "UPDATE attempts SET submitted = 1, submit_unknown = 0, resources_json = ? WHERE attempt_id = ?",
            (json.dumps([resource_to_dict(r) for r in resources]), attempt_id))

    def mark_submit_unknown(self, attempt_id: str, unknown: bool = True) -> None:
        self._db.execute("UPDATE attempts SET submit_unknown = ? WHERE attempt_id = ?",
                         (int(unknown), attempt_id))

    def record_cost(self, attempt_id: str, cost_usd: float) -> None:
        self._db.execute("UPDATE attempts SET cost_usd = MAX(cost_usd, ?) WHERE attempt_id = ?",
                         (cost_usd, attempt_id))

    def submit_error(self, job_id: str) -> Optional[str]:
        att = self.current_attempt(job_id)
        if att is None or att.ended_at is None or att.submitted:
            return None
        rows = self._db.query(
            "SELECT data_json FROM job_events WHERE job_id = ? AND type = 'submit_failed' "
            "ORDER BY id DESC LIMIT 1", (job_id,))
        data = json.loads(rows[0][0]) if rows else {}
        return data.get("code") if data.get("attempt_id") == att.attempt_id else None

    def pending_restart(self, job_id: str) -> Optional[Dict[str, Any]]:
        rows = self._db.query(
            "SELECT type, data_json FROM job_events WHERE job_id = ? "
            "AND type IN ('restart_pending', 'restart_resumed') ORDER BY id DESC LIMIT 1", (job_id,))
        return json.loads(rows[0][1]) if rows and rows[0][0] == "restart_pending" else None

    def end_attempt(self, attempt_id: str, cost_usd: float, teardown_done: bool) -> None:
        self._db.execute(
            "UPDATE attempts SET cost_usd = ?, teardown_done = ?, ended_at = COALESCE(ended_at, ?) "
            "WHERE attempt_id = ?", (cost_usd, int(teardown_done), self._clock(), attempt_id))

    def open_teardowns(self, job_id: str) -> List[AttemptRow]:
        return [a for a in self.attempts(job_id) if a.submitted and not a.teardown_done]

    # --- shards & events ----------------------------------------------------

    def mark_ready(self, job_id: str, indices: Sequence[int], durable: bool) -> None:
        """Persist that the worker finished these shards (only the first report counts)."""
        for idx in indices:
            changed = self._db.execute(
                "UPDATE shards SET ready = 1, durable = ? WHERE job_id = ? AND idx = ? AND ready = 0",
                (int(durable), job_id, idx))
            if changed:
                self.event(job_id, "shard_ready", {"shard": idx, "durable": durable})

    def reset_shards(self, job_id: str, indices: Sequence[int]) -> None:
        """A retry re-runs these shards from scratch."""
        for idx in indices:
            self._db.execute("UPDATE shards SET ready = 0, durable = 0, collect_attempts = 0, "
                             "collect_failed = 0, failures = failures + 1 WHERE job_id = ? AND idx = ? "
                             "AND collected = 0", (job_id, idx))

    def note_collect_failure(self, job_id: str, idx: int, error: str, give_up: bool) -> int:
        self._db.execute("UPDATE shards SET collect_attempts = collect_attempts + 1, "
                         "collect_failed = MAX(collect_failed, ?) WHERE job_id = ? AND idx = ?",
                         (int(give_up), job_id, idx))
        n = int(self._db.query("SELECT collect_attempts FROM shards WHERE job_id = ? AND idx = ?",
                               (job_id, idx))[0][0])
        self.event(job_id, "collect_failed" if give_up else "collect_retry",
                   {"shard": idx, "error": error, "attempts": n})
        return n

    def collect_shard(self, job_id: str, idx: int, outputs: Sequence[str]) -> None:
        self._db.execute("UPDATE shards SET collected = 1, outputs_json = ? WHERE job_id = ? AND idx = ?",
                         (json.dumps(list(outputs)), job_id, idx))
        self.event(job_id, "collected", {"shard": idx, "outputs": len(outputs)})

    def shard_outputs(self, job_id: str) -> Dict[int, List[str]]:
        rows = self._db.query("SELECT idx, outputs_json FROM shards WHERE job_id = ? AND collected = 1",
                              (job_id,))
        return {int(r[0]): json.loads(r[1]) for r in rows}

    def event(self, job_id: str, type_: str, data: Optional[Dict[str, Any]] = None) -> None:
        self._db.execute("INSERT INTO job_events(job_id, ts, type, data_json) VALUES (?,?,?,?)",
                         (job_id, self._clock(), type_, json.dumps(data or {}, sort_keys=True)))

    def events(self, job_id: str, after_id: int = 0) -> List[Dict[str, Any]]:
        rows = self._db.query(
            "SELECT id, ts, type, data_json FROM job_events WHERE job_id = ? AND id > ? ORDER BY id",
            (job_id, after_id))
        return [{"id": r[0], "ts": r[1], "type": r[2], "data": json.loads(r[3])} for r in rows]

    # --- reconciler view ----------------------------------------------------

    def view(self, job_id: str, admitted: bool = True, spend_prior_usd: float = 0.0) -> JobView:
        rows = self._db.query(
            "SELECT state, outcome, outcome_reason, cancel_request, teardown_pending, "
            "capability_override, attempts_used, fallback_used_json, scheduled_at, spec_json "
            "FROM jobs WHERE job_id = ?", (job_id,))
        if not rows:
            raise UnknownJob(job_id)
        r = rows[0]
        spec = JobSpec.from_json(r[9])
        shards = tuple(
            ShardView(int(s[0]), bool(s[1]), int(s[2]), bool(s[3]), bool(s[4]), bool(s[5]))
            for s in self._db.query("SELECT idx, collected, failures, ready, durable, collect_failed "
                                    "FROM shards WHERE job_id = ? ORDER BY idx", (job_id,)))
        att = self.current_attempt(job_id)
        return JobView(
            job_id=job_id, state=JobState(r[0]), shards=shards,
            attempt=att.view() if att is not None and att.ended_at is None else None,
            attempts_used=int(r[6]),
            outcome=Outcome(r[1]) if r[1] else None, outcome_reason=r[2] or "",
            cancel=CancelRequest(r[3]) if r[3] else None, teardown_pending=bool(r[4]),
            scheduled_at=r[8], admitted=admitted, resumable=spec.resumable,
            capability_override=bool(r[5]),
            max_runtime_s=spec.limits.max_runtime_s, max_spend_usd=spec.limits.max_spend_usd,
            spend_prior_attempts_usd=spend_prior_usd, fallback_used=tuple(json.loads(r[7])),
        )
