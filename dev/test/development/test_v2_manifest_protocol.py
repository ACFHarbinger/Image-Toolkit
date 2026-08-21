"""Tests for #410: manifest-first plugin protocol (v2).

plugin.json is the single discovery contract; PluginManifest is a parsed
view of it. python_module runs in-process; command entries are argv the
host spawns with "--stdio" appended (D52 / Grok lock #8).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tool.host import (
    Channel,
    PluginEntry,
    PluginManifest,
    Surface,
    build_command_argv,
    discover_plugins,
    load_manifest,
    write_manifest,
)
from tool.host.plugins import MANIFEST_SCHEMA


def _manifest() -> PluginManifest:
    return PluginManifest(
        name="demo",
        version="1.2.3",
        description="demo plugin",
        surfaces=(Surface("cli"),),
        channels=(Channel("ch1", "Channel One", retention="7d"),),
        entry=PluginEntry(python_module="demo:plugin", command=("python", "-m", "demo")),
    )


class TestManifestRoundTrip:
    def test_to_dict_from_dict_roundtrip(self):
        m = _manifest()
        restored = PluginManifest.from_dict(m.to_dict())
        assert restored.name == "demo"
        assert restored.version == "1.2.3"
        assert restored.surface_names() == ("cli",)
        assert restored.channel_keys() == ("ch1",)
        assert restored.effective_entry().python_module == "demo:plugin"
        assert restored.effective_entry().command == ("python", "-m", "demo")

    def test_schema_fields(self):
        m = _manifest()
        d = m.to_dict()
        assert d["schema"] == MANIFEST_SCHEMA
        assert d["schema_version"] == 1
        assert d["entry"]["python_module"] == "demo:plugin"
        assert d["entry"]["command"] == ["python", "-m", "demo"]

    def test_legacy_entry_point_derives_python_module(self):
        m = PluginManifest(name="old", version="0", entry_point="tool.plugins.x:plugin")
        assert m.effective_entry().python_module == "tool.plugins.x:plugin"
        assert m.to_dict()["entry"]["python_module"] == "tool.plugins.x:plugin"


class TestManifestFileIO:
    def test_write_and_load(self, tmp_path):
        path = tmp_path / "demo.plugin.json"
        write_manifest(path, _manifest())
        restored = load_manifest(path)
        assert restored.name == "demo"
        assert restored.effective_entry().command == ("python", "-m", "demo")

    def test_rejects_unknown_schema(self, tmp_path):
        path = tmp_path / "bad.plugin.json"
        path.write_text(
            json.dumps({"schema": "other.schema", "name": "x", "version": "0"}),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="unsupported plugin manifest schema"):
            load_manifest(path)

    def test_rejects_newer_schema_version(self, tmp_path):
        path = tmp_path / "new.plugin.json"
        path.write_text(
            json.dumps(
                {"schema": MANIFEST_SCHEMA, "schema_version": 999, "name": "x", "version": "0"}
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="newer than host"):
            load_manifest(path)


class TestCommandArgv:
    def test_appends_stdio(self):
        m = _manifest()
        assert build_command_argv(m) == ["python", "-m", "demo", "--stdio"]

    def test_requires_command_entry(self):
        m = PluginManifest(name="x", version="0", entry=PluginEntry(python_module="x:plugin"))
        with pytest.raises(ValueError, match="no command entry"):
            build_command_argv(m)


class TestManifestFirstDiscovery:
    def test_in_tree_plugins_discovered_from_manifests(self):
        """discover_plugins() must load the 4 in-tree plugins from their
        .plugin.json manifests (python_module resolved in-process)."""
        plugins = discover_plugins()
        names = {p.manifest.name for p in plugins}
        assert {
            "telemetry_workbench",
            "asp_evaluator",
            "benchmarks",
            "editor_integration",
        } <= names
        for plugin in plugins:
            assert plugin.manifest.schema == MANIFEST_SCHEMA
            # the JSON manifest is authoritative: entry carries both selectors
            assert plugin.manifest.effective_entry().command, (
                f"{plugin.manifest.name} manifest must carry a command entry"
            )

    def test_in_tree_plugin_artifacts_still_work(self, tmp_path):
        from tool import WorkspaceStore

        store = WorkspaceStore(root=tmp_path)
        plugins = discover_plugins()
        bench = next(p for p in plugins if p.manifest.name == "benchmarks")
        # artifacts(store) must still be callable (no NotImplementedError)
        assert list(bench.artifacts(store)) == []
