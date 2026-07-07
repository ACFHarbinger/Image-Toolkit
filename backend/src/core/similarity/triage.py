"""Heuristic rule engine for smart triage / auto-selection.

Given a cluster of similar images and a :class:`TriageRules`, score every file
and pick the *keeper*; the rest are proposed for deletion/consolidation.
"""

import contextlib
import logging
import os
from typing import Dict, List, Optional, Tuple

from .config import TriageRules

logger = logging.getLogger(__name__)

# Format quality ladder — lossless first
_FORMAT_RANK = {
    ".png": 1.0,
    ".tiff": 1.0,
    ".tif": 1.0,
    ".bmp": 0.9,
    ".webp": 0.7,   # may be lossless, usually lossy
    ".jpg": 0.4,
    ".jpeg": 0.4,
    ".gif": 0.3,
}


def _probe(path: str) -> Dict:
    """Collect the per-file facts the rules need. Failure-tolerant."""
    info: Dict = {
        "path": path,
        "width": 0,
        "height": 0,
        "file_size": 0,
        "has_exif": False,
        "ext": os.path.splitext(path)[1].lower(),
    }
    with contextlib.suppress(OSError):
        info["file_size"] = os.path.getsize(path)
    try:
        from PIL import Image

        with Image.open(path) as img:
            info["width"], info["height"] = img.size
            exif = img.getexif()
            info["has_exif"] = bool(exif and len(exif) > 0)
    except Exception as e:
        logger.debug("Triage probe failed for %s: %s", path, e)
    return info


def _path_score(path: str, rules: TriageRules) -> float:
    """+1..0 for preferred directory substrings, negative for deprioritised."""
    lowered = os.path.dirname(path).lower()
    n = len(rules.path_priority)
    for rank, token in enumerate(rules.path_priority):
        if token.lower() in lowered:
            return (n - rank) / max(1, n)
    for token in rules.path_deprioritize:
        if token.lower() in lowered:
            return -1.0
    return 0.0


def score_file(info: Dict, cluster_max: Dict, rules: TriageRules) -> float:
    score = 0.0
    if rules.prefer_highest_resolution and cluster_max["pixels"] > 0:
        score += rules.weight_resolution * (
            (info["width"] * info["height"]) / cluster_max["pixels"]
        )
    if rules.prefer_largest_file and cluster_max["file_size"] > 0:
        score += rules.weight_file_size * (info["file_size"] / cluster_max["file_size"])
    if rules.prefer_lossless_format:
        score += rules.weight_format * _FORMAT_RANK.get(info["ext"], 0.5)
    if rules.prefer_exif_metadata and info["has_exif"]:
        score += rules.weight_exif
    score += rules.weight_path * _path_score(info["path"], rules)
    return score


def auto_select(
    cluster_paths: List[str],
    rules: Optional[TriageRules] = None,
    protected: Optional[set] = None,
) -> Tuple[Optional[str], List[str]]:
    """Return ``(keeper, discards)`` for one cluster.

    ``protected`` paths (e.g. everything inside the Reference directory in a
    directional scan) can never be discarded; if all files are protected the
    result is ``(None, [])``.
    """
    rules = rules or TriageRules()
    protected = protected or set()

    infos = [_probe(p) for p in cluster_paths]
    cluster_max = {
        "pixels": max((i["width"] * i["height"] for i in infos), default=0),
        "file_size": max((i["file_size"] for i in infos), default=0),
    }

    scored = sorted(
        infos,
        key=lambda i: (i["path"] in protected,  # protected files win ties as keeper
                       score_file(i, cluster_max, rules)),
        reverse=True,
    )
    keeper = scored[0]["path"]
    discards = [i["path"] for i in scored[1:] if i["path"] not in protected]
    if not discards and keeper in protected:
        return None, []
    return keeper, discards
