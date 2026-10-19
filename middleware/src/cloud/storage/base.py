"""Staging storage: one interface over buckets, provider volumes and Cloud Sync (#833).

Workers only ever see short-lived presigned URLs, never credentials. Inputs
are content-addressed (``cas/<sha256>``), so a file is uploaded once and
reused by every job and shard that needs it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol, Tuple, runtime_checkable

from ..spec import InputBlob, JobSpec, StorageMethod


class StorageUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class ObjectInfo:
    key: str
    size_bytes: int
    modified: float


@runtime_checkable
class ObjectStore(Protocol):
    """A bucket-like store (S3, GCS, Azure Blob, R2, or a provider volume gateway)."""

    name: str
    region_bound: bool

    def exists(self, key: str) -> bool: ...

    def put_file(self, key: str, local_path: str) -> None: ...

    def presign_get(self, key: str, ttl_s: int) -> str: ...

    def presign_put(self, key: str, ttl_s: int) -> str: ...

    def read_range(self, key: str, start: int) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def list(self, prefix: str) -> List[ObjectInfo]: ...


def input_key(sha256: str) -> str:
    return f"cas/{sha256}"


def output_key(job_id: str, shard: int) -> str:
    return f"jobs/{job_id}/out/shard-{shard:05d}.tar"


def events_key(job_id: str) -> str:
    return f"jobs/{job_id}/events.jsonl"


def job_prefix(job_id: str) -> str:
    return f"jobs/{job_id}/"


@dataclass(frozen=True)
class Upload:
    blob: InputBlob
    key: str


@dataclass(frozen=True)
class ShardUrls:
    shard: int
    inputs: Dict[str, str]  # sha256 -> GET url
    output_put: str


@dataclass(frozen=True)
class StagingManifest:
    """What the daemon uploads, and the URLs the worker is given. No credentials inside."""

    job_id: str
    method: StorageMethod
    path_description: str
    uploads: Tuple[Upload, ...]
    shards: Tuple[ShardUrls, ...]
    events_put: str
    reused_bytes: int = 0
    upload_bytes: int = 0
    finalize_to_remote: Optional[str] = None  # Cloud Sync: copy outputs back here after collection
    notes: Tuple[str, ...] = field(default_factory=tuple)

    def worker_payload(self) -> Dict[str, object]:
        return {
            "job_id": self.job_id,
            "events_put": self.events_put,
            "shards": [{"shard": s.shard, "inputs": dict(s.inputs), "output_put": s.output_put}
                       for s in self.shards],
        }


@runtime_checkable
class StagingStrategy(Protocol):
    method: StorageMethod

    def describe(self) -> str: ...

    def manifest(self, spec: JobSpec, ttl_s: int) -> StagingManifest: ...

    def stage(self, manifest: StagingManifest) -> int:
        """Upload what's missing; returns bytes uploaded. Safe to repeat."""
        ...

    def read_events(self, job_id: str, offset: int) -> bytes: ...

    def cleanup_job(self, job_id: str) -> None: ...
