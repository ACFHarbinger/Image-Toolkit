"""Tests for Cloud Jobs table and detail service (#848)."""

from __future__ import annotations

import io
from typing import Any

import pytest
from middleware.src.bridge.envelope import BridgeAppError
from middleware.src.services.cloud_jobs.jobs_service import job_detail, list_jobs
from middleware.src.sidecar.server import SidecarServer

MOCK_JOB_DATA: list[dict[str, Any]] = [
    {
        "job_id": "job-alpha",
        "kind": "batch",
        "title": "Batch convert 100 images",
        "state": "running",
        "provider": "aws",
        "created_at": 1729700000.0,
        "started_at": 1729700010.0,
        "ended_at": None,
        "cost_usd": 0.85,
        "shards_total": 5,
        "shards_done": 2,
        "events": [
            {"id": 1, "ts": 1729700000.0, "type": "created", "data": {"shards": 5}},
            {"id": 2, "ts": 1729700010.0, "type": "attempt", "data": {"attempt_no": 1}},
        ],
        "outputs": ["/data/out1.png", "/data/out2.png"],
        "logs": ["[info] batch started", "[info] shard 1 complete"],
        "metrics": {
            "gpu_util_pct": 88.0,
            "vram_used_mb": 12288.0,
            "peak_vcpu": 4.0,
        },
        "spend": {
            "cost_so_far_usd": 0.85,
            "reserved_usd": 2.50,
            "max_spend_usd": 5.00,
        },
        "daemon_status": {
            "lease_owner": "worker-1",
            "wal_depth": 1,
            "last_poll_ts": 1729700060.0,
        },
    },
    {
        "job_id": "job-beta",
        "kind": "train",
        "title": "Train LoRA character",
        "state": "completed",
        "provider": "runpod",
        "created_at": 1729690000.0,
        "started_at": 1729690010.0,
        "ended_at": 1729693600.0,
        "cost_usd": 3.40,
        "shards_total": 1,
        "shards_done": 1,
        "events": [],
        "outputs": ["/data/checkpoint.safetensors"],
        "logs": ["[info] training finished"],
        "metrics": {
            "gpu_util_pct": 98.5,
            "vram_used_mb": 24576.0,
            "peak_vcpu": 8.0,
        },
        "spend": {
            "cost_so_far_usd": 3.40,
            "reserved_usd": 3.40,
            "max_spend_usd": 4.00,
        },
        "daemon_status": {
            "lease_owner": "worker-2",
            "wal_depth": 0,
            "last_poll_ts": 1729693600.0,
        },
    },
]


def test_list_jobs_empty_or_none():
    assert list_jobs(None, {}) == {"jobs": []}
    assert list_jobs([], {}) == {"jobs": []}


def test_list_jobs_filters():
    res = list_jobs(MOCK_JOB_DATA, {})
    assert len(res["jobs"]) == 2

    res_running = list_jobs(MOCK_JOB_DATA, {"state": "running"})
    assert len(res_running["jobs"]) == 1
    assert res_running["jobs"][0]["job_id"] == "job-alpha"

    res_provider = list_jobs(MOCK_JOB_DATA, {"provider": "runpod"})
    assert len(res_provider["jobs"]) == 1
    assert res_provider["jobs"][0]["job_id"] == "job-beta"

    res_kind = list_jobs(MOCK_JOB_DATA, {"kind": "train"})
    assert len(res_kind["jobs"]) == 1
    assert res_kind["jobs"][0]["job_id"] == "job-beta"

    res_search = list_jobs(MOCK_JOB_DATA, {"search": "LoRA"})
    assert len(res_search["jobs"]) == 1
    assert res_search["jobs"][0]["job_id"] == "job-beta"


def test_job_detail_success():
    detail = job_detail(MOCK_JOB_DATA, {"job_id": "job-alpha"})
    assert detail["job_id"] == "job-alpha"
    assert detail["kind"] == "batch"
    assert detail["title"] == "Batch convert 100 images"
    assert detail["state"] == "running"
    assert detail["provider"] == "aws"
    assert len(detail["events"]) == 2
    assert len(detail["outputs"]) == 2
    assert len(detail["logs"]) == 2
    assert detail["metrics"]["gpu_util_pct"] == 88.0
    assert detail["spend"]["cost_so_far_usd"] == 0.85
    assert detail["daemon_status"]["lease_owner"] == "worker-1"


def test_job_detail_missing_id():
    with pytest.raises(BridgeAppError) as exc:
        job_detail(MOCK_JOB_DATA, {})
    assert exc.value.code == "bridge.invalid_request"


def test_job_detail_not_found():
    with pytest.raises(BridgeAppError) as exc:
        job_detail(MOCK_JOB_DATA, {"job_id": "unknown-job"})
    assert exc.value.code == "jobs.not_found"


def test_sidecar_server_dispatch_list_and_detail():
    server = SidecarServer(
        stdin=io.StringIO(),
        stdout=io.StringIO(),
        jobs_source=lambda: MOCK_JOB_DATA,
    )
    # Handshake
    hs = server.handle_frame(
        {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "system.handshake",
            "params": {
                "protocol": "image-toolkit-bridge",
                "client": {"name": "test", "version": "1.0.0"},
            },
        }
    )
    assert hs["result"]["protocol"] == "image-toolkit-bridge"

    # List jobs
    list_res = server.handle_frame(
        {
            "jsonrpc": "2.0",
            "id": "2",
            "method": "cloud_jobs.list",
            "params": {"state": "running"},
        }
    )
    assert len(list_res["result"]["jobs"]) == 1
    assert list_res["result"]["jobs"][0]["job_id"] == "job-alpha"

    # Detail
    detail_res = server.handle_frame(
        {
            "jsonrpc": "2.0",
            "id": "3",
            "method": "cloud_jobs.detail",
            "params": {"job_id": "job-alpha"},
        }
    )
    assert detail_res["result"]["job_id"] == "job-alpha"
    assert detail_res["result"]["metrics"]["gpu_util_pct"] == 88.0

    spec_payload = {
        "job_id": "job-test-1",
        "kind": "extract",
        "title": "Test job",
        "placement": {"provider": "fake", "region": "us-east-1", "mode": "instance"},
        "shards": [{"index": 0, "params": {}, "inputs": []}],
    }

    # Preview with fake service
    preview_res = server.handle_frame(
        {
            "jsonrpc": "2.0",
            "id": "4",
            "method": "cloud_jobs.preview",
            "params": {"spec": spec_payload},
        }
    )
    assert preview_res["result"]["available"] is True
    assert preview_res["result"]["provider"] == "fake"

    # Submit with fake service
    submit_res = server.handle_frame(
        {
            "jsonrpc": "2.0",
            "id": "5",
            "method": "cloud_jobs.submit",
            "params": {
                "spec": spec_payload,
                "acknowledged": ["pol.no_estimate", "pol.reduced_protection"],
            },
        }
    )
    assert submit_res["result"]["accepted"] is True
    assert submit_res["result"]["job_id"] == "job-test-1"
