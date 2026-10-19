"""Provider-neutral job description (#826).

A job is a manifest of shards: retry, collection, progress and cost
attribution all happen per shard. Origin tabs and the Request Builder both
build a :class:`JobSpec`, so the two submit surfaces can't drift.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple


class WorkloadKind(str, Enum):
    EXTRACT = "extract"
    COMFY_BATCH = "comfy_batch"
    INDEX = "index"
    LORA_TRAIN = "lora_train"


class ExecutionMode(str, Enum):
    INSTANCE = "instance"
    MANAGED_BATCH = "managed_batch"


class StorageMethod(str, Enum):
    BUCKET = "bucket"
    PROVIDER_NATIVE = "provider_native"
    CLOUD_SYNC = "cloud_sync"


class DataClass(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    SENSITIVE = "sensitive"


# Workloads that can resume from a checkpoint (spot is only sensible here).
RESUMABLE_KINDS = frozenset({WorkloadKind.LORA_TRAIN})

DEFAULT_MODE = {
    WorkloadKind.EXTRACT: ExecutionMode.MANAGED_BATCH,
    WorkloadKind.INDEX: ExecutionMode.MANAGED_BATCH,
    WorkloadKind.COMFY_BATCH: ExecutionMode.INSTANCE,
    WorkloadKind.LORA_TRAIN: ExecutionMode.INSTANCE,
}


MAX_SHARDS = 10_000  # one row + one collect per shard; bigger jobs should use larger shards


class SpecError(ValueError):
    """A :class:`JobSpec` that must not be submitted."""


@dataclass(frozen=True)
class Resources:
    vcpu: float = 2.0
    memory_gb: float = 4.0
    gpu_class: Optional[str] = None
    gpu_count: int = 0
    vram_gb_min: float = 0.0
    disk_gb: float = 20.0

    @property
    def needs_gpu(self) -> bool:
        return self.gpu_count > 0 or bool(self.gpu_class)


@dataclass(frozen=True)
class Limits:
    """Per-job safeguards; ``None`` means the Settings default applies."""

    max_runtime_s: Optional[int] = None
    max_spend_usd: Optional[float] = None
    spot_allowed: bool = False
    deadline_ts: Optional[float] = None


@dataclass(frozen=True)
class Placement:
    provider: str
    region: str
    mode: ExecutionMode
    instance_type: Optional[str] = None


@dataclass(frozen=True)
class InputBlob:
    """A content-addressed input; uploaded once, reused by every shard."""

    sha256: str
    size_bytes: int
    name: str
    local_path: Optional[str] = None


@dataclass(frozen=True)
class ShardSpec:
    index: int
    params: Mapping[str, Any] = field(default_factory=dict)
    inputs: Tuple[str, ...] = ()  # sha256 keys into JobSpec.inputs

    def to_dict(self) -> Dict[str, Any]:
        return {"index": self.index, "params": dict(self.params), "inputs": list(self.inputs)}


@dataclass(frozen=True)
class JobSpec:
    kind: WorkloadKind
    placement: Placement
    shards: Tuple[ShardSpec, ...]
    resources: Resources = Resources()
    limits: Limits = Limits()
    data_class: DataClass = DataClass.PRIVATE
    storage: StorageMethod = StorageMethod.BUCKET
    image: str = ""  # digest-pinned worker image, e.g. "...@sha256:..."
    inputs: Mapping[str, InputBlob] = field(default_factory=dict)
    params: Mapping[str, Any] = field(default_factory=dict)
    title: str = ""
    scheduled_at: Optional[float] = None
    job_id: str = field(default_factory=lambda: f"cj-{uuid.uuid4().hex[:12]}")

    def validate(self) -> None:
        if not self.shards:
            raise SpecError("a job needs at least one shard")
        if len(self.shards) > MAX_SHARDS:
            raise SpecError(f"{len(self.shards)} shards is over the {MAX_SHARDS} limit; put more items per shard")
        indices = [s.index for s in self.shards]
        if sorted(indices) != list(range(len(indices))):
            raise SpecError(f"shard indices must be 0..{len(indices) - 1}, got {indices}")
        for shard in self.shards:
            missing = [k for k in shard.inputs if k not in self.inputs]
            if missing:
                raise SpecError(f"shard {shard.index} references unknown inputs {missing}")
        if self.kind is WorkloadKind.LORA_TRAIN and len(self.shards) != 1:
            raise SpecError("LoRA training is a single-shard job")
        if self.image and "@sha256:" not in self.image:
            raise SpecError(f"worker image must be digest-pinned: {self.image!r}")
        if self.limits.max_runtime_s is not None and self.limits.max_runtime_s <= 0:
            raise SpecError("max_runtime_s must be positive")
        if self.limits.max_spend_usd is not None and self.limits.max_spend_usd <= 0:
            raise SpecError("max_spend_usd must be positive")

    @property
    def resumable(self) -> bool:
        return self.kind in RESUMABLE_KINDS

    def with_placement(self, placement: Placement) -> "JobSpec":
        return replace(self, placement=placement)

    def idempotency_key(self, attempt_no: int) -> str:
        """Stable per (job, attempt): a resubmit after an unknown outcome reuses it."""
        return hashlib.sha256(f"{self.job_id}:{attempt_no}".encode()).hexdigest()[:24]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "kind": self.kind.value,
            "placement": {**asdict(self.placement), "mode": self.placement.mode.value},
            "shards": [s.to_dict() for s in self.shards],
            "resources": asdict(self.resources),
            "limits": asdict(self.limits),
            "data_class": self.data_class.value,
            "storage": self.storage.value,
            "image": self.image,
            "inputs": {k: asdict(v) for k, v in self.inputs.items()},
            "params": dict(self.params),
            "title": self.title,
            "scheduled_at": self.scheduled_at,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "JobSpec":
        pl = dict(data["placement"])
        return cls(
            job_id=data["job_id"],
            kind=WorkloadKind(data["kind"]),
            placement=Placement(**{**pl, "mode": ExecutionMode(pl["mode"])}),
            shards=tuple(
                ShardSpec(s["index"], dict(s.get("params", {})), tuple(s.get("inputs", ())))
                for s in data["shards"]
            ),
            resources=Resources(**data.get("resources", {})),
            limits=Limits(**data.get("limits", {})),
            data_class=DataClass(data.get("data_class", DataClass.PRIVATE.value)),
            storage=StorageMethod(data.get("storage", StorageMethod.BUCKET.value)),
            image=data.get("image", ""),
            inputs={k: InputBlob(**v) for k, v in data.get("inputs", {}).items()},
            params=dict(data.get("params", {})),
            title=data.get("title", ""),
            scheduled_at=data.get("scheduled_at"),
        )

    @classmethod
    def from_json(cls, text: str) -> "JobSpec":
        return cls.from_dict(json.loads(text))


def default_mode(kind: WorkloadKind) -> ExecutionMode:
    return DEFAULT_MODE[kind]


__all__: List[str] = [
    "DataClass", "ExecutionMode", "InputBlob", "JobSpec", "Limits", "MAX_SHARDS", "Placement",
    "RESUMABLE_KINDS", "Resources", "ShardSpec", "SpecError", "StorageMethod",
    "WorkloadKind", "default_mode",
]
