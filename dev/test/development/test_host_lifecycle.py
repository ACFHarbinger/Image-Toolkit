"""Tests for C1 host lifecycle + discovery (Grok slice)."""

from __future__ import annotations

import json
from pathlib import Path

from tool import Host, WorkspaceStore, discover_plugins
from tool.devtool import main


def _write_session(root: Path, pid: int) -> Path:
    path = root / f"telemetry-{pid}.jsonl"
    path.write_text(
        json.dumps({"t": 0.0, "category": "c", "event": "e", "tid": 1, "tname": "Main"})
        + "\n",
        encoding="utf-8",
    )
    return path


class TestDiscovery:
    def test_discovers_telemetry_workbench(self):
        plugins = discover_plugins()
        names = [p.manifest.name for p in plugins]
        assert "telemetry_workbench" in names
        tw = next(p for p in plugins if p.manifest.name == "telemetry_workbench")
        assert tw.manifest.version == "0.1.0"
        assert "cli" in tw.manifest.surface_names()

    def test_discover_is_idempotent(self):
        host = Host()
        first = host.discover()
        second = host.discover()
        assert [p.manifest.name for p in first] == [p.manifest.name for p in second]

    def test_plugin_lookup(self):
        host = Host()
        assert host.plugin("telemetry_workbench") is not None
        assert host.plugin("does-not-exist") is None


class TestHostWorkspace:
    def test_load_plugin_and_list_artifacts(self, tmp_path):
        tel = tmp_path / "telemetry"
        tel.mkdir()
        _write_session(tel, 42)
        store = WorkspaceStore(root=tmp_path / "ws", telemetry_dir=tel)
        host = Host(store=store)
        arts = host.artifacts("telemetry_workbench")
        sessions = [a for a in arts if a.kind == "session"]
        assert len(sessions) == 1
        assert sessions[0].meta["pid"] == 42

    def test_workspace_snapshot(self, tmp_path):
        store = WorkspaceStore(root=tmp_path / "ws", telemetry_dir=tmp_path / "empty")
        (tmp_path / "empty").mkdir()
        store.create_investigation("case-one")
        host = Host(store=store)
        snap = host.workspace()
        assert "telemetry_workbench" in [p["name"] for p in snap["plugins"]]
        assert snap["investigations"] == ["case-one"]
        assert snap["settings"]["redact_home_paths"] is True

    def test_register_view(self, tmp_path):
        host = Host(store=WorkspaceStore(root=tmp_path))
        host.register_view("timeline", lambda: None, surface="tui", plugin="telemetry_workbench")
        views = host.views(surface="tui")
        assert len(views) == 1
        assert views[0].name == "timeline"


class TestCli:
    def test_plugins_lists_first_party(self, capsys):
        assert main(["plugins"]) == 0
        out = capsys.readouterr().out
        assert "telemetry_workbench" in out
        assert "0.1.0" in out
        assert "cli" in out

    def test_plugins_json(self, capsys):
        assert main(["plugins", "--json"]) == 0
        rows = json.loads(capsys.readouterr().out)
        assert any(r["name"] == "telemetry_workbench" for r in rows)

    def test_no_verb_prints_workspace_chooser(self, tmp_path, capsys):
        tel = tmp_path / "tel"
        tel.mkdir()
        _write_session(tel, 7)
        ws = tmp_path / "ws"
        assert main(["--workspace", str(ws), "--telemetry-dir", str(tel)]) == 0
        out = capsys.readouterr().out
        assert "Development Tool" in out
        assert "telemetry_workbench" in out
        assert "telemetry-7.jsonl" in out

    def test_workspace_json(self, tmp_path, capsys):
        ws = tmp_path / "ws"
        tel = tmp_path / "tel"
        tel.mkdir()
        assert main(["--workspace", str(ws), "--telemetry-dir", str(tel), "workspace", "--json"]) == 0
        snap = json.loads(capsys.readouterr().out)
        assert snap["workspace"] == str(ws)
        assert any(p["name"] == "telemetry_workbench" for p in snap["plugins"])
