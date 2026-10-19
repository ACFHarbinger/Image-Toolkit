"""Executes reconciler actions against the store and the adapters (#828).

The daemon (B1) drives :meth:`JobEngine.tick`; tests drive it directly with
a fake clock. Every side effect is persisted before the next provider call,
so a crash between any two lines is recovered by the next tick.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from .adapter import (
    AmbiguousSubmit,
    AttemptContext,
    Observation,
    OutOfStock,
    ProviderAdapter,
    QuotaExceeded,
    find_by_idempotency,
)
from .cost.caps import AdmissionSnapshot, admission_blockers
from .reconciler import (
    SUBMIT_FAILED,
    SUBMIT_OUT_OF_STOCK,
    SUBMIT_QUOTA,
    Action,
    BeginAttempt,
    Checkpoint,
    Collect,
    Fallback,
    ReconcileSettings,
    ResolveSubmit,
    Retry,
    SetOutcome,
    Teardown,
    Transition,
    reconcile,
)
from .settings import CloudSettings
from .spec import JobSpec, Placement
from .state import ACTIVE, CancelRequest, JobState
from .store import KIND_ACTUAL, KIND_RESERVED, CloudJobStore, LedgerEntry, transaction
from .store.jobs import AttemptRow

log = logging.getLogger(__name__)

_MAX_STEPS = 12  # actions per job per tick; a healthy job needs 2-3


@dataclass(frozen=True)
class EngineSettings:
    owner: str
    max_attempts: int = 3
    fallback_enabled: bool = False
    fallback_candidates: Tuple[Placement, ...] = ()
    cap_margin_s: float = 60.0
    expiry_grace_s: float = 900.0
    default_max_runtime_s: float = 6 * 3600.0
    max_concurrent_jobs: int = 4
    max_concurrent_gpu_instances: int = 2
    max_reserved_usd: float = float("inf")

    @classmethod
    def from_cloud_settings(cls, settings: CloudSettings, owner: str,
                            fallback_candidates: Tuple[Placement, ...] = ()) -> "EngineSettings":
        """The engine reads the user's CloudSettings; only the owner tag and candidates are its own."""
        return cls(owner=owner, max_attempts=settings.max_attempts,
                   fallback_enabled=settings.fallback_enabled, fallback_candidates=fallback_candidates,
                   default_max_runtime_s=float(settings.default_max_runtime_s),
                   max_concurrent_jobs=settings.max_concurrent_jobs,
                   max_concurrent_gpu_instances=settings.max_concurrent_gpu_instances,
                   max_reserved_usd=settings.max_reserved_usd)


@dataclass
class _TickState:
    submit_error: Optional[str] = None
    obs: Optional[Observation] = None


