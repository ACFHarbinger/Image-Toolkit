"""Timeline & Waterfall TUI View.

Visualizes:
- Multi-track thread waterfall lanes with duration bars ([■■■■■■■] 142ms).
- Minimap scrub bar displaying event density over the session timeline.
- Hierarchical span listing with duration deltas and orphan highlights.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from ...model.session import Session, Span


def _build_minimap(session: "Session", bins: int = 40) -> Text:
    """Build a mini ASCII/Unicode density sparkline of events across time."""
    if not session.events or session.duration <= 0:
        return Text("[ no activity ]", style="dim")

    start = session.start_time or 0.0
    dur = session.duration
    counts = [0] * bins

    for e in session.events:
        t = e.get("t", start)
        idx = min(bins - 1, max(0, int(((t - start) / dur) * bins)))
        counts[idx] += 1

    max_count = max(counts) if counts else 1
    blocks = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

    text = Text("Timeline Density: [", style="bold cyan")
    for c in counts:
        if c == 0:
            text.append("·", style="dim")
        else:
            block_idx = min(len(blocks) - 1, max(1, int((c / max_count) * (len(blocks) - 1))))
            # Highlight peaks
            color = "bright_red" if c == max_count and max_count > 5 else "green"
            text.append(blocks[block_idx], style=color)
    text.append("]", style="bold cyan")
    text.append(f" {session.duration * 1000.0:.1f}ms total", style="dim")
    return text


def _format_duration_bar(duration_ms: Optional[float], max_ms: float, bar_width: int = 15) -> Text:
    """Render a visual duration bar like [■■■■■■░░░] 142ms."""
    if duration_ms is None:
        return Text("[ORPHANED IN-FLIGHT]", style="bold red")

    if max_ms <= 0:
        filled = 0
    else:
        fraction = min(1.0, max(0.0, duration_ms / max_ms))
        filled = int(fraction * bar_width)

    bar = "■" * filled + "░" * (bar_width - filled)

    # Color based on relative latency
    if duration_ms > 500:
        color = "red"
    elif duration_ms > 100:
        color = "yellow"
    else:
        color = "cyan"

    text = Text()
    text.append(f"[{bar}] ", style=color)
    text.append(f"{duration_ms:.1f}ms", style="bold white")
    return text


def render_timeline(session: "Session", max_spans: int = 40) -> RenderableType:
    """Render the Timeline & Waterfall view."""
    spans: List["Span"] = session.spans()
    orphans = session.orphaned_spans()
    threads = session.thread_ids()

    # Calculate max duration for relative scaling
    durations = [s.duration_ms for s in spans if s.duration_ms is not None]
    max_duration_ms = max(durations) if durations else 100.0

    # 1. Summary Header
    header = Table.grid(padding=(0, 2))
    header.add_column(style="bold cyan")
    header.add_column()
    header.add_column(style="bold cyan")
    header.add_column()

    header.add_row("Session PID:", str(session.pid), "Total Events:", str(len(session.events)))
    header.add_row(
        "Duration:",
        f"{session.duration * 1000.0:.2f} ms ({session.duration:.2f} s)",
        "Threads:",
        f"{len(threads)} unique threads",
    )
    header.add_row(
        "Spans:",
        f"{len(spans)} reconstructed",
        "Orphans:",
        f"[bold red]{len(orphans)} orphaned[/bold red]" if orphans else "[green]0 orphans[/green]",
    )

    # 2. Minimap
    minimap = _build_minimap(session, bins=50)

    # 3. Spans Table
    table = Table(
        title=f"Spans Waterfall (Showing {min(len(spans), max_spans)} of {len(spans)})",
        title_style="bold blue",
        expand=True,
        header_style="bold white on navy_blue",
    )
    table.add_column("Start", justify="right", style="dim", width=8)
    table.add_column("Thread", style="magenta", width=12)
    table.add_column("Category", style="yellow", width=10)
    table.add_column("Span Name", style="bold white", min_width=16, ratio=1)
    table.add_column("Duration Bar", justify="left", width=18)
    table.add_column("Status", justify="center", width=8)

    start_t = session.start_time or 0.0

    for s in spans[:max_spans]:
        rel_ms = (s.start - start_t) * 1000.0
        tname = s.start_event.get("tname", f"tid={s.tid}")
        dur_bar = _format_duration_bar(s.duration_ms, max_duration_ms, bar_width=12)

        if s.orphaned:
            status = Text("ORPHAN", style="bold red")
        elif s.ended_ok:
            status = Text("OK", style="green")
        else:
            status = Text("ERROR", style="bold yellow")

        table.add_row(
            f"+{rel_ms:.1f}ms",
            f"{tname} ({s.tid})",
            s.category,
            s.name,
            dur_bar,
            status,
        )

    if len(spans) > max_spans:
        table.add_row(
            "...", "...", "...", f"... {len(spans) - max_spans} more spans ...", "...", "..."
        )

    # 4. Category breakdown table
    cat_counts = session.category_counts()
    cat_table = Table(title="Category Event Counts", expand=True, header_style="bold white on grey23")
    for cat in cat_counts:
        cat_table.add_column(cat, justify="center")
    cat_table.add_row(*[str(c) for c in cat_counts.values()])

    content = Group(
        Panel(header, title="[bold]Session Metadata[/bold]", border_style="cyan"),
        Panel(minimap, border_style="blue"),
        table,
        cat_table,
    )
    return Panel(content, title=f"[bold cyan]Timeline & Waterfall — PID {session.pid}[/bold cyan]", border_style="bright_blue")
