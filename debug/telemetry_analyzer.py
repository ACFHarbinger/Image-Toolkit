#!/usr/bin/env python3
"""Analyze telemetry JSONL files written by backend/src/core/telemetry.py.

Built for the gallery-scan crash class documented in
docs/TROUBLESHOOTING.md and
.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md -- sixteen-plus
rounds of that investigation were bottlenecked on reading raw stdout dumps
by eye to figure out "what was in flight when the crash happened." This
tool automates that: it reconstructs a single merged, time-ordered timeline
from every event any thread/module emitted, and flags the two patterns
that investigation kept needing and never had tooling for:

1. **Orphaned spans** -- a `telemetry.span()` that emitted its `.start`
   event but never got to emit `.end`/`.error`. If the process died mid-
   span (SIGSEGV/SIGABRT), this is direct, unambiguous evidence of what
   native call was in flight at the moment of the crash -- exactly the
   question every addendum in the crash doc had to infer indirectly from
   which `print()` line appeared last.

2. **Overlapping scanner-thread windows** -- two ImageScannerWorker/
   VideoScannerWorker (or their extractor-tab equivalents) lifetimes that
   overlap in time, which is the shape of every root-cause theory in the
   investigation (deleteOrphaned races, stale scan_finished deliveries,
   linked-panel cross-talk) even though no single fix has yet closed it
   for good.

Usage:
    python debug/telemetry_analyzer.py                  # latest file, full report
    python debug/telemetry_analyzer.py PATH              # specific file
    python debug/telemetry_analyzer.py --tail 40          # last 40 events only
    python debug/telemetry_analyzer.py --list              # list available files
    python debug/telemetry_analyzer.py --category native   # filter timeline

Enable telemetry before reproducing a crash:
    IMAGE_TOOLKIT_TELEMETRY=1 just python
Files land in ~/.image-toolkit/telemetry/telemetry-<pid>.jsonl -- every line
is flushed immediately, so a truncated final line (the process died mid-
write) is expected and safely ignored, not an error.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

TELEMETRY_DIR = Path.home() / ".image-toolkit" / "telemetry"


def discover_files() -> List[Path]:
    if not TELEMETRY_DIR.exists():
        return []
    return sorted(TELEMETRY_DIR.glob("telemetry-*.jsonl"), key=lambda p: p.stat().st_mtime)


def latest_file() -> Optional[Path]:
    files = discover_files()
    return files[-1] if files else None


def load_events(path: Path) -> List[Dict[str, Any]]:
    """Parse a telemetry JSONL file, silently dropping a truncated final
    line (expected when the process crashed mid-write -- every completed
    line is still exactly as reliable as before)."""
    events = []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            if i == len(lines) - 1:
                print(f"(note: last line of {path.name} is truncated -- process likely crashed mid-write)")
            else:
                print(f"(warning: malformed line {i + 1} in {path.name}, skipping)")
    events.sort(key=lambda e: e.get("t", 0))
    return events


def format_event(e: Dict[str, Any]) -> str:
    fields = {
        k: v for k, v in e.items()
        if k not in ("t", "wall", "pid", "tid", "tname", "category", "event")
    }
    field_str = " ".join(f"{k}={v!r}" for k, v in fields.items())
    return f"t={e['t']:9.3f} tid={e['tid']} {e['category']}/{e['event']} {field_str}"


def find_orphaned_spans(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Any span whose `.start` has no matching `.end`/`.error` later in the
    file, matched per-thread (a span can't legitimately cross threads)."""
    open_spans: Dict[tuple, Dict[str, Any]] = {}
    for e in events:
        event_name = e.get("event", "")
        if event_name.endswith(".start"):
            base_name = event_name[: -len(".start")]
            key = (e["tid"], e["category"], base_name)
            open_spans[key] = e
        elif event_name.endswith(".end") or event_name.endswith(".error"):
            base_name = event_name.rsplit(".", 1)[0]
            key = (e["tid"], e["category"], base_name)
            open_spans.pop(key, None)
    return list(open_spans.values())


