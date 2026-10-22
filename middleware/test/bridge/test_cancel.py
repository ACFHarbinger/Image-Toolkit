from __future__ import annotations

import time

import pytest

from middleware.src.bridge.cancel import Cancelled, CancelRegistry, CancelToken
from middleware.src.bridge.envelope import BridgeAppError


def test_cancel_is_idempotent() -> None:
    registry = CancelRegistry()
    registry.register("job-1")
    assert registry.cancel("job-1") == {"ok": True}
    assert registry.cancel("job-1") == {"ok": True}  # safe to retry
    token = registry.token("job-1")
    assert token.cancelled


def test_cancel_on_terminal_job_is_ok() -> None:
    registry = CancelRegistry()
    registry.register("job-1")
    registry.mark_terminal("job-1")
    assert registry.cancel("job-1") == {"ok": True}  # no-op, not an error
    assert registry.token("job-1").cancelled is False  # terminal job never re-cancels


def test_cancel_unknown_job_is_not_found() -> None:
    registry = CancelRegistry()
    with pytest.raises(BridgeAppError) as exc_info:
        registry.cancel("ghost")
    assert exc_info.value.code == "jobs.not_found"
    with pytest.raises(BridgeAppError):
        registry.mark_terminal("ghost")


def test_token_raises_at_cooperative_checkpoint() -> None:
    token = CancelToken("job-1", grace_seconds=60.0)
    token.raise_if_cancelled()  # no-op before cancel
    token.cancel()
    with pytest.raises(Cancelled):
        token.raise_if_cancelled()


def test_escalation_runs_once_after_grace(monkeypatch: pytest.MonkeyPatch) -> None:
    now = 1000.0
    monkeypatch.setattr("middleware.src.bridge.cancel.time.monotonic", lambda: now)
    escalated: list[str] = []
    token = CancelToken("job-1", grace_seconds=5.0)
    token.on_escalate = lambda t: escalated.append(t.job_id)
    token.cancel()
    assert escalated == []  # inside the grace period
    now = 1006.0
    assert token.cancelled
    assert escalated == ["job-1"]
    now = 1012.0
    _ = token.cancelled  # escalation does not repeat
    assert escalated == ["job-1"]


def test_escalation_fires_without_worker_polling() -> None:
    escalated: list[str] = []
    token = CancelToken("job-1", grace_seconds=0.05)
    token.on_escalate = lambda t: escalated.append(t.job_id)
    token.cancel()
    # never reads the token: the deadline must fire on its own schedule
    deadline = time.monotonic() + 2.0
    while not escalated and time.monotonic() < deadline:
        time.sleep(0.01)
    assert escalated == ["job-1"]


def test_terminal_cleanup_cancels_escalation_deadline() -> None:
    escalated: list[str] = []
    token = CancelToken("job-1", grace_seconds=0.05)
    token.on_escalate = lambda t: escalated.append(t.job_id)
    token.cancel()
    token.finish()
    time.sleep(0.2)
    assert escalated == []


def test_registry_mark_terminal_stops_pending_escalation() -> None:
    escalated: list[str] = []
    registry = CancelRegistry(grace_seconds=0.05)
    token = registry.register("job-1")
    token.on_escalate = lambda t: escalated.append(t.job_id)
    assert registry.cancel("job-1") == {"ok": True}
    registry.mark_terminal("job-1")
    time.sleep(0.2)
    assert escalated == []


def test_reregistration_stops_previous_deadline() -> None:
    escalated: list[str] = []
    registry = CancelRegistry(grace_seconds=0.05)
    first = registry.register("job-1")
    first.on_escalate = lambda t: escalated.append(t.job_id)
    first.cancel()
    second = registry.register("job-1")
    assert second is not first
    time.sleep(0.2)
    assert escalated == []  # the orphaned token's deadline was cleaned up


def test_registered_token_replaces_previous_registration() -> None:
    registry = CancelRegistry()
    registry.register("job-1")
    registry.mark_terminal("job-1")
    second = registry.register("job-1")
    assert not second.cancelled
    assert registry.cancel("job-1") == {"ok": True}  # the fresh registration cancels
