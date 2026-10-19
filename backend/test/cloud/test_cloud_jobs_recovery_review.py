"""Restart and teardown regressions from the Gate A review."""
from dataclasses import replace

import pytest

pytest.importorskip("base")

from backend.src.cloud.adapter import Observation, ProviderStatus
from backend.src.cloud.engine import EngineSettings, JobEngine
from backend.src.cloud.fakes import FakeProvider, accept_unchecked, finished, running
from backend.src.cloud.settings import CloudSettings
from backend.src.cloud.spec import ExecutionMode, JobSpec, Placement, ShardSpec, WorkloadKind
from backend.src.cloud.state import JobState
from backend.src.cloud.store import CloudJobStore


class Crash(BaseException):
    pass


@pytest.fixture
def setup(tmp_path):
    now = [1_800_000_000.0]
    def clock():
        return now[0]
    store = CloudJobStore.open("review-secret" * 3, "salt-0123456789ab", tmp_path / "jobs.db", clock=clock)
    provider = FakeProvider(timelines=[[finished(1, cost=0.5)]])
    settings = EngineSettings(owner="review")
    def engine():
        return JobEngine(store, {"fake": provider}, settings, clock=clock)
    spec = JobSpec(WorkloadKind.EXTRACT, Placement("fake", "fake-1", ExecutionMode.INSTANCE), (ShardSpec(0),))
    yield store, provider, engine, spec, now
    store.close()


def test_restart_after_teardown_is_persisted(setup, monkeypatch):
    store, provider, engine, spec, _ = setup
    eng = engine()
    job = eng.submit(accept_unchecked(spec))
    original = store.jobs.end_attempt
    def crash_after(*args, **kwargs):
        original(*args, **kwargs)
        raise Crash()
    with monkeypatch.context() as m:
        m.setattr(store.jobs, "end_attempt", crash_after)
        with pytest.raises(Crash):
            eng.step(job)
    fresh = engine()
    for _ in range(4):
        fresh.tick()
    assert store.jobs.state(job) is JobState.SUCCEEDED
    assert store.ledger.total(job_id=job) == pytest.approx(0.5)
    assert len(store.jobs.attempts(job)) == 1


def test_retry_waits_for_previous_teardown(setup):
    store, provider, engine, spec, _ = setup
    provider.timelines = [[Observation(ProviderStatus.FAILED)], [finished(1)]]
    provider.teardown_failures = 100
    eng = engine()
    job = eng.submit(accept_unchecked(spec))
    eng.tick()
    assert len(store.jobs.attempts(job)) == 1
    assert len(provider.billable()) == 1
    provider.teardown_failures = 0
    for _ in range(4):
        engine().tick()
    assert store.jobs.state(job) is JobState.SUCCEEDED
    assert len(store.jobs.attempts(job)) == 2


def test_failed_teardown_still_holds_admission(setup):
    store, provider, engine, spec, _ = setup
    provider.teardown_failures = 100
    eng = engine()
    eng.settings = replace(eng.settings, max_concurrent_jobs=1)
    first = eng.submit(accept_unchecked(spec, reserve_usd=1))
    second = eng.submit(accept_unchecked(replace(spec, job_id="second"), reserve_usd=1))
    eng.tick()
    assert store.jobs.view(first).teardown_pending
    assert store.jobs.state(second) is JobState.QUEUED
    assert store.ledger.total("reserved", job_id=first) == 1


def test_cancel_queued_releases_reservation(setup):
    store, _, engine, spec, _ = setup
    eng = engine()
    job = eng.submit(accept_unchecked(spec, reserve_usd=2))
    eng.cancel(job)
    eng.tick()
    assert store.jobs.state(job) is JobState.CANCELLED
    assert store.ledger.reserved() == 0


def test_settings_default_spend_cap_is_enforced(setup):
    store, provider, engine, spec, _ = setup
    provider.timelines = [[running(total=1, cost=2)]]
    eng = engine()
    eng.settings = EngineSettings.from_cloud_settings(CloudSettings(default_max_spend_usd=1), "review")
    job = eng.submit(accept_unchecked(spec))
    for _ in range(3):
        eng.tick()
    assert store.jobs.state(job) is JobState.FAILED
    assert store.jobs.view(job).outcome_reason == "spend cap reached"


def test_restart_keeps_observed_spend(setup):
    store, provider, engine, spec, _ = setup
    provider.timelines = [[running(total=1, cost=0.7)]]
    job = engine().submit(accept_unchecked(spec))
    engine().tick()
    provider.preempt_all()
    eng = engine()
    eng.settings = replace(eng.settings, max_attempts=1)
    eng.tick()
    assert store.ledger.total(job_id=job) == pytest.approx(0.7)


def test_disabled_caps_do_not_stop_job(setup):
    store, provider, engine, spec, _ = setup
    from backend.src.cloud.spec import Limits
    provider.timelines = [[running(total=1, cost=2)]]
    eng = engine()
    eng.settings = EngineSettings.from_cloud_settings(CloudSettings(hard_caps_enabled=False), "review")
    job = eng.submit(accept_unchecked(replace(spec, limits=Limits(max_spend_usd=1))))
    eng.tick()
    assert store.jobs.state(job) is JobState.RUNNING


def test_force_stop_does_not_depend_on_observation(setup, monkeypatch):
    store, provider, engine, spec, _ = setup
    provider.timelines = [[running(total=1)]]
    eng = engine()
    job = eng.submit(accept_unchecked(spec))
    eng.tick()
    def unavailable(*args, **kwargs):
        raise ConnectionError("status endpoint unavailable")
    monkeypatch.setattr(provider, "observe", unavailable)
    eng.cancel(job, force=True)
    eng.tick()
    assert store.jobs.state(job) is JobState.CANCELLED
    assert not provider.billable()


def test_unexpected_submit_error_reconciles_created_resources(setup, monkeypatch):
    store, provider, engine, spec, _ = setup
    submit = provider.submit
    def broken_response(ctx):
        submit(ctx)
        raise ValueError("invalid provider response")
    monkeypatch.setattr(provider, "submit", broken_response)
    eng = engine()
    job = eng.submit(accept_unchecked(spec))
    for _ in range(3):
        eng.tick()
    assert store.jobs.state(job) is JobState.SUCCEEDED
    assert len(store.jobs.attempts(job)) == 1
    assert not provider.billable()


def test_submit_rejection_survives_restart(setup, monkeypatch):
    store, provider, engine, spec, _ = setup
    from backend.src.cloud import fakes
    provider.submit_faults = [fakes.QUOTA]
    eng = engine()
    job = eng.submit(accept_unchecked(spec))
    failed = eng._submit_failed
    def crash_after(*args, **kwargs):
        result = failed(*args, **kwargs)
        raise Crash(result)
    monkeypatch.setattr(eng, "_submit_failed", crash_after)
    with pytest.raises(Crash):
        eng.step(job)
    engine().tick()
    assert store.jobs.state(job) is JobState.FAILED
    assert provider.calls.count("submit:1") == 1
    assert len(store.jobs.attempts(job)) == 1