def find_scanner_overlaps(events: List[Dict[str, Any]]) -> List[str]:
    """Pairs of scanner-thread start windows (img/vid, wallpaper/extractor)
    whose [start.begin, start.returned-or-later-event] intervals overlap in
    time -- the shape every theory in the crash investigation has pointed
    at, across both linked Wallpaper panels and the Extractor tab."""
    START_MARKERS = (
        "img_worker.start.begin", "vid_worker.start.begin",
        "extractor_vid_worker.start.begin",
    )
    intervals: List[tuple] = []  # (start_t, end_t, label)
    open_by_worker: Dict[Any, Dict[str, Any]] = {}
    for e in events:
        event_name = e.get("event", "")
        if event_name in START_MARKERS:
            worker_key = e.get("img_thread") or e.get("vid_worker")
            open_by_worker[worker_key] = e
        elif event_name.endswith("wait.end") or event_name == "process_video_task.end":
            worker_key = e.get("img_thread") or e.get("vid_worker")
            start_e = open_by_worker.pop(worker_key, None)
            if start_e is not None:
                label = f"{start_e['event']} panel={start_e.get('panel')} worker={worker_key} [{start_e['t']:.3f}-{e['t']:.3f}]"
                intervals.append((start_e["t"], e["t"], label))

    overlaps = []
    for i in range(len(intervals)):
        for j in range(i + 1, len(intervals)):
            a_start, a_end, a_label = intervals[i]
            b_start, b_end, b_label = intervals[j]
            if a_start < b_end and b_start < a_end:
                overlaps.append(f"OVERLAP:\n    {a_label}\n    {b_label}")
    return overlaps


def print_report(events: List[Dict[str, Any]], path: Path) -> None:
    print(f"=== {path.name} ({len(events)} events) ===\n")

    if not events:
        print("No events in this file.")
        return

    by_category = defaultdict(int)
    for e in events:
        by_category[e["category"]] += 1
    print("Event counts by category:")
    for cat, count in sorted(by_category.items(), key=lambda kv: -kv[1]):
        print(f"  {cat:20s} {count}")
    print()

    threads = sorted({(e["tid"], e.get("tname", "?")) for e in events})
    print(f"Threads observed: {len(threads)}")
    for tid, tname in threads:
        print(f"  tid={tid} name={tname!r}")
    print()

    orphaned = find_orphaned_spans(events)
    if orphaned:
        print(f"⚠️  {len(orphaned)} ORPHANED SPAN(S) -- .start with no matching .end/.error.")
        print("    If this run crashed, this is almost certainly what was in flight:")
        for e in orphaned:
            print(f"    {format_event(e)}")
    else:
        print("No orphaned spans (every .start had a matching .end/.error).")
    print()

    overlaps = find_scanner_overlaps(events)
    if overlaps:
        print(f"⚠️  {len(overlaps)} OVERLAPPING SCANNER-THREAD WINDOW(S):")
        for o in overlaps:
            print(f"  {o}")
    else:
        print("No overlapping scanner-thread windows detected.")
    print()

    print("Last 15 events (crash-adjacent, if this run crashed):")
    for e in events[-15:]:
        print(f"  {format_event(e)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", nargs="?", help="Telemetry JSONL file to analyze (default: most recent)")
    parser.add_argument("--list", action="store_true", help="List available telemetry files and exit")
    parser.add_argument("--tail", type=int, default=None, help="Print only the last N events, no report")
    parser.add_argument("--category", default=None, help="Filter --tail output to one category")
    args = parser.parse_args()

    if args.list:
        files = discover_files()
        if not files:
            print(f"No telemetry files found in {TELEMETRY_DIR}")
            return 0
        for f in files:
            print(f"{f}  ({f.stat().st_size} bytes, mtime={f.stat().st_mtime:.0f})")
        return 0

    path = Path(args.path) if args.path else latest_file()
    if path is None or not path.exists():
        print(f"No telemetry file found (looked in {TELEMETRY_DIR}). "
              f"Run with IMAGE_TOOLKIT_TELEMETRY=1 set first.", file=sys.stderr)
        return 1

    events = load_events(path)
    if args.category:
        events = [e for e in events if e["category"] == args.category]

    if args.tail is not None:
        for e in events[-args.tail:]:
            print(format_event(e))
        return 0

    print_report(events, path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
