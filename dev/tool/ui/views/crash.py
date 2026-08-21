"""Crash Forensics Splicer TUI View.

Correlates:
- Truncated telemetry lines and in-flight/orphaned spans at the moment of failure.
- GDB all-thread backtraces & JVM hs_err logs.
- Native symbol offset resolution (libQt6Core.so.6+0x... -> function symbol).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from ...model.session import Session, Span


def _find_hs_err_logs(pid: int) -> List[Path]:
    """Look for hs_err_pid<pid>.log in current working directory and home."""
    candidates = [
        Path.cwd() / f"hs_err_pid{pid}.log",
        Path.home() / f"hs_err_pid{pid}.log",
        Path("/tmp") / f"hs_err_pid{pid}.log",
    ]
    return [p for p in candidates if p.exists()]


def _extract_crash_frame_from_hs_err(path: Path) -> Optional[str]:
    """Extract 'Problematic frame: ...' from an hs_err log."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "Problematic frame:" in line or "# C  [" in line:
                    return line.strip()
    except Exception:
        pass
    return None


def render_crash(
    session: "Session",
    gdb_trace: Optional[str] = None,
    hs_err_path: Optional[str] = None,
) -> RenderableType:
    """Render the Crash Forensics Splicer view."""
    orphans: List["Span"] = session.orphaned_spans()
    end_t = session.end_time or 0.0

    # 1. Fault Summary Header
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold red")
    summary.add_column()
    summary.add_column(style="bold yellow")
    summary.add_column()

    summary.add_row(
        "Crash Status:",
        "[bold red]PROCESS TERMINATED ABNORMALLY[/bold red]"
        if (session.truncated_final_line or orphans)
        else "[green]Clean Exit (No truncated lines/orphans)[/green]",
        "Final Telemetry Time:",
        f"t = {end_t:.4f} s",
    )
    summary.add_row(
        "Truncated Line:",
        "[bold red]YES (died mid-write / SIGSEGV/SIGABRT)[/bold red]"
        if session.truncated_final_line
        else "No",
        "Orphaned Spans:",
        f"[bold red]{len(orphans)} in-flight at crash[/bold red]",
    )

    # 2. In-flight Spans Table
    in_flight_table = Table(
        title="Spans In-Flight at Timestamp of Crash",
        title_style="bold red",
        expand=True,
        header_style="bold white on dark_red",
    )
    in_flight_table.add_column("Thread (TID)", style="magenta", width=18)
    in_flight_table.add_column("Category", style="yellow", width=14)
    in_flight_table.add_column("Span Name", style="bold white")
    in_flight_table.add_column("Start Time", justify="right", style="cyan", width=14)
    in_flight_table.add_column("Active For", justify="right", style="bold red", width=14)
    in_flight_table.add_column("Initial Event Payload", style="dim")

    for s in orphans:
        active_ms = (end_t - s.start) * 1000.0
        payload_str = ", ".join(
            f"{k}={v}"
            for k, v in s.start_event.items()
            if k not in ("t", "wall", "pid", "tid", "tname", "category", "event")
        )
        in_flight_table.add_row(
            f"{s.start_event.get('tname', '?')} ({s.tid})",
            s.category,
            s.name,
            f"{s.start:.4f}s",
            f"{active_ms:.1f}ms",
            payload_str or "-",
        )

    # 3. Crash logs correlation (hs_err or GDB)
    hs_err_files = [Path(hs_err_path)] if hs_err_path else _find_hs_err_logs(session.pid)

    log_sections = []
    if hs_err_files:
        for p in hs_err_files:
            frame = _extract_crash_frame_from_hs_err(p)
            log_text = Text()
            log_text.append(f"Found JVM Fatal Error Log: {p}\n", style="bold yellow")
            if frame:
                log_text.append(f"  {frame}\n", style="bold red")
            log_sections.append(Panel(log_text, title="[bold]JVM hs_err Crash Dump[/bold]", border_style="red"))

    if gdb_trace:
        log_sections.append(
            Panel(Text(gdb_trace, style="dim white"), title="[bold]GDB Backtrace[/bold]", border_style="red")
        )

    # 4. Tail events leading up to crash
    tail_table = Table(
        title="Last 8 Telemetry Events Before Process Termination",
        title_style="bold yellow",
        expand=True,
        header_style="bold white on grey23",
    )
    tail_table.add_column("Time", justify="right", style="cyan", width=12)
    tail_table.add_column("Thread", style="magenta", width=14)
    tail_table.add_column("Category", style="yellow", width=12)
    tail_table.add_column("Event", style="bold white")
    tail_table.add_column("Details", style="dim")

    for e in session.events[-8:]:
        details = ", ".join(
            f"{k}={v}"
            for k, v in e.items()
            if k not in ("t", "wall", "pid", "tid", "tname", "category", "event")
        )
        tail_table.add_row(
            f"{e.get('t', 0.0):.4f}s",
            f"{e.get('tname', '?')}",
            e.get("category", "?"),
            e.get("event", "?"),
            details or "-",
        )

    content_items = [
        Panel(summary, title="[bold]Crash Splicer Summary[/bold]", border_style="red"),
        in_flight_table,
    ]
    content_items.extend(log_sections)
    content_items.append(tail_table)

    return Panel(
        Group(*content_items),
        title=f"[bold red]Crash Forensics Splicer — Session PID {session.pid}[/bold red]",
        border_style="bright_red",
    )
