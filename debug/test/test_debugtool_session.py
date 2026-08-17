"""Tests for the Session model: loading, discovery, metadata, spans."""

from __future__ import annotations

from conftest import event, write_session
from debugtool import Session, discover_sessions, open_session, session_path_for_pid


def test_discover_sessions_sorted(telemetry_dir):
    write_session(telemetry_dir, 111, [event(0.0, "cat", "a")])
    write_session(telemetry_dir, 222, [event(0.0, "cat", "b")])
    files = discover_sessions(telemetry_dir)
    assert len(files) == 2
    # Sorted by mtime (oldest first).
    assert files[0].name == "telemetry-111.jsonl"
    assert files[1].name == "telemetry-222.jsonl"


def test_open_session_parses_and_sorts(telemetry_dir):
    path = write_session(
        telemetry_dir,
        333,
        [event(0.5, "cat", "later"), event(0.1, "cat", "earlier")],
    )
    session = Session.open(path)
    assert session.pid == 333
    assert len(session.events) == 2
    # Events are time-ordered regardless of file order.
    assert session.events[0]["event"] == "earlier"
    assert session.events[1]["event"] == "later"
    assert session.start_time == 0.1
    assert session.end_time == 0.5


def test_open_session_tolerates_truncated_final_line(telemetry_dir):
    path = telemetry_dir / "telemetry-444.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        f.write('{"t": 0.1, "category": "cat", "event": "ok"}\n')
        f.write('{"t": 0.2, "category": "cat", "event": "crash"')  # truncated
    session = Session.open(path)
    assert len(session.events) == 1
    assert session.truncated_final_line is True


def test_open_session_skips_malformed_middle_line(telemetry_dir):
    path = telemetry_dir / "telemetry-555.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        f.write('{"t": 0.1, "category": "cat", "event": "ok"}\n')
        f.write("not-json\n")
        f.write('{"t": 0.3, "category": "cat", "event": "later"}\n')
    session = Session.open(path)
    assert len(session.events) == 2
    assert session.malformed_lines == [2]


def test_open_session_by_pid(telemetry_dir):
    write_session(telemetry_dir, 666, [event(0.0, "cat", "x")])
    assert session_path_for_pid(666, telemetry_dir) is not None
    session = open_session(pid=666, directory=telemetry_dir)
    assert session is not None and session.pid == 666
    assert open_session(pid=999999, directory=telemetry_dir) is None


def test_open_session_requires_path_or_pid():
    try:
        open_session()
    except ValueError:
        return
    raise AssertionError("expected ValueError when neither path nor pid given")


def test_category_counts_and_events_for(telemetry_dir):
    path = write_session(
        telemetry_dir,
        777,
        [
            event(0.0, "native", "decode.start"),
            event(0.1, "native", "decode.end"),
            event(0.2, "cat", "other"),
        ],
    )
    session = Session.open(path)
    assert session.category_counts() == {"native": 2, "cat": 1}
    assert len(session.events_for(category="native")) == 2
    assert len(session.events_for(category="native", event="decode.start")) == 1
