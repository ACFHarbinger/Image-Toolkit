"""devtool command-line interface.

    python -m devtool                 # workspace chooser (no daemon)
    python -m devtool plugins         # name / version / surfaces
    python -m devtool plugins --json
    python -m devtool workspace       # same snapshot as the no-verb chooser
    python -m devtool workspace --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from ..host.app import Host
from ..host.store import WorkspaceStore


def _host_from_args(args: Any) -> Host:
    root = Path(args.workspace) if getattr(args, "workspace", None) else None
    tel = Path(args.telemetry_dir) if getattr(args, "telemetry_dir", None) else None
    store = WorkspaceStore(root=root, telemetry_dir=tel)
    return Host(store=store)


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
    print("Commands: plugins | workspace | python -m debugtool list|analyze|tui")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devtool",
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
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        args.json = False
        return cmd_workspace(args)
    if args.command == "plugins":
        return cmd_plugins(args)
    if args.command == "workspace":
        return cmd_workspace(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
