"""Staging strategies, content-addressed reuse, events, Cloud Sync paths, retention (#833)."""

from __future__ import annotations

import pytest
from middleware.src.cloud.fakes import FakeObjectStore, FakeSyncRemote
from middleware.src.cloud.settings import CloudSettings
from middleware.src.cloud.sharding import blob_for_file, plan_extraction
from middleware.src.cloud.spec import ExecutionMode, JobSpec, Placement, StorageMethod, WorkloadKind
from middleware.src.cloud.storage import (
    BucketStaging,
    CloudSyncStaging,
    ObjectRole,
    ProviderNativeStaging,
    StorageUnavailable,
    StoredObject,
    events_key,
    output_key,
    plan_cleanup,
)

DAY = 86400.0


@pytest.fixture
def spec(tmp_path):
    files = []
    for i, data in enumerate((b"one", b"two", b"one")):  # third is a duplicate of the first
        p = tmp_path / f"v{i}.mp4"
        p.write_bytes(data)
        files.append(blob_for_file(str(p)))
    shards, inputs = plan_extraction(files, 1, {})
    return JobSpec(WorkloadKind.EXTRACT, Placement("gcp", "eu", ExecutionMode.MANAGED_BATCH), shards,
                   inputs=inputs, storage=StorageMethod.BUCKET)


def test_bucket_uploads_each_input_once_and_reuses_it(spec):
    store = FakeObjectStore()
    staging = BucketStaging(store)
    m = staging.manifest(spec, 3600)
    assert len(m.uploads) == 2 and m.upload_bytes == 6
    assert staging.stage(m) == 6 and staging.stage(m) == 0
    again = staging.manifest(spec, 3600)
    assert again.uploads == () and again.reused_bytes == 6
    payload = m.worker_payload()
    assert all(u.startswith("fake://") and "op=get" in u for s in payload["shards"] for u in s["inputs"].values())
    assert "secret" not in repr(payload).lower()


def test_events_are_read_from_an_offset(spec):
    store = FakeObjectStore()
    staging = BucketStaging(store)
    assert staging.read_events(spec.job_id, 0) == b""
    store.put_bytes(events_key(spec.job_id), b'{"step":1}\n{"step":2}\n')
    first = staging.read_events(spec.job_id, 0)
    assert staging.read_events(spec.job_id, len(first)) == b""
    store.put_bytes(events_key(spec.job_id), first + b'{"step":3}\n')
    assert staging.read_events(spec.job_id, len(first)) == b'{"step":3}\n'


def test_cloud_sync_uses_remote_temp_links_when_available(spec):
    remote = FakeSyncRemote("Dropbox", supports_temp_links=True)
    staging = CloudSyncStaging(remote)
    m = staging.manifest(spec, 600)
    assert m.path_description == "Dropbox temporary links"
    assert m.events_put.startswith("remote://Dropbox/") and m.finalize_to_remote is None
    staging.stage(m)
    assert len(remote.files) == 2


def test_cloud_sync_without_links_goes_through_transit_and_empties_it(spec):
    remote = FakeSyncRemote("Google Drive", supports_temp_links=False)
    with pytest.raises(StorageUnavailable, match="transit bucket"):
        CloudSyncStaging(remote)
    transit = FakeObjectStore("r2-transit")
    staging = CloudSyncStaging(remote, transit=transit)
    m = staging.manifest(spec, 600)
    assert "transit bucket r2-transit" in m.path_description
    for s in m.shards:
        transit.put_bytes(output_key(spec.job_id, s.shard), b"tar")
    assert staging.finalize(m) == len(m.shards)
    assert all(k.startswith("Image-Toolkit/Cloud Jobs/") for k in remote.files)
    assert not [k for k in transit.objects if k.startswith(f"jobs/{spec.job_id}/")]


def test_provider_native_describes_region_binding():
    assert "region-bound" in ProviderNativeStaging(FakeObjectStore("runpod-volume", region_bound=True)).describe()


def test_retention_plan():
    s = CloudSettings(staged_input_ttl_days=0, output_retention_days=7, cache_ttl_days=30, cache_budget_gb=1)
    now = 100 * DAY
    gb = 1024 ** 3
    objs = [
        StoredObject("in-done", ObjectRole.INPUT, 10, now, collected_at=now - 1),
        StoredObject("in-running", ObjectRole.INPUT, 10, now, refcount=1),
        StoredObject("out-old", ObjectRole.OUTPUT, 10, now, collected_at=now - 8 * DAY),
        StoredObject("out-new", ObjectRole.OUTPUT, 10, now, collected_at=now - 1 * DAY),
        StoredObject("out-uncollected", ObjectRole.OUTPUT, 10, now, job_ended_at=now - 9 * DAY),
        StoredObject("cache-stale", ObjectRole.CACHE, gb, now - 31 * DAY),
        StoredObject("cache-recent", ObjectRole.CACHE, gb // 2 + 1, now - 1),
        StoredObject("cache-older", ObjectRole.CACHE, gb // 2 + 1, now - 2 * DAY),
        StoredObject("cache-in-use", ObjectRole.CACHE, 5 * gb, now - 40 * DAY, refcount=1),
    ]
    gone = {d.key for d in plan_cleanup(objs, s, now)}
    assert gone == {"in-done", "out-old", "out-uncollected", "cache-stale", "cache-older"}
