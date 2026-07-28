"""Discovers ASP benchmark datasets and locates every on-disk artifact one
test can have, mirroring ``bench_anime_stitch.py``'s own directory layout
(``{base_dir}/output/{name}_anime_stitch.png``, ``{base_dir}/ground_truth/``,
and the ``paths``/``metrics_*`` fields of its ``anime_stitch_*.json`` results
file) so the dashboard reads exactly what that script already writes without
recomputing anything.
"""

from __future__ import annotations

import dataclasses
import glob
import json
import os
from typing import Dict, List, Optional

import cv2
import numpy as np


@dataclasses.dataclass
class TestAssets:
    name: str
    asp_path: Optional[str]
    simple_path: Optional[str]
    gt_path: Optional[str]
    plots_dir: Optional[str]
    stage_dir: Optional[str]
    metrics: Dict


def discover_datasets(base_dir: str) -> List[str]:
    out_dir = os.path.join(base_dir, "output")
    names = []
    for p in sorted(glob.glob(os.path.join(out_dir, "asp_test*_anime_stitch.png"))):
        names.append(os.path.basename(p)[: -len("_anime_stitch.png")])
    return names


def _find_gt_path(name: str, gt_dir: str) -> Optional[str]:
    for ext in (".png", ".jpg", ".jpeg"):
        p = os.path.join(gt_dir, f"{name}{ext}")
        if os.path.exists(p):
            return p
    return None


_METRICS_CACHE: Optional[Dict[str, Dict]] = None


def _load_latest_metrics(repo_root: str) -> Dict[str, Dict]:
    """Index the most recent bench_anime_stitch.py results JSON by dataset
    name. Cached per-process — a dashboard session never straddles a new
    benchmark run finishing mid-session."""
    global _METRICS_CACHE
    if _METRICS_CACHE is not None:
        return _METRICS_CACHE
    results_dir = os.path.join(repo_root, "backend", "benchmark", "output")
    files = sorted(glob.glob(os.path.join(results_dir, "anime_stitch_*.json")))
    if not files:
        _METRICS_CACHE = {}
        return _METRICS_CACHE
    try:
        with open(files[-1]) as fh:
            doc = json.load(fh)
    except (OSError, json.JSONDecodeError):
        _METRICS_CACHE = {}
        return _METRICS_CACHE
    _METRICS_CACHE = {d["name"]: d for d in doc.get("datasets", [])}
    return _METRICS_CACHE


def repo_root_from(file_path: str) -> str:
    """Walk up from ``file_path`` to the repo root (the directory holding
    ``pyproject.toml``). The original rating_manager.py hardcoded a fixed
    ``dirname`` chain depth that, at this package's nesting level, resolves
    to ``backend/`` instead of the real repo root ``bench_anime_stitch.py``'s
    own ``_load_human_ratings()`` reads ``data/human_ratings/`` from — a
    latent bug that silently split ratings across two directories. Walking
    up to a known sentinel file is depth-independent and can't drift again
    if this package gets moved or nested further."""
    d = os.path.dirname(os.path.abspath(file_path))
    while d != os.path.dirname(d):
        if os.path.exists(os.path.join(d, "pyproject.toml")):
            return d
        d = os.path.dirname(d)
    raise RuntimeError(f"Could not locate repo root (pyproject.toml) above {file_path}")


def load_test_assets(base_dir: str, name: str, repo_root: str) -> TestAssets:
    out_dir = os.path.join(base_dir, "output")
    gt_dir = os.path.join(base_dir, "ground_truth")
    asp_path = os.path.join(out_dir, f"{name}_anime_stitch.png")
    simple_path = os.path.join(out_dir, f"{name}_simple_stitch.png")
    metrics_all = _load_latest_metrics(repo_root)
    entry = metrics_all.get(name, {})
    paths = entry.get("paths", {})
    plots_dir = paths.get("plots_dir")
    stage_dir = paths.get("stage_dir")
    return TestAssets(
        name=name,
        asp_path=asp_path if os.path.exists(asp_path) else None,
        simple_path=simple_path if os.path.exists(simple_path) else None,
        gt_path=_find_gt_path(name, gt_dir),
        plots_dir=plots_dir if plots_dir and os.path.isdir(plots_dir) else None,
        stage_dir=stage_dir if stage_dir and os.path.isdir(stage_dir) else None,
        metrics=entry,
    )


def imread_bgr(path: Optional[str]) -> Optional[np.ndarray]:
    if not path:
        return None
    return cv2.imread(path)


def list_plot_images(plots_dir: Optional[str]) -> List[str]:
    if not plots_dir:
        return []
    return sorted(glob.glob(os.path.join(plots_dir, "*.png")))
