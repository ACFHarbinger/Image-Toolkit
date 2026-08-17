"""Tests for Session span/overlap queries (the crash-analysis core)."""

from __future__ import annotations

from conftest import event, write_session
from debugtool import Session


def _session_with_spans(telemetry_dir, events):
    path = write_session(telemetry_dir, 101, events)
    return Session.open(path)


def test_orphaned_span_detected(telemetry_dir):
    session = _session_with_spans(
        telemetry_dir,
        [
            event(0.0, "native", "decode.start", path="/a.mp4"),
            # no .end/.error -- the process died in the span
        ],
    )
    orphaned = session.orphaned_spans()
    assert len(orphaned) == 1
    assert orphaned[0].name == "decode"
    assert orphaned[0].orphaned is True
    assert orphaned[0].start_event["path"] == "/a.mp4"


def test_completed_span_not_orphaned(telemetry_dir):
    session = _session_with_spans(
        telemetry_dir,
        [
            event(0.0, "native", "decode.start"),
            event(0.1, "native", "decode.end", duration_ms=100.0),
        ],
    )
    assert session.orphaned_spans() == []
    spans = session.spans()
    assert len(spans) == 1
    assert spans[0].ended_ok is True
    assert spans[0].duration_ms == 100.0


def test_error_span_not_orphaned_but_flagged(telemetry_dir):
    session = _session_with_spans(
        telemetry_dir,
        [
            event(0.0, "native", "decode.start"),
            event(0.1, "native", "decode.error", error="boom"),
        ],
    )
    assert session.orphaned_spans() == []
    spans = session.spans()
    assert spans[0].ended_ok is False


def test_in_flight_at_returns_active_spans(telemetry_dir):
    session = _session_with_spans(
        telemetry_dir,
        [
            event(0.0, "native", "decode.start"),
            event(0.5, "native", "decode.end"),
        ],
    )
    assert len(session.in_flight_at(0.2)) == 1
    assert session.in_flight_at(0.6) == []
    # A never-ended span is in flight at any time after its start.
    session2 = _session_with_spans(telemetry_dir, [event(0.0, "native", "decode.start")])
    assert len(session2.in_flight_at(100.0)) == 1


def test_overlapping_windows_detected(telemetry_dir):
    session = _session_with_spans(
        telemetry_dir,
        [
            event(0.0, "scan", "img_worker.start.begin", img_thread="A", panel="p1"),
            event(0.1, "scan", "vid_worker.start.begin", vid_worker="B", panel="p2"),
            event(0.2, "scan", "vid_worker.wait.end", vid_worker="B"),
            event(0.3, "scan", "img_worker.wait.end", img_thread="A"),
        ],
    )
    overlaps = session.overlapping_windows()
    assert len(overlaps) == 1
    (a_label, b_label, *_rest) = overlaps[0]
    labels = a_label + " " + b_label
    assert "img_worker" in labels and "vid_worker" in labels


def test_non_overlapping_windows_not_detected(telemetry_dir):
    session = _session_with_spans(
        telemetry_dir,
        [
            event(0.0, "scan", "img_worker.start.begin", img_thread="A"),
            event(0.1, "scan", "img_worker.wait.end", img_thread="A"),
            event(0.2, "scan", "vid_worker.start.begin", vid_worker="B"),
            event(0.3, "scan", "vid_worker.wait.end", vid_worker="B"),
        ],
    )
    assert session.overlapping_windows() == []
