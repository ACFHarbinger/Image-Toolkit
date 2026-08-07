"""View-specific landmark prompts selected from orientation construction layers."""

from __future__ import annotations

import math

VIEW_LAYERS = {
    "01 Left Profile Construction": ("left_profile", 0),
    "02 Left Three-Quarter Construction": ("left_three_quarter", 1),
    "03 Front Construction": ("front", 2),
    "04 Right Three-Quarter Construction": ("right_three_quarter", 3),
    "05 Right Profile Construction": ("right_profile", 4),
}
DESIGN_LAYERS = {
    "01 Neutral Front Construction": ("front", 0, "neutral"),
    "02 Youthful Soft Front Construction": ("front", 1, "youthful_soft"),
    "03 Long Tapered Front Construction": ("front", 2, "long_tapered"),
    "04 Broad Angular Front Construction": ("front", 3, "broad_angular"),
    "05 Selected Variant Right Three-Quarter Construction": (
        "right_three_quarter",
        4,
        "selected_variant",
    ),
}

THREE_QUARTER_PROMPTS = (
    ("cranium_center", "Click the center of the cranial mass."),
    ("cranium_edge", "Click an outer edge of the cranial mass to define its radius."),
    ("centerline_top", "Click the top of the curved facial centerline."),
    ("chin", "Click the chin where the facial centerline ends."),
    ("eye_line_left", "Click the left end of the eye-line cross-contour."),
    ("eye_line_right", "Click the right end of the eye-line cross-contour."),
    ("left_contour", "Click the left cranial contour at eye-line height."),
    ("right_contour", "Click the right cranial contour at eye-line height."),
    ("jaw_left", "Click the left jaw attachment or widest structural turn."),
    ("jaw_right", "Click the right jaw attachment or widest structural turn."),
)

PROFILE_PROMPTS = (
    ("cranium_center", "Click the center of the cranial mass."),
    ("cranium_edge", "Click the upper cranial edge to define its radius."),
    ("front_cranium_edge", "Click the front edge of the cranial ball."),
    ("back_cranium_edge", "Click the back edge of the cranial ball."),
    ("brow_front", "Click the front of the brow plane."),
    ("muzzle_front", "Click the front of the simple muzzle plane."),
    ("eye_line_back", "Click the back end of the eye-line cross-contour."),
    ("eye_line_front", "Click the front end of the eye-line cross-contour."),
    ("jaw_hinge", "Click where the jaw attaches below the cranium."),
    ("chin", "Click the point of the chin."),
)


def selected_orientation_view(active_node):
    if active_node is None:
        raise ValueError("select one named orientation construction layer")
    name = active_node.name() if callable(getattr(active_node, "name", None)) else active_node.name
    if name not in VIEW_LAYERS:
        raise ValueError("active layer is not one of the five orientation construction layers")
    return VIEW_LAYERS[name]


def selected_design_view(active_node):
    if active_node is None:
        raise ValueError("select one named cranial/jaw construction layer")
    name = active_node.name() if callable(getattr(active_node, "name", None)) else active_node.name
    if name not in DESIGN_LAYERS:
        raise ValueError("active layer is not one of the five cranial/jaw construction layers")
    return DESIGN_LAYERS[name]


class OrientationLandmarkCollector:
    def __init__(self, view):
        if view in {"left_profile", "right_profile"}:
            self.prompts = PROFILE_PROMPTS
            self.kind = "profile"
        elif view in {"left_three_quarter", "right_three_quarter"}:
            self.prompts = THREE_QUARTER_PROMPTS
            self.kind = "three_quarter"
        else:
            raise ValueError("front orientation uses the calibrated front landmark workflow")
        self.view = view
        self._points = []

    @property
    def complete(self):
        return len(self._points) == len(self.prompts)

    @property
    def prompt(self):
        if self.complete:
            return "All view-specific landmarks are placed. Confirm to review this head."
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
            raise ValueError("all landmarks must be placed before review")
        values = dict(zip((name for name, _ in self.prompts), self._points, strict=True))
        center = values.pop("cranium_center")
        edge = values.pop("cranium_edge")
        radius = math.dist(center, edge)
        if radius <= 0:
            raise ValueError("cranial center and edge must be distinct")
        return {"cranium_center": center, "cranium_radius": radius} | values
