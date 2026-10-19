"""Crash-point matrix and adapter certification (#829).

The engine is killed at every provider call, both before the call reaches
the provider and after the provider acted but before the engine heard back.
A fresh engine must then finish the job with no leaked resources and no
duplicate live instances.
"""

from __future__ import annotations

import datetime as dt

import pytest

pytest.importorskip("base")

from backend.src.cloud.adapter import CapabilityManifest  # noqa: E402
from backend.src.cloud.certification import LEVEL_DECLARED, certify  # noqa: E402
from backend.src.cloud.engine import EngineSettings, JobEngine  # noqa: E402
from backend.src.cloud.fakes import FakeProvider, finished, running  # noqa: E402
from backend.src.cloud.spec import (  # noqa: E402
    ExecutionMode,
    JobSpec,
    Placement,
    ShardSpec,
    StorageMethod,
    WorkloadKind,
)
from backend.src.cloud.state import TERMINAL, JobState  # noqa: E402
from backend.src.cloud.store import CloudJobStore  # noqa: E402


class Crash(BaseException):
    """Process death: BaseException so the engine's per-job error guard can't swallow it."""


class Crashing:
    def __init__(self, inner: FakeProvider, at: int, after_effect: bool):
        self.inner, self.at, self.after, self.n = inner, at, after_effect, 0
        self.name = inner.name

    def __getattr__(self, attr):
        target = getattr(self.inner, attr)
        if attr not in ("submit", "observe", "collect", "teardown", "list_owned_resources", "checkpoint"):
            return target

        def call(*a, **kw):
            self.n += 1
            if self.n == self.at and not self.after:
                raise Crash(attr)
            result = target(*a, **kw)
            if self.n == self.at and self.after:
                raise Crash(attr)
            return result

        return call


class Clock:
    t = 1_800_000_000.0

    def __call__(self):
        return self.t


def _spec():
    return JobSpec(WorkloadKind.EXTRACT, Placement("fake", "fake-1", ExecutionMode.MANAGED_BATCH),
                   tuple(ShardSpec(i) for i in range(3)))


def _provider():
    return FakeProvider(timelines=[[running(0, total=3), finished(3, cost=0.2)]] * 4)


def _drive(store, adapter, clock, ticks=8):
    eng = JobEngine(store, {"fake": adapter}, EngineSettings(owner="it-crash"), clock=clock)
    for _ in range(ticks):
        eng.tick()
        clock.t += 30
    return eng


def _calls_in_clean_run(tmp_path):
    clock = Clock()
    store = CloudJobStore.open("s" * 40, "salt-0123456789ab", tmp_path / "clean.db", clock=clock)
    counter = Crashing(_provider(), at=-1, after_effect=False)
    eng = _drive(store, counter, clock)
    eng.submit(_spec())
    _drive(store, counter, clock)
    store.close()
    return counter.n


@pytest.mark.parametrize("after_effect", [False, True], ids=["before-call", "after-effect"])
def test_engine_recovers_from_a_crash_at_every_provider_call(tmp_path, after_effect):
    total = _calls_in_clean_run(tmp_path)
    assert total >= 5
    for k in range(1, total + 1):
        clock = Clock()
        path = tmp_path / f"crash-{after_effect}-{k}.db"
        store = CloudJobStore.open("s" * 40, "salt-0123456789ab", path, clock=clock)
        provider = _provider()
        job = JobEngine(store, {"fake": provider}, EngineSettings(owner="it-crash"), clock=clock).submit(_spec())
        with pytest.raises(Crash):
            _drive(store, Crashing(provider, k, after_effect), clock)
        store.close()

        store = CloudJobStore.open("s" * 40, "salt-0123456789ab", path, clock=clock)  # the restart
        _drive(store, provider, clock, ticks=12)
        state = store.jobs.state(job)
        assert state in TERMINAL, f"crash at call {k}: stuck in {state.value}"
        assert state is JobState.SUCCEEDED, f"crash at call {k}: {store.jobs.view(job).outcome_reason}"
        assert provider.billable() == {}, f"crash at call {k}: leaked {list(provider.billable())}"
        assert sorted(store.jobs.shard_outputs(job)) == [0, 1, 2]
        live_submits = [a for a in store.jobs.attempts(job) if a.submitted]
        assert len(live_submits) <= 2, f"crash at call {k}: {len(live_submits)} submitted attempts"
        store.close()


def test_fake_provider_passes_certification():
    p = FakeProvider(manifest=CapabilityManifest("fake", frozenset(ExecutionMode), frozenset(StorageMethod),
                                                 verified_on="2026-10-19"))
    rep = certify(p, _spec, today=dt.date(2026, 10, 19))
    assert rep.ok, rep.failed


def test_certification_catches_untagged_resources_and_stale_facts():
    class Untagged(FakeProvider):
        def submit(self, ctx):
            receipt = super().submit(ctx)
            for r in receipt.resources:
                r.tags.clear()
            return receipt

    p = Untagged(manifest=CapabilityManifest("fake", frozenset(ExecutionMode), frozenset(StorageMethod),
                                             verified_on="2025-01-01"))
    rep = certify(p, _spec, today=dt.date(2026, 10, 19))
    names = [n for n, _ in rep.failed]
    assert "manifest.verified_on_recent" in names
    assert any(n.startswith("submit.tags") for n in names)
    assert certify(p, _spec, level=LEVEL_DECLARED).ok
