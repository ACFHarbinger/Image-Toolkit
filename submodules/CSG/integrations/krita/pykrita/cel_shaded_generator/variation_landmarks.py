"""Layer selection for character-variation identity comparisons."""

from __future__ import annotations

from .asymmetry_landmarks import AsymmetryLandmarkCollector

VARIATION_LAYERS = {
    "01 Undecorated Identity Baseline": ("baseline", 0),
    "02 Proportion Variant": ("proportion_variant", 1),
    "03 Feature Shape Variant": ("feature_variant", 2),
    "04 Age and Style Variant": ("age_style_variant", 3),
    "05 Selected Front Identity Reconstruction": ("selected_front", 4),
    "06 Selected Right Three-Quarter Identity Check": ("selected_turned", 5),
}


def selected_variation_stage(active_node):
    if active_node is None:
        raise ValueError("select one named character-variation layer")
    name = active_node.name() if callable(getattr(active_node, "name", None)) else active_node.name
    if name not in VARIATION_LAYERS:
        raise ValueError("active layer is not one of the six character-variation layers")
    return VARIATION_LAYERS[name]


class VariationLandmarkCollector(AsymmetryLandmarkCollector):
    """Reuse the full structural relationship set for identity comparison."""
