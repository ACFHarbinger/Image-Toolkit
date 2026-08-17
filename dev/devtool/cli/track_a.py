"""Track A CLI verbs: export, diff, resolve-offset, prune, repro (A2/A4/A5).

Kept in a separate module so the canonical CLI (cli/main.py) stays a thin
dispatcher. Each command takes the parsed argparse Namespace and returns an
int exit code.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, List, Optional

from debugtool import list_sessions, open_session


def _resolve_session_path(args: Any) -> Optional[Path]:
    if getattr(args, "path", None):
        return Path(args.path)
    if getattr(args, "pid", None):
        session = open_session(pid=args.pid)
        return session.path if session is not None else None
    sessions = list_sessions()
    return sessions[-1] if sessions else None


# ---------------------------------------------------------------------------
# export (A2)
# ---------------------------------------------------------------------------

def cmd_export(args: Any) -> int:
    from ..export import export_session

    path = _resolve_session_path(args)
    if path is None:
        print("No telemetry session found.", file=sys.stderr)
        return 1
    session = open_session(path=path)
    text = export_session(session, fmt=args.format, out=(Path(args.out) if args.out else None))
    if not args.out:
        print(text)
    return 0


# ---------------------------------------------------------------------------
# diff (A2/A5)
# ---------------------------------------------------------------------------

def cmd_diff(args: Any) -> int:
    from ..queries import diff_sessions, format_diff

    a = open_session(path=Path(args.a))
    b = open_session(path=Path(args.b))
    diff = diff_sessions(a, b)
    if args.json:
        print(json.dumps(diff, indent=2))
    else:
        print(format_diff(diff))
    return 0


# ---------------------------------------------------------------------------
# resolve-offset (A2)
# ---------------------------------------------------------------------------

def _print_resolved(lib: str, offset: int) -> None:
    try:
        from resolve_qt_offset import find_library, resolve
    except ImportError:
        from debug.resolve_qt_offset import find_library, resolve

    try:
        lib_path = find_library(lib)
    except FileNotFoundError as exc:
        print(f"{lib}+{hex(offset)}: {exc}", file=sys.stderr)
        return
    result = resolve(lib_path, offset)
    if result is None:
        print(f"{lib}+{hex(offset)}: no symbol at or before this offset")
    else:
        _addr, demangled, delta = result
        print(f"{lib}+{hex(offset)} -> {demangled} + {hex(delta)}")


def cmd_resolve_offset(args: Any) -> int:
    try:
        from resolve_qt_offset import extract_frames_from_hs_err
    except ImportError:
        from debug.resolve_qt_offset import extract_frames_from_hs_err

    if args.hs_err:
        frames = extract_frames_from_hs_err(Path(args.hs_err))
        for lib, offset in frames:
            _print_resolved(lib, offset)
        return 0
    if args.frame and "+" in args.frame:
        lib, offset_str = args.frame.rsplit("+", 1)
        _print_resolved(lib, int(offset_str, 16))
        return 0
    print("provide a FRAME (lib.so+0xOFF) or --hs-err PATH", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------
# prune (A2)
# ---------------------------------------------------------------------------

def cmd_prune(args: Any) -> int:
    sessions = list_sessions()
    keep = args.keep
    removed = 0
    if keep is not None and keep >= 0 and len(sessions) > keep:
        for path in sessions[:-keep]:
            path.unlink(missing_ok=True)
            removed += 1
    print(f"pruned {removed} session(s); {max(0, len(sessions) - removed)} remain")
    return 0


# ---------------------------------------------------------------------------
# repro (A4)
# ---------------------------------------------------------------------------

def cmd_repro(args: Any) -> int:
    """Run a command or named scenario under telemetry (optionally gdb), then write an
    investigation summarizing the run (session path, orphans, overlaps,
    natural-language hypothesis, gdb frames)."""
    from ..host.scenarios import get_scenario, list_scenarios
    from ..host.store import WorkspaceStore

    if getattr(args, "list_scenarios", False):
        print("Available Reproduction Scenarios:")
        for s in list_scenarios():
            tags_str = f"[{', '.join(s.tags)}]" if s.tags else ""
            print(f"  {s.name:22} {tags_str:20} {s.description}")
            print(f"    cmd: {' '.join(s.command)}")
        return 0

    cmd = list(args.cmd)
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]

    scenario_name = args.scenario
    if not cmd and scenario_name:
        sc = get_scenario(scenario_name)
        if sc:
            cmd = sc.command
            print(f"Running catalog scenario '{scenario_name}': {' '.join(cmd)}")
        else:
            print(f"Unknown scenario '{scenario_name}'. Use 'devtool repro --list-scenarios' to list.", file=sys.stderr)
            return 2

    if not cmd:
        print("repro requires a command or scenario (devtool repro --scenario <NAME> OR devtool repro -- CMD ARGS...)", file=sys.stderr)
        return 2

    env = os.environ.copy()
    env["IMAGE_TOOLKIT_TELEMETRY"] = "1"
    before = time.time()

    gdb_output = ""
    if args.gdb:
        gdb_output = _run_under_gdb(cmd, env)
        exit_code = 0
    else:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        exit_code = proc.returncode
        if proc.stdout:
            print(proc.stdout, end="")
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)

    # newest session written since we started
    sessions = [s for s in list_sessions() if s.stat().st_mtime >= before]
    session_path = sessions[-1] if sessions else None
    summary = _summarize(session_path, exit_code, gdb_output)

    root = Path(args.workspace) if getattr(args, "workspace", None) else None
    store = WorkspaceStore(root=root)
    name = scenario_name or f"repro-{int(time.time())}"
    try:
        inv = store.create_investigation(name)
    except FileExistsError:
        inv = store.open_investigation(name)
    for line in summary.splitlines():
        inv.append_note(line, author="devtool.repro")
    if session_path is not None:
        inv.link_session(str(session_path))
    if gdb_output:
        gdb_path = inv.root / "gdb-backtrace.txt"
        gdb_path.write_text(gdb_output, encoding="utf-8")

    print(summary)
    print(f"investigation: {inv.root}")
    return 0


def _run_under_gdb(cmd: List[str], env: dict) -> str:
    gdb_cmds = [
        "set pagination off",
        "handle SIGABRT stop print nopass",
        "handle SIGSEGV nostop noprint pass",
        "run",
        "thread apply all bt",
        "quit",
    ]
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".gdb", delete=False) as f:
        f.write("\n".join(gdb_cmds) + "\n")
        cmd_path = f.name
    try:
        result = subprocess.run(
            ["gdb", "-q", "-batch", "-x", cmd_path, "--args", *cmd],
            env=env,
            capture_output=True,
            text=True,
        )
        return result.stdout + result.stderr
    except FileNotFoundError:
        return "(gdb not installed; ran without a backtrace)"
    finally:
        os.unlink(cmd_path)


def _summarize(session_path: Optional[Path], exit_code: int, gdb_output: str) -> str:
    from ..queries.hypothesis import generate_hypothesis

    lines = [f"repro exit={exit_code}"]
    session = None
    if session_path is None:
        lines.append("no new telemetry session written")
    else:
        session = open_session(path=session_path)
        lines.append(f"session: {session_path}")
        lines.append(f"  events={len(session.events)} threads={len(session.thread_ids())}")
        orphaned = session.orphaned_spans()
        lines.append(f"  orphaned_spans={len(orphaned)}")
        for span in orphaned[:10]:
            lines.append(f"    {span}")
        overlaps = session.overlapping_windows()
        lines.append(f"  overlapping_windows={len(overlaps)}")
    if gdb_output and gdb_output.strip() and "gdb not installed" not in gdb_output:
        lines.append("gdb backtrace captured")

    # Natural-language root cause hypothesis
    hypothesis = generate_hypothesis(session, exit_code, gdb_output)
    lines.append("\nHypothesis & Diagnosis:")
    lines.append(hypothesis)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# parser wiring
# ---------------------------------------------------------------------------

def add_parsers(sub) -> None:
    p_export = sub.add_parser("export", help="Export a session (json|csv|html)")
    p_export.add_argument("path", nargs="?", help="Telemetry JSONL file")
    p_export.add_argument("--pid", type=int, default=None, help="Session pid")
    p_export.add_argument("--format", choices=["json", "csv", "html"], default="json")
    p_export.add_argument("--out", default=None, help="Write to this path instead of stdout")

    p_diff = sub.add_parser("diff", help="Diff two sessions")
    p_diff.add_argument("a", help="First telemetry JSONL file")
    p_diff.add_argument("b", help="Second telemetry JSONL file")
    p_diff.add_argument("--json", action="store_true", help="Machine-readable")

    p_ro = sub.add_parser("resolve-offset", help="Resolve lib.so+0xOFF to a symbol")
    p_ro.add_argument("frame", nargs="?", help="e.g. libQt6Core.so.6+0x1e74d5")
    p_ro.add_argument("--hs-err", default=None, help="Scan an hs_err/gdb log for frames")

    p_prune = sub.add_parser("prune", help="Remove old sessions, keep the newest N")
    p_prune.add_argument("--keep", type=int, default=20, help="Keep the newest N (default 20)")

    p_repro = sub.add_parser("repro", help="Run a command under telemetry and summarize (A4)")
    p_repro.add_argument("--scenario", default=None, help="Scenario or investigation name")
    p_repro.add_argument("--list-scenarios", action="store_true", help="List all catalogued reproduction scenarios")
    p_repro.add_argument("--gdb", action="store_true", help="Run under gdb (SIGABRT stop)")
    p_repro.add_argument("cmd", nargs=argparse.REMAINDER, help="Command + args to run")
    return None


__all__ = [
    "add_parsers",
    "cmd_diff",
    "cmd_export",
    "cmd_prune",
    "cmd_repro",
    "cmd_resolve_offset",
]
