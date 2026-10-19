"""Bucket, provider-native and Cloud Sync staging strategies (#833)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol, Tuple, runtime_checkable

from ..spec import JobSpec, StorageMethod
from .base import (
    ObjectStore,
    ShardUrls,
    StagingManifest,
    StorageUnavailable,
    Upload,
    events_key,
    input_key,
    job_prefix,
    output_key,
)


def _build(spec: JobSpec, store: ObjectStore, method: StorageMethod, ttl_s: int, describe: str,
           finalize_to: Optional[str] = None, notes: Tuple[str, ...] = ()) -> StagingManifest:
    uploads: List[Upload] = []
    reused = upload_bytes = 0
    for blob in spec.inputs.values():
        key = input_key(blob.sha256)
        if store.exists(key):
            reused += blob.size_bytes
        else:
            uploads.append(Upload(blob, key))
            upload_bytes += blob.size_bytes
    shards = tuple(
        ShardUrls(s.index, {sha: store.presign_get(input_key(sha), ttl_s) for sha in s.inputs},
                  store.presign_put(output_key(spec.job_id, s.index), ttl_s))
        for s in spec.shards
    )
    return StagingManifest(spec.job_id, method, describe, tuple(uploads), shards,
                           store.presign_put(events_key(spec.job_id), ttl_s), reused, upload_bytes,
                           finalize_to, notes)


@dataclass
class _ObjectStoreStaging:
    store: ObjectStore
    method: StorageMethod = StorageMethod.BUCKET

    def describe(self) -> str:
        return f"{self.store.name} with presigned URLs"

    def manifest(self, spec: JobSpec, ttl_s: int) -> StagingManifest:
        return _build(spec, self.store, self.method, ttl_s, self.describe())

    def stage(self, manifest: StagingManifest) -> int:
        sent = 0
        for up in manifest.uploads:
            if self.store.exists(up.key):
                continue
            if not up.blob.local_path:
                raise StorageUnavailable(f"input {up.blob.name} has no local file to upload")
            self.store.put_file(up.key, up.blob.local_path)
            sent += up.blob.size_bytes
        return sent

    def read_events(self, job_id: str, offset: int) -> bytes:
        if not self.store.exists(events_key(job_id)):
            return b""
        return self.store.read_range(events_key(job_id), offset)

    def cleanup_job(self, job_id: str) -> None:
        for obj in self.store.list(job_prefix(job_id)):
            self.store.delete(obj.key)


class BucketStaging(_ObjectStoreStaging):
    def __init__(self, store: ObjectStore):
        super().__init__(store, StorageMethod.BUCKET)


class ProviderNativeStaging(_ObjectStoreStaging):
    """A provider's own storage (e.g. a network volume behind a gateway); region-bound."""

    def __init__(self, store: ObjectStore):
        super().__init__(store, StorageMethod.PROVIDER_NATIVE)

    def describe(self) -> str:
        bound = ", region-bound" if self.store.region_bound else ""
        return f"{self.store.name} (provider storage{bound})"


@runtime_checkable
class SyncRemote(Protocol):
    """A Cloud Sync remote (Google Drive, OneDrive, Dropbox). The daemon holds its OAuth tokens."""

    name: str
    supports_temp_links: bool

    def temp_download_link(self, path: str, ttl_s: int) -> str: ...

    def temp_upload_link(self, path: str, ttl_s: int) -> str: ...

    def exists(self, path: str) -> bool: ...

    def upload(self, local_path: str, path: str) -> None: ...

    def read(self, path: str, offset: int) -> bytes: ...

    def copy_from(self, store: ObjectStore, key: str, path: str) -> None: ...


class _RemoteAsStore:
    """Adapts a remote with its own temp links to the ObjectStore shape."""

    def __init__(self, remote: SyncRemote, root: str):
        self.remote, self.root = remote, root.rstrip("/")
        self.name, self.region_bound = remote.name, False

    def _p(self, key: str) -> str:
        return f"{self.root}/{key}"

    def exists(self, key: str) -> bool:
        return self.remote.exists(self._p(key))

    def put_file(self, key: str, local_path: str) -> None:
        self.remote.upload(local_path, self._p(key))

    def presign_get(self, key: str, ttl_s: int) -> str:
        return self.remote.temp_download_link(self._p(key), ttl_s)

    def presign_put(self, key: str, ttl_s: int) -> str:
        return self.remote.temp_upload_link(self._p(key), ttl_s)

    def read_range(self, key: str, start: int) -> bytes:
        return self.remote.read(self._p(key), start)

    def delete(self, key: str) -> None:  # job folders on the user's remote are theirs to keep
        return None

    def list(self, prefix: str):
        return []


class CloudSyncStaging:
    """Remote's own short-lived links where it has them; otherwise a transit bucket, emptied after collection."""

    method = StorageMethod.CLOUD_SYNC

    def __init__(self, remote: SyncRemote, root: str = "Image-Toolkit/Cloud Jobs",
                 transit: Optional[ObjectStore] = None):
        self.remote, self.root, self.transit = remote, root, transit
        if not remote.supports_temp_links and transit is None:
            raise StorageUnavailable(f"{remote.name} has no temporary upload links; configure a transit bucket")
        self._direct = _RemoteAsStore(remote, root) if remote.supports_temp_links else None

    def describe(self) -> str:
        if self._direct is not None:
            return f"{self.remote.name} temporary links"
        return f"transit bucket {self.transit.name}, then {self.remote.name} (transit emptied after collection)"

    def manifest(self, spec: JobSpec, ttl_s: int) -> StagingManifest:
        if self._direct is not None:
            return _build(spec, self._direct, self.method, ttl_s, self.describe())
        return _build(spec, self.transit, self.method, ttl_s, self.describe(),
                      finalize_to=f"{self.root}/{spec.job_id}", notes=("via transit bucket",))

    def stage(self, manifest: StagingManifest) -> int:
        store = self._direct or self.transit
        return _ObjectStoreStaging(store).stage(manifest)

    def read_events(self, job_id: str, offset: int) -> bytes:
        return _ObjectStoreStaging(self._direct or self.transit).read_events(job_id, offset)

    def finalize(self, manifest: StagingManifest) -> int:
        """After verified collection: copy outputs to the remote and empty the transit bucket."""
        if self._direct is not None or manifest.finalize_to_remote is None:
            return 0
        copied = 0
        for s in manifest.shards:
            key = output_key(manifest.job_id, s.shard)
            if self.transit.exists(key):
                self.remote.copy_from(self.transit, key, f"{manifest.finalize_to_remote}/{key.rsplit('/', 1)[-1]}")
                copied += 1
        self.cleanup_job(manifest.job_id)
        return copied

    def cleanup_job(self, job_id: str) -> None:
        if self.transit is not None:
            _ObjectStoreStaging(self.transit).cleanup_job(job_id)
