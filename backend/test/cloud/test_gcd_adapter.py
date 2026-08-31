"""GCDCloudRunAdapter — POST /jobs dispatch, fully mocked HTTP."""

from __future__ import annotations

import pytest
from backend.src.web.cloud.compute import (
    CloudflareAdapter,
    CloudJob,
    GCDCloudRunAdapter,
    OracleAdapter,
    get_adapter,
)


class _Resp:
    def __init__(self, status, payload, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text or str(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class _FakeSession:
    def __init__(self, resp):
        self._resp = resp
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append(("POST", url, json, headers))
        return self._resp

    def get(self, url, headers=None, timeout=None):
        self.calls.append(("GET", url, None, headers))
        return _Resp(200, {"status": "ok"})


_JOB = CloudJob(source_uri="gs://in/vid.mp4", mode="gif", start_ms=0, end_ms=2000, job_id="job-1")


def test_run_posts_job_json_and_maps_usage_row():
    usage = {
        "job_id": "job-1", "provider": "gcd", "task": "extract_gif",
        "status": "success", "duration_seconds": 4.2,
        "output_uris": ["gs://res/cloud-jobs/job-1/clip.gif"],
    }
    fake = _FakeSession(_Resp(200, usage))
    adapter = GCDCloudRunAdapter("https://svc.run.app/", session=fake)

    result = adapter.run(_JOB)

    assert fake.calls[0][1] == "https://svc.run.app/jobs"
    assert fake.calls[0][2]["mode"] == "gif"  # to_job_json payload
    assert result.ok
    assert result.output_uris == ["gs://res/cloud-jobs/job-1/clip.gif"]
    assert result.usage["duration_seconds"] == 4.2


def test_run_adds_bearer_when_id_token_provider_given():
    fake = _FakeSession(_Resp(200, {"status": "success"}))
    adapter = GCDCloudRunAdapter(
        "https://svc.run.app", session=fake, id_token_provider=lambda: "tok-123"
    )
    adapter.run(_JOB)
    assert fake.calls[0][3]["Authorization"] == "Bearer tok-123"


def test_run_non_200_is_an_error_result():
    fake = _FakeSession(_Resp(400, {"status": "error", "error": "bad range"}))
    adapter = GCDCloudRunAdapter("https://svc.run.app", session=fake)
    result = adapter.run(_JOB)
    assert not result.ok
    assert "bad range" in result.error


def test_run_network_failure_is_an_error_result():
    import requests

    class _Boom(_FakeSession):
        def post(self, *a, **k):
            raise requests.ConnectionError("dns")

    adapter = GCDCloudRunAdapter("https://svc.run.app", session=_Boom(None))
    result = adapter.run(_JOB)
    assert not result.ok
    assert "request failed" in result.error


def test_stub_adapters_raise_not_implemented():
    for adapter in (CloudflareAdapter(), OracleAdapter()):
        assert adapter.healthz() is False
        with pytest.raises(NotImplementedError, match="not implemented yet"):
            adapter.run(_JOB)


def test_get_adapter_dispatch():
    assert isinstance(get_adapter("gcd", service_url="https://x.run.app"), GCDCloudRunAdapter)
    assert isinstance(get_adapter("cloudflare"), CloudflareAdapter)
    assert isinstance(get_adapter("oracle"), OracleAdapter)
    with pytest.raises(ValueError, match="unknown cloud provider"):
        get_adapter("azure")
