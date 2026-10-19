"""Risk rules (#830) and the cost model (#832)."""

from __future__ import annotations

import datetime as dt
import re

import pytest
from middleware.src.cloud.adapter import CapabilityManifest
from middleware.src.cloud.cost import (
    AdmissionSnapshot,
    ComputePrice,
    EgressPrice,
    PriceCatalogue,
    StoragePrice,
    admission_blockers,
    budget_alert,
    calibration,
    cheaper_cross_region,
    estimate,
    rank_candidates,
)
from middleware.src.cloud.risk import Rule, RuleSet, Severity, build_context, load_seed
from middleware.src.cloud.settings import CloudSettings
from middleware.src.cloud.spec import (
    DataClass,
    ExecutionMode,
    InputBlob,
    JobSpec,
    Limits,
    Placement,
    Resources,
    ShardSpec,
    StorageMethod,
    WorkloadKind,
)

TODAY = dt.date(2026, 10, 19)
MANIFEST = CapabilityManifest(
    provider="gcp",
    modes=frozenset(ExecutionMode),
    storage=frozenset({StorageMethod.BUCKET}),
    gpu_classes=frozenset({"L4"}),
    regions=("europe-west1",),
    max_task_seconds={"managed_batch": 3600},
    supports_spot=True,
)
CAT = PriceCatalogue(
    [ComputePrice("gcp", "*", "managed_batch", "L4", 0.72, billing_increment_s=60, minimum_s=60,
                  startup_s=30, last_verified="2026-10-01"),
     ComputePrice("gcp", "*", "instance", "L4", 0.80, startup_s=120, ipv4_usd_per_hour=0.005,
                  last_verified="2026-08-01"),
     ComputePrice("gcp", "us-central1", "instance", "L4", 0.60, startup_s=120, last_verified="2026-10-01")],
    [EgressPrice("gcp", "internet", 0.12, "2026-10-01")],
    [StoragePrice("gcp", 0.02, "2026-10-01")],
)


def _spec(mode=ExecutionMode.MANAGED_BATCH, region="europe-west1", runtime=600.0, kind=WorkloadKind.EXTRACT,
          limits=None, **kw):
    return JobSpec(kind, Placement("gcp", region, mode), (ShardSpec(0),),
                   resources=Resources(gpu_class="L4", gpu_count=1), limits=limits or Limits(),
                   params={"expected_runtime_s": runtime, "expected_output_gb": 2.0},
                   inputs={"a" * 64: InputBlob("a" * 64, 1024 ** 3, "in.mp4")}, **kw)


_DEFAULTS = CloudSettings()


def _diag(spec, settings=_DEFAULTS, rules=None, mtd=0.0, manifest=MANIFEST):
    est = estimate(spec, CAT, today=TODAY)
    ctx = build_context(spec, manifest, est, settings, mtd)
    return (rules or RuleSet(load_seed())).evaluate(ctx, settings.warnings_enabled), ctx


def _leaf_fields(cond):
    if "all" in cond or "any" in cond:
        for c in cond.get("all", cond.get("any")):
            yield from _leaf_fields(c)
    elif "not" in cond:
        yield from _leaf_fields(cond["not"])
    else:
        yield cond["field"]
        if "ref" in cond:
            yield cond["ref"]


def test_seed_rules_reference_only_real_context_fields():
    _, ctx = _diag(_spec())
    for rule in load_seed():
        for f in _leaf_fields(rule.when):
            assert f in ctx, f"{rule.id} reads unknown field {f}"
        rendered = re.sub(r"\{[A-Za-z0-9_.]+\}", lambda m: str(ctx.get(m.group(0)[1:-1], m.group(0))), rule.message)
        assert "{" not in rendered, f"{rule.id}: unresolved placeholder in {rendered!r}"


def test_spot_is_greyed_out_for_non_resumable_and_warned_for_training():
    d, _ = _diag(_spec(limits=Limits(spot_allowed=True)))
    assert "pol.spot_non_resumable" in [f.rule_id for f in d.blocking]
    assert "limits.spot_allowed" in d.disabled_fields()
    assert d.severity_of("limits.spot_allowed") is Severity.BLOCK

    d, _ = _diag(_spec(kind=WorkloadKind.LORA_TRAIN, limits=Limits(spot_allowed=True)))
    assert not d.blocking
    assert d.severity_of("limits.spot_allowed") is Severity.WARN


def test_task_timeout_blocks_and_an_override_leaves_a_permanent_warning():
    long_job = _spec(runtime=7200)
    d, _ = _diag(long_job)
    assert [f.rule_id for f in d.blocking] == ["cap.task_timeout"]

    seed = load_seed()
    edited = next(r for r in seed if r.id == "cap.task_timeout")
    off = Rule.from_dict({**edited.to_dict(), "enabled": False})
    d, _ = _diag(long_job, rules=RuleSet(seed, {off.id: off}))
    assert not d.blocking and d.capability_override
    assert not d.ok_to_submit() and d.ok_to_submit(d.needs_ack + ("pol.private_data",))
    assert "⚠ Capability rule overridden" in next(f.message for f in d.findings if f.capability_override)


