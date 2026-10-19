"""Codex's three Gate A blockers: enforced preflight, ledger-backed monthly caps, graceful cleanup."""

from __future__ import annotations

import datetime as dt

import pytest

pytest.importorskip("base")

from middleware.src.cloud import fakes  # noqa: E402
from middleware.src.cloud.adapter import CapabilityManifest  # noqa: E402
from middleware.src.cloud.cost import ComputePrice, PriceCatalogue  # noqa: E402
from middleware.src.cloud.engine import EngineSettings, JobEngine  # noqa: E402
from middleware.src.cloud.fakes import FakeProvider, accept_unchecked, finished, running  # noqa: E402
from middleware.src.cloud.service import CloudJobService, SubmissionRefused  # noqa: E402
from middleware.src.cloud.settings import CloudSettings  # noqa: E402
from middleware.src.cloud.spec import (  # noqa: E402
    DataClass,
    ExecutionMode,
    JobSpec,
    Limits,
    Placement,
    ShardSpec,
    StorageMethod,
    WorkloadKind,
)
from middleware.src.cloud.state import JobState  # noqa: E402
from middleware.src.cloud.store import KIND_RESERVED, CloudJobStore  # noqa: E402

ACKS = ("pol.reduced_protection",)


class Clock:
    t = 1_800_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def store(tmp_path):
    clock = Clock()
    s = CloudJobStore.open("b" * 40, "salt-0123456789ab", tmp_path / "b.db", clock=clock)
    s.clock = clock
    yield s
    s.close()


def _spec(n=3, provider="fake", **kw):
    params = {"expected_runtime_s": 600, **kw.pop("params", {})}
    return JobSpec(WorkloadKind.EXTRACT, Placement(provider, "fake-1", ExecutionMode.INSTANCE),
                   tuple(ShardSpec(i) for i in range(n)), params=params, **kw)


def _run(eng, ticks=8, dt_s=30.0):
    for _ in range(ticks):
        eng.tick()
        eng.clock.t += dt_s


def _engine(store, providers, **kw):
    return JobEngine(store, {p.name: p for p in providers}, EngineSettings(owner="it-b", **kw), clock=store.clock)


def _types(store, job):
    return [e["type"] for e in store.jobs.events(job)]


# --- 3. graceful cleanup never depends on checkpoint or collection -----------------


def test_failed_checkpoint_does_not_block_teardown(store):
    p = FakeProvider(timelines=[[running(total=1)]], checkpoint_error=True)
    eng = _engine(store, [p])
    job = eng.submit(accept_unchecked(JobSpec(WorkloadKind.LORA_TRAIN, Placement("fake", "fake-1",
                                                                              ExecutionMode.INSTANCE), (ShardSpec(0),))))
    _run(eng, 2)
    eng.cancel(job)
    _run(eng, 3)
    assert store.jobs.state(job) is JobState.CANCELLED
    assert "checkpoint_failed" in _types(store, job) and p.billable() == {}


def test_durable_outputs_are_collected_after_teardown_when_downloads_fail(store):
    p = FakeProvider(timelines=[[running(0, 1, total=3, cost=0.5, burn=0.01),
                                 running(0, 1, total=3, cost=0.9, burn=0.01)]],
                     collect_errors={0: 2, 1: 2})
    eng = _engine(store, [p])
    job = eng.submit(accept_unchecked(_spec(limits=Limits(max_spend_usd=1.2))))
    _run(eng, 10)
    assert store.jobs.state(job) is JobState.FAILED
    assert store.jobs.view(job).outcome_reason.startswith("spend cap reached")
    assert sorted(store.jobs.shard_outputs(job)) == [0, 1]
    assert p.billable() == {}
    # The instance went before the retried downloads that finally worked.
    assert p.calls.index("teardown") < max(i for i, c in enumerate(p.calls) if c == "collect:0")


