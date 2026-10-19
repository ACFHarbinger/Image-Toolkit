"""Segmentation tools connecting the standalone editor's ``LayerStack`` to
the existing deterministic ``colorization.segmentation`` baseline (roadmap
milestone 1, issue #19) -- reused rather than reimplemented, since it is
already the tested, numpy-based engine algorithm the Line Art Segmentation
Krita Docker's ``segmentation_masks.py`` mirrors for the Krita-boundary
"no numpy" constraint. The standalone editor has no such constraint (its
GUI package already depends on numpy), so it calls the engine module
directly instead of duplicating a second pure-Python copy.

A layer's "line art" is simply wherever its alpha channel is painted --
this module treats any layer as a possible source, not just ones an artist
labels specially. Qt-free.
"""

from __future__ import annotations

import numpy as np

from colorization.segmentation import (
    close_line_gaps,
    filter_small_regions,
    region_adjacency,
    segment_regions,
)

from .layer_stack import LayerStack

__all__ = [
    "close_line_gaps_in_layer",
    "segment_layer_into_regions",
    "region_adjacency_for_regions",
]

# A small deterministic, high-contrast cycling palette for region layers --
# purely a visual aid distinguishing adjacent regions, not semantic color.
_REGION_PALETTE = (
    (230, 25, 75),
    (60, 180, 75),
    (255, 225, 25),
    (0, 130, 200),
    (245, 130, 48),
    (145, 30, 180),
    (70, 240, 240),
    (240, 50, 230),
    (210, 245, 60),
    (250, 190, 212),
)


def close_line_gaps_in_layer(layer_stack: LayerStack, layer_id: str, max_gap_px: int) -> bool:
    """Bridge small gaps in ``layer_id``'s painted ink (its alpha channel)
    in place. Bridged-in pixels that had no color yet are filled black, as
    a hand-inked bridge would be. Returns ``False`` if the layer doesn't
    exist."""
    layer = layer_stack.layer(layer_id)
    if layer is None:
        return False
    line_mask = layer.pixels[:, :, 3] > 0
    closed = close_line_gaps(line_mask, max_gap_px)
    newly_opaque = closed & ~line_mask
    if not newly_opaque.any():
        return True
    layer.pixels[newly_opaque, 3] = 255
    colorless = newly_opaque & (layer.pixels[:, :, :3].sum(axis=2) == 0)
    layer.pixels[colorless, :3] = 0
    return True


def segment_layer_into_regions(
    layer_stack: LayerStack, layer_id: str, *, min_region_area: int = 0
) -> list[str]:
    """Segment ``layer_id``'s painted ink (its alpha channel) into enclosed
    background regions, each becoming a new, distinctly colored layer
    stacked directly above the source layer. Returns the new layer ids in
    label order; an empty list if the source layer doesn't exist or no
    region survives ``min_region_area``. Never mutates the source layer."""
    layer = layer_stack.layer(layer_id)
    if layer is None:
        return []
    line_mask = layer.pixels[:, :, 3] > 0
    labels = filter_small_regions(segment_regions(line_mask), min_region_area)
    source_index = layer_stack.layers().index(layer)
    new_ids = []
    for position, label in enumerate(sorted(int(value) for value in np.unique(labels) if value)):
        region_id = f"{layer_id}-region-{label}"
        region_layer = layer_stack.add_layer(
            region_id, f"Region {label}", index=source_index + 1 + position
        )
        color = _REGION_PALETTE[(label - 1) % len(_REGION_PALETTE)]
        region_mask = labels == label
        region_layer.pixels[region_mask, :3] = color
        region_layer.pixels[region_mask, 3] = 255
        new_ids.append(region_id)
    return new_ids


def region_adjacency_for_regions(
    layer_stack: LayerStack, region_layer_ids: list[str]
) -> set[tuple[str, str]]:
    """Unordered region-id pairs whose layers' current alpha masks touch,
    among ``region_layer_ids`` (typically :func:`segment_layer_into_regions`'s
    return value). Reads each region layer's *current* alpha mask rather
    than re-deriving from the original line art, so it reflects any manual
    repainting of a region's boundary since segmentation. Empty set if
    fewer than two ids are given or any id doesn't exist."""
    if len(region_layer_ids) < 2:
        return set()
    maybe_layers = [layer_stack.layer(layer_id) for layer_id in region_layer_ids]
    if any(layer is None for layer in maybe_layers):
        return set()
    layers = [layer for layer in maybe_layers if layer is not None]
    labels = np.zeros((layer_stack.height, layer_stack.width), dtype=np.int32)
    for index, layer in enumerate(layers, start=1):
        labels[layer.pixels[:, :, 3] > 0] = index
    return {
        (region_layer_ids[a - 1], region_layer_ids[b - 1])
        for a, b in region_adjacency(labels)
    }
