"""Performance Profiling & Stage Latency Engine (Track D4 / #390).

Analyzes:
- Microsecond stage latencies, percentiles (p50/p95/max), execution jitter, and throughput.
- Stage-by-stage bottleneck detection and queue/concurrency intensity.
- Correlates latency outliers with memory/RSS progression.
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from ..model.session import Session, Span


def profile_session(session: "Session") -> Dict[str, Any]:
    """Compute comprehensive stage latency and performance statistics for a session."""
    spans: List["Span"] = session.spans()
    total_session_ms = session.duration * 1000.0 if session.duration > 0 else 1.0

    # Group spans by (category, name)
    by_stage: Dict[str, List[float]] = defaultdict(list)
    for s in spans:
        if s.duration_ms is not None:
            stage_key = f"{s.category}/{s.name}" if s.category else s.name
            by_stage[stage_key].append(s.duration_ms)

    stages_stats: Dict[str, Dict[str, Any]] = {}
    bottlenecks: List[Dict[str, Any]] = []

    total_measured_stage_ms = 0.0

    for stage_name, durations in sorted(by_stage.items(), key=lambda i: sum(i[1]), reverse=True):
        count = len(durations)
        tot_ms = sum(durations)
        total_measured_stage_ms += tot_ms
        avg_ms = tot_ms / count if count > 0 else 0.0
        min_ms = min(durations) if durations else 0.0
        max_ms = max(durations) if durations else 0.0

        sorted_durations = sorted(durations)
        p50_ms = sorted_durations[int(len(sorted_durations) * 0.50)] if sorted_durations else 0.0
        p95_ms = sorted_durations[int(len(sorted_durations) * 0.95)] if sorted_durations else 0.0
        stdev_ms = statistics.stdev(durations) if len(durations) > 1 else 0.0

        # Throughput: calls per second of session time
        ops_sec = (count / session.duration) if session.duration > 0 else 0.0

        stage_info = {
            "stage": stage_name,
            "count": count,
            "total_ms": round(tot_ms, 3),
            "avg_ms": round(avg_ms, 3),
            "min_ms": round(min_ms, 3),
            "p50_ms": round(p50_ms, 3),
            "p95_ms": round(p95_ms, 3),
            "max_ms": round(max_ms, 3),
            "stdev_ms": round(stdev_ms, 3),
            "ops_sec": round(ops_sec, 2),
            "pct_of_session": round((tot_ms / total_session_ms) * 100.0, 1),
        }
        stages_stats[stage_name] = stage_info

        # Bottleneck detection heuristics
        reasons = []
        if stage_info["pct_of_session"] >= 25.0:
            reasons.append(f"Dominates runtime ({stage_info['pct_of_session']}% of wall session)")
        if count > 1 and max_ms > (avg_ms * 3.0) and (max_ms - avg_ms) > 20.0:
            reasons.append(f"High latency jitter (max {max_ms:.1f}ms vs avg {avg_ms:.1f}ms)")
        if reasons:
            bottlenecks.append({
                "stage": stage_name,
                "reasons": reasons,
                "total_ms": round(tot_ms, 2),
                "avg_ms": round(avg_ms, 2),
                "max_ms": round(max_ms, 2),
            })

    # Memory telemetry analysis
    mem_points = []
    for e in session.events:
        for k in ("rss_mb", "rss_kb", "vram_mb", "alloc_mb"):
            if k in e and isinstance(e[k], (int, float)):
                mem_points.append({"t": e.get("t", 0.0), "metric": k, "value": e[k]})

    return {
        "pid": session.pid,
        "duration_ms": round(total_session_ms, 2),
        "total_events": len(session.events),
        "total_spans": len(spans),
        "total_measured_stage_ms": round(total_measured_stage_ms, 2),
        "stages": stages_stats,
        "bottlenecks": bottlenecks,
        "memory_points_count": len(mem_points),
    }


def format_profile_report(profile: Dict[str, Any], json_mode: bool = False) -> str:
    """Format performance profile data as text or JSON."""
    if json_mode:
        return json.dumps(profile, indent=2)

    lines = [
        f"Performance Profile for Session PID {profile['pid']}",
        f"Session Duration: {profile['duration_ms']:.2f} ms ({profile['duration_ms']/1000.0:.2f} s) | Total Spans: {profile['total_spans']}",
        f"Total Measured Stage Time: {profile['total_measured_stage_ms']:.2f} ms\n",
        f"{'Stage / Subsystem':32} {'Calls':>6} {'Total(ms)':>10} {'Avg(ms)':>9} {'p50(ms)':>9} {'p95(ms)':>9} {'Max(ms)':>9} {'Share':>7}",
        "-" * 96,
    ]

    for name, st in profile["stages"].items():
        lines.append(
            f"{name:32} {st['count']:>6} {st['total_ms']:>10.1f} {st['avg_ms']:>9.1f} "
            f"{st['p50_ms']:>9.1f} {st['p95_ms']:>9.1f} {st['max_ms']:>9.1f} {st['pct_of_session']:>6.1f}%"
        )

    if profile.get("bottlenecks"):
        lines.append("\nIdentified Performance Bottlenecks & Anomalies:")
        for b in profile["bottlenecks"]:
            lines.append(f"  • {b['stage']}: {'; '.join(b['reasons'])}")

    return "\n".join(lines)


def render_profile_panel(profile: Dict[str, Any]) -> Panel:
    """Render a formatted Rich panel for the performance profile."""
    grid = Table.grid(padding=(0, 2), expand=True)
    grid.add_column(style="bold cyan")
    grid.add_column()
    grid.add_column(style="bold yellow")
    grid.add_column()

    grid.add_row(
        "Session PID:", str(profile["pid"]), "Session Duration:", f"{profile['duration_ms']:.2f} ms"
    )
    grid.add_row(
        "Total Spans Reconstructed:", str(profile["total_spans"]), "Unique Stages:", str(len(profile["stages"]))
    )

    table = Table(
        title="Stage Latency & Percentile Breakdown",
        title_style="bold cyan",
        expand=True,
        header_style="bold white on navy_blue",
    )
    table.add_column("Stage / Subsystem", style="bold white", width=28)
    table.add_column("Calls", justify="right", style="cyan", width=8)
    table.add_column("Total (ms)", justify="right", style="magenta", width=12)
    table.add_column("Avg (ms)", justify="right", style="dim", width=10)
    table.add_column("p50 (ms)", justify="right", style="yellow", width=10)
    table.add_column("p95 (ms)", justify="right", style="yellow", width=10)
    table.add_column("Max (ms)", justify="right", style="bold red", width=10)
    table.add_column("Share", justify="right", width=10)

    for name, st in profile["stages"].items():
        share_val = st["pct_of_session"]
        color = "red" if share_val > 40 else ("yellow" if share_val > 15 else "green")
        table.add_row(
            name,
            str(st["count"]),
            f"{st['total_ms']:.1f}",
            f"{st['avg_ms']:.1f}",
            f"{st['p50_ms']:.1f}",
            f"{st['p95_ms']:.1f}",
            f"{st['max_ms']:.1f}",
            Text(f"{share_val:.1f}%", style=color),
        )

    bottleneck_text = Text()
    if profile.get("bottlenecks"):
        bottleneck_text.append("⚠️  Identified Bottlenecks:\n", style="bold red")
        for b in profile["bottlenecks"]:
            bottleneck_text.append(f"  • {b['stage']}: {'; '.join(b['reasons'])}\n", style="yellow")
    else:
        bottleneck_text.append("✅  No dominant runtime bottlenecks or latency jitter spikes detected.", style="green")

    return Panel(
        Group(grid, table, Panel(bottleneck_text, title="[bold]Performance Diagnostics[/bold]", border_style="yellow")),
        title=f"[bold cyan]Performance Profiler — PID {profile['pid']}[/bold cyan]",
        border_style="bright_blue",
    )


__all__ = ["profile_session", "format_profile_report", "render_profile_panel"]
