"""Deterministic line-art gap closing and region segmentation baseline
(roadmap milestone 1, issue #19).

Region correspondence (``colorization.correspondence``) assumes
target-drawing regions already exist as artist-editable masks. This module
supplies the deterministic step that produces those regions from raw line
art: close small gaps in hand-drawn ink so enclosed areas are topologically
closed, then flood-fill the enclosed background into labeled regions, and
build the region-adjacency graph the roadmap's implementation-avenues list
names alongside gap closing and trapped-ball filling.

Deliberately a single-radius flood fill for this first pass, not the
roadmap's full multi-radius trapped-ball algorithm (which reconciles
line-thickness variation by filling with several ball sizes and keeping the
largest non-leaking result per pixel) -- one structuring-element radius
covers the common case of roughly uniform line weight and gives an artist
something to review/correct before a more expensive multi-radius pass is
justified. The region-adjacency graph this module builds is independent of
which fill strategy produced the labels, so upgrading the fill later does
not change downstream callers.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

__all__ = [
    "close_line_gaps",
    "segment_regions",
    "filter_small_regions",
    "region_adjacency",
    "region_statistics",
]


def close_line_gaps(line_mask: np.ndarray, max_gap_px: int) -> np.ndarray:
    """Bridge ink gaps up to ``max_gap_px`` wide with morphological closing.

    ``line_mask`` is a 2D boolean/``{0, 1}`` array where truthy values are
    ink. Returns a new boolean array; the input is never modified in place.
    """
    if not isinstance(line_mask, np.ndarray) or line_mask.ndim != 2:
        raise ValueError("line mask must be a 2D array")
    if not isinstance(max_gap_px, int) or isinstance(max_gap_px, bool) or max_gap_px < 0:
        raise ValueError("max_gap_px must be a non-negative integer")
    mask = line_mask.astype(bool)
    if max_gap_px == 0:
        return mask
    structure = ndimage.generate_binary_structure(2, 2)
    return ndimage.binary_closing(mask, structure=structure, iterations=max_gap_px)


def segment_regions(line_mask: np.ndarray) -> np.ndarray:
    """Label enclosed background regions from a (gap-closed) line mask.

    Returns an int array the same shape as ``line_mask`` where ``0`` marks
    ink/boundary pixels and each enclosed region carries a distinct positive
    label. Regions touching the array border are not enclosed by any drawn
    boundary and are excluded (labeled ``0``); the remaining labels are not
    guaranteed contiguous.
    """
    if not isinstance(line_mask, np.ndarray) or line_mask.ndim != 2:
        raise ValueError("line mask must be a 2D array")
    background = ~line_mask.astype(bool)
    labels, count = ndimage.label(background, structure=np.ones((3, 3), dtype=int))
    if count == 0:
        return labels
    border_labels = (
        set(np.unique(labels[0, :]))
        | set(np.unique(labels[-1, :]))
        | set(np.unique(labels[:, 0]))
        | set(np.unique(labels[:, -1]))
    )
    border_labels.discard(0)
    if border_labels:
        labels = labels.copy()
        labels[np.isin(labels, list(border_labels))] = 0
    return labels


def filter_small_regions(labels: np.ndarray, min_area: int) -> np.ndarray:
    """Return a copy of ``labels`` with regions smaller than ``min_area`` cleared.

    Line art routinely produces dust-speck regions from stray anti-aliased
    pixels or hairline imperfections; this clears them back to ``0`` (ink/
    unenclosed) without disturbing any region that meets the threshold.
    """
    if not isinstance(labels, np.ndarray) or labels.ndim != 2:
        raise ValueError("labels must be a 2D array")
    if not isinstance(min_area, int) or isinstance(min_area, bool) or min_area < 0:
        raise ValueError("min_area must be a non-negative integer")
    result = labels.copy()
    if min_area == 0:
        return result
    for label in np.unique(labels):
        if label == 0:
            continue
        if int(np.count_nonzero(labels == label)) < min_area:
            result[labels == label] = 0
    return result


def region_adjacency(labels: np.ndarray) -> set[tuple[int, int]]:
    """Return unordered ``(smaller, larger)`` label pairs that share a border."""
    if not isinstance(labels, np.ndarray) or labels.ndim != 2:
        raise ValueError("labels must be a 2D array")
    pairs: set[tuple[int, int]] = set()

    def _collect(left: np.ndarray, right: np.ndarray) -> None:
        left_flat, right_flat = left.ravel(), right.ravel()
        touching = (left_flat > 0) & (right_flat > 0) & (left_flat != right_flat)
        for a, b in zip(left_flat[touching], right_flat[touching], strict=True):
            pairs.add((int(a), int(b)) if a < b else (int(b), int(a)))

    _collect(labels[:, :-1], labels[:, 1:])
    _collect(labels[:-1, :], labels[1:, :])
    return pairs


def region_statistics(labels: np.ndarray) -> dict[int, dict[str, object]]:
    """Return area, centroid, and bounding box for each labeled region."""
    if not isinstance(labels, np.ndarray) or labels.ndim != 2:
        raise ValueError("labels must be a 2D array")
    stats: dict[int, dict[str, object]] = {}
    for label in sorted(int(value) for value in np.unique(labels) if value != 0):
        rows, cols = np.nonzero(labels == label)
        stats[label] = {
            "area": int(rows.size),
            "centroid": (float(rows.mean()), float(cols.mean())),
            "bbox": (int(rows.min()), int(cols.min()), int(rows.max()), int(cols.max())),
        }
    return stats