@dataclass
class JobEngine:
    store: CloudJobStore
    adapters: Mapping[str, ProviderAdapter]
    settings: EngineSettings
    clock: Callable[[], float] = time.time
    _last_cost: Dict[str, float] = field(default_factory=dict)

    # --- public -------------------------------------------------------------

    def submit(self, spec: JobSpec, capability_override: bool = False,
               reserve_usd: float = 0.0) -> str:
        if spec.placement.provider not in self.adapters:
            raise KeyError(f"no adapter for provider {spec.placement.provider!r}")
        with transaction(self.store.db):
            job_id = self.store.jobs.create(spec, capability_override)
            if reserve_usd > 0:
                self.store.ledger.add(LedgerEntry(job_id, spec.placement.provider, KIND_RESERVED,
                                                  reserve_usd, task=spec.kind.value))
        return job_id

    def cancel(self, job_id: str, force: bool = False) -> None:
        self.store.jobs.request_cancel(job_id, CancelRequest.FORCE if force else CancelRequest.CANCEL)

    def tick(self) -> int:
        ids = self.store.jobs.needing_work()
        for job_id in ids:
            try:
                self.step(job_id)
            except Exception:  # one bad job must not stall teardown of the others
                log.exception("cloud job %s: step failed", job_id)
                self.store.jobs.event(job_id, "engine_error", {})
        return len(ids)

    def step(self, job_id: str) -> None:
        ts = _TickState()
        for _ in range(_MAX_STEPS):
            view = self.store.jobs.view(job_id, self._admitted(job_id), self._prior_spend(job_id))
            ts.obs = self._observe(job_id, view.state) if ts.obs is None else ts.obs
            actions = reconcile(view, ts.obs, self._reconcile_settings(job_id), self.clock(),
                                ts.submit_error)
            if not actions:
                return
            ts.submit_error = None
            changed = self._apply(job_id, actions, ts)
            if not changed:
                return
        # Not an error (the next tick continues), but make a slow-moving job visible.
        self.store.jobs.event(job_id, "step_limit", {"max_steps": _MAX_STEPS})

    # --- helpers ------------------------------------------------------------

    def _adapter(self, job_id: str) -> ProviderAdapter:
        return self.adapters[self.store.jobs.spec(job_id).placement.provider]

    def _ctx(self, att: AttemptRow) -> AttemptContext:
        spec = self.store.jobs.spec(att.job_id)
        max_rt = spec.limits.max_runtime_s or self.settings.default_max_runtime_s
        return AttemptContext(att.job_id, att.attempt_id, att.attempt_no, att.idempotency_key, spec,
                              att.shards, self.settings.owner,
                              att.started_at + max_rt + self.settings.expiry_grace_s)

    def _admitted(self, job_id: str) -> bool:
        if self.store.jobs.state(job_id) is not JobState.QUEUED:
            return True
        active = [j for j in self.store.jobs.job_ids(ACTIVE) if j != job_id]
        gpu = sum(1 for j in active if self.store.jobs.spec(j).resources.needs_gpu)
        own = self.store.ledger.total(KIND_RESERVED, job_id=job_id)
        # Only admitted jobs hold reserved spend; counting queued ones lets them block each other forever.
        held = sum(self.store.ledger.total(KIND_RESERVED, job_id=j) for j in active)
        snap = AdmissionSnapshot(len(active), gpu, held)
        limits = CloudSettings(max_concurrent_jobs=self.settings.max_concurrent_jobs,
                               max_concurrent_gpu_instances=self.settings.max_concurrent_gpu_instances,
                               max_reserved_usd=self.settings.max_reserved_usd)
        return not admission_blockers(snap, limits, self.store.jobs.spec(job_id).resources.needs_gpu, own)

    def _prior_spend(self, job_id: str) -> float:
        cur = self.store.jobs.current_attempt(job_id)
        return sum(a.cost_usd for a in self.store.jobs.attempts(job_id)
                   if cur is None or a.attempt_id != cur.attempt_id)

    def _remaining_fallbacks(self, job_id: str) -> List[Placement]:
        view_used = set(self.store.jobs.view(job_id).fallback_used)
        current = self.store.jobs.spec(job_id).placement
        return [p for p in self.settings.fallback_candidates
                if p != current and _placement_key(p) not in view_used]

    def _reconcile_settings(self, job_id: str) -> ReconcileSettings:
        return ReconcileSettings(self.settings.max_attempts, self.settings.fallback_enabled,
                                 bool(self._remaining_fallbacks(job_id)), self.settings.cap_margin_s)

    def _observe(self, job_id: str, state: JobState) -> Optional[Observation]:
        if state not in ACTIVE:
            return None
        att = self.store.jobs.current_attempt(job_id)
        if att is None or not att.submitted or att.ended_at is not None:
            return None
        obs = self._adapter(job_id).observe(self._ctx(att), att.resources)
        self._last_cost[att.attempt_id] = obs.cost_so_far_usd
        return obs

    def _apply(self, job_id: str, actions: Sequence[Action], ts: _TickState) -> bool:
        changed = False
        for action in actions:
            if isinstance(action, Transition):
                self.store.jobs.transition(job_id, action.to, action.reason)
                changed = True
            elif isinstance(action, BeginAttempt):
                att = self.store.jobs.begin_attempt(job_id, action.shards)
                ts.submit_error = self._submit(att)
                ts.obs = None
                changed = True
            elif isinstance(action, ResolveSubmit):
                self._resolve(job_id, ts)
                changed = True
            elif isinstance(action, Collect):
                changed |= self._collect(job_id, action.shard)
            elif isinstance(action, Checkpoint):
                self._checkpoint(job_id)
            elif isinstance(action, Teardown):
                changed |= self._teardown(job_id)
            elif isinstance(action, SetOutcome):
                self.store.jobs.set_outcome(job_id, action.outcome, action.reason)
                self.store.ledger.release_reservation(job_id)
            elif isinstance(action, Retry):
                self._restart(job_id, action.reason, ts)
                return True
            elif isinstance(action, Fallback):
                self._fallback(job_id, action.reason, ts)
                return True
        return changed

    def _submit(self, att: AttemptRow) -> Optional[str]:
        adapter = self.adapters[att.provider]
        try:
            receipt = adapter.submit(self._ctx(att))
        except AmbiguousSubmit as exc:
            self.store.jobs.mark_submit_unknown(att.attempt_id)
            self.store.jobs.event(att.job_id, "submit_unknown", {"error": str(exc)})
            return None
        except OutOfStock as exc:
            return self._submit_failed(att, SUBMIT_OUT_OF_STOCK, str(exc))
        except QuotaExceeded as exc:
            return self._submit_failed(att, SUBMIT_QUOTA, str(exc), request_url=exc.request_url)
        except Exception as exc:  # definitive rejection: nothing was created
            return self._submit_failed(att, SUBMIT_FAILED, str(exc))
        self.store.jobs.mark_submitted(att.attempt_id, receipt.resources)
        self.store.jobs.event(att.job_id, "submitted", {"resources": [r.resource_id for r in receipt.resources]})
        return None

    def _submit_failed(self, att: AttemptRow, code: str, message: str, **extra: str) -> str:
        self.store.jobs.end_attempt(att.attempt_id, 0.0, teardown_done=True)
        self.store.jobs.event(att.job_id, "submit_failed", {"code": code, "error": message, **extra})
        return code

    def _resolve(self, job_id: str, ts: _TickState) -> None:
        att = self.store.jobs.current_attempt(job_id)
        if att is None:
            return
        adapter = self.adapters[att.provider]
        found = find_by_idempotency(adapter.list_owned_resources(self.settings.owner), att.idempotency_key)
        if found:
            self.store.jobs.mark_submitted(att.attempt_id, found)
            self.store.jobs.event(job_id, "submit_resolved", {"found": [r.resource_id for r in found]})
            return
        self.store.jobs.event(job_id, "submit_resolved", {"found": []})
        self.store.jobs.mark_submit_unknown(att.attempt_id, False)
        if self.store.jobs.view(job_id).cancel is not None:
            self.store.jobs.end_attempt(att.attempt_id, 0.0, teardown_done=True)
            return
        ts.submit_error = self._submit(att)  # same attempt, same idempotency key

    def _collect(self, job_id: str, shard: int) -> bool:
        att = self.store.jobs.current_attempt(job_id)
        if att is None:
            return False
        res = self._adapter(job_id).collect(self._ctx(att), shard)
        if not res.verified:
            self.store.jobs.event(job_id, "collect_unverified", {"shard": shard})
            return False
        self.store.jobs.collect_shard(job_id, shard, res.outputs)
        return True

    def _checkpoint(self, job_id: str) -> None:
        att = self.store.jobs.current_attempt(job_id)
        fn = getattr(self._adapter(job_id), "checkpoint", None)
        if att is not None and callable(fn):
            fn(self._ctx(att))
            self.store.jobs.event(job_id, "checkpoint", {})

    def _teardown(self, job_id: str) -> bool:
        spec = self.store.jobs.spec(job_id)
        pending = False
        for att in self.store.jobs.open_teardowns(job_id):
            ok = self.adapters[att.provider].teardown(att.resources)
            if ok:
                cost = self._last_cost.pop(att.attempt_id, att.cost_usd)
                self.store.jobs.end_attempt(att.attempt_id, cost, teardown_done=True)
                self.store.ledger.add(LedgerEntry(
                    job_id, att.provider, KIND_ACTUAL, cost, attempt_id=att.attempt_id,
                    task=spec.kind.value, status="torn_down",
                    duration_s=max(0.0, self.clock() - att.started_at)))
                self.store.jobs.event(job_id, "torn_down", {"attempt_id": att.attempt_id})
            else:
                pending = True
                self.store.jobs.event(job_id, "teardown_failed", {"attempt_id": att.attempt_id})
        was = self.store.jobs.view(job_id).teardown_pending
        self.store.jobs.set_teardown_pending(job_id, pending)
        return was != pending or not pending

    def _restart(self, job_id: str, reason: str, ts: _TickState) -> None:
        self._teardown(job_id)
        self.store.jobs.event(job_id, "retry", {"reason": reason})
        if self.store.jobs.state(job_id) is not JobState.SUBMITTING:
            self.store.jobs.transition(job_id, JobState.SUBMITTING, f"retry: {reason}")
        att = self.store.jobs.begin_attempt(job_id, self.store.jobs.view(job_id).pending_shards)
        ts.submit_error = self._submit(att)
        ts.obs = None

    def _fallback(self, job_id: str, reason: str, ts: _TickState) -> None:
        target = self._remaining_fallbacks(job_id)[0]
        spec = self.store.jobs.spec(job_id)
        self.store.jobs.replace_spec(spec.with_placement(target))
        self.store.jobs.note_fallback(job_id, _placement_key(target))
        self.store.jobs.event(job_id, "fallback", {"reason": reason, "to": _placement_key(target)})
        self._restart(job_id, f"fallback: {reason}", ts)


def _placement_key(p: Placement) -> str:
    return f"{p.provider}/{p.region}/{p.mode.value}/{p.instance_type or ''}"
