"""Unit tests for Track B Phase 7: Omniscient Debugging & Deterministic Replay (#399)."""

from __future__ import annotations

import json

import pytest
from conftest import event, write_session
from tool.host import Host, discover_plugins
from tool.host.store import WorkspaceStore
from tool.model.crash_bundle import CrashBundle
from tool.model.replay_trace import BugCapsule, ReplayTrace
from tool.model.session import Session
from tool.plugins.omniscient_debug import plugin
from tool.research.omniscient_debug import (
    delta_debug_events,
    occurrences,
    reverse_watch,
    state_at,
    suspicious_interleavings,
)


def _session(telemetry_dir, events, pid=399) -> Session:
    return Session.open(write_session(telemetry_dir, pid, events))


def test_trace_from_session_is_telemetry_backend(telemetry_dir):
    session = _session(telemetry_dir, [event(0.1, "log", "printf", msg="hello")])
    trace = ReplayTrace.from_session(session)
    assert trace.backend == "telemetry"
    assert len(trace.events) == 1
    assert trace.events[0].payload["msg"] == "hello"


def test_occurrences_finds_printf_and_payload(telemetry_dir):
    session = _session(
        telemetry_dir,
        [
            event(0.1, "log", "printf", msg="frame 0"),
            event(0.2, "log", "other"),
            event(0.3, "log", "printf", msg="frame 1"),
        ],
    )
    hits = occurrences(ReplayTrace.from_session(session), "printf")
    assert [h.t for h in hits] == [0.1, 0.3]
    by_msg = occurrences(ReplayTrace.from_session(session), "frame 1")
    assert len(by_msg) == 1
    assert by_msg[0].t == 0.3


def test_reverse_watch_returns_last_write_before_t(telemetry_dir):
    session = _session(
        telemetry_dir,
        [
            event(0.1, "mem", "store", pixel=1),
            event(0.4, "mem", "store", pixel=9),
            event(0.9, "mem", "store", pixel=3),
        ],
    )
    hit = reverse_watch(ReplayTrace.from_session(session), "pixel", at_t=0.5)
    assert hit is not None
    assert hit.t == 0.4
    assert hit.payload["pixel"] == 9
    assert reverse_watch(ReplayTrace.from_session(session), "pixel", at_t=0.5, value=1).t == 0.1


def test_state_at_sees_in_flight_span(telemetry_dir):
    session = _session(
        telemetry_dir,
        [
            event(0.1, "scan", "work.start"),
            event(0.2, "scan", "tick"),
            event(0.9, "scan", "work.end"),
        ],
    )
    snap = state_at(session, 0.3)
    assert snap["n_events"] == 2
    assert snap["in_flight"][0]["event"] == "work"
    assert snap["in_flight"][0]["start"] == 0.1
    assert snap["in_flight"][0]["end"] == 0.9


def test_suspicious_interleavings_flags_overlap_and_orphan(telemetry_dir):
    session = _session(
        telemetry_dir,
        [
            event(0.0, "scan", "work.start", worker="a"),
            event(0.1, "scan", "work.start", worker="b"),
            event(0.5, "scan", "work.end", worker="a"),
            event(0.8, "scan", "work.end", worker="b"),
            event(1.0, "scan", "hang.start"),
        ],
    )
    report = suspicious_interleavings(session)
    assert report["overlaps"]
    assert report["orphans"]
    assert report["orphans"][0]["event"] == "hang"


def test_delta_debug_keeps_failing_core():
    events = [
        event(0.0, "ok", "a"),
        event(0.1, "bad", "boom", worker="x"),
        event(0.2, "ok", "c"),
        event(0.3, "bad", "boom", worker="y"),
        event(0.4, "ok", "e"),
    ]

    def has_boom(subset):
        return any(e.get("event") == "boom" for e in subset)

    minimized = delta_debug_events(events, has_boom)
    assert minimized
    assert all(e.get("event") == "boom" for e in minimized)
    assert len(minimized) == 1


def test_capsule_digest_is_stable(telemetry_dir, tmp_path):
    session = _session(telemetry_dir, [event(0.1, "log", "x")])
    gdb = tmp_path / "bt.txt"
    gdb.write_text("Thread 1\n#0 foo\n", encoding="utf-8")
    bundle = CrashBundle(session=session, gdb_output=gdb, notes=["flake"])
    a = BugCapsule.from_crash_bundle(bundle)
    b = BugCapsule.from_crash_bundle(bundle)
    assert a.digest == b.digest
    assert a.gdb_present is True
    assert a.backend == "gdb"
    assert a.n_events == 1


def test_rr_sidecar_loads_without_invoking_rr(tmp_path):
    path = tmp_path / "trace.json"
    path.write_text(
        json.dumps(
            {
                "backend": "rr",
                "events": [
                    {"t": 0.2, "kind": "syscall", "name": "read", "thread": 1, "payload": {"fd": 3}},
                    {"t": 0.1, "kind": "sched", "name": "switch", "thread": 2},
                ],
            }
        ),
        encoding="utf-8",
    )
    trace = ReplayTrace.from_rr_sidecar(path)
    assert trace.backend == "rr"
    assert [e.t for e in trace.events] == [0.1, 0.2]


def test_rr_sidecar_rejects_wrong_backend(tmp_path):
    path = tmp_path / "nope.json"
    path.write_text(json.dumps({"backend": "gdb", "events": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="backend"):
        ReplayTrace.from_rr_sidecar(path)


def test_plugin_manifest_and_discovery(tmp_path):
    assert plugin.manifest.name == "omniscient_debug"
    assert plugin.manifest.channel_keys() == ("replay_trace", "bug_capsule")
    names = [p.manifest.name for p in Host(store=WorkspaceStore(root=tmp_path)).discover()]
    assert "omniscient_debug" in names
    assert "omniscient_debug" in [p.manifest.name for p in discover_plugins()]


def test_plugin_queries_end_to_end():
    events = [
        event(0.1, "log", "printf", msg="hi", pixel=1),
        event(0.2, "scan", "work.start", worker="a"),
        event(0.3, "scan", "work.start", worker="b"),
        event(0.4, "log", "printf", msg="hi", pixel=7),
        event(0.5, "scan", "work.end", worker="a"),
        event(0.6, "scan", "work.end", worker="b"),
    ]
    hits = plugin.find_occurrences(events, "printf")
    assert len(hits) == 2
    watch = plugin.watch(events, "pixel", 0.35)
    assert watch["payload"]["pixel"] == 1
    snap = plugin.snapshot(events, 0.35)
    assert any(row["event"] == "work" for row in snap["in_flight"])
    report = plugin.interleavings(events)
    assert report["overlaps"]
    capsule = plugin.capsule_from_events(events, pid=399, notes=["ci"])
    assert len(capsule["digest"]) == 64
    assert capsule["pid"] == 399


def test_plugin_load_rr_sidecar(tmp_path):
    path = tmp_path / "rr.json"
    path.write_text(json.dumps({"backend": "rr", "events": [{"t": 1.0, "kind": "user", "name": "x"}]}), encoding="utf-8")
    out = plugin.load_rr_sidecar(str(path))
    assert out["backend"] == "rr"
    assert out["events"][0]["name"] == "x"
