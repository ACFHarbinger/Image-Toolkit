"""MCP / stdio JSON-RPC server (C4).

Implements the Model Context Protocol over newline-delimited JSON-RPC 2.0 on
stdio (Claude/Codex/Gemini/Grok can attach). The only v1 mutation is
append_investigation_note -- timestamped, attributed, append-only, restricted
to an existing Investigation. Everything else is read-only; lifecycle, command,
retention, and settings changes stay human/CLI actions.

No third-party deps: the server is stdlib-only so it runs anywhere devtool
imports.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

from ..host.store import WorkspaceStore
from ..model import Session

SERVER_NAME = "devtool"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"


def _text_result(text: str, is_error: bool = False) -> Dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "isError": is_error,
    }


TOOLS: List[Dict[str, Any]] = [
    {
        "name": "list_sessions",
        "description": "List available telemetry session files (pid + path).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_investigations",
        "description": "List durable investigation folders in the workspace.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "session_summary",
        "description": "Summarize one telemetry session: categories, threads, orphaned spans.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pid": {"type": "integer"},
                "path": {"type": "string"},
            },
        },
    },
    {
        "name": "list_artifacts",
        "description": "List a plugin's artifacts (name, kind, path, meta).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entry_point": {"type": "string"},
            },
            "required": ["entry_point"],
        },
    },
    {
        "name": "append_investigation_note",
        "description": "Append a timestamped, attributed note to an existing investigation. The only mutation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "investigation": {"type": "string"},
                "text": {"type": "string"},
                "author": {"type": "string"},
            },
            "required": ["investigation", "text", "author"],
        },
    },
]


class McpServer:
    """Stateless-ish MCP server over a WorkspaceStore."""

    def __init__(self, store: WorkspaceStore, name: str = SERVER_NAME, version: str = SERVER_VERSION):
        self.store = store
        self.name = name
        self.version = version

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name == "list_sessions":
            return self._list_sessions()
        if name == "list_investigations":
            return self._list_investigations()
        if name == "session_summary":
            return self._session_summary(arguments)
        if name == "list_artifacts":
            return self._list_artifacts(arguments)
        if name == "append_investigation_note":
            return self._append_investigation_note(arguments)
        return _text_result(f"unknown tool: {name}", is_error=True)

    def _list_sessions(self) -> Dict[str, Any]:
        sessions = self.store.sessions()
        lines = [f"{s}  (pid from filename)" for s in sessions]
        return _text_result("\n".join(lines) if lines else "No sessions found.")

    def _list_investigations(self) -> Dict[str, Any]:
        invs = self.store.list_investigations()
        lines = [f"{i.name}  ({i.note_count} notes, {len(i.sessions)} sessions)" for i in invs]
        return _text_result("\n".join(lines) if lines else "No investigations.")

    def _session_summary(self, args: Dict[str, Any]) -> Dict[str, Any]:
        session: Optional[Session] = None
        if args.get("path"):
            session = Session.open(args["path"])
        elif args.get("pid") is not None:
            path = self.store.sessions()
            for p in path:
                if p.name == f"telemetry-{args['pid']}.jsonl":
                    session = Session.open(p)
                    break
        if session is None:
            return _text_result("session not found", is_error=True)
        cats = ", ".join(f"{k}={v}" for k, v in sorted(session.category_counts().items()))
        orphaned = len(session.orphaned_spans())
        summary = (
            f"pid={session.pid} events={len(session.events)} "
            f"threads={len(session.thread_ids())} orphaned_spans={orphaned}\n"
            f"categories: {cats}"
        )
        return _text_result(summary)

    def _list_artifacts(self, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            plugin = self.store.load_plugin(args["entry_point"])
        except Exception as exc:  # noqa: BLE001
            return _text_result(f"failed to load plugin: {exc}", is_error=True)
        artifacts = self.store.list_artifacts(plugin)
        lines = [f"{a.kind:14s} {a.name}" for a in artifacts]
        return _text_result("\n".join(lines) if lines else "No artifacts.")

    def _append_investigation_note(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("investigation", "")
        try:
            inv = self.store.open_investigation(name)
        except FileNotFoundError:
            return _text_result(f"no investigation named {name!r}", is_error=True)
        note = inv.append_note(args.get("text", ""), args.get("author", "agent"))
        return _text_result(f"note appended to {name} at {note['t']}")

    # ------------------------------------------------------------------
    # JSON-RPC 2.0
    # ------------------------------------------------------------------

    def handle(self, raw: str) -> Optional[str]:
        """Handle one JSON-RPC message; return the response line (or None for
        notifications)."""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
        if not isinstance(msg, dict) or "id" not in msg:
            # notification: no response
            return None
        method = msg.get("method")
        msg_id = msg["id"]
        if method == "initialize":
            return json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": self.name, "version": self.version},
                    },
                }
            )
        if method == "tools/list":
            return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}})
        if method == "tools/call":
            params = msg.get("params", {})
            result = self.call_tool(params.get("name", ""), params.get("arguments", {}))
            return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result})
        if method == "ping":
            return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": {}})
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"method not found: {method}"},
            }
        )

    def serve_stdio(self, stdin=None, stdout=None) -> None:
        """Run the stdio transport: read newline-delimited JSON-RPC, respond."""
        stdin = stdin or sys.stdin
        stdout = stdout or sys.stdout
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            response = self.handle(line)
            if response is not None:
                stdout.write(response + "\n")
                stdout.flush()

    def serve_http(self, host: str = "127.0.0.1", port: int = 8000) -> None:
        """Optional localhost HTTP transport (devtool serve --mcp)."""
        from http.server import BaseHTTPRequestHandler, HTTPServer

        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                response = server.handle(body)
                if response is None:
                    response = "{}"
                payload = response.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):  # silence default stderr logging
                pass

        if host == "0.0.0.0":
            raise ValueError("refusing to bind 0.0.0.0 (C4: never bind all-interfaces by default)")
        httpd = HTTPServer((host, port), Handler)
        print(f"devtool mcp listening on http://{host}:{httpd.server_port}", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            httpd.server_close()


__all__ = ["McpServer", "TOOLS", "SERVER_NAME", "SERVER_VERSION", "PROTOCOL_VERSION"]
