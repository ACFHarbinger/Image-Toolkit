"""Pure reconciler: ``(job view, observation, settings, now) → actions`` (#828).

No IO. The engine executes the actions and persists what they did, so after
a crash the same inputs give the same decisions. Every path that stops a
job collects the shards that already finished (partial outputs are kept)
and leaves a teardown obligation until the provider confirms nothing bills.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, Union

from .adapter import Observation, ProviderStatus, ShardStatus
from .state import TERMINAL, CancelRequest, JobState, JobView, Outcome


@dataclass(frozen=True)
class ReconcileSettings:
    max_attempts: int = 3
    fallback_enabled: bool = False
    fallback_available: bool = False
    cap_margin_s: float = 60.0  # one poll interval: stop *before* the cap, not after


@dataclass(frozen=True)
class BeginAttempt:
    shards: Tuple[int, ...]


@dataclass(frozen=True)
class ResolveSubmit:
    """Look for resources tagged with the attempt's idempotency key before retrying."""


@dataclass(frozen=True)
class Collect:
    shard: int


@dataclass(frozen=True)
class Checkpoint:
    pass


@dataclass(frozen=True)
class Teardown:
    pass


@dataclass(frozen=True)
class Retry:
    reason: str


@dataclass(frozen=True)
class Fallback:
    reason: str


@dataclass(frozen=True)
class SetOutcome:
    outcome: Outcome
    reason: str


@dataclass(frozen=True)
class Transition:
    to: JobState
    reason: str = ""


Action = Union[BeginAttempt, ResolveSubmit, Collect, Checkpoint, Teardown, Retry, Fallback,
               SetOutcome, Transition]

# Submit failures the engine reports back through ``submit_error``.
SUBMIT_OUT_OF_STOCK = "out_of_stock"
SUBMIT_QUOTA = "quota"
SUBMIT_FAILED = "failed"


def reconcile(
    job: JobView,
    obs: Optional[Observation],
    settings: ReconcileSettings,
    now: float,
    submit_error: Optional[str] = None,
) -> List[Action]:
    if job.state in TERMINAL:
        return [Teardown()] if job.teardown_pending else []
    if job.state is JobState.SETTLING:
        if job.teardown_pending:
            return [Teardown()]
        outcome = job.outcome or Outcome.FAILED
        return [Transition(outcome.terminal_state, job.outcome_reason)]

    if job.cancel is not None:
        return _cancel(job, obs)

    if job.state is JobState.QUEUED:
        if job.scheduled_at is not None and now < job.scheduled_at:
            return []
        if not job.admitted:
            return []
        return [Transition(JobState.SUBMITTING, "submit"), BeginAttempt(job.pending_shards)]

    if job.state is JobState.SUBMITTING:
        if submit_error is not None:
            return _submit_failed(job, settings, submit_error)
        att = job.attempt
        if att is None:
            return [BeginAttempt(job.pending_shards)]
        if att.submit_unknown or not att.submitted:
            return [ResolveSubmit()]
        if obs is None:
            return []

    if obs is None:
        return []
    return _observed(job, obs, settings, now)


def _cancel(job: JobView, obs: Optional[Observation]) -> List[Action]:
    if job.state is JobState.QUEUED:
        return [Transition(JobState.CANCELLED, "cancelled before submit")]
    if job.attempt is not None and (job.attempt.submit_unknown or not job.attempt.submitted):
        return [ResolveSubmit()]  # can't tear down what we haven't found yet
    force = job.cancel is CancelRequest.FORCE
    reason = "force stopped" if force else "cancelled"
    return _stop(job, obs, Outcome.CANCELLED, reason, checkpoint=not force and job.resumable)


def _submit_failed(job: JobView, settings: ReconcileSettings, error: str) -> List[Action]:
    if error == SUBMIT_QUOTA:
        return _stop(job, None, Outcome.FAILED, "quota exceeded")
    if error == SUBMIT_OUT_OF_STOCK:
        if settings.fallback_enabled and settings.fallback_available:
            return [Fallback("out of stock")]
        return _stop(job, None, Outcome.FAILED, "out of stock")
    if job.attempts_used < settings.max_attempts:
        return [Retry("submit failed")]
    return _stop(job, None, Outcome.FAILED, "submit failed")


