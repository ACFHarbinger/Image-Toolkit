"""Preflight pipeline: order, secret scan, weight classes, quota probe, sheet (#831)."""

from __future__ import annotations

from backend.src.cloud.adapter import QuotaExceeded
from backend.src.cloud.cost import ComputePrice, PriceCatalogue
from backend.src.cloud.fakes import FakeProvider
from backend.src.cloud.preflight import (
    KEEP,
    REDACTED,
    STAGES,
    STRIP,
    WeightClass,
    run_preflight,
    scan_workflow_secrets,
)
from backend.src.cloud.settings import CloudSettings
from backend.src.cloud.spec import (
    ExecutionMode,
    InputBlob,
    JobSpec,
    Placement,
    ShardSpec,
    WorkloadKind,
)

CAT = PriceCatalogue([ComputePrice("fake", "*", "instance", "cpu", 1.0, last_verified="2026-10-01")])
WORKFLOW = {
    "3": {"class_type": "KSampler", "inputs": {"seed": 7, "steps": 20}},
    "9": {"class_type": "SomeAPINode", "inputs": {"api_key": "sk-abcdefghijklmnopqrstuv", "prompt": "a cat"}},
    "11": {"class_type": "Loader", "inputs": {"url": "https://user:hunter2@example.com/model"}},
}
W_SHA = "f" * 64


def _spec(**params):
    return JobSpec(WorkloadKind.COMFY_BATCH, Placement("fake", "fake-1", ExecutionMode.INSTANCE),
                   (ShardSpec(0, inputs=(W_SHA,)),), inputs={W_SHA: InputBlob(W_SHA, 100, "w.safetensors")},
                   params={"expected_runtime_s": 60, **params})


def _run(spec, **kw):
    return run_preflight(spec, catalogue=CAT, settings=CloudSettings(), adapter=FakeProvider(), **kw)


def test_all_stages_run_in_order_and_a_clean_job_only_needs_acks():
    rep = _run(_spec())
    assert rep.stages_run == STAGES
    assert not rep.blocking
    assert not rep.ok_to_submit()  # private-data warning is fine, but reduced protection needs an ack
    assert rep.ok_to_submit(rep.needs_ack)
    sheet = rep.sheet()
    assert sheet["provider"] == "fake" and not sheet["estimate_known"] and sheet["staging_bytes"] == 100


def test_validation_error_stops_before_anything_else():
    rep = _run(JobSpec(WorkloadKind.EXTRACT, Placement("fake", "x", ExecutionMode.INSTANCE), ()))
    assert rep.stages_run == ("validate",) and rep.blocking


def test_secret_scan_blocks_until_each_field_is_stripped_or_kept():
    assert {(f.node_id, f.field) for f in scan_workflow_secrets(WORKFLOW)} == {("9", "api_key"), ("11", "url")}
    rep = _run(_spec(workflow=WORKFLOW))
    assert len([i for i in rep.blocking if i.stage == "secrets"]) == 2
    assert rep.redacted_workflow["9"]["inputs"]["api_key"] == REDACTED
    assert rep.redacted_workflow["3"]["inputs"]["steps"] == 20

    rep = _run(_spec(workflow=WORKFLOW), secret_decisions={("9", "api_key"): STRIP, ("11", "url"): KEEP})
    assert not [i for i in rep.blocking if i.stage == "secrets"]
    sent = rep.spec.params["workflow"]
    assert sent["9"]["inputs"]["api_key"] == "" and sent["11"]["inputs"]["url"].startswith("https://user")
    assert WORKFLOW["9"]["inputs"]["api_key"].startswith("sk-")  # caller's graph untouched


def test_ui_format_graph_is_scanned_too():
    ui = {"nodes": [{"id": 4, "widgets_values": ["hf_" + "a" * 30, 512]}]}
    assert [(f.node_id, f.field) for f in scan_workflow_secrets(ui)] == [("4", "widgets_values[0]")]


def test_weight_classes_block_warn_and_exclude():
    spec = _spec(weights={W_SHA: "w.safetensors"})
    rep = _run(spec)
    assert f"weight:{W_SHA}" in rep.needs_ack  # unknown hash: warn + ack
    rep = _run(spec, weight_classes={W_SHA: WeightClass.ALLOW})
    assert f"weight:{W_SHA}" not in rep.needs_ack
    rep = _run(spec, weight_classes={W_SHA: WeightClass.BLOCK})
    assert rep.excluded_weights == (W_SHA,) and W_SHA not in rep.spec.inputs
    assert any(i.stage == "weights" for i in rep.blocking)


def test_quota_probe_failure_blocks_with_link():
    class Quota(FakeProvider):
        def probe_quota(self, spec):
            raise QuotaExceeded("GPU quota is 0", "https://console.example/quotas")

    rep = run_preflight(_spec(), catalogue=CAT, settings=CloudSettings(), adapter=Quota())
    msg = next(i.message for i in rep.blocking if i.stage == "quota")
    assert "https://console.example/quotas" in msg


def test_estimates_off_skips_costing():
    rep = run_preflight(_spec(), catalogue=CAT, settings=CloudSettings(estimates_enabled=False),
                        adapter=FakeProvider())
    assert not rep.estimate.known
    assert "pol.no_estimate" not in rep.needs_ack


def test_invalid_secret_decision_does_not_authorize_upload():
    rep = _run(_spec(workflow=WORKFLOW), secret_decisions={("9", "api_key"): "typo", ("11", "url"): STRIP})
    assert any(i.stage == "secrets" for i in rep.blocking)
    assert not rep.ok_to_submit(rep.needs_ack)
