"""Sidecar JSON-RPC-over-stdio server (#408).

Speaks the *same* frozen D52 command-plugin contract as d52_proof
(dev/plugins/d52_proof/) so the host has one process protocol for both a
command plugin and the sidecar: newline-delimited JSON-RPC 2.0 on stdio, with
``--stdio`` appended by the host (lock 8).

Methods (the frozen contract, per development_tool.md D52):
- initialize      -> {protocolVersion, capabilities, serverInfo}
- list_artifacts  -> {artifacts: [{kind, name, path, meta}...]} (#410 shape)
- ping            -> {}

Errors follow JSON-RPC 2.0: -32700 parse error (id null), -32601
method-not-found. Notifications (no id) get no response. The process exits 0
on stdin EOF.

Unlike a command plugin, the sidecar can import this monorepo's ``tool``
package, so list_artifacts serves the *real* Python plugin registry over the
same wire format -- the bundled, isolated Python surface (lock 5). The Record
adapter (#409) will add its own methods here later.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

from ..host.app import Host
from ..host.store import WorkspaceStore

SERVER_NAME = "devtool-sidecar"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "1"


class SidecarServer:
    """Stateless JSON-RPC server over a WorkspaceStore, D52 plugin protocol."""

    def __init__(self, store: WorkspaceStore, name: str = SERVER_NAME, version: str = SERVER_VERSION):
        self.store = store
        self.name = name
        self.version = version

    # ------------------------------------------------------------------
    # Protocol methods (the frozen D52 contract)
    # ------------------------------------------------------------------

    def _list_artifacts(self) -> List[Dict[str, Any]]:
        host = Host(store=self.store)
        out: List[Dict[str, Any]] = []
        for plugin in host.discover():
            try:
                artifacts = plugin.artifacts(self.store)
            except Exception:  # noqa: BLE001 -- one broken plugin must not fail the sidecar
                continue
            for artifact in artifacts:
                out.append(
                    {
                        "kind": artifact.kind,
                        "name": artifact.name,
                        "path": str(artifact.path) if artifact.path else None,
                        "meta": artifact.meta,
                    }
                )
        return out

    # ------------------------------------------------------------------
    # JSON-RPC 2.0 transport
    # ------------------------------------------------------------------

    def handle(self, raw: str) -> Optional[str]:
        """Handle one JSON-RPC message; return the response line (or None for
        notifications). Mirrors McpServer.handle and the d52_proof contract."""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
        if not isinstance(msg, dict) or "id" not in msg:
            return None  # notification: no response
        method = msg.get("method")
        msg_id = msg["id"]
        if method == "initialize":
            return json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {"artifacts": True},
                        "serverInfo": {"name": self.name, "version": self.version},
                    },
                }
            )
        if method == "list_artifacts":
            return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": {"artifacts": self._list_artifacts()}})
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


__all__ = ["SidecarServer", "SERVER_NAME", "SERVER_VERSION", "PROTOCOL_VERSION"]