"""Cloud Jobs lifecycle end to end against FakeProvider + a real encrypted store (#826-#829)."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

pytest.importorskip("backend")

from middleware.src.cloud import fakes  # noqa: E402
from middleware.src.cloud.adapter import Observation, ProviderStatus  # noqa: E402
from middleware.src.cloud.engine import EngineSettings, JobEngine  # noqa: E402
from middleware.src.cloud.fakes import FakeProvider, accept_unchecked, finished, running  # noqa: E402
from middleware.src.cloud.sharding import plan_extraction  # noqa: E402
from middleware.src.cloud.spec import (  # noqa: E402
    ExecutionMode,
    InputBlob,
    JobSpec,
    Limits,
    Placement,
    WorkloadKind,
)
from middleware.src.cloud.state import JobState  # noqa: E402
from middleware.src.cloud.store import KIND_ACTUAL, KIND_RESERVED, CloudJobStore, prune_history  # noqa: E402
from middleware.src.cloud.store.db import StoreUnavailable, open_store_db  # noqa: E402

OWNER = "it-test"


class Clock:
    def __init__(self, t: float = 1_800_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


@pytest.fixture(scope="module")
def _db_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("cloudstore")


@pytest.fixture
def store(_db_dir, request):
    clock = Clock()
    path = _db_dir / f"{request.node.name[:40]}.db"
    s = CloudJobStore.open("secret-" + "x" * 32, "salt-0123456789ab", path, clock=clock)
    s.clock = clock
    yield s
    s.close()


_NO_LIMITS = Limits()


def _spec(n_shards=3, provider="fake", limits=_NO_LIMITS, kind=WorkloadKind.EXTRACT, **kw):
    blobs = [InputBlob(f"{i:064x}", 10, f"v{i}.mp4") for i in range(n_shards)]
    shards, inputs = plan_extraction(blobs, 1, {"mode": "range", "fps": 12})
    return JobSpec(kind=kind, placement=Placement(provider, "fake-1", ExecutionMode.MANAGED_BATCH),
                   shards=shards, inputs=inputs, limits=limits, **kw)


def _engine(store, providers, **settings):
    return JobEngine(store, {p.name: p for p in providers},
                     EngineSettings(owner=OWNER, **settings), clock=store.clock)


def _run(engine, ticks=6, dt=30.0):
    for _ in range(ticks):
        engine.tick()
        engine.clock.t += dt


def _types(store, job_id):
    return [e["type"] for e in store.jobs.events(job_id)]


def test_happy_path_collects_every_shard_and_tears_down(store):
    p = FakeProvider(timelines=[[Observation(ProviderStatus.PROVISIONING), running(0, total=3, cost=0.1),
                                 finished(3, cost=0.25)]])
    eng = _engine(store, [p])
    job = eng.submit(accept_unchecked(_spec(), reserve_usd=1.0))
    assert store.ledger.reserved() == 1.0
    _run(eng)
    assert store.jobs.state(job) is JobState.SUCCEEDED
    assert sorted(store.jobs.shard_outputs(job)) == [0, 1, 2]
    assert p.billable() == {}
    assert store.ledger.total(KIND_ACTUAL, job_id=job) == pytest.approx(0.25)
    assert store.ledger.total(KIND_RESERVED, job_id=job) == 0
    t = _types(store, job)
    assert t.index("attempt") < t.index("submitted") < t.index("torn_down")
    assert p.calls.count("collect:0") == 1  # collected once, while still running


def test_ambiguous_submit_that_created_resources_is_found_not_duplicated(store):
    p = FakeProvider(submit_faults=[fakes.AMBIGUOUS_CREATED], timelines=[[finished(3)]])
    eng = _engine(store, [p])
    job = eng.submit(accept_unchecked(_spec()))
    _run(eng)
    assert store.jobs.state(job) is JobState.SUCCEEDED
    assert p.calls.count("submit:1") == 1
    assert len(store.jobs.attempts(job)) == 1
    assert "submit_resolved" in _types(store, job)


def test_ambiguous_submit_with_nothing_created_resubmits_same_attempt(store):
    p = FakeProvider(submit_faults=[fakes.AMBIGUOUS_NOT_CREATED], timelines=[[finished(3)]])
    eng = _engine(store, [p])
    job = eng.submit(accept_unchecked(_spec()))
    _run(eng)
    assert store.jobs.state(job) is JobState.SUCCEEDED
    atts = store.jobs.attempts(job)
    assert len(atts) == 1 and p.calls.count("submit:1") == 2


def test_crash_between_intent_and_submit_is_recovered(store):
    p = FakeProvider(timelines=[[finished(2)]])
    eng = _engine(store, [p])
    job = eng.submit(accept_unchecked(_spec(2)))
    store.jobs.transition(job, JobState.SUBMITTING)
    store.jobs.begin_attempt(job, (0, 1))  # process died before calling the provider
    _run(_engine(store, [p]))
    assert store.jobs.state(job) is JobState.SUCCEEDED
    assert len(store.jobs.attempts(job)) == 1


def test_preemption_retries_only_uncollected_shards(store):
    p = FakeProvider(timelines=[[running(0, total=3)], [finished(3)]])
    eng = _engine(store, [p])
    job = eng.submit(accept_unchecked(_spec()))
    eng.tick()
    eng.tick()  # shard 0 collected while running
    p.preempt_all()
    _run(eng)
    atts = store.jobs.attempts(job)
    assert store.jobs.state(job) is JobState.SUCCEEDED
    assert len(atts) == 2 and atts[1].shards == (1, 2)
    assert p.billable() == {}


def test_out_of_stock_fails_fast_without_fallback(store):
    p = FakeProvider(submit_faults=[fakes.OUT_OF_STOCK])
    eng = _engine(store, [p])
    job = eng.submit(accept_unchecked(_spec()))
    _run(eng, 2)
    assert store.jobs.state(job) is JobState.FAILED
    assert store.jobs.view(job).outcome_reason == "out of stock"
    assert p.calls.count("submit:1") == 1


def test_out_of_stock_falls_back_when_enabled(store):
    a = FakeProvider(name="a", submit_faults=[fakes.OUT_OF_STOCK])
    b = FakeProvider(name="b", timelines=[[finished(3)]])
    alt = Placement("b", "b-1", ExecutionMode.INSTANCE)
    eng = _engine(store, [a, b], fallback_enabled=True, fallback_candidates=(alt,))
    eng.revalidator = lambda job_id, spec: None
    job = eng.submit(accept_unchecked(_spec(provider="a")))
    _run(eng)
    assert store.jobs.state(job) is JobState.SUCCEEDED
    assert store.jobs.spec(job).placement == alt
    assert "fallback" in _types(store, job)


def test_fallback_skips_candidates_that_fail_revalidation(store):
    a = FakeProvider(name="a", submit_faults=[fakes.OUT_OF_STOCK])
    b = FakeProvider(name="b")
    c = FakeProvider(name="c", timelines=[[finished(3)]])
    bad, good = (Placement("b", "b-1", ExecutionMode.INSTANCE), Placement("c", "c-1", ExecutionMode.INSTANCE))
    eng = _engine(store, [a, b, c], fallback_enabled=True, fallback_candidates=(bad, good))
    eng.revalidator = lambda job_id, spec: "sensitive data" if spec.placement.provider == "b" else None
    job = eng.submit(accept_unchecked(_spec(provider="a")))
    _run(eng)
    assert store.jobs.state(job) is JobState.SUCCEEDED and store.jobs.spec(job).placement == good
    assert b.calls == []  # never provisioned on the rejected candidate
    assert "fallback_rejected" in _types(store, job)


def test_fallback_without_a_revalidator_fails_instead_of_moving(store):
    a = FakeProvider(name="a", submit_faults=[fakes.OUT_OF_STOCK])
    b = FakeProvider(name="b", timelines=[[finished(3)]])
    eng = _engine(store, [a, b], fallback_enabled=True,
                  fallback_candidates=(Placement("b", "b-1", ExecutionMode.INSTANCE),))
    job = eng.submit(accept_unchecked(_spec(provider="a")))
    _run(eng)
    assert store.jobs.state(job) is JobState.FAILED and b.calls == []


def test_engine_refuses_specs_that_skipped_preflight(store):
    from middleware.src.cloud.acceptance import AcceptedJob, NotAccepted

    eng = _engine(store, [FakeProvider()])
    with pytest.raises(NotAccepted):
        eng.submit(AcceptedJob(_spec(), 0.0, False, ()))


def test_scheduled_start_is_revalidated(store):
    p = FakeProvider(timelines=[[finished(1)]])
    eng = _engine(store, [p])
    eng.revalidator = lambda job_id, spec: "quota is now 0"
    job = eng.submit(accept_unchecked(_spec(1, scheduled_at=store.clock.t + 60)))
    _run(eng, 4)
    assert store.jobs.state(job) is JobState.FAILED
    assert "revalidation before start: quota is now 0" in store.jobs.view(job).outcome_reason
    assert p.calls == []


def test_quota_blocks_with_request_link(store):
    p = FakeProvider(submit_faults=[fakes.QUOTA])
    eng = _engine(store, [p])
    job = eng.submit(accept_unchecked(_spec()))
    _run(eng, 2)
    assert store.jobs.state(job) is JobState.FAILED
    ev = [e for e in store.jobs.events(job) if e["type"] == "submit_failed"][0]
    assert ev["data"]["request_url"].startswith("https://")


def test_predictive_spend_cap_stops_and_keeps_partial_outputs(store):
    p = FakeProvider(timelines=[[running(0, total=3, cost=0.5, burn=0.01), running(0, 1, total=3, cost=0.9, burn=0.01)]])
    eng = _engine(store, [p])
    job = eng.submit(accept_unchecked(_spec(limits=Limits(max_spend_usd=1.2))))
    _run(eng)
    v = store.jobs.view(job)
    assert store.jobs.state(job) is JobState.FAILED and v.outcome_reason == "spend cap reached"
    assert sorted(store.jobs.shard_outputs(job)) == [0, 1]
    assert p.billable() == {}


def test_max_runtime_stops_resumable_job_with_checkpoint(store):
    p = FakeProvider(timelines=[[running(total=1)]])
    eng = _engine(store, [p], cap_margin_s=10)
    spec = _spec(1, kind=WorkloadKind.LORA_TRAIN, limits=Limits(max_runtime_s=100))
    job = eng.submit(accept_unchecked(spec))
    _run(eng, 6, dt=30)
    assert store.jobs.view(job).outcome_reason == "max runtime reached"
    assert "checkpoint" in p.calls


def test_cancel_checkpoints_but_force_stop_does_not(store):
    for force, expect in ((False, True), (True, False)):
        p = FakeProvider(timelines=[[running(total=1)]])
        eng = _engine(store, [p])
        job = eng.submit(accept_unchecked(_spec(1, kind=WorkloadKind.LORA_TRAIN)))
        _run(eng, 2)
        eng.cancel(job, force=force)
        _run(eng, 2)
        assert store.jobs.state(job) is JobState.CANCELLED
        assert ("checkpoint" in p.calls) is expect
        assert p.billable() == {}


def test_failed_teardown_stays_owed_until_it_succeeds(store):
    p = FakeProvider(timelines=[[finished(1)]], teardown_failures=3)
    eng = _engine(store, [p])
    job = eng.submit(accept_unchecked(_spec(1)))
    eng.tick()
    assert store.jobs.view(job).teardown_pending
    assert job in store.jobs.needing_work()
    _run(eng, 4)
    assert store.jobs.state(job) is JobState.SUCCEEDED
    assert not store.jobs.view(job).teardown_pending and p.billable() == {}


def test_capability_override_failure_is_structural(store):
    p = FakeProvider(timelines=[[Observation(ProviderStatus.FAILED, detail="GPU timeout")]])
    eng = _engine(store, [p])
    job = eng.submit(accept_unchecked(_spec(1), capability_override=True))
    _run(eng)
    assert store.jobs.state(job) is JobState.FAILED
    assert store.jobs.view(job).outcome_reason.startswith("structural")
    assert len(store.jobs.attempts(job)) == 1


def test_scheduled_job_waits_and_admission_queues(store):
    p = FakeProvider(timelines=[[running(total=1)], [finished(1)], [finished(1)]])
    eng = _engine(store, [p], max_concurrent_jobs=1)
    later = eng.submit(accept_unchecked(_spec(1, scheduled_at=store.clock.t + 3600)))
    first = eng.submit(accept_unchecked(_spec(1)))
    second = eng.submit(accept_unchecked(_spec(1)))
    _run(eng, 2)
    assert store.jobs.state(later) is JobState.QUEUED
    assert store.jobs.state(second) is JobState.QUEUED
    eng.cancel(first)
    _run(eng, 4)
    assert store.jobs.state(second) is JobState.SUCCEEDED


def test_prune_keeps_ledger_and_exports(store, tmp_path):
    p = FakeProvider(timelines=[[finished(1, cost=0.4)]])
    eng = _engine(store, [p])
    job = eng.submit(accept_unchecked(_spec(1)))
    _run(eng, 2)
    export = tmp_path / "export.jsonl"
    assert prune_history(store.db, 3600, store.clock.t + 7200, export) == 1
    assert store.jobs.job_ids() == []
    assert store.ledger.total(KIND_ACTUAL, job_id=job) == pytest.approx(0.4)
    assert json.loads(export.read_text().splitlines()[0])["job_id"] == job


def test_poc_usage_rows_import_once(store):
    from middleware.src.cloud.poc.usage import UsageRow

    rows = [UsageRow("poc-1", "gcd", "range", "success", 12.0, "2026-09-01T10:00:00Z", cost_usd=0.03)]
    assert store.ledger.import_poc_rows(rows) == 1
    assert store.ledger.import_poc_rows(rows) == 0
    assert [r.job_id for r in store.ledger.usage_rows(source="poc")] == ["poc-1"]


def test_open_retries_while_locked(tmp_path):
    calls = []

    def factory(path, secret, salt):
        calls.append(path)
        if len(calls) < 3:
            raise RuntimeError("cannot read database (database is locked)")
        import backend

        return backend.database.Database(path, secret, salt)

    db = open_store_db("s" * 40, "salt-0123456789ab", tmp_path / "x.db", factory=factory, sleep=lambda s: None)
    assert len(calls) == 3
    db.close()
    with pytest.raises(StoreUnavailable):
        open_store_db("", "salt", tmp_path / "y.db")


def test_cloud_core_is_qt_free():
    code = ("import sys; import middleware.src.cloud.engine, middleware.src.cloud.store, middleware.src.cloud.fakes; "
            "assert not any(m.startswith('PySide6') for m in sys.modules), 'Qt imported'")
    subprocess.run([sys.executable, "-c", code], check=True)


def test_gpu_and_reserved_spend_admission(store):
    from middleware.src.cloud.settings import CloudSettings
    from middleware.src.cloud.spec import Resources

    p = FakeProvider(timelines=[[running(total=1)], [finished(1)], [finished(1)]])
    settings = EngineSettings.from_cloud_settings(
        CloudSettings(max_concurrent_jobs=5, max_concurrent_gpu_instances=1, max_reserved_usd=3.0), OWNER)
    eng = JobEngine(store, {"fake": p}, settings, clock=store.clock)
    gpu = Resources(gpu_class="L4", gpu_count=1)
    a = eng.submit(accept_unchecked(_spec(1, resources=gpu), reserve_usd=1.0))
    b = eng.submit(accept_unchecked(_spec(1, resources=gpu), reserve_usd=1.0))  # second GPU instance: waits
    c = eng.submit(accept_unchecked(_spec(1), reserve_usd=2.5))  # CPU, but would push reserved spend past $3
    _run(eng, 2)
    assert store.jobs.state(a) is JobState.RUNNING
    assert store.jobs.state(b) is JobState.QUEUED and store.jobs.state(c) is JobState.QUEUED
    eng.cancel(a)
    _run(eng, 4)
    assert store.jobs.state(b) is JobState.SUCCEEDED


def test_store_written_by_a_newer_build_refuses_to_open(tmp_path):
    path = tmp_path / "future.db"
    s = CloudJobStore.open("s" * 40, "salt-0123456789ab", path)
    s.db.execute("UPDATE schema_meta SET value = '99' WHERE key = 'version'")
    s.close()
    with pytest.raises(StoreUnavailable, match="v99"):
        CloudJobStore.open("s" * 40, "salt-0123456789ab", path)


def test_open_keeps_retrying_past_the_busy_timeout(tmp_path):
    slept = []

    def always_locked(path, secret, salt):
        raise RuntimeError("database is locked")

    with pytest.raises(StoreUnavailable, match="stayed locked"):
        open_store_db("s" * 40, "salt-0123456789ab", tmp_path / "z.db", factory=always_locked,
                      sleep=slept.append)
    assert sum(slept) >= 5.0

