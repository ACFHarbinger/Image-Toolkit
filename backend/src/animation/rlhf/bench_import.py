"""§1.10E — Benchmark JSON import helpers for RLHF feedback collection.

Provides pure-Python utilities for parsing benchmark result JSON files and
suggesting a human-calibrated quality rating from automated metrics.

These helpers are GUI-agnostic so they can be unit-tested and reused.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


def parse_bench_json(path: str) -> List[Dict[str, Any]]:
    """Parse a benchmark results JSON file into a list of per-dataset dicts.

    Handles both:
    - Full suite doc (``doc["datasets"]`` list) produced by ``_save_report()``
    - Single-dataset dict (saved directly, e.g. for quick one-off runs)

    Parameters
    ----------
    path:
        Absolute or relative path to a ``*.json`` benchmark results file.

    Returns
    -------
    List of per-dataset dicts, each containing at minimum:
    ``name``, ``anime_path``, ``metrics_asp``, ``comparison``, ``used_fallback``.
    """
    with open(path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)

    if isinstance(doc, list):
        return doc

    if isinstance(doc, dict):
        # Full suite report: doc["datasets"] is the per-dataset list
        if "datasets" in doc and isinstance(doc["datasets"], list):
            return doc["datasets"]
        # Single-dataset dict — wrap in a list
        if "name" in doc or "anime_path" in doc or "metrics_asp" in doc:
            return [doc]

    raise ValueError(
        f"Unrecognised benchmark JSON structure in {os.path.basename(path)!r}: "
        f"expected a list, a dict with 'datasets' key, or a single dataset dict."
    )


def resolve_anime_path(dataset: Dict[str, Any]) -> Optional[str]:
    """Return the ASP output panorama path from a dataset dict.

    Tries ``dataset["anime_path"]`` first (the primary field), then
    ``dataset["paths"]["anime_stitch"]`` as fallback.  Returns ``None``
    when neither is available or neither path exists on disk.
    """
    candidates = [
        dataset.get("anime_path"),
        (dataset.get("paths") or {}).get("anime_stitch"),
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return str(p)
    # Return the first non-None candidate even if the file doesn't exist yet
    # (lets the GUI show the path and report a load failure with context).
    for p in candidates:
        if p:
            return str(p)
    return None


def suggested_rating(metrics: Optional[Dict[str, Any]]) -> float:
    """Translate automated metrics_asp into a suggested 0–10 quality rating.

    §3.32C: Updated to use ``ghosting_siqe`` (FFT autocorrelation, 0–100,
    higher = more ghosting) instead of ``ghosting_score`` (double-Sobel
    sharpness proxy — larger = sharper, NOT more ghosting).  The old formula
    used ``(1 − ghosting_score)`` which penalised sharp outputs; the correct
    term is ``(1 − ghosting_siqe / 100)``.

        composite = coverage * 0.35
                  + sharpness_norm * 0.25
                  + (1 − ghosting_siqe / 100) * 0.20
                  + seam_coherence * 0.20

    where ``sharpness_norm`` is ``min(sharpness / 80, 1.0)`` (80 is a
    reference value for a sharp anime panel at 1080p).

    Returns a float in [0.0, 10.0].  Returns 5.0 when metrics is None or
    lacks the expected keys (neutral mid-point).
    """
    if not metrics:
        return 5.0

    coverage = float(metrics.get("coverage", 0.9))
    sharpness = float(metrics.get("sharpness", 40.0))
    # ghosting_siqe: 0=clean, 100=heavy ghost. Normalise to [0,1] for formula.
    ghosting_siqe = float(metrics.get("ghosting_siqe", 30.0))
    seam_coh = float(metrics.get("seam_coherence", 0.7))

    sharpness_norm = min(sharpness / 80.0, 1.0)
    composite = (
        coverage * 0.35
        + sharpness_norm * 0.25
        + max(0.0, 1.0 - ghosting_siqe / 100.0) * 0.20
        + seam_coh * 0.20
    )
    return round(min(10.0, max(0.0, composite * 10.0)), 1)


def verdict_label(dataset: Dict[str, Any]) -> str:
    """Return a short textual verdict label for display in the dataset list.

    Examples: ``"asp_better"`` → ``"✓ ASP"``, ``"simple_better"`` → ``"✗ SIMP"``.
    """
    v = (dataset.get("comparison") or {}).get("verdict") or ""
    if v == "asp_better":
        return "✓ ASP"
    if v == "simple_better":
        return "✗ SIMP"
    if v == "tie":
        return "~ TIE"
    return "?"


__all__ = [
    "parse_bench_json",
    "resolve_anime_path",
    "suggested_rating",
    "verdict_label",
]
