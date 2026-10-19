"""Layer selection and shared landmark contract for controlled asymmetry."""

from __future__ import annotations

import math

ASYMMETRY_LAYERS = {
    "01 Symmetric Front Control": ("front_control", 0, False),
    "02 Corrected Accidental Drift": ("corrected_drift", 1, False),
    "03 Persistent Design Asymmetry": ("design", 2, True),
    "04 Expression Asymmetry": ("expression", 3, True),
    "05 Symmetric Right Three-Quarter Control": ("turned_control", 4, False),
    "06 Transferred Right Three-Quarter Asymmetry": ("transferred", 5, True),
}
ASYMMETRY_PROMPTS = (
    ("cranium_center", "Click the center of the cranial mass."),
    ("cranium_edge", "Click an outer cranial edge to define radius."),
    ("axis_top", "Click the top of the facial axis."),
    ("chin", "Click the chin at the end of the facial axis."),
    ("left_eye_center", "Click the center of the image-left eye."),
    ("right_eye_center", "Click the center of the image-right eye."),
    ("jaw_left", "Click the image-left jaw attachment or structural turn."),
    ("jaw_right", "Click the image-right jaw attachment or structural turn."),
    ("mouth_left", "Click the image-left mouth corner."),
    ("mouth_right", "Click the image-right mouth corner."),
    ("left_ear_top", "Click the top of the image-left or far ear evidence."),
    ("right_ear_top", "Click the top of the image-right or near ear."),
    ("left_ear_bottom", "Click the bottom of the image-left or far ear evidence."),
    ("right_ear_bottom", "Click the bottom of the image-right or near ear."),
)


def selected_asymmetry_stage(active_node):
    if active_node is None:
        raise ValueError("select one named controlled-asymmetry layer")
    name = active_node.name() if callable(getattr(active_node, "name", None)) else active_node.name
    if name not in ASYMMETRY_LAYERS:
        raise ValueError("active layer is not one of the six controlled-asymmetry layers")
    return ASYMMETRY_LAYERS[name]


class AsymmetryLandmarkCollector:
    prompts = ASYMMETRY_PROMPTS

    def __init__(self):
        self._points = []

    @property
    def complete(self):
        return len(self._points) == len(self.prompts)

    @property
    def prompt(self):
        if self.complete:
            return "All comparison landmarks are placed. Confirm to continue."
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
            raise ValueError("all comparison landmarks must be placed")
        return dict(zip((name for name, _ in self.prompts), self._points, strict=True))
