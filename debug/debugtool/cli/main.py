"""debugtool command-line interface.

Commands (Phase 1/2 of the debug workbench roadmap):

    debugtool list                     -- list available telemetry sessions
    debugtool analyze [path|--pid N]   -- full analysis report for one session
    debugtool analyze [path] --tail N  -- last N events only
    debugtool analyze [path] --category X -- filter tail by category

Later phases add: export, diff, repro, resolve-offset, investigation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .. import list_sessions, open_session
from ..analyzer import print_report, tail


def _resolve_session(args) -> Path:
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


def cmd_list(_args) -> int:
    files = list_sessions()
    if not files:
        print("No telemetry files found.")
        return 0
    for f in files:
        print(f"{f}  ({f.stat().st_size} bytes, mtime={f.stat().st_mtime:.0f})")
    return 0


def cmd_analyze(args) -> int:
    path = _resolve_session(args)
    session = open_session(path=path)
    if args.tail is not None:
        for line in tail(session, n=args.tail, category=args.category):
            print(line)
        return 0
    for line in print_report(session, path=path):
        print(line)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="debugtool",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List available telemetry sessions")

    p_analyze = sub.add_parser("analyze", help="Full analysis report for one session")
    p_analyze.add_argument("path", nargs="?", help="Telemetry JSONL file")
    p_analyze.add_argument("--pid", type=int, default=None, help="Session pid")
    p_analyze.add_argument("--tail", type=int, default=None, help="Only last N events")
    p_analyze.add_argument("--category", default=None, help="Filter --tail by category")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "list":
        return cmd_list(args)
    if args.command == "analyze":
        return cmd_analyze(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
