"""D52 command-plugin stdio server (#413).

A command entry (Grok lock #8) is spawned by the host as
entry.command --stdio; the process must speak the frozen JSON-RPC
2.0-over-stdio contract (initialize / list_artifacts / ping) exactly like
the sidecar and the Go d52_proof plugin. This module is that server for a
single first-party IT plugin: it wraps one plugin object + a store and
answers with the plugin's real artifacts in the #410 shape
({kind, name, path, meta}).

Entry points:
- PluginStdioServer -- the JSON-RPC handler (mirrors SidecarServer).
- run_plugin_stdio(plugin, store=None, argv=None) -- the stdio main()
  used by each plugin module's __main__ guard and by the CLI's
  plugin-run <name> verb. Requires --stdio (the host appends it); exits
  with code 2 when missing, mirroring d52_proof.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

from .plugins import Plugin
from .store import WorkspaceStore

PROTOCOL_VERSION = "1"
SERVER_NAME = "devtool-plugin"


class PluginStdioServer:
    """JSON-RPC-over-stdio server for one first-party IT plugin (D52)."""

    def __init__(self, plugin: Plugin, store: WorkspaceStore) -> None:
        self.plugin = plugin
        self.store = store
        manifest = plugin.manifest
        self.name = manifest.name
        self.version = manifest.version

    def _list_artifacts(self) -> List[Dict[str, Any]]:
        try:
            artifacts = self.plugin.artifacts(self.store)
        except Exception:  # noqa: BLE001 -- one broken artifact call must not kill the process
            return []
        out: List[Dict[str, Any]] = []
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

    def handle(self, raw: str) -> Optional[str]:
        """Handle one JSON-RPC message; return the response line (or None
        for notifications). Mirrors SidecarServer / the d52_proof contract."""
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
                stdout.write(response + chr(10))
                stdout.flush()


def run_plugin_stdio(
    plugin: Plugin,
    store: Optional[WorkspaceStore] = None,
    argv: Optional[List[str]] = None,
) -> int:
    """The command-plugin entry main(): require --stdio, then serve.

    argv defaults to sys.argv[1:]; the host appends --stdio to the
    manifest's entry.command (Grok lock #8), so a spawn always satisfies it.
    Returns the process exit code.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--stdio" not in argv:
        print(
            f"{plugin.manifest.name}: --stdio is required (Grok lock #8: the host appends it)",
            file=sys.stderr,
        )
        return 2
    store = store or WorkspaceStore()
    PluginStdioServer(plugin, store).serve_stdio()
    return 0


__all__ = ["PluginStdioServer", "PROTOCOL_VERSION", "run_plugin_stdio"]
