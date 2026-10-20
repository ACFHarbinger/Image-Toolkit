"""Supervisor sibling lifecycle against fake children (#877)."""

from __future__ import annotations

import os
import signal
import time

import pytest

from middleware.src.supervisor import (
    BRIDGE_DOWN,
    BRIDGE_READY,
    PROTOCOL_VERSION,
    Supervisor,
)
from middleware.src.supervisor.children import CLOUD_JOBS, SIDECAR, SLIDESHOW, is_pid_alive


@pytest.fixture
def supervisor(tmp_path):
    sup = Supervisor(tmp_path, poll_interval_s=0.05)
    sup.start()
    try:
        sup.wait_until_ready(timeout_s=5)
        yield sup
    finally:
        sup.stop()


def _wait_for(predicate, timeout_s: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.03)
    raise AssertionError("condition not met before timeout")


def test_three_siblings_start(supervisor: Supervisor) -> None:
    kids = supervisor.children
    assert set(kids) == {SIDECAR, CLOUD_JOBS, SLIDESHOW}
    assert all(is_pid_alive(child.pid) for child in kids.values())
    assert kids[CLOUD_JOBS].durable is True
    assert kids[SLIDESHOW].durable is True
    assert kids[SIDECAR].durable is False


def test_second_supervisor_refuses_same_data_dir(supervisor: Supervisor, tmp_path) -> None:
    other = Supervisor(tmp_path, poll_interval_s=0.05)
    with pytest.raises(RuntimeError, match="already running"):
        other.start()


def test_sidecar_sigkill_emits_bridge_contract(supervisor: Supervisor) -> None:
    kids = supervisor.children
    sidecar_pid = kids[SIDECAR].pid
    cloud_pid = kids[CLOUD_JOBS].pid
    show_pid = kids[SLIDESHOW].pid
    assert supervisor.begin_session("req-1") is None

    os.kill(sidecar_pid, signal.SIGKILL)
    _wait_for(
        lambda: any(event.name == BRIDGE_READY for event in supervisor.events())
    )

    names = [event.name for event in supervisor.events()]
    assert BRIDGE_DOWN in names
    assert BRIDGE_READY in names
    assert names.index(BRIDGE_DOWN) < names.index(BRIDGE_READY)

    down = next(event for event in supervisor.events() if event.name == BRIDGE_DOWN)
    ready = next(event for event in supervisor.events() if event.name == BRIDGE_READY)
    assert down.sidecar_pid == sidecar_pid
    assert ready.protocol_version == PROTOCOL_VERSION
    assert ready.sidecar_pid != sidecar_pid
    assert ready.previous_sidecar_pid == sidecar_pid

    kids = supervisor.children
    assert kids[CLOUD_JOBS].pid == cloud_pid
    assert kids[SLIDESHOW].pid == show_pid
    assert kids[SIDECAR].pid != sidecar_pid
    assert is_pid_alive(cloud_pid)
    assert is_pid_alive(show_pid)

    error = supervisor.session_error("req-1")
    assert error is not None
    assert error.code == BRIDGE_DOWN
    assert error.retryable is True
    assert error.message_key == "bridge.unavailable"


def test_durable_child_restart_does_not_emit_bridge(supervisor: Supervisor) -> None:
    cloud_pid = supervisor.children[CLOUD_JOBS].pid
    os.kill(cloud_pid, signal.SIGKILL)
    _wait_for(lambda: supervisor.children[CLOUD_JOBS].pid != cloud_pid)
    assert supervisor.events() == ()
    assert is_pid_alive(supervisor.children[CLOUD_JOBS].pid)
    assert is_pid_alive(supervisor.children[SIDECAR].pid)
