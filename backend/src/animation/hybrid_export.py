"""§2.8: HybridStitch export — serialize pipeline state to JSON for manual refinement.

Exports frame paths, solved affines, photometric corrections, seam boundaries and
post-warp diff scores so the pipeline can be resumed or hand-tuned without re-running
the full 13-stage solve.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

__all__ = [
    "HybridExportData",
    "build_hybrid_export",
    "save_hybrid_export",
    "load_hybrid_export",
]

ASP_VERSION = "S144"


@dataclass
class HybridExportData:
    """Serializable snapshot of pipeline state after Stage 13."""

    image_paths: List[str]
    affines: List[List[float]]
    photometric_gains: List[float]
    photometric_biases: List[float]
    canvas_w: int
    canvas_h: int
    seam_boundaries: List[float]
    seam_post_diffs: Dict[str, float]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    asp_version: str = ASP_VERSION


def build_hybrid_export(pipeline_state: dict) -> HybridExportData:
    """Build a ``HybridExportData`` from a pipeline-state dict.

    Expected keys (all optional — missing keys fall back to empty/zero):
    ``image_paths``, ``affines`` (list of 2×3 numpy arrays or flat lists),
    ``photometric_gains``, ``photometric_biases``,
    ``canvas_w``, ``canvas_h``,
    ``seam_boundaries``, ``seam_post_diffs``.
    """
    import numpy as np

    raw_affines = pipeline_state.get("affines", [])
    flat_affines: List[List[float]] = []
    for a in raw_affines:
        if isinstance(a, np.ndarray):
            flat_affines.append(a.flatten().tolist()[:6])
        else:
            flat_affines.append([float(v) for v in list(a)][:6])

    seam_boundaries = pipeline_state.get("seam_boundaries", [])
    if isinstance(seam_boundaries, np.ndarray):
        seam_boundaries = seam_boundaries.tolist()

    seam_post_diffs = pipeline_state.get("seam_post_diffs", {})
    seam_post_diffs = {str(k): float(v) for k, v in seam_post_diffs.items()}

    return HybridExportData(
        image_paths=[str(p) for p in pipeline_state.get("image_paths", [])],
        affines=flat_affines,
        photometric_gains=[float(g) for g in pipeline_state.get("photometric_gains", [])],
        photometric_biases=[float(b) for b in pipeline_state.get("photometric_biases", [])],
        canvas_w=int(pipeline_state.get("canvas_w", 0)),
        canvas_h=int(pipeline_state.get("canvas_h", 0)),
        seam_boundaries=seam_boundaries,
        seam_post_diffs=seam_post_diffs,
    )


def save_hybrid_export(data: HybridExportData, path: str) -> None:
    """Serialize *data* to *path* as UTF-8 JSON (indent=2)."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(asdict(data), indent=2), encoding="utf-8")


def load_hybrid_export(path: str) -> HybridExportData:
    """Deserialize a JSON file written by :func:`save_hybrid_export`.

    Raises ``FileNotFoundError`` if *path* does not exist.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Hybrid export not found: {path}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    return HybridExportData(**raw)
