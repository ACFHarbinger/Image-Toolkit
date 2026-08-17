"""tool CLI: argument parser + command handlers.

Built by ``build_parser()``; each ``cmd_*`` function takes the parsed
argparse Namespace and returns an exit code. ``devtool.py`` (sibling of
this package) owns ``main()`` and command dispatch.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ..debug.analyzer import print_report, tail
from ..host.app import Host
from ..host.store import WorkspaceStore
from ..model import list_sessions, open_session
from . import track_a


def _host_from_args(args: Any) -> Host:
    root = Path(args.workspace) if getattr(args, "workspace", None) else None
    tel = Path(args.telemetry_dir) if getattr(args, "telemetry_dir", None) else None
    store = WorkspaceStore(root=root, telemetry_dir=tel)
    return Host(store=store)


def _resolve_session(args: Any) -> Path:
    if args.path:
        return Path(args.path)
    if args.pid is not None:
        session = open_session(pid=args.pid)
        if session is None:
            print(f"No telemetry file for pid {args.pid}.", file=sys.stderr)
            sys.exit(1)
        return session.path
    latest = list_sessions()
    if not latest:
        print(
            "No telemetry file found. Run with IMAGE_TOOLKIT_TELEMETRY=1 set first.",
            file=sys.stderr,
        )
        sys.exit(1)
    return latest[-1]


def cmd_list(_args: Any) -> int:
    files = list_sessions()
    if not files:
        print("No telemetry files found.")
        return 0
    for f in files:
        print(f"{f}  ({f.stat().st_size} bytes, mtime={f.stat().st_mtime:.0f})")
    return 0


def cmd_analyze(args: Any) -> int:
    path = _resolve_session(args)
    session = open_session(path=path)
    if args.tail is not None:
        for line in tail(session, n=args.tail, category=args.category):
            print(line)
        return 0
    for line in print_report(session, path=path):
        print(line)
    return 0


def cmd_tui(args: Any) -> int:
    from ..ui.app import run_tui

    path = _resolve_session(args)
    return run_tui(path, initial_view=args.view)


def cmd_watch(args: Any) -> int:
    from ..ui.app import run_tui

    path = _resolve_session(args)
    return run_tui(path, initial_view="live", live=True)


def cmd_plugins(args: Any) -> int:
    host = _host_from_args(args)
    plugins = host.discover()
    rows = [
        {
            "name": p.manifest.name,
            "version": p.manifest.version,
            "surfaces": list(p.manifest.surface_names()),
            "description": p.manifest.description,
        }
        for p in plugins
    ]
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    if not rows:
        print("No plugins discovered.")
        return 0
    for row in rows:
        surfaces = ",".join(row["surfaces"]) or "-"
        print(f"{row['name']}  {row['version']}  [{surfaces}]  {row['description']}")
    return 0


def cmd_workspace(args: Any) -> int:
    host = _host_from_args(args)
    snapshot = host.workspace()
    if args.json:
        print(json.dumps(snapshot, indent=2))
        return 0
    print(f"Development Tool  workspace={snapshot['workspace']}")
    print("Plugins")
    if not snapshot["plugins"]:
        print("  (none)")
    for plugin in snapshot["plugins"]:
        surfaces = ",".join(plugin["surfaces"]) or "-"
        print(f"  {plugin['name']}  {plugin['version']}  [{surfaces}]")
    print("Sessions")
    if not snapshot["sessions"]:
        print("  (none — run with IMAGE_TOOLKIT_TELEMETRY=1)")
    for path in snapshot["sessions"]:
        print(f"  {path}")
    print("Investigations")
    if not snapshot["investigations"]:
        print("  (none)")
    for name in snapshot["investigations"]:
        print(f"  {name}")
    print("Commands: plugins | workspace | list | analyze | tui | watch | web | mcp")
    return 0


def cmd_web(args: Any) -> int:
    from ..ui.web import WebServer

    host = _host_from_args(args)
    httpd = WebServer(host.store).serve(host=args.host, port=args.port)
    print(f"tool web listening on http://{args.host}:{httpd.server_port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()
    return 0


def cmd_mcp(args: Any) -> int:
    from ..mcp import McpServer

    host = _host_from_args(args)
    McpServer(host.store).serve_stdio()
    return 0


def cmd_serve(args: Any) -> int:
    from ..mcp import McpServer

    if not args.mcp:
        print("tool serve requires --mcp for now (C4).", file=sys.stderr)
        return 2
    host = _host_from_args(args)
    McpServer(host.store).serve_http(host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tool",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Workspace root (investigations + settings). Default: dev/investigations",
    )
    parser.add_argument(
        "--telemetry-dir",
        default=None,
        help="Override telemetry JSONL directory",
    )
    sub = parser.add_subparsers(dest="command")

    p_plugins = sub.add_parser("plugins", help="List discovered plugins")
    p_plugins.add_argument("--json", action="store_true", help="Machine-readable")

    p_ws = sub.add_parser("workspace", help="Print the workspace chooser")
    p_ws.add_argument("--json", action="store_true", help="Machine-readable")

    sub.add_parser("list", help="List available telemetry sessions")

    p_analyze = sub.add_parser("analyze", help="Full analysis report for one session")
    p_analyze.add_argument("path", nargs="?", help="Telemetry JSONL file")
    p_analyze.add_argument("--pid", type=int, default=None, help="Session pid")
    p_analyze.add_argument("--tail", type=int, default=None, help="Only last N events")
    p_analyze.add_argument("--category", default=None, help="Filter --tail by category")

    p_tui = sub.add_parser("tui", help="Launch visual TUI workbench")
    p_tui.add_argument("path", nargs="?", help="Telemetry JSONL file")
    p_tui.add_argument("--pid", type=int, default=None, help="Session pid")
    p_tui.add_argument(
        "--view",
        choices=["timeline", "crash", "concurrency", "memory", "flame", "live"],
        default="timeline",
        help="Initial view to display (default: timeline)",
    )

    p_watch = sub.add_parser("watch", help="Live btop-style telemetry monitor")
    p_watch.add_argument("path", nargs="?", help="Telemetry JSONL file")
    p_watch.add_argument("--pid", type=int, default=None, help="Session pid")

    p_web = sub.add_parser("web", help="Launch the localhost web viewer (C3)")
    p_web.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    p_web.add_argument("--port", type=int, default=0, help="Bind port (default 0 = ephemeral)")

    sub.add_parser("mcp", help="Run the MCP stdio server (C4)")

    p_serve = sub.add_parser("serve", help="Run tool in serve mode")
    p_serve.add_argument("--mcp", action="store_true", help="Serve MCP over localhost HTTP")
    p_serve.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=8000, help="Bind port")

    track_a.add_parsers(sub)
    return parser


#: Command name -> handler, assembled here so ``devtool.py``'s ``main()``
#: stays a thin dispatcher. Handlers needing an extra module (track_a's
#: cmd_export etc.) are referenced directly; no lazy import needed since
#: they all live in this same tool package now.
COMMANDS = {
    "plugins": cmd_plugins,
    "workspace": cmd_workspace,
    "list": cmd_list,
    "analyze": cmd_analyze,
    "tui": cmd_tui,
    "watch": cmd_watch,
    "web": cmd_web,
    "mcp": cmd_mcp,
    "serve": cmd_serve,
    "export": track_a.cmd_export,
    "diff": track_a.cmd_diff,
    "resolve-offset": track_a.cmd_resolve_offset,
    "prune": track_a.cmd_prune,
    "repro": track_a.cmd_repro,
}