def test_durable_output_that_never_downloads_is_reported_not_collected(store):
    p = FakeProvider(timelines=[[running(0, total=1)]], collect_errors={0: 99})
    eng = _engine(store, [p])
    job = eng.submit(accept_unchecked(_spec(1)))
    _run(eng, 2)
    eng.cancel(job, force=True)
    _run(eng, 8)
    assert store.jobs.state(job) is JobState.CANCELLED
    assert "1 shard output(s) not collected" in [e for e in store.jobs.events(job) if e["type"] == "state"][-1]["data"]["reason"]
    assert p.calls.count("collect:0") <= 4 and p.billable() == {}


def test_ephemeral_outputs_get_one_try_before_teardown_then_are_lost(store):
    p = FakeProvider(timelines=[[running(0, total=2, durable=False)]], collect_errors={0: 99})
    eng = _engine(store, [p])
    job = eng.submit(accept_unchecked(_spec(2)))
    eng.tick()
    eng.cancel(job)
    _run(eng, 4)
    assert store.jobs.state(job) is JobState.CANCELLED
    lost = [e for e in store.jobs.events(job) if e["type"] == "collect_failed"]
    assert lost and lost[-1]["data"]["error"] == "output lost with the instance"
    assert p.billable() == {}


def test_unverified_output_is_retried(store):
    p = FakeProvider(timelines=[[finished(1)]], collect_unverified=[0])
    eng = _engine(store, [p])
    job = eng.submit(accept_unchecked(_spec(1)))
    eng.tick()
    p.collect_unverified = []
    _run(eng, 3)
    assert store.jobs.state(job) is JobState.SUCCEEDED
    assert "collect_retry" in _types(store, job)


def test_retry_does_not_rerun_shards_already_staged(store):
    p = FakeProvider(timelines=[[running(0, 1, total=3)], [finished(3)]], collect_errors={0: 1, 1: 1})
    eng = _engine(store, [p])
    job = eng.submit(accept_unchecked(_spec()))
    eng.tick()  # 0 and 1 finish, downloads fail once
    p.preempt_all()
    _run(eng, 6)
    atts = store.jobs.attempts(job)
    assert store.jobs.state(job) is JobState.SUCCEEDED
    assert atts[-1].shards == (2,)
    assert sorted(store.jobs.shard_outputs(job)) == [0, 1, 2]


# --- 1 + 2. one enforced submission path, ledger-backed monthly budget --------------

CAT = PriceCatalogue([ComputePrice(n, "*", "instance", "cpu", 1.0, last_verified="2026-10-10")
                      for n in ("fake", "b", "c")])


def _service(store, providers, settings=None, **eng):
    engine = _engine(store, providers, **eng)
    return CloudJobService(engine, settings or CloudSettings(default_max_spend_usd=6.0, monthly_cap_usd=10.0),
                           CAT, clock=store.clock, today=lambda: dt.date(2026, 10, 19))


def test_submit_requires_preflight_acks_and_sends_the_sanitized_spec(store):
    svc = _service(store, [FakeProvider()])
    wf = {"9": {"class_type": "X", "inputs": {"api_key": "sk-abcdefghijklmnopqrstuv"}}}
    with pytest.raises(SubmissionRefused) as exc:
        svc.submit(_spec(params={"workflow": wf}), ACKS)
    assert "looks like a secret" in str(exc.value)
    with pytest.raises(SubmissionRefused, match="acknowledgement needed"):
        svc.submit(_spec(params={"workflow": wf}), secret_decisions={("9", "api_key"): "strip"})
    job = svc.submit(_spec(params={"workflow": wf}), ACKS, secret_decisions={("9", "api_key"): "strip"})
    assert store.jobs.spec(job).params["workflow"]["9"]["inputs"]["api_key"] == ""
    assert store.ledger.total(KIND_RESERVED, job_id=job) == 6.0  # the job's cap, not its estimate
    assert store.jobs.accepted_record(job)["acknowledged"] == list(ACKS)


