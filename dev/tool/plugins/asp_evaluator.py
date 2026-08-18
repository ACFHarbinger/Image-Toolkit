"""First-party ASP Evaluator plugin (Track C5).

Adapter around ASP benchmark evaluation datasets and human coherence ratings:
- Discovers evaluation datasets and benchmark outputs across the repository.
- Computes mean human coherence scores, comparator preferences (ASP vs SCANS),
  and defect category distributions.
- Does not fork or copy UI code — human ratings remain the source of truth.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from rich.panel import Panel
from rich.table import Table

from ..host.plugins import Artifact, Channel, PluginManifest, Surface

MANIFEST = PluginManifest(
    name="asp_evaluator",
    version="0.1.0",
    description="ASP benchmark evaluation & human coherence ratings adapter.",
    surfaces=(
        Surface("cli", "summary / inspect ASP human evaluation datasets"),
        Surface("tui", "visual defect distributions & coherence score tables"),
        Surface("web", "image comparison and rating inspector"),
        Surface("gui", "launch native PySide6 ASP evaluator window"),
    ),
    channels=(
        Channel("evaluations", "ASP evaluation JSON snapshots", retention="forever"),
        Channel("human_ratings", "human-verified coherence score datasets", retention="forever"),
    ),
    entry_point="tool.plugins.asp_evaluator:plugin",
)

_EVAL_PATHS = [
    Path("docs/website/public/data/asp_evaluations.json"),
    Path("submodules/ASP/data/benchmarks/asp_evaluations_20260810.json"),
    Path("docs/website/public/data/human_ratings_summary.json"),
]


class AspEvaluatorPlugin:
    manifest = MANIFEST

    def artifacts(self, store: Any) -> List[Artifact]:
        """Discover evaluation datasets across the repository."""
        artifacts: List[Artifact] = []
        repo_root = getattr(store, "repo_root", Path.cwd())

        for rel_path in _EVAL_PATHS:
            full_path = repo_root / rel_path
            if full_path.exists():
                artifacts.append(
                    Artifact(
                        kind="eval_dataset",
                        name=full_path.name,
                        path=full_path,
                        meta={"relative_path": str(rel_path)},
                    )
                )
        return artifacts

    @staticmethod
    def load_evaluations(path: Path) -> Dict[str, Any]:
        """Load and parse an ASP evaluation dataset."""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def summarize(eval_data: Dict[str, Any]) -> Dict[str, Any]:
        """Compute metrics summary over an ASP evaluation dataset."""
        total = len(eval_data)
        reviewed = 0
        asp_scores: List[float] = []
        simple_scores: List[float] = []
        prefs: Counter[str] = Counter()
        defects: Counter[str] = Counter()

        for _case_id, item in eval_data.items():
            if not isinstance(item, dict):
                continue
            if item.get("reviewed"):
                reviewed += 1

            # Scores (1-4 scale)
            asp_s = item.get("asp")
            if isinstance(asp_s, (int, float)):
                asp_scores.append(float(asp_s))

            sim_s = item.get("simple")
            if isinstance(sim_s, (int, float)):
                simple_scores.append(float(sim_s))

            # Preference
            pref = item.get("preference")
            if pref:
                prefs[str(pref).lower()] += 1

            # Defects
            for d in item.get("defects", []):
                defects[str(d)] += 1

        asp_mean = sum(asp_scores) / len(asp_scores) if asp_scores else 0.0
        simple_mean = sum(simple_scores) / len(simple_scores) if simple_scores else 0.0

        return {
            "total_cases": total,
            "reviewed_cases": reviewed,
            "asp_mean_score": round(asp_mean, 3),
            "simple_mean_score": round(simple_mean, 3),
            "preferences": dict(prefs),
            "top_defects": dict(defects.most_common(8)),
        }

    @classmethod
    def render_summary_table(cls, summary: Dict[str, Any], title: str = "ASP Evaluation Summary") -> Panel:
        """Render a formatted Rich table representing the evaluation summary."""
        grid = Table.grid(padding=(0, 2), expand=True)
        grid.add_column(style="bold cyan")
        grid.add_column()
        grid.add_column(style="bold yellow")
        grid.add_column()

        grid.add_row(
            "Total Cases:",
            str(summary.get("total_cases", 0)),
            "Reviewed Cases:",
            f"{summary.get('reviewed_cases', 0)} / {summary.get('total_cases', 0)}",
        )
        grid.add_row(
            "ASP Mean Coherence:",
            f"[bold magenta]{summary.get('asp_mean_score', 0.0):.2f} / 4.0[/bold magenta]",
            "Simple (SCANS) Mean:",
            f"[bold green]{summary.get('simple_mean_score', 0.0):.2f} / 4.0[/bold green]",
        )

        # Preferences Breakdown
        prefs = summary.get("preferences", {})
        pref_str = " | ".join(f"{k.upper()}: {v}" for k, v in prefs.items())
        grid.add_row("Comparator Preferences:", pref_str or "No preferences recorded", "", "")

        # Defects Breakdown Table
        defects_table = Table(
            title="Top Defect Categories Reported",
            title_style="bold red",
            expand=True,
            header_style="bold white on dark_red",
        )
        defects_table.add_column("Defect Tag", style="bold white")
        defects_table.add_column("Reported Occurrences", justify="right", style="bold yellow")

        top_defects = summary.get("top_defects", {})
        if not top_defects:
            defects_table.add_row("[green]No defect tags reported[/green]", "0")
        else:
            for tag, count in top_defects.items():
                defects_table.add_row(tag, str(count))

        from rich.console import Group

        return Panel(
            Group(grid, defects_table),
            title=f"[bold cyan]{title}[/bold cyan]",
            border_style="bright_blue",
        )

    @staticmethod
    def launch(
        repo_root: Path | str | None = None,
        surface: str = "inspector",
        extra_args: List[str] | None = None,
    ) -> int:
        """Launch the native PySide6 ASP evaluator window or CLI dispatch surface."""
        import os
        import subprocess
        import sys

        root = Path(repo_root) if repo_root else Path.cwd()
        asp_dir = root / "submodules" / "ASP"
        dispatch_script = asp_dir / "backend" / "src" / "cli" / "eval_dispatch.py"

        if not dispatch_script.exists():
            raise FileNotFoundError(f"ASP evaluation script not found at {dispatch_script}")

        env = os.environ.copy()
        pythonpath = env.get("PYTHONPATH", "")
        paths = [str(root), str(asp_dir)]
        if pythonpath:
            paths.append(pythonpath)
        env["PYTHONPATH"] = os.pathsep.join(paths)

        cmd = [sys.executable, str(dispatch_script), "--surface", surface]
        if extra_args:
            cmd.extend(extra_args)

        return subprocess.run(cmd, env=env).returncode


plugin = AspEvaluatorPlugin()

