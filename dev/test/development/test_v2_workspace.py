"""Tests for #412: workspace devtool.toml + global/workspace plugin discovery +
last-workspace restore."""

from __future__ import annotations

import json

from tool import WorkspaceStore, discover_plugins
from tool.host import workspace
from tool.host.plugins import MANIFEST_SCHEMA, PluginManifest, load_manifest
from tool.host.workspace import (
    discover_plugin_sources,
    load_last_workspace,
    load_workspace_config,
    save_last_workspace,
)


class TestWorkspaceConfig:
    def test_parse_devtool_toml(self, tmp_path):
        (tmp_path / "devtool.toml").write_text(
            "\n".join(
                [
                    "[workspace]",
                    'name = "my-repo"',
                    "monitor_depth = 5",
                    "",
                    "[[plugin]]",
                    'name = "local"',
                    'manifest = "local.plugin.json"',
                    "",
                    "[[plugin]]",
                    'name = "inline"',
                    'entry.python_module = "mypkg.plugin:plugin"',
                    'entry.command = [".venv/bin/python", "-m", "mypkg.plugin"]',
                ]
            ),
            encoding="utf-8",
        )
        config = load_workspace_config(tmp_path)
        assert config is not None
        assert config.name == "my-repo"
        assert config.monitor_depth == 5
        assert len(config.plugins) == 2
        assert config.plugins[0].name == "local"
        assert config.plugins[0].manifest == tmp_path / "local.plugin.json"
        assert config.plugins[1].python_module == "mypkg.plugin:plugin"
        assert config.plugins[1].command == [".venv/bin/python", "-m", "mypkg.plugin"]

    def test_no_config_returns_none(self, tmp_path):
        assert load_workspace_config(tmp_path) is None


class TestDiscovery:
    def _write_manifest(self, directory, name, entry_command=None):
        path = directory / f"{name}.plugin.json"
        path.write_text(
            json.dumps(
                {
                    "schema": MANIFEST_SCHEMA,
                    "name": name,
                    "version": "0.1.0",
                    "entry": {"python_module": None, "command": entry_command},
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_global_manifest_discovered(self, tmp_path):
        gdir = tmp_path / "global"
        gdir.mkdir()
        self._write_manifest(gdir, "gplugin")
        sources = discover_plugin_sources(root=None, global_dir=gdir, in_tree_dir=None)
        assert [load_manifest(s).name for s in sources if isinstance(s, __import__("pathlib").Path)] == ["gplugin"]

    def test_workspace_manifest_overrides_global(self, tmp_path):
        gdir = tmp_path / "global"
        gdir.mkdir()
        self._write_manifest(gdir, "dup")
        # workspace declares the same-name plugin at a local path
        local = self._write_manifest(tmp_path, "dup", entry_command=["python", "-m", "dup"])
        (tmp_path / "devtool.toml").write_text(
            "\n".join(["[[plugin]]", 'name = "dup"', 'manifest = "dup.plugin.json"']),
            encoding="utf-8",
        )
        sources = discover_plugin_sources(root=tmp_path, global_dir=gdir, in_tree_dir=None)
        paths = [s for s in sources if isinstance(s, __import__("pathlib").Path)]
        assert paths == [local], "workspace manifest must override the global one"

    def test_inline_command_entry_synthesized(self, tmp_path):
        (tmp_path / "devtool.toml").write_text(
            "\n".join(
                [
                    "[[plugin]]",
                    'name = "inline"',
                    'entry.command = ["python", "-m", "inline_plugin"]',
                ]
            ),
            encoding="utf-8",
        )
        sources = discover_plugin_sources(root=tmp_path, global_dir=None, in_tree_dir=None)
        manifests = [s for s in sources if isinstance(s, PluginManifest)]
        assert len(manifests) == 1
        assert manifests[0].name == "inline"
        assert manifests[0].effective_entry().command == ("python", "-m", "inline_plugin")


class TestLastWorkspace:
    def test_save_and_restore(self, tmp_path, monkeypatch):
        monkeypatch.setattr(workspace, "config_dir", lambda: tmp_path)
        save_last_workspace(tmp_path)
        assert load_last_workspace() == tmp_path

    def test_store_restores_last_workspace(self, tmp_path, monkeypatch):
        monkeypatch.setattr(workspace, "config_dir", lambda: tmp_path)
        save_last_workspace(tmp_path)
        store = WorkspaceStore(root=None)
        assert store.root == tmp_path

    def test_store_with_explicit_root_ignores_last(self, tmp_path, monkeypatch):
        monkeypatch.setattr(workspace, "config_dir", lambda: tmp_path)
        save_last_workspace(tmp_path)
        other = tmp_path / "other"
        other.mkdir()
        store = WorkspaceStore(root=other)
        assert store.root == other


class TestHostWorkspaceIntegration:
    def test_discover_plugins_still_finds_in_tree(self, monkeypatch):
        # in-tree pack must still be found when config_dir is isolated
        monkeypatch.setattr(workspace, "config_dir", lambda: __import__("pathlib").Path(__import__("tempfile").gettempdir()))
        names = {p.manifest.name for p in discover_plugins()}
        assert "telemetry_workbench" in names
