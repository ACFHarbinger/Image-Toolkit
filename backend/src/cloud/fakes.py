"""Scripted fake provider for zero-spend lifecycle tests (#829).

Each attempt plays a timeline of observations; submit, collect and teardown
can be told to fail in the ways real providers do. ``billable()`` is the leak
check: anything still listed there after a job settles is a bug.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence

from .adapter import (
    TAG_OWNER,
    AmbiguousSubmit,
    AttemptContext,
    CapabilityManifest,
    CollectResult,
    Observation,
    OutOfStock,
    Plan,
    ProviderStatus,
    QuotaExceeded,
    ResourceRef,
    ShardStatus,
    SubmitReceipt,
    SubmitRejected,
)
from .spec import ExecutionMode, JobSpec, StorageMethod

# submit faults
AMBIGUOUS_CREATED = "ambiguous_created"          # timed out, but the instance exists
AMBIGUOUS_NOT_CREATED = "ambiguous_not_created"  # timed out, nothing was created
OUT_OF_STOCK = "out_of_stock"
QUOTA = "quota"
ERROR = "error"


def running(*succeeded: int, cost: float = 0.0, burn: float = 0.0, total: int = 0,
            durable: bool = True) -> Observation:
    shards = {i: ShardStatus.SUCCEEDED if i in succeeded else ShardStatus.RUNNING for i in range(total)}
    return Observation(ProviderStatus.RUNNING, shards, cost, burn, outputs_durable=durable)


def finished(total: int, failed: Sequence[int] = (), cost: float = 0.0) -> Observation:
    shards = {i: ShardStatus.FAILED if i in failed else ShardStatus.SUCCEEDED for i in range(total)}
    return Observation(ProviderStatus.SUCCEEDED, shards, cost)


@dataclass
class FakeProvider:
    name: str = "fake"
    timelines: List[List[Observation]] = field(default_factory=list)  # one per submit that succeeds
    submit_faults: List[Optional[str]] = field(default_factory=list)  # consumed per submit call
    teardown_failures: int = 0
    collect_unverified: Sequence[int] = ()
    collect_errors: Dict[int, int] = field(default_factory=dict)  # shard -> times collect raises first
    checkpoint_error: bool = False
    manifest: Optional[CapabilityManifest] = None
    calls: List[str] = field(default_factory=list)
    _live: Dict[str, ResourceRef] = field(default_factory=dict)
    _by_attempt: Dict[str, List[Observation]] = field(default_factory=dict)
    _resource_attempt: Dict[str, str] = field(default_factory=dict)
    _seq: int = 0

    def capabilities(self) -> CapabilityManifest:
        return self.manifest or CapabilityManifest(
            provider=self.name,
            modes=frozenset(ExecutionMode),
            storage=frozenset(StorageMethod),
            gpu_classes=frozenset({"A100", "L4"}),
            regions=("fake-1",),
            supports_spot=True,
        )

    def plan(self, spec: JobSpec) -> Plan:
        pl = spec.placement
        return Plan(self.name, pl.mode, pl.region, pl.instance_type)

    def _create(self, ctx: AttemptContext) -> ResourceRef:
        self._seq += 1
        ref = ResourceRef(self.name, "instance", f"{self.name}-r{self._seq}", ctx.spec.placement.region,
                          dict(ctx.tags))
        self._live[ref.resource_id] = ref
        self._resource_attempt[ref.resource_id] = ctx.attempt_id
        timeline = self.timelines.pop(0) if self.timelines else [Observation(ProviderStatus.SUCCEEDED)]
        self._by_attempt[ctx.attempt_id] = list(timeline)
        return ref

    def submit(self, ctx: AttemptContext) -> SubmitReceipt:
        self.calls.append(f"submit:{ctx.attempt_no}")
        fault = self.submit_faults.pop(0) if self.submit_faults else None
        if fault == AMBIGUOUS_CREATED:
            self._create(ctx)
            raise AmbiguousSubmit("timed out after the request was sent")
        if fault == AMBIGUOUS_NOT_CREATED:
            raise AmbiguousSubmit("connection dropped")
        if fault == OUT_OF_STOCK:
            raise OutOfStock("no capacity")
        if fault == QUOTA:
            raise QuotaExceeded("GPU quota is 0", "https://example.invalid/quota")
        if fault == ERROR:
            raise SubmitRejected("bad request")
        return SubmitReceipt((self._create(ctx),))

    def observe(self, ctx: AttemptContext, resources: Sequence[ResourceRef]) -> Observation:
        self.calls.append(f"observe:{ctx.attempt_no}")
        if not any(r.resource_id in self._live for r in resources):
            return Observation(ProviderStatus.NOT_FOUND)
        timeline = self._by_attempt.get(ctx.attempt_id) or [Observation(ProviderStatus.SUCCEEDED)]
        obs = timeline.pop(0) if len(timeline) > 1 else timeline[0]
        self._by_attempt[ctx.attempt_id] = timeline
        return obs

    def collect(self, ctx: AttemptContext, shard_index: int) -> CollectResult:
        self.calls.append(f"collect:{shard_index}")
        if self.collect_errors.get(shard_index, 0) > 0:
            self.collect_errors[shard_index] -= 1
            raise ConnectionError("download endpoint unavailable")
        verified = shard_index not in self.collect_unverified
        return CollectResult(shard_index, (f"out/{ctx.job_id}/shard{shard_index}.bin",), verified)

    def checkpoint(self, ctx: AttemptContext) -> None:
        self.calls.append("checkpoint")
        if self.checkpoint_error:
            raise TimeoutError("checkpoint endpoint did not answer")

    def teardown(self, resources: Sequence[ResourceRef]) -> bool:
        self.calls.append("teardown")
        if self.teardown_failures > 0:
            self.teardown_failures -= 1
            return False
        for r in resources:
            self._live.pop(r.resource_id, None)
        return True

    def list_owned_resources(self, owner: str) -> List[ResourceRef]:
        return [r for r in self._live.values() if r.tags.get(TAG_OWNER) == owner]

    def billable(self) -> Mapping[str, ResourceRef]:
        return dict(self._live)

    def preempt_all(self) -> None:
        """Simulate the provider reclaiming every instance."""
        self._live.clear()


class FakeObjectStore:
    """In-memory bucket; presigned URLs are opaque strings carrying op, key and expiry."""

    def __init__(self, name: str = "fake-bucket", region_bound: bool = False, clock=lambda: 0.0):
        self.name, self.region_bound, self._clock = name, region_bound, clock
        self.objects: Dict[str, bytes] = {}
        self.puts: List[str] = []

    def exists(self, key: str) -> bool:
        return key in self.objects

    def put_file(self, key: str, local_path: str) -> None:
        with open(local_path, "rb") as fh:
            self.objects[key] = fh.read()
        self.puts.append(key)

    def put_bytes(self, key: str, data: bytes) -> None:  # what a worker does through a PUT url
        self.objects[key] = data

    def presign_get(self, key: str, ttl_s: int) -> str:
        return f"fake://{self.name}/{key}?op=get&exp={int(self._clock() + ttl_s)}"

    def presign_put(self, key: str, ttl_s: int) -> str:
        return f"fake://{self.name}/{key}?op=put&exp={int(self._clock() + ttl_s)}"

    def read_range(self, key: str, start: int) -> bytes:
        return self.objects[key][start:]

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def list(self, prefix: str):
        from .storage.base import ObjectInfo

        return [ObjectInfo(k, len(v), 0.0) for k, v in self.objects.items() if k.startswith(prefix)]


class FakeSyncRemote:
    def __init__(self, name: str = "Dropbox", supports_temp_links: bool = True):
        self.name, self.supports_temp_links = name, supports_temp_links
        self.files: Dict[str, bytes] = {}

    def temp_download_link(self, path: str, ttl_s: int) -> str:
        return f"remote://{self.name}/{path}?op=get&ttl={ttl_s}"

    def temp_upload_link(self, path: str, ttl_s: int) -> str:
        return f"remote://{self.name}/{path}?op=put&ttl={ttl_s}"

    def exists(self, path: str) -> bool:
        return path in self.files

    def upload(self, local_path: str, path: str) -> None:
        with open(local_path, "rb") as fh:
            self.files[path] = fh.read()

    def read(self, path: str, offset: int) -> bytes:
        return self.files.get(path, b"")[offset:]

    def copy_from(self, store, key: str, path: str) -> None:
        self.files[path] = store.read_range(key, 0)


def accept_unchecked(spec: JobSpec, reserve_usd: float = 0.0, capability_override: bool = False):
    """Tests of the engine alone: skip preflight. Production code goes through CloudJobService."""
    from .acceptance import issue

    return issue(spec, reserve_usd, capability_override, ())

