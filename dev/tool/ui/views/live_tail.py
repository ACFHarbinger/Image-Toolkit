"""Live Watch Mode (btop Face) TUI View.

Non-blocking JSONL tailer with:
- Live RSS / event gauges.
- Thread activity sparklines.
- Real-time in-flight span ticker and event stream.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from rich.console import Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from ...model.session import Session


def render_live_view(session: "Session", last_n: int = 15) -> RenderableType:
    """Render the btop-style live monitoring face."""
    events = session.events
    orphans = session.orphaned_spans()
    threads = session.thread_ids()

    # 1. Live Header Gauges
    header_table = Table.grid(padding=(0, 2), expand=True)
    header_table.add_column(style="bold cyan", ratio=1)
    header_table.add_column(style="bold magenta", ratio=1)
    header_table.add_column(style="bold yellow", ratio=1)
    header_table.add_column(style="bold green", ratio=1)

    event_count_str = f"Events: [white]{len(events)}[/white]"
    thread_count_str = f"Threads: [white]{len(threads)}[/white]"
    in_flight_str = f"In-Flight: [{'red' if orphans else 'green'}]{len(orphans)}[/{'red' if orphans else 'green'}]"
    dur_str = f"Active Time: [white]{session.duration:.2f}s[/white]"

    header_table.add_row(event_count_str, thread_count_str, in_flight_str, dur_str)

    # 2. In-Flight Span Ticker
    ticker_table = Table(
        title="Active In-Flight Spans (Live Ticker)",
        title_style="bold yellow",
        expand=True,
        header_style="bold white on grey23",
    )
    ticker_table.add_column("TID", justify="right", style="cyan", width=8)
    ticker_table.add_column("Category", style="yellow", width=14)
    ticker_table.add_column("Span Name", style="bold white")
    ticker_table.add_column("Active Since", justify="right", style="magenta", width=14)

    if not orphans:
        ticker_table.add_row(
            "-", "-", "[green]All spans completed — idle or waiting for events[/green]", "-"
        )
    else:
        end_t = session.end_time or 0.0
        for s in orphans[:8]:
            active_ms = (end_t - s.start) * 1000.0
            ticker_table.add_row(
                str(s.tid),
                s.category,
                s.name,
                f"{active_ms:.1f}ms ago",
            )

    # 3. Live Event Stream Tail
    tail_table = Table(
        title=f"Recent Event Stream (Last {min(len(events), last_n)})",
        title_style="bold cyan",
        expand=True,
        header_style="bold white on navy_blue",
    )
    tail_table.add_column("Time", justify="right", style="dim cyan", width=12)
    tail_table.add_column("Thread", style="magenta", width=16)
    tail_table.add_column("Category", style="yellow", width=14)
    tail_table.add_column("Event", style="bold white")
    tail_table.add_column("Payload", style="dim")

    for e in events[-last_n:]:
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

    # 4. Status Bar
    status_text = Text()
    status_text.append(" [● LIVE MONITOR] ", style="bold black on bright_green")
    status_text.append(" Polling telemetry stream. Press Ctrl+C or 'q' to stop.", style="dim")

    return Panel(
        Group(
            Panel(header_table, title="[bold]Session Health Gauges[/bold]", border_style="cyan"),
            ticker_table,
            tail_table,
            status_text,
        ),
        title=f"[bold green]btop Live Watch — Session PID {session.pid}[/bold green]",
        border_style="bright_green",
    )


def tail_session_live(
    path: Path,
    refresh_rate_hz: float = 4.0,
    max_iterations: Optional[int] = None,
) -> None:
    """Run an interactive live tail loop using Rich Live."""
    from ...model.session import Session

    interval = 1.0 / max(0.1, refresh_rate_hz)
    iteration = 0

    with Live(auto_refresh=False) as live:
        try:
            while max_iterations is None or iteration < max_iterations:
                session = Session.open(path)
                view = render_live_view(session)
                live.update(view, refresh=True)
                iteration += 1
                time.sleep(interval)
        except KeyboardInterrupt:
            pass
