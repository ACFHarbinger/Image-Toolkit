"""Provider adapter contract and capability manifest (#826).

``plan`` is pure; the rest talk to the provider. Every call must be safe to
repeat: the reconciler re-issues them after a crash. Provider SDKs live only
inside concrete adapters, never here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Protocol, Sequence, Tuple, runtime_checkable

from .spec import ExecutionMode, JobSpec, StorageMethod

TAG_JOB = "it-job-id"
TAG_OWNER = "it-owner"
TAG_EXPIRES = "it-expires-at"
TAG_IDEMPOTENCY = "it-idem"


@dataclass(frozen=True)
class CapabilityManifest:
    """What a provider can run. Data only: the risk engine reads it, no SDK needed."""

    provider: str
    modes: FrozenSet[ExecutionMode]
    storage: FrozenSet[StorageMethod]
    gpu_classes: FrozenSet[str] = frozenset()
    regions: Tuple[str, ...] = ()
    cpu_only_modes: FrozenSet[ExecutionMode] = frozenset()
    max_task_seconds: Mapping[str, int] = field(default_factory=dict)  # mode value -> limit
    supports_spot: bool = False
    supports_labels: bool = True
    native_deadline: bool = False
    third_party_gpu_host: bool = False
    verified_on: str = ""  # date the facts were last checked against provider docs

    def supports(self, mode: ExecutionMode, needs_gpu: bool) -> bool:
        if mode not in self.modes:
            return False
        return not (needs_gpu and mode in self.cpu_only_modes)


@dataclass(frozen=True)
class AttemptContext:
    """Everything an adapter needs for one attempt; persisted before ``submit``."""

    job_id: str
    attempt_id: str
    attempt_no: int
    idempotency_key: str
    spec: JobSpec
    shard_indices: Tuple[int, ...]
    owner: str
    expires_at: float

    @property
    def tags(self) -> Dict[str, str]:
        return {
            TAG_JOB: self.job_id,
            TAG_OWNER: self.owner,
            TAG_EXPIRES: str(int(self.expires_at)),
            TAG_IDEMPOTENCY: self.idempotency_key,
        }


@dataclass(frozen=True)
class ResourceRef:
    provider: str
    kind: str  # "instance" | "job" | "volume" | "bucket-prefix" | ...
    resource_id: str
    region: str = ""
    tags: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Plan:
    provider: str
    mode: ExecutionMode
    region: str
    instance_type: Optional[str]
    est_startup_s: float = 0.0
    notes: Tuple[str, ...] = ()


class ProviderStatus(str, Enum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PREEMPTED = "preempted"
    NOT_FOUND = "not_found"


class ShardStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class Observation:
    status: ProviderStatus
    shards: Mapping[int, ShardStatus] = field(default_factory=dict)
    cost_so_far_usd: float = 0.0
    burn_rate_usd_per_s: float = 0.0
    detail: str = ""
    structural: bool = False  # failure caused by the configuration, not chance
    # Workers PUT shard outputs to staging storage, so they outlive the instance. An
    # adapter whose outputs only exist on the instance must report False: those
    # shards are collected before teardown or lost with it.
    outputs_durable: bool = True


@dataclass(frozen=True)
class SubmitReceipt:
    resources: Tuple[ResourceRef, ...]


@dataclass(frozen=True)
class CollectResult:
    shard_index: int
    outputs: Tuple[str, ...]
    verified: bool


class AmbiguousSubmit(RuntimeError):
    """The provider may or may not have created resources (timeout, dropped connection)."""


class SubmitRejected(RuntimeError):
    """Definitive rejection: the adapter guarantees no resources were created."""


class OutOfStock(SubmitRejected):
    """The chosen GPU/flavour has no capacity right now."""


class QuotaExceeded(SubmitRejected):
    def __init__(self, message: str, request_url: str = ""):
        super().__init__(message)
        self.request_url = request_url


@runtime_checkable
class ProviderAdapter(Protocol):
    name: str

    def capabilities(self) -> CapabilityManifest: ...

    def plan(self, spec: JobSpec) -> Plan: ...

    def submit(self, ctx: AttemptContext) -> SubmitReceipt: ...

    def observe(self, ctx: AttemptContext, resources: Sequence[ResourceRef]) -> Observation: ...

    def collect(self, ctx: AttemptContext, shard_index: int) -> CollectResult: ...

    def teardown(self, resources: Sequence[ResourceRef]) -> bool:
        """True once nothing billable remains. Must tolerate already-deleted resources."""
        ...

    def list_owned_resources(self, owner: str) -> List[ResourceRef]: ...


def find_by_idempotency(resources: Sequence[ResourceRef], key: str) -> List[ResourceRef]:
    return [r for r in resources if r.tags.get(TAG_IDEMPOTENCY) == key]


def resource_to_dict(ref: ResourceRef) -> Dict[str, Any]:
    return {"provider": ref.provider, "kind": ref.kind, "resource_id": ref.resource_id,
            "region": ref.region, "tags": dict(ref.tags)}


def resource_from_dict(data: Mapping[str, Any]) -> ResourceRef:
    return ResourceRef(data["provider"], data["kind"], data["resource_id"],
                       data.get("region", ""), dict(data.get("tags", {})))
