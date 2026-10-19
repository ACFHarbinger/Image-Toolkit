"""Specialized manual landmark workflows for nose, mouth, and ear studies."""

from __future__ import annotations

import math

FEATURE_LAYERS = {
    "01 Front Nose and Muzzle Construction": ("nose", "front", 0),
    "02 Front Mouth Construction": ("mouth", "front", 1),
    "03 Front Ear Construction": ("ear", "front", 2),
    "04 Right Three-Quarter Nose and Muzzle Construction": (
        "nose",
        "right_three_quarter",
        3,
    ),
    "05 Right Three-Quarter Mouth Construction": ("mouth", "right_three_quarter", 4),
    "06 Right Three-Quarter Ear Construction": ("ear", "right_three_quarter", 5),
}

NOSE_PROMPTS = (
    ("axis_top", "Click the top of the facial centerline."),
    ("chin", "Click the chin at the end of the facial centerline."),
    ("bridge_top", "Click the top of the simplified nose bridge."),
    ("tip", "Click the nose-tip projection."),
    ("base_left", "Click the image-left edge of the nose base."),
    ("base_right", "Click the image-right edge of the nose base."),
    ("nostril_left", "Click the image-left nostril evidence."),
    ("nostril_right", "Click the image-right nostril evidence."),
    ("muzzle_left", "Click the image-left edge of the muzzle form."),
    ("muzzle_right", "Click the image-right edge of the muzzle form."),
)
MOUTH_PROMPTS = (
    ("axis_top", "Click the top of the facial centerline."),
    ("chin", "Click the chin at the end of the facial centerline."),
    ("nose_base", "Click the center of the nose base."),
    ("mouth_center", "Click the mouth center on the facial axis."),
    ("corner_left", "Click the image-left mouth corner."),
    ("corner_right", "Click the image-right mouth corner."),
    ("upper_peak", "Click the central upper edge of the mouth opening."),
    ("lower_peak", "Click the central lower edge of the mouth opening."),
    ("muzzle_left", "Click the image-left edge of the muzzle surface."),
    ("muzzle_right", "Click the image-right edge of the muzzle surface."),
)
FRONT_EAR_PROMPTS = (
    ("eye_line_left", "Click the image-left end of the eye line."),
    ("eye_line_right", "Click the image-right end of the eye line."),
    ("left_top", "Click the top of the image-left ear."),
    ("left_bottom", "Click the bottom of the image-left ear."),
    ("left_outer", "Click the outermost point of the image-left ear rim."),
    ("left_inner", "Click the deepest visible point of the image-left ear bowl."),
    ("left_attach_top", "Click the upper attachment of the image-left ear."),
    ("left_attach_bottom", "Click the lower attachment of the image-left ear."),
    ("right_top", "Click the top of the image-right ear."),
    ("right_bottom", "Click the bottom of the image-right ear."),
    ("right_outer", "Click the outermost point of the image-right ear rim."),
    ("right_inner", "Click the deepest visible point of the image-right ear bowl."),
    ("right_attach_top", "Click the upper attachment of the image-right ear."),
    ("right_attach_bottom", "Click the lower attachment of the image-right ear."),
)
TURNED_EAR_PROMPTS = (
    ("side_plane_top", "Click the top of the visible cranial side plane."),
    ("side_plane_bottom", "Click the bottom of the visible cranial side plane."),
    ("near_top", "Click the top of the near ear."),
    ("near_bottom", "Click the bottom of the near ear."),
    ("near_outer", "Click the outermost point of the near ear rim."),
    ("near_inner", "Click the deepest visible point of the near ear bowl."),
    ("near_attach_top", "Click the upper attachment of the near ear."),
    ("near_attach_bottom", "Click the lower attachment of the near ear."),
    ("skull_edge", "Click the skull contour immediately beside the near ear."),
    ("far_evidence", "Click any visible far-ear evidence, or its expected occlusion point."),
)


def selected_feature_view(active_node):
    if active_node is None:
        raise ValueError("select one named feature construction layer")
    name = active_node.name() if callable(getattr(active_node, "name", None)) else active_node.name
    if name not in FEATURE_LAYERS:
        raise ValueError("active layer is not one of the six feature exercise layers")
    return FEATURE_LAYERS[name]


class FeatureLandmarkCollector:
    def __init__(self, feature, view):
        if feature == "nose":
            self.prompts = NOSE_PROMPTS
        elif feature == "mouth":
            self.prompts = MOUTH_PROMPTS
        elif feature == "ear" and view == "front":
            self.prompts = FRONT_EAR_PROMPTS
        elif feature == "ear" and view == "right_three_quarter":
            self.prompts = TURNED_EAR_PROMPTS
        else:
            raise ValueError("unsupported feature landmark workflow")
        self._points = []

    @property
    def complete(self):
        return len(self._points) == len(self.prompts)

    @property
    def prompt(self):
        if self.complete:
            return "All feature landmarks are placed. Confirm to request review."
        return self.prompts[len(self._points)][1]

    @property
    def points(self):
        return tuple(self._points)

    def add(self, x, y):
        if self.complete:
            raise ValueError("all landmarks are already placed")
        if any(not math.isfinite(value) or not 0 <= value <= 1 for value in (x, y)):
            raise ValueError("landmark coordinates must be normalized")
        self._points.append((float(x), float(y)))

    def undo(self):
        if self._points:
            self._points.pop()

    def reset(self):
        self._points.clear()

    def result(self):
        if not self.complete:
            raise ValueError("all feature landmarks must be placed before review")
        return dict(zip((name for name, _ in self.prompts), self._points, strict=True))
