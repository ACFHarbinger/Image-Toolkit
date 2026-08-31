"""CloudExtractionDispatcher — upload → adapter → download → usage row."""

from __future__ import annotations

import pytest
from backend.src.web.cloud.compute import (
    CloudExtractionDispatcher,
    CloudRunResult,
    UsageStore,
)


class _FakeGCS:
    def __init__(self):
        self.uploads = []
        self.downloads = []

    def upload_file(self, local_path, bucket, object_name):
        self.uploads.append((local_path, bucket, object_name))
        return f"gs://{bucket}/{object_name}"

    def download_file(self, gs_uri, local_path):
        self.downloads.append((gs_uri, local_path))
        with open(local_path, "w") as fh:
            fh.write("payload")
        return local_path


class _FakeAdapter:
    name = "gcd"

    def __init__(self, result):
        self._result = result
        self.jobs = []

    def run(self, job):
        self.jobs.append(job)
        return self._result


_CFG = {
    "type": "gif", "video_path": "/videos/clip.mp4",
    "start_ms": 1000, "end_ms": 3000, "fps": 24,
    "target_resolution": (640, 360),
}


@pytest.fixture
def store(tmp_path):
    return UsageStore(tmp_path / "cloud_usage.jsonl")


def test_happy_path_uploads_runs_downloads_and_records(tmp_path, store):
    out = tmp_path / "out"
    out.mkdir()
    result = CloudRunResult(
        job_id="job-x", provider="gcd", status="success",
        output_uris=["gs://res/cloud-jobs/job-x/clip.gif"],
        usage={"job_id": "job-x", "provider": "gcd", "task": "extract_gif",
               "status": "success", "duration_seconds": 5.5,
               "peak_rss_kib": 120_000},
    )
    gcs = _FakeGCS()
    adapter = _FakeAdapter(result)
    disp = CloudExtractionDispatcher(
        adapter, source_bucket="itk-src", output_dir=str(out),
        gcs=gcs, usage_store=store,
    )

    res = disp.dispatch(_CFG, job_id="job-x")

    assert res.ok
    # source uploaded once, to the source bucket, under the job prefix
    assert gcs.uploads == [("/videos/clip.mp4", "itk-src", "cloud-jobs/job-x/source.mp4")]
    # the job the adapter saw carries the wire schema
    sent = adapter.jobs[0].to_job_json()
    assert sent["mode"] == "gif" and sent["source_uri"] == "gs://itk-src/cloud-jobs/job-x/source.mp4"
    assert sent["target_size"] == [640, 360]
    # output pulled back locally
    assert res.local_paths == [str(out / "clip.gif")]
    assert (out / "clip.gif").read_text() == "payload"
    # usage row persisted for the Dashboards tab
    rows = store.load_rows()
    assert len(rows) == 1 and rows[0].job_id == "job-x" and rows[0].duration_seconds == 5.5


def test_gs_source_is_not_re_uploaded(tmp_path, store):
    out = tmp_path / "out"
    out.mkdir()
    gcs = _FakeGCS()
    adapter = _FakeAdapter(CloudRunResult("j", "gcd", "success", output_uris=[]))
    disp = CloudExtractionDispatcher(
        adapter, source_bucket="b", output_dir=str(out), gcs=gcs, usage_store=store
    )
    res = disp.dispatch({**_CFG, "video_path": "gs://already/there.mp4"}, job_id="j")
    assert res.ok
    assert gcs.uploads == []
    assert adapter.jobs[0].to_job_json()["source_uri"] == "gs://already/there.mp4"


def test_adapter_error_is_reported_and_still_records_usage(tmp_path, store):
    out = tmp_path / "out"
    out.mkdir()
    adapter = _FakeAdapter(
        CloudRunResult("j2", "gcd", "error", error="bad range",
                       usage={"job_id": "j2", "provider": "gcd", "status": "error"})
    )
    disp = CloudExtractionDispatcher(
        adapter, source_bucket="b", output_dir=str(out), gcs=_FakeGCS(), usage_store=store
    )
    res = disp.dispatch(_CFG, job_id="j2")
    assert not res.ok
    assert "bad range" in res.error
    assert res.local_paths == []
    assert store.load_rows()[0].status == "error"


def test_missing_source_fails_fast(tmp_path, store):
    disp = CloudExtractionDispatcher(
        _FakeAdapter(CloudRunResult("j", "gcd", "success")),
        source_bucket="b", output_dir=str(tmp_path), gcs=_FakeGCS(), usage_store=store,
    )
    res = disp.dispatch({"type": "gif", "start_ms": 0, "end_ms": 1000})
    assert not res.ok
    assert "no source" in res.error


def test_usage_store_round_trips_and_skips_corrupt_lines(tmp_path):
    from backend.src.web.cloud.compute import UsageRow, aggregate_usage_rows

    store = UsageStore(tmp_path / "u.jsonl")
    store.append(UsageRow.from_mapping(
        {"job_id": "a", "provider": "gcd", "task": "extract_gif",
         "status": "success", "duration_seconds": 3}
    ))
    (tmp_path / "u.jsonl").open("a").write("not json\n")
    store.append(UsageRow.from_mapping(
        {"job_id": "b", "provider": "gcd", "status": "error"}
    ))

    rows = store.load_rows()
    assert [r.job_id for r in rows] == ["a", "b"]
    summary = aggregate_usage_rows(rows)
    assert summary.total_jobs == 2 and summary.failures == 1
