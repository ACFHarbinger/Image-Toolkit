"""Tests for #413: IT plugin pack migrates to D52 command entries.

The four IT plugins (telemetry_workbench / asp_evaluator / benchmarks /
editor_integration) ship .plugin.json manifests whose entry.command the host
spawns with "--stdio" appended (Grok lock #8); the plugin process must then
speak the frozen JSON-RPC-over-stdio contract (initialize / list_artifacts /
ping) and answer with its REAL artifacts (#410 shape).

These tests pin: the shared PluginStdioServer protocol (mirroring the
sidecar), the run_plugin_stdio entry (--stdio required), the manifests'
spawnable argv, and a real subprocess spawn end-to-end.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from tool import WorkspaceStore
from tool.host import build_command_argv, discover_plugins, load_manifest
from tool.host.command import PROTOCOL_VERSION, PluginStdioServer, run_plugin_stdio

_REPO_ROOT = Path(__file__).resolve().parents[3]

IT_PLUGIN_NAMES = [
    "telemetry_workbench",
    "asp_evaluator",
    "benchmarks",
    "editor_integration",
]


def _server(plugin_name, tmp_path):
    store = WorkspaceStore(root=tmp_path)
    plugin = next(p for p in discover_plugins() if p.manifest.name == plugin_name)
    return PluginStdioServer(plugin, store)


class TestPluginStdioProtocol:
    @pytest.mark.parametrize("plugin_name", IT_PLUGIN_NAMES)
    def test_initialize_handshake(self, plugin_name, tmp_path):
        server = _server(plugin_name, tmp_path)
        resp = json.loads(server.handle('{"jsonrpc":"2.0","id":1,"method":"initialize"}'))
        assert resp["id"] == 1
        result = resp["result"]
        assert result["protocolVersion"] == PROTOCOL_VERSION
        assert result["serverInfo"]["name"] == plugin_name
        assert result["capabilities"]["artifacts"] is True

    @pytest.mark.parametrize("plugin_name", IT_PLUGIN_NAMES)
    def test_list_artifacts_wire_shape(self, plugin_name, tmp_path):
        server = _server(plugin_name, tmp_path)
        resp = json.loads(server.handle('{"jsonrpc":"2.0","id":2,"method":"list_artifacts"}'))
        assert resp["id"] == 2
        artifacts = resp["result"]["artifacts"]
        assert isinstance(artifacts, list)
        for artifact in artifacts:
            assert {"kind", "name", "path", "meta"} <= set(artifact)

    @pytest.mark.parametrize("plugin_name", IT_PLUGIN_NAMES)
    def test_ping(self, plugin_name, tmp_path):
        server = _server(plugin_name, tmp_path)
        resp = json.loads(server.handle('{"jsonrpc":"2.0","id":3,"method":"ping"}'))
        assert resp["result"] == {}

    @pytest.mark.parametrize("plugin_name", IT_PLUGIN_NAMES)
    def test_unknown_method(self, plugin_name, tmp_path):
        server = _server(plugin_name, tmp_path)
        resp = json.loads(server.handle('{"jsonrpc":"2.0","id":4,"method":"nope"}'))
        assert resp["error"]["code"] == -32601

    def test_parse_error_id_null(self, tmp_path):
        server = _server("telemetry_workbench", tmp_path)
        resp = json.loads(server.handle("{not json"))
        assert resp["id"] is None
        assert resp["error"]["code"] == -32700

    def test_notification_no_response(self, tmp_path):
        server = _server("telemetry_workbench", tmp_path)
        assert server.handle('{"jsonrpc":"2.0","method":"ping"}') is None

    @pytest.mark.parametrize("plugin_name", IT_PLUGIN_NAMES)
    def test_serve_stdio_end_to_end(self, plugin_name, tmp_path):
        import io

        server = _server(plugin_name, tmp_path)
        stdin = io.StringIO(
            '{"jsonrpc":"2.0","id":1,"method":"initialize"}\n'
            '{"jsonrpc":"2.0","id":2,"method":"list_artifacts"}\n'
            '{"jsonrpc":"2.0","id":3,"method":"ping"}\n'
        )
        stdout = io.StringIO()
        server.serve_stdio(stdin=stdin, stdout=stdout)
        lines = [json.loads(line) for line in stdout.getvalue().strip().splitlines()]
        assert [line["id"] for line in lines] == [1, 2, 3]
        assert lines[0]["result"]["serverInfo"]["name"] == plugin_name


class TestRunPluginStdio:
    def test_missing_stdio_returns_2(self, tmp_path):
        from tool.plugins import telemetry_workbench

        code = run_plugin_stdio(
            telemetry_workbench.plugin,
            store=WorkspaceStore(root=tmp_path),
            argv=[],
        )
        assert code == 2


class TestITPluginManifests:
    @pytest.mark.parametrize("plugin_name", IT_PLUGIN_NAMES)
    def test_manifest_carries_command_and_module(self, plugin_name):
        manifest = load_manifest(Path("dev/tool/plugins") / f"{plugin_name}.plugin.json")
        entry = manifest.effective_entry()
        assert entry.python_module == f"tool.plugins.{plugin_name}:plugin"
        assert entry.command == (".venv/bin/python", "dev", "plugin-run", plugin_name)
        # the host appends --stdio (lock #8)
        assert build_command_argv(manifest) == [
            ".venv/bin/python",
            "dev",
            "plugin-run",
            plugin_name,
            "--stdio",
        ]


class TestSpawnEndToEnd:
    """Spawn the plugin exactly as the host would (command argv + --stdio)
    and speak JSON-RPC over stdio; the process must answer with real
    artifacts."""

    @pytest.mark.parametrize("plugin_name", IT_PLUGIN_NAMES)
    def test_spawn_and_handshake(self, plugin_name, tmp_path):
        env = dict(__import__("os").environ)
        env["HOME"] = str(tmp_path / "home")
        (tmp_path / "home").mkdir(exist_ok=True)

        proc = subprocess.Popen(
            [sys.executable, "dev", "plugin-run", plugin_name, "--stdio"],
            cwd=str(_REPO_ROOT),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write('{"jsonrpc":"2.0","id":1,"method":"initialize"}\n')
        proc.stdin.write('{"jsonrpc":"2.0","id":2,"method":"list_artifacts"}\n')
        proc.stdin.write('{"jsonrpc":"2.0","id":3,"method":"ping"}\n')
        proc.stdin.flush()
        proc.stdin.close()

        lines = []
        for _ in range(3):
            line = proc.stdout.readline()
            assert line, f"plugin {plugin_name} closed stdout early"
            lines.append(json.loads(line))
        proc.wait(timeout=30)

        assert [line["id"] for line in lines] == [1, 2, 3]
        assert lines[0]["result"]["serverInfo"]["name"] == plugin_name
        artifacts = lines[1]["result"]["artifacts"]
        assert isinstance(artifacts, list)
        assert lines[2]["result"] == {}
