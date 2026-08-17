"""Tests for A2/A5: export, diff, sidecar index, RSS, manifest, resolve-offset."""

from __future__ import annotations

import json
from pathlib import Path

from debugtool import Session
from devtool import (
    WorkspaceStore,
    diff_sessions,
    export_session,
    format_diff,
    rss_trajectory,
)
from devtool.host.index import build_index, write_index


def _write_session(path: Path, events: list) -> Path:
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return path


def _ev(t, category, event, tid=1, tname="Main", **fields):
    base = {"t": t, "category": category, "event": event, "tid": tid, "tname": tname}
    base.update(fields)
    return base


class TestExport:
    def test_json(self, tmp_path):
        s = Session.open(_write_session(tmp_path / "telemetry-1.jsonl", [_ev(1.0, "a", "x.start")]))
        text = export_session(s, fmt="json")
        data = json.loads(text)
        assert data["pid"] == 1
        assert data["events"] == 1
        assert len(data["spans"]) == 1

    def test_csv(self, tmp_path):
        s = Session.open(_write_session(tmp_path / "telemetry-1.jsonl", [_ev(1.0, "a", "x")]))
        text = export_session(s, fmt="csv")
        assert "t,pid,tid,tname,category,event" in text

    def test_html(self, tmp_path):
        s = Session.open(_write_session(tmp_path / "telemetry-1.jsonl", [_ev(1.0, "a", "x.start")]))
        text = export_session(s, fmt="html")
        assert "<table>" in text
        assert "x.start" in text

    def test_export_to_file(self, tmp_path):
        s = Session.open(_write_session(tmp_path / "telemetry-1.jsonl", [_ev(1.0, "a", "x")]))
        out = tmp_path / "out.json"
        export_session(s, fmt="json", out=out)
        assert json.loads(out.read_text())["pid"] == 1

    def test_unknown_format(self, tmp_path):
        s = Session.open(_write_session(tmp_path / "telemetry-1.jsonl", [_ev(1.0, "a", "x")]))
        import pytest

        with pytest.raises(ValueError):
            export_session(s, fmt="yaml")


class TestDiff:
    def test_event_set_delta(self, tmp_path):
        a = Session.open(_write_session(tmp_path / "telemetry-1.jsonl", [_ev(1.0, "a", "x.start"), _ev(2.0, "a", "x.end")]))
        b = Session.open(_write_session(tmp_path / "telemetry-2.jsonl", [_ev(1.0, "a", "x.start"), _ev(2.0, "a", "x.end"), _ev(3.0, "b", "new")]))
        d = diff_sessions(a, b)
        assert d["event_count_delta"] == 1
        assert "b/new" in d["only_in_b"]

    def test_format_diff(self, tmp_path):
        a = Session.open(_write_session(tmp_path / "telemetry-1.jsonl", [_ev(1.0, "a", "x")]))
        b = Session.open(_write_session(tmp_path / "telemetry-2.jsonl", [_ev(1.0, "a", "x"), _ev(2.0, "a", "y")]))
        text = format_diff(diff_sessions(a, b))
        assert "diff pid 1 -> 2" in text


class TestRss:
    def test_trajectory(self, tmp_path):
        s = Session.open(_write_session(tmp_path / "telemetry-1.jsonl", [_ev(1.0, "lifecycle", "snap", rss_mb=100.0), _ev(2.0, "lifecycle", "snap", rss_mb=200.0)]))
        assert rss_trajectory(s) == [(1.0, 100.0), (2.0, 200.0)]


class TestSidecarIndex:
    def test_build_and_write(self, tmp_path):
        tel = tmp_path / "telemetry"
        tel.mkdir()
        _write_session(tel / "telemetry-7.jsonl", [_ev(1.0, "a", "x")])
        store = WorkspaceStore(root=tmp_path / "ws", telemetry_dir=tel)
        index = build_index(store)
        assert 7 in index
        assert index[7]["events"] == 1
        path = write_index(store)
        assert path.name == "index.json"
        assert json.loads(path.read_text())[str(7)]["events"] == 1


class TestManifest:
    def test_investigation_writes_manifest(self, tmp_path):
        store = WorkspaceStore(root=tmp_path)
        inv = store.create_investigation("bug-a")
        inv.append_note("hi", "deepseek")
        manifest = json.loads((inv.root / "manifest.json").read_text())
        assert manifest["name"] == "bug-a"
        assert manifest["note_count"] == 1
        assert manifest["format"] == "devtool.investigation"


class TestResolveOffset:
    def test_extract_frames_from_hs_err(self, tmp_path):
        try:
            from resolve_qt_offset import extract_frames_from_hs_err
        except ImportError:
            from debug.resolve_qt_offset import extract_frames_from_hs_err

        hs = tmp_path / "hs_err.log"
        hs.write_text("Problematic frame: C [libQt6Core.so.6+0x1e74d5]\n")
        frames = extract_frames_from_hs_err(hs)
        assert ("libQt6Core.so.6", 0x1E74D5) in frames

    def test_missing_library_reports_error(self, capsys):
        from devtool.cli import track_a

        track_a._print_resolved("libDoesNotExist.so.1", 0x1234)
        err = capsys.readouterr().err
        assert "Could not find" in err
