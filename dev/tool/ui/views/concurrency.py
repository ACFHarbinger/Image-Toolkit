"""Concurrency & Overlap Inspector TUI View.

Visualizes:
- Thread collision matrix flagging dangerous concurrent windows (e.g. scanner worker threads vs Qt GUI main loop).
- Worker window overlaps and lock contention diagnostics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from ...model.session import Session


def render_concurrency(session: "Session") -> RenderableType:
    """Render the Concurrency & Overlap Inspector view."""
    overlaps: List[Tuple] = session.overlapping_windows()
    threads = session.thread_ids()

    # 1. Header Summary
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan")
    summary.add_column()
    summary.add_column(style="bold yellow")
    summary.add_column()

    summary.add_row(
        "Active Threads:",
        f"{len(threads)} unique threads",
        "Overlapping Windows:",
        f"[bold red]{len(overlaps)} collisions detected[/bold red]"
        if overlaps
        else "[green]0 worker collisions[/green]",
    )

    # 2. Thread Inventory Table
    thread_table = Table(
        title="Observed Thread Inventory",
        title_style="bold blue",
        expand=True,
        header_style="bold white on navy_blue",
    )
    thread_table.add_column("TID", justify="right", style="cyan", width=10)
    thread_table.add_column("Thread Name", style="bold magenta", width=24)
    thread_table.add_column("Event Count", justify="right", style="yellow", width=14)
    thread_table.add_column("First Activity", justify="right", style="dim", width=16)
    thread_table.add_column("Last Activity", justify="right", style="dim", width=16)

    for tid, tname in threads:
        t_events = [e for e in session.events if e.get("tid") == tid]
        first_t = t_events[0].get("t", 0.0) if t_events else 0.0
        last_t = t_events[-1].get("t", 0.0) if t_events else 0.0
        thread_table.add_row(
            str(tid),
            str(tname),
            str(len(t_events)),
            f"{first_t:.4f}s",
            f"{last_t:.4f}s",
        )

    # 3. Overlap Collisions Table
    overlap_table = Table(
        title="Dangerous Worker Window Overlaps (Thread Collisions)",
        title_style="bold red",
        expand=True,
        header_style="bold white on dark_red",
    )
    overlap_table.add_column("Window A", style="bold white", width=36)
    overlap_table.add_column("Window B", style="bold white", width=36)
    overlap_table.add_column("A Span (t)", justify="center", style="cyan", width=18)
    overlap_table.add_column("B Span (t)", justify="center", style="yellow", width=18)
    overlap_table.add_column("Overlap (ms)", justify="right", style="bold red", width=14)

    if not overlaps:
        overlap_table.add_row(
            "[green]No overlapping worker windows detected[/green]",
            "-",
            "-",
            "-",
            "0.0ms",
        )
    else:
        for a_label, b_label, a_start, a_end, b_start, b_end in overlaps:
            overlap_dur_ms = (min(a_end, b_end) - max(a_start, b_start)) * 1000.0
            overlap_table.add_row(
                a_label,
                b_label,
                f"{a_start:.3f}-{a_end:.3f}s",
                f"{b_start:.3f}-{b_end:.3f}s",
                f"{overlap_dur_ms:.1f}ms",
            )

    # 4. Diagnostics & Recommendations
    notes = Text()
    if overlaps:
        notes.append("⚠️  RACE CONDITION WARNING: ", style="bold red")
        notes.append(
            f"Found {len(overlaps)} overlapping worker windows. In PySide6 / native C++ bindings, "
            "concurrent access to un-synchronized structures or running multiple heavy scanner/converter "
            "threads simultaneously can cause memory corruption or deadlocks.\n",
            style="yellow",
        )
    else:
        notes.append("✅  All worker windows executed serially without detected overlap.", style="green")

    return Panel(
        Group(
            Panel(summary, title="[bold]Concurrency Overview[/bold]", border_style="cyan"),
            thread_table,
            overlap_table,
            Panel(notes, title="[bold]Concurrency Diagnostics[/bold]", border_style="yellow"),
        ),
        title=f"[bold cyan]Concurrency & Overlap Inspector — PID {session.pid}[/bold cyan]",
        border_style="bright_blue",
    )
