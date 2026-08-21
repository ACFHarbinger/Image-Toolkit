"""Pipeline Flamegraph Breakdown TUI View.

Visualizes:
- Hierarchical flame-chart breakdown for pipeline execution bottlenecks.
- Microsecond/millisecond aggregated execution times, percentages, and call counts.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List, Tuple

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

if TYPE_CHECKING:
    from ...model.session import Session, Span


def render_flame(session: "Session") -> RenderableType:
    """Render the Pipeline Flamegraph Breakdown view."""
    spans: List["Span"] = session.spans()

    # Aggregate durations by (category, name)
    aggregated: Dict[Tuple[str, str], Dict[str, float]] = defaultdict(
        lambda: {"count": 0, "total_ms": 0.0, "max_ms": 0.0}
    )

    total_span_time_ms = 0.0
    for s in spans:
        dur = s.duration_ms or 0.0
        key = (s.category, s.name)
        aggregated[key]["count"] += 1
        aggregated[key]["total_ms"] += dur
        aggregated[key]["max_ms"] = max(aggregated[key]["max_ms"], dur)
        total_span_time_ms += dur

    # 1. Summary Header
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan")
    summary.add_column()
    summary.add_column(style="bold yellow")
    summary.add_column()

    summary.add_row(
        "Total Spans Reconstructed:",
        str(len(spans)),
        "Total Aggregated Span Time:",
        f"{total_span_time_ms:.2f} ms",
    )
    summary.add_row(
        "Unique Span Types:",
        str(len(aggregated)),
        "Wall Session Duration:",
        f"{session.duration * 1000.0:.2f} ms",
    )

    # 2. Aggregated Bottlenecks Table
    table = Table(
        title="Span Latency & Call Aggregates (Ranked by Total Time)",
        title_style="bold yellow",
        expand=True,
        header_style="bold white on grey23",
    )
    table.add_column("Category", style="yellow", width=16)
    table.add_column("Span Name", style="bold white")
    table.add_column("Calls", justify="right", style="cyan", width=8)
    table.add_column("Total Time", justify="right", style="bold magenta", width=14)
    table.add_column("Avg (ms)", justify="right", style="dim", width=12)
    table.add_column("Max (ms)", justify="right", style="dim", width=12)
    table.add_column("Share Bar", justify="left", width=24)

    sorted_items = sorted(
        aggregated.items(), key=lambda item: item[1]["total_ms"], reverse=True
    )

    for (cat, name), stats in sorted_items:
        tot = stats["total_ms"]
        cnt = int(stats["count"])
        avg = tot / cnt if cnt > 0 else 0.0
        max_t = stats["max_ms"]
        share = (tot / total_span_time_ms * 100.0) if total_span_time_ms > 0 else 0.0

        bar_len = int((share / 100.0) * 12)
        bar = "█" * bar_len + "░" * (12 - bar_len)

        color = "red" if share > 40 else ("yellow" if share > 15 else "green")
        bar_text = Text(f"[{bar}] {share:.1f}%", style=color)

        table.add_row(
            cat,
            name,
            str(cnt),
            f"{tot:.1f}ms",
            f"{avg:.1f}ms",
            f"{max_t:.1f}ms",
            bar_text,
        )

    # 3. Hierarchical Category Tree
    tree = Tree(f"[bold cyan]Execution Hierarchy Breakdown (PID {session.pid})[/bold cyan]")
    by_category: Dict[str, List[Tuple[str, Dict[str, float]]]] = defaultdict(list)
    for (cat, name), stats in sorted_items:
        by_category[cat].append((name, stats))

    for cat, items in by_category.items():
        cat_tot = sum(it[1]["total_ms"] for it in items)
        cat_share = (cat_tot / total_span_time_ms * 100.0) if total_span_time_ms > 0 else 0.0
        cat_node = tree.add(f"[bold yellow]{cat}[/bold yellow]  [dim]({cat_tot:.1f}ms total, {cat_share:.1f}%)[/dim]")
        for name, stats in items:
            span_share = (stats["total_ms"] / total_span_time_ms * 100.0) if total_span_time_ms > 0 else 0.0
            cat_node.add(
                f"[bold white]{name}[/bold white] — [magenta]{stats['total_ms']:.1f}ms[/magenta] "
                f"({int(stats['count'])} calls, [dim]{span_share:.1f}%[/dim])"
            )

    return Panel(
        Group(
            Panel(summary, title="[bold]Latency Flame Summary[/bold]", border_style="cyan"),
            table,
            Panel(tree, title="[bold]Category Flame Tree[/bold]", border_style="blue"),
        ),
        title=f"[bold yellow]Pipeline Flamegraph Breakdown — PID {session.pid}[/bold yellow]",
        border_style="bright_yellow",
    )
