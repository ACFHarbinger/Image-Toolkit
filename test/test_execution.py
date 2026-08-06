"""Tests for native-worker crash containment and metadata-only diagnostics."""

from __future__ import annotations

import json
from threading import Event

import numpy as np
import pytest

from cel_shaded_generator.execution import (
    IsolatedRunner,
    JobCancelled,
    JobRequest,
    JobTimedOut,
    Operation,
    WorkerCrashed,
    adaptive_timeout,
    default_diagnostics_path,
)


def test_deliberate_worker_crash_does_not_kill_host_and_next_job_succeeds():
    runner = IsolatedRunner(maximum_timeout_seconds=5, diagnostics_enabled=False)

    with pytest.raises(WorkerCrashed, match="exit.*86"):
        runner.run(JobRequest(Operation._TEST_CRASH))

    assert runner.run(JobRequest(Operation.HEALTH_CHECK)) == "ok"


def test_timeout_terminates_hung_worker_and_runner_recovers():
    runner = IsolatedRunner(maximum_timeout_seconds=0.05, diagnostics_enabled=False)

    with pytest.raises(JobTimedOut):
        runner.run(JobRequest(Operation._TEST_HANG))

    runner.maximum_timeout_seconds = 5
    assert runner.run(JobRequest(Operation.HEALTH_CHECK)) == "ok"


def test_pre_requested_cancellation_is_deterministic():
    cancel = Event()
    cancel.set()

    with pytest.raises(JobCancelled):
        IsolatedRunner(diagnostics_enabled=False).run(JobRequest(Operation._TEST_HANG), cancel)


def test_adaptive_timeout_is_operation_specific_and_user_capped():
    inputs = {"gray_stack": np.zeros((4, 100, 100), dtype=np.uint8)}
    temporal = adaptive_timeout(JobRequest(Operation.TEMPORAL_COLORIZE, inputs), 60)
    scribble = adaptive_timeout(JobRequest(Operation.SCRIBBLE_COLORIZE, inputs), 60)

    assert temporal > scribble
    assert adaptive_timeout(JobRequest(Operation.TEMPORAL_COLORIZE, inputs), 3) == 3


def test_diagnostics_include_shapes_but_neither_pixels_nor_filenames(tmp_path):
    diagnostics = tmp_path / "diagnostics.jsonl"
    artwork = np.full((2, 3), 217, dtype=np.uint8)
    runner = IsolatedRunner(diagnostics_path=diagnostics)

    assert runner.run(JobRequest(Operation.HEALTH_CHECK, {"artwork": artwork})) == "ok"

    text = diagnostics.read_text()
    record = json.loads(text)
    assert record["dimensions"] == {"artwork": [2, 3]}
    assert "217" not in text
    assert "filename" not in text


def test_diagnostics_default_to_xdg_state_and_rotate_by_size(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    path = default_diagnostics_path()
    runner = IsolatedRunner(diagnostic_max_bytes=1)
    assert runner.diagnostics_path == path

    runner.run(JobRequest(Operation.HEALTH_CHECK))
    runner.run(JobRequest(Operation.HEALTH_CHECK))

    assert path.exists()
    assert path.with_suffix(".jsonl.previous").exists()


def test_diagnostics_can_be_disabled():
    assert IsolatedRunner(diagnostics_enabled=False).diagnostics_path is None
