"""Quadtree-accelerated dirty-region colorization (roadmap §5.2, issue #191).

**Pain point this addresses:** a full-resolution 4K sparse-solve on every
scribble stroke is too slow for interactive feedback -- §2.1-§2.4's solvers
already cap solve cost via `max_solve_dim` (downscale-for-solve), but that
still re-solves the *entire* page on every stroke. Genuine live interactivity
needs the opposite: re-solve only the region touched by the latest stroke,
leaving everything else untouched.

**Scope of this module, and what's deliberately deferred:** this ships the
spatial-partitioning and windowed-resolve *mechanism* -- `build_quadtree()`
recursively partitions a grayscale image into flat vs. detailed leaf regions
(subdividing where local variance is high, i.e. where line art/screentone
detail lives, and staying coarse over flat regions), and
`colorize_region_incremental()` re-solves only a small window around a
"dirty" bounding box (the latest stroke's extent, expanded to cover whatever
quadtree leaves it touches) and composites that window back into a
previously-solved full-canvas result. It does **not** wire this into a live
per-stroke GUI dispatch loop -- the Manga Colorization Tab (issue #195) and
Manga Animation Tab (issue #196) both still solve on an explicit "Colorize"
button click, not per-stroke. Issue #191's own text explicitly allows this:
"Deferrable for an initial 'solve on demand' (non-live) MVP" -- which is
this project's actual current state. Wiring `colorize_region_incremental()`
into a real live-stroke dispatch loop (debounced re-solve on
`scribble_changed`, replacing the current single big "Colorize" action) is
a real, separately-scoped follow-up, not attempted here.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

import numpy as np

from .colorization import colorize_scribble

__all__ = ["build_quadtree", "colorize_region_incremental"]

# A leaf's (y0, x0, y1, x1) pixel bounding box, half-open on the high end
# (matches NumPy slicing: gray[y0:y1, x0:x1]).
BBox = Tuple[int, int, int, int]


def _region_variance(gray: np.ndarray, bbox: BBox) -> float:
    y0, x0, y1, x1 = bbox
    region = gray[y0:y1, x0:x1]
    if region.size == 0:
        return 0.0
    return float(np.var(region.astype(np.float64)))


def build_quadtree(
    gray: np.ndarray,
    max_depth: int = 6,
    min_size: int = 32,
    variance_threshold: float = 150.0,
) -> List[BBox]:
    """Recursively partition ``gray`` into flat-vs-detailed leaf regions.

    A region subdivides into 4 quadrants when its local intensity variance
    exceeds ``variance_threshold`` (a proxy for line art/screentone detail
    -- high-frequency content, the same kind of signal a stroke's affinity
    graph needs fine granularity to represent) *and* it's still larger than
    ``min_size`` on both axes *and* shallower than ``max_depth``. Otherwise
    it stays a single flat leaf. This means detailed regions end up
    partitioned into many small leaves and flat regions into a few large
    ones -- exactly the "flat vs. detailed regions" split the roadmap calls
    for (research report §9.3).

    Args:
        gray: HxW grayscale image (any numeric dtype).
        max_depth: hard cap on recursion depth (bounds leaf count).
        min_size: a region smaller than this on either axis never
            subdivides further, regardless of variance.
        variance_threshold: intensity-variance (in the image's own value
            scale, e.g. 0-255 for uint8) above which a region subdivides.

    Returns:
        A list of leaf bounding boxes, together exactly covering the image
        (no gaps, no overlaps) -- a flattened quadtree, not the tree
        structure itself, since every caller here only needs the leaves.
    """
    h, w = gray.shape
    leaves: List[BBox] = []

    def _recurse(bbox: BBox, depth: int) -> None:
        y0, x0, y1, x1 = bbox
        rh, rw = y1 - y0, x1 - x0
        if rh <= 0 or rw <= 0:
            return

        can_subdivide = depth < max_depth and rh > min_size and rw > min_size
        if can_subdivide and _region_variance(gray, bbox) > variance_threshold:
            my, mx = y0 + rh // 2, x0 + rw // 2
            _recurse((y0, x0, my, mx), depth + 1)
            _recurse((y0, mx, my, x1), depth + 1)
            _recurse((my, x0, y1, mx), depth + 1)
            _recurse((my, mx, y1, x1), depth + 1)
        else:
            leaves.append(bbox)

    _recurse((0, 0, h, w), 0)
    return leaves


def _touched_leaves(leaves: List[BBox], dirty_bbox: BBox) -> List[BBox]:
    dy0, dx0, dy1, dx1 = dirty_bbox
    touched = []
    for y0, x0, y1, x1 in leaves:
        if x0 < dx1 and x1 > dx0 and y0 < dy1 and y1 > dy0:
            touched.append((y0, x0, y1, x1))
    return touched


def colorize_region_incremental(
    gray: np.ndarray,
    scribble_rgb: np.ndarray,
    scribble_mask: np.ndarray,
    prev_result: np.ndarray,
    dirty_bbox: BBox,
    leaves: Optional[List[BBox]] = None,
    halo: int = 16,
    colorize_fn: Optional[Callable[..., np.ndarray]] = None,
    **colorize_kwargs,
) -> np.ndarray:
    """Re-solve only the quadtree-expanded window around ``dirty_bbox``,
    compositing it into an already-solved ``prev_result``.

    This is the incremental counterpart to a full-page
    :func:`backend.src.manga.colorization.colorize_scribble` (or
    ``colorize_scribble_screentone``/``colorize_reference`` via
    ``colorize_fn``) call: it solves a small window instead of the whole
    image, then pastes that window's output into ``prev_result``. Every
    pixel outside the resolved window is copied through from
    ``prev_result`` unchanged.

    Args:
        gray: full HxW grayscale line-art image.
        scribble_rgb: full HxWx3 scribble color image (see
            ``colorize_scribble``'s own docstring for the contract).
        scribble_mask: full HxW scribble mask.
        prev_result: the previously-solved HxWx3 uint8 output to update in
            place (a copy is returned; the input is not mutated). Must come
            from a prior full or incremental solve -- there is no
            "solve from nothing" path here, matching how a live-interaction
            loop would actually use this (one initial full solve to seed
            ``prev_result``, then incremental updates per stroke).
        dirty_bbox: ``(y0, x0, y1, x1)`` bounding box of the region that
            changed (typically the latest stroke's extent).
        leaves: pre-computed quadtree leaves (see :func:`build_quadtree`);
            computed from ``gray`` with default parameters if not given.
        halo: extra pixels of padding added around the touched leaves'
            union bbox before re-solving, so the windowed solve's own
            boundary doesn't introduce a visible seam at the window edge.
        colorize_fn: which single-image colorizer to run on the window
            (defaults to :func:`colorize_scribble`). Must accept
            ``(gray, scribble_rgb, scribble_mask, **kwargs)`` and return an
            HxWx3 uint8 RGB array, the same contract every §2.1-§2.4
            colorizer already follows.
        **colorize_kwargs: forwarded to ``colorize_fn`` (e.g.
            ``max_solve_dim``).

    Returns:
        HxWx3 uint8 RGB array: ``prev_result`` with the resolved window
        pasted in.
    """
    h, w = gray.shape
    if prev_result.shape[:2] != (h, w):
        raise ValueError(f"prev_result shape {prev_result.shape[:2]} must match gray shape {(h, w)}")

    if leaves is None:
        leaves = build_quadtree(gray)

    touched = _touched_leaves(leaves, dirty_bbox)
    if not touched:
        # The dirty bbox landed entirely outside every leaf (e.g. a
        # degenerate empty bbox) -- nothing to re-solve.
        return prev_result.copy()

    y0 = min(b[0] for b in touched)
    x0 = min(b[1] for b in touched)
    y1 = max(b[2] for b in touched)
    x1 = max(b[3] for b in touched)

    y0 = max(0, y0 - halo)
    x0 = max(0, x0 - halo)
    y1 = min(h, y1 + halo)
    x1 = min(w, x1 + halo)

    window_mask = scribble_mask[y0:y1, x0:x1]
    if not np.any(window_mask):
        # No scribbles in the re-solve window (e.g. an erase-only stroke) --
        # nothing for the solver to propagate from; leave prev_result as-is
        # rather than raising, since this is a normal outcome of a live
        # per-stroke dispatch loop, not an error.
        return prev_result.copy()

    fn = colorize_fn or colorize_scribble
    window_result = fn(
        gray[y0:y1, x0:x1],
        scribble_rgb[y0:y1, x0:x1],
        window_mask,
        **colorize_kwargs,
    )

    out = prev_result.copy()
    out[y0:y1, x0:x1] = window_result
    return out
