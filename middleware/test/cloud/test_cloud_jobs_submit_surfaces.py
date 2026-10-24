"""Tests verifying origin-tab and Request Builder JobSpec parity (#826, #850)."""

from __future__ import annotations

from middleware.src.cloud.cost import ComputePrice, PriceCatalogue
from middleware.src.cloud.preflight.pipeline import run_preflight
from middleware.src.cloud.risk.engine import Severity
from middleware.src.cloud.settings import CloudSettings
from middleware.src.cloud.spec import (
    DataClass,
    ExecutionMode,
    JobSpec,
    Limits,
    Placement,
    Resources,
    ShardSpec,
    StorageMethod,
    WorkloadKind,
)


def _catalogue() -> PriceCatalogue:
    return PriceCatalogue([ComputePrice("runpod", "*", "managed_batch", "cpu", 1.0, last_verified="2026-10-01")])


def test_request_builder_job_spec_roundtrip():
    """Verify that a JobSpec constructed with Request Builder fields validates and roundtrips."""
    spec = JobSpec(
        job_id="cj-builder-01",
        kind=WorkloadKind.EXTRACT,
        placement=Placement(provider="runpod", region="us-central1", mode=ExecutionMode.MANAGED_BATCH),
        shards=(ShardSpec(0, {"file": "a.png"}), ShardSpec(1, {"file": "b.png"})),
        resources=Resources(vcpu=2.0, memory_gb=4.0),
        limits=Limits(max_runtime_s=3600, max_spend_usd=10.0),
        data_class=DataClass.PRIVATE,
        storage=StorageMethod.BUCKET,
        image="ghcr.io/image-toolkit/worker@sha256:7b28c894e63412356c9a7516fbc82b3a6ef4e11234567890abcdef1234567890",
    )
    spec.validate()

    serialized = spec.to_dict()
    deserialized = JobSpec.from_dict(serialized)
    assert deserialized == spec

    report = run_preflight(spec, catalogue=_catalogue(), settings=CloudSettings())
    assert not report.blocking
    assert report.ok_to_submit(report.needs_ack)


def test_convert_origin_tab_job_spec_parity():
    """Verify JobSpec generated from Convert origin tab matches engine expectations."""
    spec_dict = {
        "job_id": "cj-convert-01",
        "kind": "extract",
        "placement": {
            "provider": "runpod",
            "region": "us-central1",
            "mode": "managed_batch",
        },
        "shards": [
            {"index": 0, "params": {"file_path": "/tmp/1.webp", "output_format": "png"}, "inputs": []},
            {"index": 1, "params": {"file_path": "/tmp/2.webp", "output_format": "png"}, "inputs": []},
        ],
        "resources": {"vcpu": 2.0, "memory_gb": 4.0, "disk_gb": 20.0},
        "limits": {"max_runtime_s": 3600, "max_spend_usd": 10.0, "spot_allowed": False},
        "data_class": "private",
        "storage": "bucket",
        "image": "ghcr.io/image-toolkit/worker@sha256:7b28c894e63412356c9a7516fbc82b3a6ef4e11234567890abcdef1234567890",
        "params": {"action": "convert", "output_format": "png", "files_count": 2},
    }
    spec = JobSpec.from_dict(spec_dict)
    spec.validate()
    assert spec.kind == WorkloadKind.EXTRACT
    assert len(spec.shards) == 2

    sheet = run_preflight(spec, catalogue=_catalogue(), settings=CloudSettings()).sheet()
    assert sheet["job_id"] == "cj-convert-01"
    assert sheet["kind"] == "extract"
    assert sheet["provider"] == "runpod"
    assert sheet["shards"] == 2


def test_preflight_risk_feedback_blocks_unallowlisted_sensitive_provider():
    """Verify that preflight risk detection identifies sensitive data sent to unallowlisted providers."""
    spec = JobSpec(
        job_id="cj-sensitive-01",
        kind=WorkloadKind.EXTRACT,
        placement=Placement(provider="untrusted_cloud", region="us-central1", mode=ExecutionMode.MANAGED_BATCH),
        shards=(ShardSpec(0),),
        data_class=DataClass.SENSITIVE,
        storage=StorageMethod.CLOUD_SYNC,
        image="ghcr.io/image-toolkit/worker@sha256:7b28c894e63412356c9a7516fbc82b3a6ef4e11234567890abcdef1234567890",
    )
    spec.validate()

    settings = CloudSettings(sensitive_allowlist=("gcp", "aws"))
    report = run_preflight(spec, catalogue=_catalogue(), settings=settings)
    assert any(i.severity == Severity.BLOCK for i in report.issues)
    assert not report.ok_to_submit()
