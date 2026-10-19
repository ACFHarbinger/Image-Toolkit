"""Executes reconciler actions against the store and the adapters (#828).

The daemon (B1) drives :meth:`JobEngine.tick`; tests drive it directly with
a fake clock. Every side effect is persisted before the next provider call,
so a crash between any two lines is recovered by the next tick.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace
from typing import Callable, List, Mapping, Optional, Sequence, Tuple

from .acceptance import AcceptedJob
from .adapter import (
    AmbiguousSubmit,
    AttemptContext,
    Observation,
    OutOfStock,
    ProviderAdapter,
    QuotaExceeded,
    ShardStatus,
    SubmitRejected,
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
from .spec import ExecutionMode, JobSpec, Placement
from .state import ACTIVE, TERMINAL, CancelRequest, JobState, Outcome
from .store import KIND_ACTUAL, KIND_RESERVED, CloudJobStore, LedgerEntry, transaction
from .store.jobs import AttemptRow

log = logging.getLogger(__name__)

_MAX_STEPS = 12  # actions per job per tick; a healthy job needs 2-3
MAX_COLLECT_ATTEMPTS = 3  # per durable shard, across ticks, before its output is reported lost


@dataclass(frozen=True)
class EngineSettings:
    owner: str
    max_attempts: int = 3
    fallback_enabled: bool = False
    fallback_candidates: Tuple[Placement, ...] = ()
    cap_margin_s: float = 60.0
    expiry_grace_s: float = 900.0
    default_max_runtime_s: float = 6 * 3600.0
    default_max_spend_usd: float = 10.0
    hard_caps_enabled: bool = True
    max_concurrent_jobs: int = 4
    max_concurrent_gpu_instances: int = 2
    max_reserved_usd: float = float("inf")
    revalidate_after_s: float = 3600.0  # a job queued longer than this is re-checked before it provisions

    @classmethod
    def from_cloud_settings(cls, settings: CloudSettings, owner: str,
                            fallback_candidates: Tuple[Placement, ...] = ()) -> "EngineSettings":
        """The engine reads the user's CloudSettings; only the owner tag and candidates are its own."""
        return cls(owner=owner, max_attempts=settings.max_attempts,
                   fallback_enabled=settings.fallback_enabled, fallback_candidates=fallback_candidates,
                   default_max_runtime_s=float(settings.default_max_runtime_s),
                   default_max_spend_usd=settings.default_max_spend_usd,
                   hard_caps_enabled=settings.hard_caps_enabled,
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
    # Re-runs preflight for a placement chosen without the user (scheduled start,
    # automatic fallback); returns a refusal reason, or None when it still passes.
    revalidator: Optional[Callable[[str, JobSpec], Optional[str]]] = None

    # --- public -------------------------------------------------------------

    def submit(self, accepted: AcceptedJob) -> str:
        """Enqueue a job that already passed preflight; see CloudJobService.submit."""
        accepted.check()
        spec = accepted.spec
        if spec.placement.provider not in self.adapters:
            raise KeyError(f"no adapter for provider {spec.placement.provider!r}")
        with transaction(self.store.db):
            job_id = self.store.jobs.create(spec, accepted.capability_override)
            if accepted.reservation_usd > 0:
                self.store.ledger.add(LedgerEntry(job_id, spec.placement.provider, KIND_RESERVED,
                                                  accepted.reservation_usd, task=spec.kind.value))
            self.store.jobs.event(job_id, "accepted", accepted.record())
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
            pending = self.store.jobs.pending_restart(job_id)
            if pending is not None and view.cancel is None and view.state not in TERMINAL:
                if not self._resume_restart(job_id, pending, ts):
                    return
                continue
            if self.settings.hard_caps_enabled:
                cap = view.max_spend_usd or self.settings.default_max_spend_usd
                reserved = self.store.ledger.total(KIND_RESERVED, job_id=job_id)
                if reserved > 0:  # the monthly budget only holds the reservation, so never spend past it
                    cap = min(cap, reserved)
                view = replace(view,
                               max_runtime_s=view.max_runtime_s or self.settings.default_max_runtime_s,
                               max_spend_usd=cap)
            else:
                view = replace(view, max_runtime_s=None, max_spend_usd=None)
            if ts.obs is None and view.cancel is not CancelRequest.FORCE:
                ts.obs = self._observe(job_id, view.state)
                if ts.obs is not None:
                    view = replace(view, shards=self.store.jobs.view(job_id).shards)
            if ts.submit_error is None and view.state is JobState.SUBMITTING:
                ts.submit_error = self.store.jobs.submit_error(job_id)
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
        active = [j for j in self.store.jobs.needing_work()
                  if j != job_id and (self.store.jobs.state(j) in ACTIVE
                                     or self.store.jobs.view(j).teardown_pending)]
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
        with transaction(self.store.db):
            self.store.jobs.record_cost(att.attempt_id, obs.cost_so_far_usd)
            done = [i for i, st in obs.shards.items() if st is ShardStatus.SUCCEEDED and i in att.shards]
            self.store.jobs.mark_ready(job_id, done, obs.outputs_durable)
        return obs

    def _apply(self, job_id: str, actions: Sequence[Action], ts: _TickState) -> bool:
        changed = False
        for action in actions:
            if isinstance(action, Transition):
                with transaction(self.store.db):
                    self.store.jobs.transition(job_id, action.to, action.reason)
                    if action.to in TERMINAL:
                        self.store.ledger.release_reservation(job_id)
                changed = True
            elif isinstance(action, BeginAttempt):
                refusal = self._first_start_refusal(job_id)
                if refusal is not None:
                    with transaction(self.store.db):
                        self.store.jobs.set_outcome(job_id, Outcome.FAILED, refusal)
                        self.store.jobs.transition(job_id, JobState.SETTLING, refusal)
                    return True
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
                self._checkpoint(job_id)  # never raises: a failed checkpoint must not block teardown
            elif isinstance(action, Teardown):
                changed |= self._teardown(job_id)
            elif isinstance(action, SetOutcome):
                # Record settlement before destructive IO; restart must not rerun completed work.
                with transaction(self.store.db):
                    self.store.jobs.set_outcome(job_id, action.outcome, action.reason)
                    self.store.jobs.set_teardown_pending(job_id, bool(self.store.jobs.open_teardowns(job_id)))
                    self.store.jobs.transition(job_id, JobState.SETTLING, action.reason)
            elif isinstance(action, Retry):
                return self._restart(job_id, action.reason, ts)
            elif isinstance(action, Fallback):
                return self._fallback(job_id, action.reason, ts)
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
        except SubmitRejected as exc:
            return self._submit_failed(att, SUBMIT_FAILED, str(exc))
        except Exception as exc:
            # Parsing/transport failures can happen after provisioning succeeded.
            self.store.jobs.mark_submit_unknown(att.attempt_id)
            self.store.jobs.event(att.job_id, "submit_unknown", {"error": str(exc)})
            return None
        self.store.jobs.mark_submitted(att.attempt_id, receipt.resources)
        self.store.jobs.event(att.job_id, "submitted", {"resources": [r.resource_id for r in receipt.resources]})
        return None

    def _submit_failed(self, att: AttemptRow, code: str, message: str, **extra: str) -> str:
        with transaction(self.store.db):
            self.store.jobs.end_attempt(att.attempt_id, 0.0, teardown_done=True)
            self.store.jobs.event(att.job_id, "submit_failed", {
                "attempt_id": att.attempt_id, "code": code, "error": message, **extra})
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
        """Returns True when the job's collection state changed (collected or given up)."""
        att = self.store.jobs.current_attempt(job_id)
        if att is None:
            return False
        try:
            res = self._adapter(job_id).collect(self._ctx(att), shard)
            error = "" if res.verified else "output failed verification"
        except Exception as exc:  # download endpoint down, checksum mismatch raised, ...
            res, error = None, f"{type(exc).__name__}: {exc}"
        if res is not None and res.verified:
            self.store.jobs.collect_shard(job_id, shard, res.outputs)
            return True
        view = next(s for s in self.store.jobs.view(job_id).shards if s.index == shard)
        attempts = self.store.jobs.note_collect_failure(job_id, shard, error, give_up=False)
        # Durable outputs can be retried after teardown; ephemeral ones are given up at teardown.
        if view.durable and attempts >= MAX_COLLECT_ATTEMPTS:
            self.store.jobs.note_collect_failure(job_id, shard, error, give_up=True)
            return True
        return False

    def _checkpoint(self, job_id: str) -> None:
        att = self.store.jobs.current_attempt(job_id)
        fn = getattr(self._adapter(job_id), "checkpoint", None)
        if att is None or not callable(fn):
            return
        try:
            fn(self._ctx(att))
        except Exception as exc:
            self.store.jobs.event(job_id, "checkpoint_failed", {"error": f"{type(exc).__name__}: {exc}"})
            return
        self.store.jobs.event(job_id, "checkpoint", {})

    def _teardown(self, job_id: str) -> bool:
        spec = self.store.jobs.spec(job_id)
        pending = False
        for att in self.store.jobs.open_teardowns(job_id):
            ok = self.adapters[att.provider].teardown(att.resources)
            if ok:
                with transaction(self.store.db):
                    self.store.jobs.end_attempt(att.attempt_id, att.cost_usd, teardown_done=True)
                    self.store.ledger.add(LedgerEntry(
                        job_id, att.provider, KIND_ACTUAL, att.cost_usd, attempt_id=att.attempt_id,
                        task=spec.kind.value, status="torn_down",
                        duration_s=max(0.0, self.clock() - att.started_at)))
                    self.store.jobs.event(job_id, "torn_down", {"attempt_id": att.attempt_id})
                    for sh in self.store.jobs.view(job_id).shards:
                        if sh.index in att.shards and sh.collectable and not sh.durable:
                            self.store.jobs.note_collect_failure(job_id, sh.index, "output lost with the instance",
                                                                 give_up=True)
            else:
                pending = True
                self.store.jobs.event(job_id, "teardown_failed", {"attempt_id": att.attempt_id})
        was = self.store.jobs.view(job_id).teardown_pending
        self.store.jobs.set_teardown_pending(job_id, pending)
        return was != pending or not pending

    def _restart(self, job_id: str, reason: str, ts: _TickState,
                 target: Optional[Placement] = None) -> bool:
        intent = {"reason": reason, "placement": self.store.jobs.spec(job_id).with_placement(
            target or self.store.jobs.spec(job_id).placement).to_dict()["placement"],
                  "fallback": target is not None}
        self.store.jobs.event(job_id, "restart_pending", intent)
        return self._resume_restart(job_id, intent, ts)

    def _resume_restart(self, job_id: str, intent: dict, ts: _TickState) -> bool:
        self._teardown(job_id)
        if self.store.jobs.view(job_id).teardown_pending:
            return False
        pl = intent["placement"]
        target = Placement(**{**pl, "mode": ExecutionMode(pl["mode"])})
        reason = intent["reason"]
        with transaction(self.store.db):
            if intent["fallback"]:
                self.store.jobs.replace_spec(self.store.jobs.spec(job_id).with_placement(target))
                self.store.jobs.note_fallback(job_id, _placement_key(target))
                self.store.jobs.event(job_id, "fallback", {"reason": reason, "to": _placement_key(target)})
            self.store.jobs.event(job_id, "retry", {"reason": reason})
            self.store.jobs.transition(job_id, JobState.SUBMITTING, f"retry: {reason}")
            view = self.store.jobs.view(job_id)
            safe = set(view.collectable(durable_only=True))  # finished and in staging: collect, don't re-run
            rerun = tuple(i for i in view.pending_shards if i not in safe)
            if not rerun:
                # Everything left is finished and staged: settle and collect, don't provision.
                self.store.jobs.event(job_id, "restart_resumed", {"attempt_id": None})
                self.store.jobs.set_outcome(job_id, Outcome.SUCCEEDED, "remaining shards finished")
                self.store.jobs.transition(job_id, JobState.SETTLING, "remaining shards finished")
                return True
            self.store.jobs.reset_shards(job_id, rerun)
            att = self.store.jobs.begin_attempt(job_id, rerun)
            self.store.jobs.event(job_id, "restart_resumed", {"attempt_id": att.attempt_id})
        ts.submit_error = self._submit(att)
        ts.obs = None
        return True

    def _revalidate(self, job_id: str, spec: JobSpec) -> Optional[str]:
        if self.revalidator is None:
            return "no revalidator configured; refusing a placement the user didn't confirm"
        return self.revalidator(job_id, spec)

    def _first_start_refusal(self, job_id: str) -> Optional[str]:
        """Scheduled or long-queued jobs are re-checked: prices, quota and rules may have changed."""
        view = self.store.jobs.view(job_id)
        if view.attempts_used > 0:
            return None
        waited = self.clock() - self.store.jobs.created_at(job_id)
        if view.scheduled_at is None and waited < self.settings.revalidate_after_s:
            return None
        why = self._revalidate(job_id, self.store.jobs.spec(job_id))
        return None if why is None else f"revalidation before start: {why}"

    def _fallback(self, job_id: str, reason: str, ts: _TickState) -> bool:
        spec = self.store.jobs.spec(job_id)
        for target in self._remaining_fallbacks(job_id):
            why = self._revalidate(job_id, spec.with_placement(target))
            if why is None:
                return self._restart(job_id, reason, ts, target)
            self.store.jobs.note_fallback(job_id, _placement_key(target))
            self.store.jobs.event(job_id, "fallback_rejected", {"to": _placement_key(target), "why": why})
        why = f"{reason}; no fallback placement passed revalidation"
        with transaction(self.store.db):
            self.store.jobs.set_outcome(job_id, Outcome.FAILED, why)
            self.store.jobs.set_teardown_pending(job_id, bool(self.store.jobs.open_teardowns(job_id)))
            self.store.jobs.transition(job_id, JobState.SETTLING, why)
        return True


def _placement_key(p: Placement) -> str:
    return f"{p.provider}/{p.region}/{p.mode.value}/{p.instance_type or ''}"
