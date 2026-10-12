"""#741: TrainingEventTail reads events.jsonl off the GUI thread."""
import json
import time

import pytest
from gui.src.helpers.models.training_event_tail import TrainingEventTail
from PySide6.QtTest import QTest as qt_test

pytestmark = pytest.mark.gui


def wait_for(predicate, timeout_ms=4000):
    end = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < end:
        qt_test.qWait(20)
        if predicate():
            return True
    return False


@pytest.fixture
def tail(q_app):
    tail = TrainingEventTail()
    yield tail
    tail.stop()


def _append(path, events):
    with open(path, "a", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")
        fh.flush()


def test_tail_emits_appended_events(tmp_path, tail):
    received = []
    tail.events.connect(received.extend)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    tail.start(run_dir)

    _append(run_dir / "events.jsonl", [{"step": 1, "epoch": 0, "loss": 0.5}])
    assert wait_for(lambda: len(received) >= 1)
    assert received[0]["loss"] == 0.5

    _append(run_dir / "events.jsonl", [{"step": 2, "epoch": 0, "loss": 0.4}])
    assert wait_for(lambda: len(received) >= 2)
    assert received[1]["step"] == 2


def test_tail_starts_before_file_exists(tmp_path, tail):
    received = []
    tail.events.connect(received.extend)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    tail.start(run_dir)
    # The events file is created by the training process after start().
    _append(run_dir / "events.jsonl", [{"step": 1, "loss": 0.1}])
    assert wait_for(lambda: len(received) >= 1)


def test_torn_tail_line_is_reassembled_not_lost(tmp_path, tail):
    received = []
    tail.events.connect(received.extend)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    tail.start(run_dir)

    events_file = run_dir / "events.jsonl"
    _append(events_file, [{"step": 1, "loss": 0.5}])
    assert wait_for(lambda: len(received) >= 1)

    # A partial line (live append, torn read) must not be emitted or lost.
    with open(events_file, "a", encoding="utf-8") as fh:
        fh.write('{"step": 2, "loss": 0.')
        fh.flush()
    qt_test.qWait(150)
    assert len(received) == 1
    with open(events_file, "a", encoding="utf-8") as fh:
        fh.write('4}\n')
        fh.flush()
    assert wait_for(lambda: len(received) >= 2)
    assert received[1] == {"step": 2, "loss": 0.4}


def test_stop_prevents_further_emissions(tmp_path, tail):
    received = []
    tail.events.connect(received.extend)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    tail.start(run_dir)
    tail.stop()
    _append(run_dir / "events.jsonl", [{"step": 1, "loss": 0.1}])
    qt_test.qWait(200)
    assert received == []


def test_restart_ignores_old_inflight_read(tmp_path, tail, monkeypatch):
    import threading

    from gui.src.helpers.models.training_event_tail import _TailRead

    old = tmp_path / "old"
    new = tmp_path / "new"
    old.mkdir()
    new.mkdir()
    _append(old / "events.jsonl", [{"step": 1, "loss": 99}])
    _append(new / "events.jsonl", [{"step": 2, "loss": 0.1}])
    entered = threading.Event()
    release = threading.Event()
    original = _TailRead._execute

    def blocked(worker):
        result = original(worker)
        if worker._path.parent == old:
            entered.set()
            assert release.wait(3)
        return result

    monkeypatch.setattr(_TailRead, "_execute", blocked)
    received = []
    tail.events.connect(received.extend)
    tail.start(old)
    try:
        assert entered.wait(1)
        tail.start(new)
    finally:
        release.set()
    assert wait_for(lambda: bool(received))
    assert received == [{"step": 2, "loss": 0.1}]
