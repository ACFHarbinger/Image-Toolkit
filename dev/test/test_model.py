"""Tests for the devtool model: Event, Investigation, CrashBundle, ProcessTree."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devtool.model import CrashBundle, Event, Investigation, ProcessTree
from debugtool import Session


def _session(tmp_path: Path) -> Session:
    path = tmp_path / "telemetry-999.jsonl"
    lines = [
        {"t": 1.0, "category": "a", "event": "x.start", "tid": 1, "tname": "Main"},
        {"t": 2.0, "category": "a", "event": "x.end", "tid": 1, "tname": "Main"},
        {"t": 3.0, "category": "a", "event": "y.start", "tid": 2, "tname": "Worker", "child_pid": 1234},
        {"t": 4.0, "category": "a", "event": "y.error", "tid": 2, "tname": "Worker"},
    ]
    path.write_text("\n".join(json.dumps(e) for e in lines) + "\n", encoding="utf-8")
    return Session.open(path)


class TestEvent:
    def test_from_dict_splits_auto_fields(self):
        e = Event.from_dict({"t": 5.0, "category": "c", "event": "ev", "tid": 7, "custom": 1})
        assert e.t == 5.0
        assert e.category == "c"
        assert e.event == "ev"
        assert e.tid == 7
        assert e.get("custom") == 1

    def test_unknown_fields_preserved(self):
        e = Event.from_dict({"t": 0, "category": "c", "event": "ev", "foo": "bar"})
        assert e.fields == {"foo": "bar"}


class TestInvestigation:
    def test_create_append_reopen(self, tmp_path):
        inv = Investigation.create("bug-1", tmp_path)
        assert (tmp_path / "bug-1").is_dir()
        inv.append_note("hello", "deepseek")
        inv.link_session("/tmp/telemetry-1.jsonl")
        reopened = Investigation.open(tmp_path / "bug-1")
        assert reopened.name == "bug-1"
        assert reopened.sessions == ["/tmp/telemetry-1.jsonl"]
        assert reopened.notes()[0]["text"] == "hello"

    def test_create_conflict(self, tmp_path):
        Investigation.create("bug-1", tmp_path)
        with pytest.raises(FileExistsError):
            Investigation.create("bug-1", tmp_path)


class TestCrashBundle:
    def test_crashed_when_orphaned_span(self, tmp_path):
        # z.start with no matching .end/.error -> orphaned -> crashed.
        path = tmp_path / "telemetry-888.jsonl"
        path.write_text(
            json.dumps({"t": 1.0, "category": "a", "event": "z.start", "tid": 1, "tname": "Main"}) + "\n",
            encoding="utf-8",
        )
        session = Session.open(path)
        bundle = CrashBundle(session=session)
        assert "pid=888" in bundle.summarize()
        assert bundle.crashed is True

    def test_not_crashed_when_all_spans_end(self, tmp_path):
        session = _session(tmp_path)
        bundle = CrashBundle(session=session)
        assert bundle.crashed is False


class TestProcessTree:
    def test_from_session(self, tmp_path):
        tree = ProcessTree.from_session(_session(tmp_path))
        assert tree.pid == 999
        assert tree.thread_count() == 2
        assert tree.child_pids == [1234]
