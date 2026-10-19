"""Job lifecycle states and the views the reconciler reads (#828)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, Optional, Tuple

from .adapter import ResourceRef


class JobState(str, Enum):
    QUEUED = "queued"
    SUBMITTING = "submitting"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    COLLECTING = "collecting"
    SETTLING = "settling"  # teardown + final spend; a job can be FAILED while still billing
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL: FrozenSet[JobState] = frozenset({JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED})
ACTIVE: FrozenSet[JobState] = frozenset(
    {JobState.SUBMITTING, JobState.PROVISIONING, JobState.RUNNING, JobState.COLLECTING}
)

ALLOWED: Dict[JobState, FrozenSet[JobState]] = {
    JobState.QUEUED: frozenset({JobState.SUBMITTING, JobState.CANCELLED, JobState.FAILED}),
    JobState.SUBMITTING: frozenset({JobState.PROVISIONING, JobState.RUNNING, JobState.COLLECTING,
                                    JobState.SUBMITTING, JobState.SETTLING, JobState.QUEUED,
                                    JobState.FAILED}),
    JobState.PROVISIONING: frozenset({JobState.RUNNING, JobState.COLLECTING, JobState.SETTLING,
                                      JobState.SUBMITTING}),
    JobState.RUNNING: frozenset({JobState.COLLECTING, JobState.SETTLING, JobState.SUBMITTING}),
    JobState.COLLECTING: frozenset({JobState.SETTLING, JobState.SUBMITTING, JobState.RUNNING}),
    JobState.SETTLING: frozenset({JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED,
                                  JobState.SUBMITTING}),
    JobState.SUCCEEDED: frozenset(),
    JobState.FAILED: frozenset(),
    JobState.CANCELLED: frozenset(),
}


class IllegalTransition(RuntimeError):
    pass


def check_transition(src: JobState, dst: JobState) -> None:
    if dst not in ALLOWED[src]:
        raise IllegalTransition(f"{src.value} -> {dst.value}")


class Outcome(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def terminal_state(self) -> JobState:
        return JobState(self.value)


class CancelRequest(str, Enum):
    CANCEL = "cancel"  # checkpoint if supported, collect verified shards, teardown
    FORCE = "force"    # teardown now, skip the checkpoint


@dataclass(frozen=True)
class ShardView:
    index: int
    collected: bool = False
    failures: int = 0
    ready: bool = False           # worker finished it (persisted, so it survives teardown)
    durable: bool = False         # output is in staging storage and can be collected after teardown
    collect_failed: bool = False  # collection given up; counts as a failed shard

    @property
    def collectable(self) -> bool:
        return self.ready and not self.collected and not self.collect_failed


@dataclass(frozen=True)
class AttemptView:
    attempt_id: str
    attempt_no: int
    provider: str
    started_at: float
    resources: Tuple[ResourceRef, ...] = ()
    submit_unknown: bool = False
    submitted: bool = False


@dataclass(frozen=True)
class JobView:
    job_id: str
    state: JobState
    shards: Tuple[ShardView, ...]
    attempt: Optional[AttemptView] = None
    attempts_used: int = 0
    outcome: Optional[Outcome] = None
    outcome_reason: str = ""
    cancel: Optional[CancelRequest] = None
    teardown_pending: bool = False
    scheduled_at: Optional[float] = None
    admitted: bool = True
    resumable: bool = False
    capability_override: bool = False
    max_runtime_s: Optional[float] = None
    max_spend_usd: Optional[float] = None
    spend_prior_attempts_usd: float = 0.0
    fallback_used: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def pending_shards(self) -> Tuple[int, ...]:
        return tuple(s.index for s in self.shards if not s.collected)

    def collectable(self, durable_only: bool = False, ephemeral_only: bool = False) -> Tuple[int, ...]:
        return tuple(s.index for s in self.shards if s.collectable
                     and not (durable_only and not s.durable) and not (ephemeral_only and s.durable))
