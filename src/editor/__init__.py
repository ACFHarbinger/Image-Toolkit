"""Deterministic, Qt-free layer-stack model for the standalone editor."""

from .brush import stamp_dot, stamp_line, stamp_mask_dot, stamp_mask_line
from .history import EditHistory
from .layer_stack import Layer, LayerMeta, LayerStack
from .segmentation_tools import (
    close_line_gaps_in_layer,
    region_adjacency_for_regions,
    segment_layer_into_regions,
)

__all__ = [
    "Layer",
    "LayerMeta",
    "LayerStack",
    "stamp_dot",
    "stamp_line",
    "stamp_mask_dot",
    "stamp_mask_line",
    "EditHistory",
    "close_line_gaps_in_layer",
    "segment_layer_into_regions",
    "region_adjacency_for_regions",
]
