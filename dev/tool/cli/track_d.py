"""Track D CLI: D2 benchmark image/result A/B (not a winner claim)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..host.git import git_state
from ..plugins.benchmarks import BenchmarksPlugin


def _collect_images(run: Dict[str, Any]) -> List[str]:
    found: List[str] = []
    for key in ("output_path", "image_path", "result_path", "png"):
        val = run.get(key)
        if isinstance(val, str) and val:
            found.append(val)
    datasets = run.get("datasets")
    if isinstance(datasets, list):
        for ds in datasets:
            if not isinstance(ds, dict):
                continue
            for key in (
                "output_path",
                "asp_path",
                "scans_path",
                "image",
                "raw_asp",
                "safe_asp",
            ):
                val = ds.get(key)
                if isinstance(val, str) and val:
                    found.append(val)
    return found


def _annotations(run: Dict[str, Any]) -> Any:
    for key in ("human", "annotations", "evaluations", "human_ratings"):
        if key in run:
            return run[key]
    return None


def _resolve_run(arg: str, repo_root: Path) -> Path:
    path = Path(arg)
    if path.is_file():
        return path
    plugin = BenchmarksPlugin()

    class _Store:
        def __init__(self, root: Path) -> None:
            self.repo_root = root

    for art in plugin.artifacts(_Store(repo_root)):
        if art.name == arg or (art.path and art.path.name == arg):
            return Path(art.path)
    raise FileNotFoundError(f"benchmark run not found: {arg}")


def compare_benchmarks(path_a: Path, path_b: Path, *, cwd: Optional[Path] = None) -> Dict[str, Any]:
    """Evidence bundle for two runs. Does not declare a winner (D36)."""
    plugin = BenchmarksPlugin()
    run_a = plugin.load_run(path_a)
    run_b = plugin.load_run(path_b)
    metrics = plugin.compare_runs(run_a, run_b)
    return {
        "format": "tool.bench.compare",
        "version": 1,
        "declaration": (
            "Evidence only. Metric deltas are not a winner claim; "
            "human ratings outrank automated numbers."
        ),
        "a": {
            "id": path_a.name,
            "path": str(path_a),
            "metadata": run_a.get("metadata", {}),
            "config": run_a.get("config") or run_a.get("metadata", {}),
            "images": _collect_images(run_a),
            "annotations": _annotations(run_a),
        },
        "b": {
            "id": path_b.name,
            "path": str(path_b),
            "metadata": run_b.get("metadata", {}),
            "config": run_b.get("config") or run_b.get("metadata", {}),
            "images": _collect_images(run_b),
            "annotations": _annotations(run_b),
        },
        "metrics": metrics.get("deltas", {}),
        "git": git_state(cwd),
    }


def format_compare(report: Dict[str, Any]) -> str:
    lines = [
        "Benchmark A/B evidence (not a winner declaration)",
        report["declaration"],
        f"A  {report['a']['id']}  {report['a']['path']}",
        f"B  {report['b']['id']}  {report['b']['path']}",
    ]
    git = report.get("git") or {}
    if git.get("commit"):
        dirty = f" dirty={git.get('dirty_hash')}" if git.get("dirty") else ""
        lines.append(f"git  {git.get('branch')}@{git.get('commit')[:12]}{dirty}")
    for _key, item in (report.get("metrics") or {}).items():
        lines.append(
            f"  {item['label']}: {item['val_a']} -> {item['val_b']}  "
            f"delta={item['delta']:+} ({item['pct_change']:+.1f}%)"
        )
    for side in ("a", "b"):
        images = report[side]["images"]
        if images:
            lines.append(f"{side} images: {', '.join(images[:6])}")
        ann = report[side]["annotations"]
        if ann is not None:
            lines.append(f"{side} annotations: present")
    return "\n".join(lines)


def cmd_bench(args: Any) -> int:
    if getattr(args, "bench_command", None) != "compare":
        print("usage: bench compare A B", file=__import__("sys").stderr)
        return 2
    repo = Path.cwd()
    try:
        path_a = _resolve_run(args.a, repo)
        path_b = _resolve_run(args.b, repo)
    except FileNotFoundError as exc:
        print(str(exc), file=__import__("sys").stderr)
        return 2
    report = compare_benchmarks(path_a, path_b, cwd=repo)
    if getattr(args, "investigation", None):
        from ..host.store import WorkspaceStore

        store = WorkspaceStore(root=Path(args.workspace) if args.workspace else None)
        try:
            inv = store.open_investigation(args.investigation)
        except FileNotFoundError:
            inv = store.create_investigation(args.investigation)
        inv.attach_git(report["git"])
        inv.append_note(format_compare(report), "devtool-bench-compare")
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    print(format_compare(report))
    return 0


def add_parsers(sub) -> None:
    p_bench = sub.add_parser("bench", help="Benchmark review (D2)")
    bench_sub = p_bench.add_subparsers(dest="bench_command")
    p_cmp = bench_sub.add_parser("compare", help="A/B evidence for two runs (not a winner)")
    p_cmp.add_argument("a", help="Path or artifact name of run A")
    p_cmp.add_argument("b", help="Path or artifact name of run B")
    p_cmp.add_argument("--json", action="store_true")
    p_cmp.add_argument(
        "--investigation",
        default=None,
        help="Stamp git provenance + note onto this investigation",
    )


__all__ = ["add_parsers", "cmd_bench", "compare_benchmarks", "format_compare"]
