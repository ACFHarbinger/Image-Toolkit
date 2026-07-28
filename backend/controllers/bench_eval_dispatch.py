#!/usr/bin/env python3
"""
ASP Phase 0.1 — human coherence evaluation tool.

The ASP roadmap's objective ("at least as good as the OpenCV SCANS simple
stitch, as judged by a human") is defined against structural-coherence
evaluations, not any automated metric — no automated metric currently measures
whether a composite has torn anatomy, duplicated strips, or misordered
content (research/ASP_Critical_Evaluation_2026-07-08.md). This dashboard
shows each test's ASP output side by side with the Simple-stitch output (and
ground truth, if available), records a 0-4 structural-coherence score for
each, and adds deep-zoom/pan, pixel-value inspection, interactive
bbox/edge failure-mode annotation, and a full pixel-data visualization +
image-comparison toolkit for debugging *why* a test scored the way it did.

Rating scale (0-4):
    4 = keepable — no visible structural defects
    3 = minor flaw — small artifact, still clearly usable
    2 = flawed but parses — visible defect, but anatomy/content still reads
    1 = mostly broken — hard to parse, major tearing/duplication
    0 = incoherent — torn anatomy, duplicated strips, or misordered content

Usage:
    just asp-benchmark-assess
    # or directly:
    uv run python backend/controllers/bench_eval_dispatch.py [--data-dir DIR] [--out PATH]
                                                               [--redo] [--default-view {display,pixel}]

Output: {out}/asp_evaluations_<YYYYMMDD>.json, schema (extended, backward
compatible — bench_anime_stitch.py's _load_human_evaluations() only ever reads
the asp/simple keys):
    {"asp_test04": {"asp": 4, "simple": 2, "notes": "", "bboxes": [...], "edges": [...]}, ...}
Saved incrementally after every evaluation/annotation change — quitting the
window never loses progress.
"""

from __future__ import annotations

import datetime
import os
import sys


def _bootstrap_repo_root() -> str:
    """Walk up from this file to the repo root (the directory holding
    ``pyproject.toml``) and put it on ``sys.path``. Needed because this
    module is invoked as a direct script (``uv run python
    backend/controllers/bench_eval_dispatch.py``, see
    tools/benchmark/justfile), which sets ``sys.path[0]`` to this file's
    own directory rather than the repo root -- the ``backend.*`` absolute
    imports below would otherwise fail with
    ``ModuleNotFoundError: No module named 'backend'``."""
    d = os.path.dirname(os.path.abspath(__file__))
    while d != os.path.dirname(d):
        if os.path.exists(os.path.join(d, "pyproject.toml")):
            if d not in sys.path:
                sys.path.insert(0, d)
            return d
        d = os.path.dirname(d)
    raise RuntimeError(f"Could not locate repo root (pyproject.toml) above {__file__}")


_bootstrap_repo_root()

from backend.benchmark.evaluation.other.discovery import repo_root_from  # noqa: E402
from backend.benchmark.evaluation.ui.panel_base import DISPLAY_PIXEL, DISPLAY_RAW  # noqa: E402


def _default_out_path(repo_root: str) -> str:
    evaluations_dir = os.path.join(repo_root, "data", "benchmarks")
    os.makedirs(evaluations_dir, exist_ok=True)
    today = datetime.datetime.now().strftime("%Y%m%d")
    return os.path.join(evaluations_dir, f"asp_evaluations_{today}.json")


def build_dashboard(args):
    """Constructs (but does not show/exec) the RatingDashboard — split out
    so a smoke test can build the window under an offscreen QPA without
    starting an event loop."""
    from backend.benchmark.evaluation.ui.main_window import RatingDashboard

    repo_root = repo_root_from(__file__)
    out_path = args.out or _default_out_path(repo_root)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    default_view = DISPLAY_PIXEL if args.default_view == "pixel" else DISPLAY_RAW
    return RatingDashboard(
        base_dir=args.data_dir,
        out_path=out_path,
        redo=args.redo,
        repo_root=repo_root,
        default_display_mode=default_view,
    )


def evaluate_benchmark_outputs() -> None:
    from backend.controllers.cli.bench_eval_args import build_parser

    args = build_parser(__doc__).parse_args()

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    window = build_dashboard(args)
    if window.total_datasets == 0:
        print(f"No *_anime_stitch.png outputs found under {args.data_dir}/output/ — run the benchmark first.")
        return
    if not window.todo:
        print(f"All {window.total_datasets} dataset(s) already rated in {window.out_path}.")
        return
    print(f"{len(window.todo)}/{window.total_datasets} dataset(s) to rate. Output: {window.out_path}")
    window.show()
    app.exec()
    print(f"\nSaved {len(window.evaluations)} evaluation(s) to {window.out_path}.")


if __name__ == "__main__":
    evaluate_benchmark_outputs()
