"""Tests for the C4 MCP server (JSON-RPC over WorkspaceStore)."""

from __future__ import annotations

import json

from tool import WorkspaceStore
from tool.mcp import McpServer


def _rpc(server: McpServer, method: str, params: dict = None, id: int = 1) -> dict:
    raw = json.dumps({"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}})
    return json.loads(server.handle(raw))


class TestMcpProtocol:
    def test_initialize(self, tmp_path):
        server = McpServer(WorkspaceStore(root=tmp_path))
        resp = _rpc(server, "initialize")
        result = resp["result"]
        assert result["serverInfo"]["name"] == "tool"
        assert result["protocolVersion"]
        assert "tools" in result["capabilities"]

    def test_tools_list(self, tmp_path):
        server = McpServer(WorkspaceStore(root=tmp_path))
        resp = _rpc(server, "tools/list")
        names = [t["name"] for t in resp["result"]["tools"]]
        assert "append_investigation_note" in names
        assert "session_summary" in names

    def test_notification_returns_none(self, tmp_path):
        server = McpServer(WorkspaceStore(root=tmp_path))
        raw = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
        assert server.handle(raw) is None

    def test_unknown_method(self, tmp_path):
        server = McpServer(WorkspaceStore(root=tmp_path))
        resp = _rpc(server, "bogus")
        assert resp["error"]["code"] == -32601


class TestMcpTools:
    def test_list_investigations(self, tmp_path):
        store = WorkspaceStore(root=tmp_path)
        store.create_investigation("bug-a")
        server = McpServer(store)
        resp = _rpc(server, "tools/call", {"name": "list_investigations", "arguments": {}})
        text = resp["result"]["content"][0]["text"]
        assert "bug-a" in text

    def test_append_note_to_existing_investigation(self, tmp_path):
        store = WorkspaceStore(root=tmp_path)
        store.create_investigation("bug-a")
        server = McpServer(store)
        resp = _rpc(
            server,
            "tools/call",
            {"name": "append_investigation_note", "arguments": {"investigation": "bug-a", "text": "hi", "author": "grok"}},
        )
        assert resp["result"]["isError"] is False
        notes = store.open_investigation("bug-a").notes()
        assert notes[0]["text"] == "hi"
        assert notes[0]["author"] == "grok"

    def test_append_note_requires_existing_investigation(self, tmp_path):
        store = WorkspaceStore(root=tmp_path)
        server = McpServer(store)
        resp = _rpc(
            server,
            "tools/call",
            {"name": "append_investigation_note", "arguments": {"investigation": "nope", "text": "x", "author": "a"}},
        )
        assert resp["result"]["isError"] is True

    def test_session_summary(self, tmp_path):
        tel = tmp_path / "telemetry"
        tel.mkdir()
        (tel / "telemetry-42.jsonl").write_text(
            json.dumps({"t": 0.0, "category": "a", "event": "e", "tid": 1, "tname": "Main"}) + "\n",
            encoding="utf-8",
        )
        store = WorkspaceStore(root=tmp_path / "ws", telemetry_dir=tel)
        server = McpServer(store)
        resp = _rpc(server, "tools/call", {"name": "session_summary", "arguments": {"pid": 42}})
        text = resp["result"]["content"][0]["text"]
        assert "pid=42" in text

    def test_list_artifacts(self, tmp_path):
        store = WorkspaceStore(root=tmp_path)
        server = McpServer(store)
        resp = _rpc(
            server,
            "tools/call",
            {"name": "list_artifacts", "arguments": {"entry_point": "tool.plugins.telemetry_workbench:plugin"}},
        )
        assert resp["result"]["isError"] is False
