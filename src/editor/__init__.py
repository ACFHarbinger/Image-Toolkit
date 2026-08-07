"""Deterministic, Qt-free layer-stack model for the standalone editor."""

from .brush import stamp_dot, stamp_line
from .layer_stack import Layer, LayerMeta, LayerStack

__all__ = ["Layer", "LayerMeta", "LayerStack", "stamp_dot", "stamp_line"]
