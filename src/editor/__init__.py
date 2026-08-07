"""Deterministic, Qt-free layer-stack model for the standalone editor."""

from .brush import stamp_dot, stamp_line, stamp_mask_dot, stamp_mask_line
from .history import EditHistory
from .layer_stack import Layer, LayerMeta, LayerStack

__all__ = [
    "Layer",
    "LayerMeta",
    "LayerStack",
    "stamp_dot",
    "stamp_line",
    "stamp_mask_dot",
    "stamp_mask_line",
    "EditHistory",
]
