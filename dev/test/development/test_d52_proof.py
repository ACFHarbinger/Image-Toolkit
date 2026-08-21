"""Tests for #411: the D52 proof plugin (language-neutral command plugin).

The plugin is a tiny Go binary (dev/plugins/d52_proof/) answering the frozen
JSON-RPC-over-stdio contract: initialize + list_artifacts (+ ping). These
tests build it to a temp dir, spawn it with --stdio (Grok lock #8), and check
the wire protocol. Also verifies the in-tree manifest is discovered by the
host as a command-only plugin (#410).

Skipped when the Go toolchain is unavailable.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tool.host import build_command_argv, discover_plugins, load_manifest

DEV_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGIN_DIR = DEV_ROOT / "plugins" / "d52_proof"
MANIFEST = DEV_ROOT / "tool" / "plugins" / "d52_proof.plugin.json"


@pytest.fixture(scope="module")
def d52_binary(tmp_path_factory) -> str:
    go = shutil.which("go")
    if go is None:
        pytest.skip("go toolchain not available; cannot build d52_proof")
    binary = tmp_path_factory.mktemp("bin") / "d52_proof"
    result = subprocess.run(
        [go, "build", "-o", str(binary), "."],
        cwd=PLUGIN_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"go build failed: {result.stderr.strip()}")
    return str(binary)


def _rpc(binary: str, payload: dict) -> dict:
    proc = subprocess.Popen(
        [binary, "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = proc.communicate(json.dumps(payload) + "\n")
    assert proc.returncode == 0, f"plugin exited {proc.returncode}: {err.strip()}"
    line = out.strip()
    assert line, f"no response; stderr={err.strip()!r}"
    return json.loads(line)


class TestWireProtocol:
    def test_initialize_handshake(self, d52_binary):
        resp = _rpc(d52_binary, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        assert resp["id"] == 1
        result = resp["result"]
        assert result["protocolVersion"] == "1"
        assert result["serverInfo"]["name"] == "d52_proof"
        assert result["capabilities"]["artifacts"] is True

    def test_list_artifacts_structured_payload(self, d52_binary):
        resp = _rpc(d52_binary, {"jsonrpc": "2.0", "id": "x", "method": "list_artifacts"})
        assert resp["id"] == "x"
        artifacts = resp["result"]["artifacts"]
        assert len(artifacts) == 1
        assert artifacts[0]["kind"] == "report"
        assert artifacts[0]["meta"]["language"] == "go"

    def test_ping(self, d52_binary):
        resp = _rpc(d52_binary, {"jsonrpc": "2.0", "id": 2, "method": "ping"})
        assert resp["result"] == {}

    def test_unknown_method(self, d52_binary):
        resp = _rpc(d52_binary, {"jsonrpc": "2.0", "id": 3, "method": "nope"})
        assert resp["error"]["code"] == -32601

    def test_multiple_requests_one_process(self, d52_binary):
        proc = subprocess.Popen(
            [d52_binary, "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        payloads = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            {"jsonrpc": "2.0", "id": 2, "method": "ping"},
        ]
        out, err = proc.communicate("".join(json.dumps(p) + "\n" for p in payloads))
        assert proc.returncode == 0, f"stderr: {err.strip()}"
        lines = [json.loads(l) for l in out.strip().splitlines()]
        assert [l["id"] for l in lines] == [1, 2]

    def test_missing_stdio_flag_exits_2(self, d52_binary):
        proc = subprocess.Popen(
            [d52_binary],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        out, err = proc.communicate('{"jsonrpc":"2.0","id":1,"method":"initialize"}\n')
        assert proc.returncode == 2
        assert "--stdio" in err


class TestManifestIntegration:
    def test_manifest_is_loaded(self):
        manifest = load_manifest(MANIFEST)
        assert manifest.name == "d52_proof"
        assert manifest.effective_entry().command == ("dev/plugins/d52_proof/bin/d52_proof",)

    def test_host_appends_stdio(self):
        manifest = load_manifest(MANIFEST)
        assert build_command_argv(manifest) == [
            "dev/plugins/d52_proof/bin/d52_proof",
            "--stdio",
        ]

    def test_discovered_as_command_plugin(self):
        plugins = discover_plugins()
        names = {p.manifest.name for p in plugins}
        assert "d52_proof" in names
        plugin = next(p for p in plugins if p.manifest.name == "d52_proof")
        # command-only: host lists it but cannot spawn until the sidecar slice (#408)
        assert not plugin.manifest.effective_entry().python_module