def _succeeded_uncollected(job: JobView, obs: Optional[Observation]) -> List[int]:
    if obs is None:
        return []
    done = {i for i, st in obs.shards.items() if st is ShardStatus.SUCCEEDED}
    return [s.index for s in job.shards if not s.collected and s.index in done]


def _stop(job: JobView, obs: Optional[Observation], outcome: Outcome, reason: str,
          checkpoint: bool = False) -> List[Action]:
    actions: List[Action] = []
    if checkpoint and job.state is JobState.RUNNING:
        actions.append(Checkpoint())
    actions += [Collect(i) for i in _succeeded_uncollected(job, obs)]
    actions += [SetOutcome(outcome, reason), Transition(JobState.SETTLING, reason), Teardown()]
    return actions


def _cap_hit(job: JobView, obs: Observation, settings: ReconcileSettings, now: float) -> Optional[str]:
    att = job.attempt
    if (job.max_runtime_s is not None and att is not None
            and now - att.started_at + settings.cap_margin_s >= job.max_runtime_s):
        return "max runtime reached"
    if job.max_spend_usd is not None:
        projected = (job.spend_prior_attempts_usd + obs.cost_so_far_usd
                     + obs.burn_rate_usd_per_s * settings.cap_margin_s)
        if projected >= job.max_spend_usd:
            return "spend cap reached"
    return None


def _observed(job: JobView, obs: Observation, settings: ReconcileSettings, now: float) -> List[Action]:
    cap = _cap_hit(job, obs, settings, now)
    if cap is not None and obs.status in (ProviderStatus.PROVISIONING, ProviderStatus.RUNNING,
                                          ProviderStatus.PENDING):
        return _stop(job, obs, Outcome.FAILED, cap, checkpoint=job.resumable)

    st = obs.status
    if st in (ProviderStatus.PENDING, ProviderStatus.PROVISIONING):
        return [] if job.state is JobState.PROVISIONING else [Transition(JobState.PROVISIONING)]

    if st is ProviderStatus.RUNNING:
        actions: List[Action] = []
        if job.state is not JobState.RUNNING:
            actions.append(Transition(JobState.RUNNING))
        return actions + [Collect(i) for i in _succeeded_uncollected(job, obs)]

    if st is ProviderStatus.SUCCEEDED:
        ready = _succeeded_uncollected(job, obs)
        if ready:
            head: List[Action] = [] if job.state is JobState.COLLECTING else [Transition(JobState.COLLECTING)]
            return head + [Collect(i) for i in ready]
        failed = [s.index for s in job.shards if not s.collected]
        if not failed:
            return [SetOutcome(Outcome.SUCCEEDED, "all shards collected"),
                    Transition(JobState.SETTLING, "all shards collected"), Teardown()]
        return _attempt_failed(job, obs, settings, f"{len(failed)} shard(s) failed")

    reason = {ProviderStatus.PREEMPTED: "preempted",
              ProviderStatus.NOT_FOUND: "resources disappeared"}.get(st, obs.detail or "attempt failed")
    return [Collect(i) for i in _succeeded_uncollected(job, obs)] + _attempt_failed(job, obs, settings, reason)


def _attempt_failed(job: JobView, obs: Observation, settings: ReconcileSettings, reason: str) -> List[Action]:
    # A failure on a job that overrode a capability rule is structural: retrying
    # or moving it would spend money reproducing the same failure.
    if obs.structural or job.capability_override:
        return [SetOutcome(Outcome.FAILED, f"structural: {reason}"),
                Transition(JobState.SETTLING, reason), Teardown()]
    if job.attempts_used < settings.max_attempts:
        return [Retry(reason)]
    if settings.fallback_enabled and settings.fallback_available:
        return [Fallback(reason)]
    return [SetOutcome(Outcome.FAILED, reason), Transition(JobState.SETTLING, reason), Teardown()]


def describe(actions: Sequence[Action]) -> List[str]:
    return [type(a).__name__ for a in actions]
