"""Memory & RSS Profiler TUI View.

Visualizes:
- Step-by-step RSS / VRAM memory growth over lifecycle allocation steps.
- Memory allocation deltas per category and garbage collection spikes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from ...model.session import Session


def _extract_memory_points(session: "Session") -> List[Dict[str, Any]]:
    """Extract any events containing memory, RSS, or VRAM telemetry fields."""
    points = []
    for e in session.events:
        mem_fields = {}
        for k in ("rss_mb", "rss_kb", "vram_mb", "mem_mb", "alloc_mb", "bytes"):
            if k in e and isinstance(e[k], (int, float)):
                mem_fields[k] = e[k]
        if mem_fields or "gc" in e.get("event", "").lower() or "memory" in e.get("category", "").lower():
            points.append({
                "t": e.get("t", 0.0),
                "event": e.get("event", "?"),
                "category": e.get("category", "?"),
                "fields": mem_fields,
            })
    return points


def render_memory(session: "Session") -> RenderableType:
    """Render the Memory & RSS Profiler view."""
    points = _extract_memory_points(session)

    # 1. Header Summary
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan")
    summary.add_column()
    summary.add_column(style="bold yellow")
    summary.add_column()

    summary.add_row(
        "Session Duration:",
        f"{session.duration * 1000.0:.2f} ms",
        "Memory Telemetry Points:",
        f"{len(points)} recorded",
    )
    summary.add_row(
        "Total Events Processed:",
        str(len(session.events)),
        "GC / Alloc Events:",
        str(sum(1 for p in points if "gc" in p["event"].lower())),
    )

    # 2. Memory Step Table
    mem_table = Table(
        title="Memory & Allocation Telemetry Timeline",
        title_style="bold green",
        expand=True,
        header_style="bold white on dark_green",
    )
    mem_table.add_column("Time (s)", justify="right", style="cyan", width=12)
    mem_table.add_column("Category", style="yellow", width=16)
    mem_table.add_column("Event", style="bold white", width=28)
    mem_table.add_column("Memory Metrics", style="magenta")

    if not points:
        mem_table.add_row(
            "-",
            "-",
            "[dim]No explicit RSS/VRAM telemetry fields found in this session[/dim]",
            "[dim]Run with memory tracking enabled in PipelineSession or PyTorch profiler[/dim]",
        )
    else:
        for p in points[:30]:
            metrics_str = ", ".join(f"{k}={v}" for k, v in p["fields"].items())
            mem_table.add_row(
                f"{p['t']:.4f}s",
                p["category"],
                p["event"],
                metrics_str or "GC/Allocation trigger",
            )

    # 3. Category Activity Estimator (Proxy for Allocation Footprint)
    cat_counts = session.category_counts()
    cat_table = Table(
        title="Category Activity Footprint (Event Density)",
        title_style="bold blue",
        expand=True,
        header_style="bold white on grey23",
    )
    cat_table.add_column("Category", style="bold white")
    cat_table.add_column("Event Count", justify="right", style="cyan")
    cat_table.add_column("Share (%)", justify="right", style="yellow")
    cat_table.add_column("Relative Footprint Bar", justify="left")

    total_events = len(session.events) or 1
    for cat, count in sorted(cat_counts.items(), key=lambda item: item[1], reverse=True):
        share = (count / total_events) * 100.0
        bar_len = int((share / 100.0) * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        cat_table.add_row(
            cat,
            str(count),
            f"{share:.1f}%",
            f"[green]{bar}[/green]",
        )

    return Panel(
        Group(
            Panel(summary, title="[bold]Memory Telemetry Overview[/bold]", border_style="cyan"),
            mem_table,
            cat_table,
        ),
        title=f"[bold green]Memory & RSS Profiler — PID {session.pid}[/bold green]",
        border_style="bright_green",
    )
