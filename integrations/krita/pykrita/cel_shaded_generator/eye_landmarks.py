"""Active-layer selection and manual prompts for eye-pair review."""

from __future__ import annotations

import math

EYE_LAYERS = {
    "01 Neutral Front Eye Structure": ("front", "structure", 0),
    "02 Stylized Front Expression": ("front", "style_expression", 1),
    "03 Neutral Right Three-Quarter Eye Structure": (
        "right_three_quarter",
        "structure",
        2,
    ),
    "04 Stylized Right Three-Quarter Expression": (
        "right_three_quarter",
        "style_expression",
        3,
    ),
}

EYE_PROMPTS = (
    ("centerline_top", "Click the top of the facial centerline."),
    ("chin", "Click the chin where the facial centerline ends."),
    ("eye_line_left", "Click the image-left end of the eye-line cross-contour."),
    ("eye_line_right", "Click the image-right end of the eye-line cross-contour."),
    ("left_inner", "Click the inner corner of the image-left eye."),
    ("left_outer", "Click the outer corner of the image-left eye."),
    ("right_inner", "Click the inner corner of the image-right eye."),
    ("right_outer", "Click the outer corner of the image-right eye."),
    ("left_upper_peak", "Click the highest upper-lid point of the image-left eye."),
    ("left_lower_peak", "Click the lowest lower-lid point of the image-left eye."),
    ("right_upper_peak", "Click the highest upper-lid point of the image-right eye."),
    ("right_lower_peak", "Click the lowest lower-lid point of the image-right eye."),
    ("left_iris_top", "Click the visible top of the image-left iris."),
    ("left_iris_bottom", "Click the visible bottom of the image-left iris."),
    ("right_iris_top", "Click the visible top of the image-right iris."),
    ("right_iris_bottom", "Click the visible bottom of the image-right iris."),
)


def selected_eye_view(active_node):
    if active_node is None:
        raise ValueError("select one named eye construction layer")
    name = active_node.name() if callable(getattr(active_node, "name", None)) else active_node.name
    if name not in EYE_LAYERS:
        raise ValueError("active layer is not one of the four eye exercise layers")
    return EYE_LAYERS[name]


class EyeLandmarkCollector:
    prompts = EYE_PROMPTS

    def __init__(self):
        self._points = []

    @property
    def complete(self):
        return len(self._points) == len(self.prompts)

    @property
    def prompt(self):
        if self.complete:
            return "All eye landmarks are placed. Confirm to request review."
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
            raise ValueError("all eye landmarks must be placed before review")
        return dict(zip((name for name, _ in self.prompts), self._points, strict=True))
