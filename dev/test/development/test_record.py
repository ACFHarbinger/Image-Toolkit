"""Tests for #409: the ``devtool.record`` schema and telemetry adapter.

Locks 9: Tauri/TUI/MCP all read this schema from day one; telemetry JSONL
becomes an adapter behind it, not a second parsed format.
"""

from __future__ import annotations

import json

from tool.model.record import SCHEMA, SCHEMA_VERSION, Record
from tool.model.session import Session
from tool.model.telemetry_record_adapter import records_from_session


class TestRecord:
    def test_round_trip(self):
        record = Record(kind="span", start_ms=1.0, end_ms=2.5, source="telemetry", workspace="/ws", payload={"a": 1})
        d = record.to_dict()
        assert d["schema"] == SCHEMA
        assert d["schema_version"] == SCHEMA_VERSION
        assert Record.from_dict(d) == record

    def test_duration_ms(self):
        assert Record(kind="span", start_ms=1.0, end_ms=3.5, source="x", workspace="/ws").duration_ms == 2.5

    def test_open_record_has_no_duration(self):
        assert Record(kind="span", start_ms=1.0, source="x", workspace="/ws").duration_ms is None

    def test_json_serializable(self):
        record = Record(kind="event", start_ms=1.0, source="telemetry", workspace="/ws", payload={"t": 1.0})
        json.dumps(record.to_dict())  # must not raise


def _write_session(tmp_path, pid=111):
    path = tmp_path / f"telemetry-{pid}.jsonl"
    lines = [
        {"t": 1.0, "wall": 1.0, "pid": pid, "tid": 1, "category": "app", "event": "startup.start"},
        {"t": 1.5, "wall": 1.5, "pid": pid, "tid": 1, "category": "app", "event": "startup.end"},
        {"t": 2.0, "wall": 2.0, "pid": pid, "tid": 1, "category": "app", "event": "marker", "note": "hi"},
    ]
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    return path


class TestTelemetryRecordAdapter:
    def test_span_becomes_span_record(self, tmp_path):
        session = Session.open(_write_session(tmp_path))
        records = records_from_session(session, workspace="/ws")
        spans = [r for r in records if r.kind == "span"]
        assert len(spans) == 1
        span = spans[0]
        assert span.start_ms == 1000.0
        assert span.end_ms == 1500.0
        assert span.payload["name"] == "startup"
        assert span.source == "telemetry"
        assert span.workspace == "/ws"

    def test_loose_event_becomes_event_record(self, tmp_path):
        session = Session.open(_write_session(tmp_path))
        records = records_from_session(session, workspace="/ws")
        events = [r for r in records if r.kind == "event"]
        assert len(events) == 1
        assert events[0].start_ms == 2000.0
        assert events[0].end_ms is None
        assert events[0].payload["note"] == "hi"

    def test_records_sorted_by_start(self, tmp_path):
        session = Session.open(_write_session(tmp_path))
        records = records_from_session(session, workspace="/ws")
        assert [r.start_ms for r in records] == sorted(r.start_ms for r in records)
