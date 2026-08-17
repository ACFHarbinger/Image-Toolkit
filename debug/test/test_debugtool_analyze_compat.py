"""Compatibility: debugtool's report must preserve the original
telemetry_analyzer.py behavior for the same input (orphaned spans, scanner
overlaps, category counts, last events).
"""

from __future__ import annotations

from conftest import event, write_session
from debugtool import Session
from debugtool.analyzer import format_event, print_report


def test_report_flags_orphaned_span(telemetry_dir):
    path = write_session(
        telemetry_dir,
        201,
        [
            event(0.0, "native", "decode.start", path="/x.mp4"),
            event(0.1, "thread-lifecycle", "scanner.start", directory="/tmp"),
        ],
    )
    session = Session.open(path)
    lines = print_report(session, path=path)
    text = chr(10).join(lines)
    assert "2 ORPHANED SPAN(S)" in text
    assert "decode.start" in text
    assert "scanner.start" in text


def test_report_shows_category_counts_and_threads(telemetry_dir):
    path = write_session(
        telemetry_dir,
        202,
        [
            event(0.0, "native", "decode.start", tid=1, tname="MainThread"),
            event(0.1, "native", "decode.end", tid=1, tname="MainThread"),
            event(0.2, "cat", "x", tid=2, tname="Worker"),
        ],
    )
    session = Session.open(path)
    lines = print_report(session, path=path)
    text = chr(10).join(lines)
    assert "native" in text and "cat" in text
    assert "MainThread" in text and "Worker" in text


def test_format_event_matches_original_shape(telemetry_dir):
    path = write_session(telemetry_dir, 203, [event(1.234, "cat", "ev", foo="bar")])
    session = Session.open(path)
    line = format_event(session.events[0])
    assert "t=" in line and "cat/ev" in line and "foo='bar'" in line
