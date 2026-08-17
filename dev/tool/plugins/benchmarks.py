"""First-party Benchmarks plugin (Track C6).

Discovers benchmark outputs across the workspace, parses results, and computes
side-by-side A/B comparisons with metric deltas.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..host.plugins import Artifact, Channel, PluginManifest, Surface

MANIFEST = PluginManifest(
    name="benchmarks",
    version="0.1.0",
    description="Benchmark results discovery, metric aggregation, and A/B comparison.",
    surfaces=(
        Surface("cli", "list benchmark runs and compute A/B metric diffs"),
        Surface("tui", "visual benchmark trend tables and delta inspections"),
        Surface("web", "interactive A/B image & metric comparison viewer"),
    ),
    channels=(
        Channel("benchmarks", "raw benchmark JSON run outputs", retention="forever"),
        Channel("comparisons", "A/B diff evidence summaries", retention="forever"),
    ),
    entry_point="tool.plugins.benchmarks:plugin",
)

_BENCHMARK_DIRS = [
    Path("submodules/ASP/backend/benchmark/output"),
    Path("backend/benchmark/output"),
    Path("docs/website/public/data"),
]


class BenchmarksPlugin:
    manifest = MANIFEST

    def artifacts(self, store: Any) -> List[Artifact]:
        """Discover benchmark output JSON files across the repository."""
        artifacts: List[Artifact] = []
        repo_root = getattr(store, "repo_root", Path.cwd())

        for b_dir in _BENCHMARK_DIRS:
            full_dir = repo_root / b_dir
            if full_dir.exists() and full_dir.is_dir():
                for json_path in sorted(full_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
                    artifacts.append(
                        Artifact(
                            kind="benchmark_run",
                            name=json_path.name,
                            path=json_path,
                            meta={"directory": str(b_dir), "size_bytes": json_path.stat().st_size},
                        )
                    )
        return artifacts

    @staticmethod
    def load_run(path: Path) -> Dict[str, Any]:
        """Load and parse a benchmark run output JSON."""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def compare_runs(run_a: Dict[str, Any], run_b: Dict[str, Any]) -> Dict[str, Any]:
        """Compute structured metric diff between two benchmark runs."""
        sum_a = run_a.get("summary", {})
        sum_b = run_b.get("summary", {})
        meta_a = run_a.get("metadata", {})
        meta_b = run_b.get("metadata", {})

        metrics = [
            ("total_datasets", "Datasets Count"),
            ("datasets_passed", "Passed Datasets"),
            ("datasets_fallback", "Fallback Datasets"),
            ("total_time_sec", "Total Time (s)"),
            ("avg_time_per_dataset_sec", "Avg Time / Dataset (s)"),
            ("avg_sharpness_asp", "Avg Sharpness (ASP)"),
            ("avg_ghosting_asp", "Avg Ghosting (ASP)"),
            ("avg_coverage_asp", "Avg Coverage (ASP)"),
        ]

        deltas = {}
        for key, label in metrics:
            val_a = sum_a.get(key)
            val_b = sum_b.get(key)
            if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
                diff = val_b - val_a
                deltas[key] = {
                    "label": label,
                    "val_a": val_a,
                    "val_b": val_b,
                    "delta": diff,
                    "pct_change": (diff / val_a * 100.0) if val_a != 0 else 0.0,
                }

        return {
            "meta_a": meta_a,
            "meta_b": meta_b,
            "deltas": deltas,
        }

    @classmethod
    def render_comparison_table(
        cls, diff_data: Dict[str, Any], label_a: str = "Baseline", label_b: str = "Candidate"
    ) -> Panel:
        """Render a formatted comparison table for two benchmark runs."""
        table = Table(
            title=f"Benchmark A/B Comparison: {label_a} vs {label_b}",
            title_style="bold cyan",
            expand=True,
            header_style="bold white on navy_blue",
        )
        table.add_column("Metric", style="bold white", width=26)
        table.add_column(f"{label_a}", justify="right", style="yellow", width=16)
        table.add_column(f"{label_b}", justify="right", style="cyan", width=16)
        table.add_column("Absolute Delta", justify="right", width=16)
        table.add_column("% Change", justify="right", width=14)

        deltas = diff_data.get("deltas", {})
        for key, item in deltas.items():
            label = item["label"]
            v_a = item["val_a"]
            v_b = item["val_b"]
            d = item["delta"]
            pct = item["pct_change"]

            # Formatting
            v_a_str = f"{v_a:.2f}" if isinstance(v_a, float) else str(v_a)
            v_b_str = f"{v_b:.2f}" if isinstance(v_b, float) else str(v_b)
            d_str = f"{d:+.2f}" if isinstance(d, float) else f"{d:+d}"
            pct_str = f"{pct:+.1f}%"

            # Color coding: lower time/ghosting is better, higher passed/coverage is better
            if "time" in key or "ghosting" in key:
                color = "green" if d < 0 else ("red" if d > 0 else "dim")
            elif "passed" in key or "coverage" in key:
                color = "green" if d > 0 else ("red" if d < 0 else "dim")
            else:
                color = "white"

            table.add_row(
                label,
                v_a_str,
                v_b_str,
                Text(d_str, style=color),
                Text(pct_str, style=color),
            )

        meta_a = diff_data.get("meta_a", {})
        meta_b = diff_data.get("meta_b", {})
        header_grid = Table.grid(padding=(0, 2), expand=True)
        header_grid.add_column(style="bold yellow")
        header_grid.add_column()
        header_grid.add_column(style="bold cyan")
        header_grid.add_column()

        header_grid.add_row(
            f"{label_a} Timestamp:",
            str(meta_a.get("timestamp", "-")),
            f"{label_b} Timestamp:",
            str(meta_b.get("timestamp", "-")),
        )

        return Panel(
            Group(header_grid, table),
            title="[bold cyan]Benchmark Metric Comparison Engine[/bold cyan]",
            border_style="bright_blue",
        )


plugin = BenchmarksPlugin()