def test_caps_and_thresholds_come_from_settings():
    spec = _spec(runtime=3 * 3600, mode=ExecutionMode.INSTANCE)
    d, ctx = _diag(spec, CloudSettings(warn_job_spend_usd=1.0, default_max_spend_usd=2.0))
    ids = {f.rule_id for f in d.findings}
    assert {"pol.expensive_job", "pol.over_job_cap"} <= ids
    d, _ = _diag(spec, CloudSettings(monthly_cap_usd=10.0), mtd=9.5)
    assert "pol.monthly_cap" in {f.rule_id for f in d.blocking}


def test_warnings_off_hides_warnings_but_never_blocks():
    spec = _spec(limits=Limits(spot_allowed=True))
    d, _ = _diag(spec, CloudSettings(warnings_enabled=False))
    assert all(f.severity is Severity.BLOCK or f.kind.value == "capability" for f in d.findings)
    assert d.blocking


def test_sensitive_data_rules_and_allowlist():
    man = CapabilityManifest("gcp", frozenset(ExecutionMode), frozenset(StorageMethod), frozenset({"L4"}),
                             ("europe-west1",), third_party_gpu_host=True)
    spec = _spec(data_class=DataClass.SENSITIVE, storage=StorageMethod.CLOUD_SYNC)
    d, _ = _diag(spec, manifest=man)
    assert {"pol.sensitive_third_party", "pol.sensitive_cloud_sync"} <= {f.rule_id for f in d.blocking}
    d, _ = _diag(spec, CloudSettings(sensitive_allowlist=("gcp",)), manifest=man)
    assert not d.blocking


def test_estimate_rounds_billing_and_counts_every_part():
    e = estimate(_spec(runtime=600), CAT, today=TODAY)
    assert e.known and e.billed_s == 660  # 30 s startup + 600 s, rounded up to 60 s increments
    assert e.startup_usd == pytest.approx(30 * 0.72 / 3600)
    assert e.egress_usd == pytest.approx(0.24)
    assert e.retries_usd == pytest.approx((e.startup_usd + e.compute_usd) * 0.1)
    assert e.total_usd == pytest.approx(sum(v for k, v in e.breakdown().items() if k != "total"), abs=1e-3)
    assert e.price_age_days == 18
    assert estimate(_spec(region="asia-east1"), PriceCatalogue(), today=TODAY).known is False


def test_ranking_prefers_compatible_same_region_then_cheapest():
    spec = _spec(mode=ExecutionMode.INSTANCE, runtime=3600)
    eu = Placement("gcp", "europe-west1", ExecutionMode.INSTANCE)
    us = Placement("gcp", "us-central1", ExecutionMode.INSTANCE)
    nope = Placement("other", "x", ExecutionMode.INSTANCE)
    ranked = rank_candidates(spec, [nope, us, eu], CAT, {"gcp": MANIFEST}, {"gcp": "europe-west1"}, now=0)
    assert [c.placement for c in ranked] == [eu, us, nope]
    assert cheaper_cross_region(ranked).placement == us  # cheaper, but moves data: shown as a warning
    ranked = rank_candidates(spec, [eu, us], CAT, {"gcp": MANIFEST}, {}, now=0, deadline_ts=100)
    assert not any(c.meets_deadline for c in ranked)


def test_admission_budget_alert_and_calibration():
    s = CloudSettings(max_concurrent_jobs=2, max_concurrent_gpu_instances=1, max_reserved_usd=10)
    assert admission_blockers(AdmissionSnapshot(1, 0, 0), s, True, 5) == []
    assert len(admission_blockers(AdmissionSnapshot(2, 1, 8), s, True, 5)) == 3
    assert budget_alert(80.0, CloudSettings()) and not budget_alert(79.0, CloudSettings())
    rep = calibration([("gcp/L4", 1.0, 1.5)] * 3 + [("runpod/A100", 2.0, 2.1)])
    assert rep["gcp/L4"].flagged and not rep["runpod/A100"].flagged


def test_rule_store_layers_user_edits(tmp_path):
    pytest.importorskip("backend")
    from middleware.src.cloud.risk import RuleStore
    from middleware.src.cloud.store import CloudJobStore

    store = CloudJobStore.open("s" * 40, "salt-0123456789ab", tmp_path / "r.db")
    rs = RuleStore(store.db)
    seed = {r.id: r for r in load_seed()}
    rs.save(Rule.from_dict({**seed["pol.private_data"].to_dict(), "severity": "info"}))
    eff = {r.id: r for r in rs.ruleset().effective()}
    assert eff["pol.private_data"].severity is Severity.INFO
    rs.restore_default("pol.private_data")
    assert rs.edited_ids() == []
    with pytest.raises(ValueError):
        Rule.from_dict({"id": "bad", "kind": "policy", "severity": "warn", "when": {"op": "eq"}})
    store.close()


def test_missing_cost_components_are_not_a_complete_estimate():
    partial = PriceCatalogue([ComputePrice("gcp", "*", "managed_batch", "L4", 0.72)])
    result = estimate(_spec(), partial, today=TODAY)
    assert not result.known
    assert set(result.missing) == {"egress", "storage"}
    assert result.compute_usd > 0
    assert not estimate(_spec(runtime=0), CAT, today=TODAY).known
