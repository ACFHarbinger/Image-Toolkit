"""Tests for the C1 host data side: plugin protocol, settings, store."""

from __future__ import annotations

import json
from pathlib import Path

from devtool import (
    Channel,
    PluginManifest,
    Settings,
    Surface,
    WorkspaceStore,
)


def _manifest():
    return PluginManifest(
        name="demo",
        version="1.2.3",
        description="demo plugin",
        surfaces=(Surface("cli"), Surface("tui", "visual")),
        channels=(Channel("ch1", "Channel One", retention="7d"),),
        entry_point="demo_mod:plugin",
    )


class TestPluginManifest:
    def test_surface_names(self):
        m = _manifest()
        assert m.surface_names() == ("cli", "tui")

    def test_channel_keys(self):
        m = _manifest()
        assert m.channel_keys() == ("ch1",)

    def test_defaults(self):
        m = PluginManifest(name="x", version="0")
        assert m.description == ""
        assert m.surfaces == ()
        assert m.channels == ()
        assert m.surface_names() == ()


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert s.alert_emphasis == "orphaned_spans"
        assert s.redact_home_paths is True
        assert s.is_channel_enabled("unknown") is True  # plugin default

    def test_roundtrip(self, tmp_path):
        path = tmp_path / "settings.json"
        s = Settings(
            channel_enabled={"ch1": False},
            channel_retention={"ch1": "7d"},
            alert_emphasis="spans",
            redact_home_paths=False,
        )
        s.save(path)
        loaded = Settings.load(path)
        assert loaded.channel_enabled == {"ch1": False}
        assert loaded.channel_retention == {"ch1": "7d"}
        assert loaded.alert_emphasis == "spans"
        assert loaded.redact_home_paths is False

    def test_load_missing_returns_defaults(self, tmp_path):
        assert Settings.load(tmp_path / "nope.json").alert_emphasis == "orphaned_spans"


class TestWorkspaceStore:
    def _write_session(self, root: Path, pid: int) -> Path:
        path = root / f"telemetry-{pid}.jsonl"
        path.write_text(
            json.dumps({"t": 0.0, "category": "c", "event": "e", "tid": 1, "tname": "Main"})
            + "\n",
            encoding="utf-8",
        )
        return path

    def test_load_plugin_by_entry_point(self, tmp_path):
        store = WorkspaceStore(root=tmp_path)
        plugin = store.load_plugin("devtool.plugins.telemetry_workbench:plugin")
        assert plugin.manifest.name == "telemetry_workbench"
        assert plugin.manifest.version == "0.1.0"
        assert "cli" in plugin.manifest.surface_names()

    def test_list_artifacts_lists_sessions(self, tmp_path):
        tel = tmp_path / "telemetry"
        tel.mkdir()
        self._write_session(tel, 111)
        self._write_session(tel, 222)
        store = WorkspaceStore(root=tmp_path / "ws", telemetry_dir=tel)
        plugin = store.load_plugin("devtool.plugins.telemetry_workbench:plugin")
        artifacts = store.list_artifacts(plugin)
        session_artifacts = [a for a in artifacts if a.kind == "session"]
        assert len(session_artifacts) == 2
        assert {a.meta["pid"] for a in session_artifacts} == {111, 222}

    def test_investigation_crud(self, tmp_path):
        store = WorkspaceStore(root=tmp_path)
        inv = store.create_investigation("my-bug")
        inv.append_note("first note", "deepseek")
        inv.append_note("second note", "grok")
        assert store.list_investigations() == [] or len(store.list_investigations()) == 1
        loaded = store.open_investigation("my-bug")
        assert loaded.name == "my-bug"
        assert len(loaded.notes()) == 2
        assert loaded.notes()[0]["author"] == "deepseek"

    def test_settings_roundtrip_via_store(self, tmp_path):
        store = WorkspaceStore(root=tmp_path)
        store.save_settings(Settings(alert_emphasis="spans"))
        assert store.load_settings().alert_emphasis == "spans"