def test_monthly_cap_counts_open_jobs_and_frees_up_when_they_settle(store):
    p = FakeProvider(timelines=[[running(total=3), finished(3, cost=0.5)], [finished(3)]])
    svc = _service(store, [p])
    first = svc.submit(_spec(), ACKS)
    with pytest.raises(SubmissionRefused, match="monthly cap"):
        svc.submit(_spec(), ACKS)  # $6 open + $6 > $10, even though the estimate is cents
    assert any(i.stage == "budget" for i in svc.preview(_spec()).blocking)
    _run(svc.engine, 6)
    assert store.jobs.state(first) is JobState.SUCCEEDED
    assert store.ledger.total(KIND_RESERVED, job_id=first) == 0
    svc.submit(_spec(), ACKS)  # settled spend is cents, so the month has room again


def test_running_job_never_spends_past_its_reservation(store):
    p = FakeProvider(timelines=[[running(total=1, cost=0.5, burn=0.01), running(total=1, cost=0.98, burn=0.01)]])
    eng = _engine(store, [p])
    job = eng.submit(accept_unchecked(_spec(1, limits=Limits(max_spend_usd=50)), reserve_usd=1.0))
    _run(eng, 4)
    assert store.jobs.view(job).outcome_reason.startswith("spend cap reached")


def test_service_revalidates_fallbacks_with_the_accepted_acknowledgements(store):
    a = FakeProvider(name="fake", submit_faults=[fakes.OUT_OF_STOCK])
    third_party = FakeProvider(name="b", manifest=CapabilityManifest(
        "b", frozenset(ExecutionMode), frozenset(StorageMethod), third_party_gpu_host=True))
    ok = FakeProvider(name="c", timelines=[[finished(3)]])
    cands = (Placement("b", "b-1", ExecutionMode.INSTANCE), Placement("c", "c-1", ExecutionMode.INSTANCE))
    svc = _service(store, [a, third_party, ok], fallback_enabled=True, fallback_candidates=cands)
    job = svc.submit(_spec(data_class=DataClass.SENSITIVE, storage=StorageMethod.BUCKET), ACKS)
    _run(svc.engine, 6)
    assert store.jobs.state(job) is JobState.SUCCEEDED and store.jobs.spec(job).placement.provider == "c"
    rejected = [e for e in store.jobs.events(job) if e["type"] == "fallback_rejected"]
    assert rejected and "Sensitive data" in rejected[0]["data"]["why"]
    assert third_party.calls == []


def test_v1_store_is_migrated_to_v2(tmp_path):
    import base
    from middleware.src.cloud.store.db import CLOUD_SCHEMA_VERSION, schema_version

    path = str(tmp_path / "v1.db")
    raw = base.database.Database(path, "m" * 40, "salt-0123456789ab")
    raw.apply_ddl("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);"
                  "INSERT INTO schema_meta VALUES ('version', '1');"
                  "CREATE TABLE shards (job_id TEXT NOT NULL, idx INTEGER NOT NULL, collected INTEGER NOT NULL "
                  "DEFAULT 0, failures INTEGER NOT NULL DEFAULT 0, outputs_json TEXT NOT NULL DEFAULT '[]', "
                  "PRIMARY KEY (job_id, idx));"
                  "INSERT INTO shards(job_id, idx) VALUES ('old', 0);")
    raw.close()
    s = CloudJobStore.open("m" * 40, "salt-0123456789ab", tmp_path / "v1.db")
    cols = {r[1] for r in s.db.query("PRAGMA table_info(shards)", ())}
    assert {"ready", "durable", "collect_attempts", "collect_failed"} <= cols
    assert schema_version(s.db) == CLOUD_SCHEMA_VERSION == 2
    assert s.db.query("SELECT ready FROM shards WHERE job_id = 'old'", ())[0][0] == 0
    s.close()
