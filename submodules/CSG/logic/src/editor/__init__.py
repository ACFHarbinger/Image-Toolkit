"""Deterministic, Qt-free layer-stack model for the standalone editor."""

from .brush import (
    erase_dot,
    erase_line,
    stamp_dot,
    stamp_dot_soft,
    stamp_line,
    stamp_line_soft,
    stamp_mask_dot,
    stamp_mask_line,
)
from .correspondence_tools import (
    adjacency_agreement_by_material,
    adjacent_region_ids,
    assign_region_correspondence,
    rank_material_candidates,
)
from .document_io import load_document, save_document
from .history import EditHistory
from .layer_stack import VALID_BLEND_MODES, Layer, LayerMeta, LayerStack
from .palette_tools import PALETTE_ROLES, apply_palette_color_to_region, resolve_palette_color
from .segmentation_tools import (
    close_line_gaps_in_layer,
    region_adjacency_for_regions,
    segment_layer_into_regions,
)

__all__ = [
    "Layer",
    "LayerMeta",
    "LayerStack",
    "VALID_BLEND_MODES",
    "erase_dot",
    "erase_line",
    "stamp_dot",
    "stamp_dot_soft",
    "stamp_line",
    "stamp_line_soft",
    "stamp_mask_dot",
    "stamp_mask_line",
    "EditHistory",
    "close_line_gaps_in_layer",
    "segment_layer_into_regions",
    "region_adjacency_for_regions",
    "PALETTE_ROLES",
    "resolve_palette_color",
    "apply_palette_color_to_region",
    "adjacency_agreement_by_material",
    "adjacent_region_ids",
    "rank_material_candidates",
    "assign_region_correspondence",
    "save_document",
    "load_document",
]
