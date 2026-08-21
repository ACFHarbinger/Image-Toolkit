"""Unit tests for D3 (Search Knowledge Base) and D4 (Performance Profiler)."""

from __future__ import annotations

import json
from pathlib import Path

from tool.cli.parser import build_parser, cmd_perf, cmd_search
from tool.host.store import WorkspaceStore
from tool.mcp.server import McpServer
from tool.model.session import Session
from tool.queries.perf import format_profile_report, profile_session, render_profile_panel
from tool.queries.search import search_workspace


def _ev(t, category, event, tid=1, tname="MainThread", **fields):
    base = {
        "t": t,
        "wall": 1786567965.0 + t,
        "pid": 999,
        "tid": tid,
        "tname": tname,
        "category": category,
        "event": event,
    }
    base.update(fields)
    return base


def _write_session(path: Path, events: list) -> Path:
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return path


class TestD3Search:
    def test_search_investigation_and_notes(self, tmp_path):
        store = WorkspaceStore(root=tmp_path / "investigations", telemetry_dir=tmp_path / "telemetry")
        inv = store.create_investigation("crash-repro-gallery")
        inv.append_note("Observed SIGSEGV in deleteOrphaned during QObject teardown", author="gemini")

        results = search_workspace("deleteOrphaned", store=store)
        assert len(results) >= 1
        assert results[0].source_type == "investigation_note"
        assert "deleteOrphaned" in results[0].snippet

        name_results = search_workspace("gallery", store=store)
        assert any(r.source_type == "investigation_meta" for r in name_results)

    def test_search_sessions(self, tmp_path):
        tel_dir = tmp_path / "telemetry"
        tel_dir.mkdir(parents=True)
        store = WorkspaceStore(root=tmp_path / "investigations", telemetry_dir=tel_dir)

        events = [
            _ev(0.1, "extractor", "video_frame.extract", video_id="vid_12345"),
            _ev(0.2, "extractor", "video_frame.done", video_id="vid_12345"),
        ]
        _write_session(tel_dir / "telemetry-999.jsonl", events)

        results = search_workspace("vid_12345", store=store, category="events")
        assert len(results) >= 1
        assert results[0].source_type == "session_event"
        assert "vid_12345" in results[0].snippet

    def test_cli_search(self, tmp_path, capsys):
        store = WorkspaceStore(root=tmp_path / "investigations", telemetry_dir=tmp_path / "telemetry")
        inv = store.create_investigation("alpha-bug")
        inv.append_note("Found memory leak in wallpaper renderer", author="grok")

        parser = build_parser()
        args = parser.parse_args(["--workspace", str(tmp_path / "investigations"), "search", "wallpaper"])
        ret = cmd_search(args)
        assert ret == 0
        out, _ = capsys.readouterr()
        assert "Search Results for 'wallpaper'" in out
        assert "alpha-bug" in out


class TestD4PerformanceProfiler:
    def test_profile_session_metrics(self, tmp_path):
        events = [
            _ev(0.0, "scanner", "scan.start", span_id="s1"),
            _ev(0.05, "scanner", "scan.end", span_id="s1"),
            _ev(0.06, "scanner", "scan.start", span_id="s2"),
            _ev(0.20, "scanner", "scan.end", span_id="s2"),
            _ev(0.21, "render", "paint.start", span_id="s3"),
            _ev(0.22, "render", "paint.end", span_id="s3"),
        ]
        path = _write_session(tmp_path / "telemetry-111.jsonl", events)
        session = Session.open(path)

        profile = profile_session(session)
        assert profile["pid"] == 111
        assert profile["total_spans"] == 3
        assert "scanner/scan" in profile["stages"]
        assert profile["stages"]["scanner/scan"]["count"] == 2
        assert profile["stages"]["scanner/scan"]["total_ms"] > 180.0

        # Bottleneck detection check
        assert len(profile["bottlenecks"]) >= 1
        assert profile["bottlenecks"][0]["stage"] == "scanner/scan"

    def test_format_and_render_profile(self, tmp_path):
        events = [
            _ev(0.0, "io", "read.start", span_id="s1"),
            _ev(0.01, "io", "read.end", span_id="s1"),
        ]
        path = _write_session(tmp_path / "telemetry-222.jsonl", events)
        session = Session.open(path)
        profile = profile_session(session)

        text_rep = format_profile_report(profile)
        assert "Performance Profile for Session PID 222" in text_rep
        assert "io/read" in text_rep

        json_rep = format_profile_report(profile, json_mode=True)
        data = json.loads(json_rep)
        assert data["pid"] == 222

        panel = render_profile_panel(profile)
        assert panel is not None

    def test_cli_perf(self, tmp_path, capsys):
        events = [
            _ev(0.0, "db", "query.start", span_id="s1"),
            _ev(0.04, "db", "query.end", span_id="s1"),
        ]
        path = _write_session(tmp_path / "telemetry-333.jsonl", events)

        parser = build_parser()
        args = parser.parse_args(["perf", str(path), "--text"])
        ret = cmd_perf(args)
        assert ret == 0
        out, _ = capsys.readouterr()
        assert "Performance Profile for Session PID 333" in out
        assert "db/query" in out


class TestMcpIntegration:
    def test_mcp_search_and_profile(self, tmp_path):
        tel_dir = tmp_path / "telemetry"
        tel_dir.mkdir(parents=True)
        store = WorkspaceStore(root=tmp_path / "investigations", telemetry_dir=tel_dir)
        inv = store.create_investigation("perf-investigation")
        inv.append_note("Recorded 45ms latency bottleneck in sqlite commit", author="claude")

        events = [
            _ev(0.0, "sqlite", "commit.start", span_id="s1"),
            _ev(0.045, "sqlite", "commit.end", span_id="s1"),
        ]
        _write_session(tel_dir / "telemetry-888.jsonl", events)

        server = McpServer(store=store)

        # 1. Search MCP Tool
        search_res = server.call_tool("search_knowledge", {"term": "sqlite"})
        assert not search_res.get("isError")
        text = search_res["content"][0]["text"]
        assert "perf-investigation" in text or "sqlite" in text

        # 2. Profile MCP Tool
        prof_res = server.call_tool("profile_session", {"pid": 888})
        assert not prof_res.get("isError")
        prof_text = prof_res["content"][0]["text"]
        assert "sqlite/commit" in prof_text
