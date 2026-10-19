"""Manual landmark collection over a document projection snapshot."""

from __future__ import annotations

import math

LANDMARK_PROMPTS = (
    ("cranium_center", "Click the center of the cranial circle."),
    ("cranium_edge", "Click the right edge of the cranial circle."),
    ("centerline_top", "Click the top of the vertical centerline."),
    ("centerline_bottom", "Click where the centerline reaches the chin."),
    ("eye_line_left", "Click the left end of the eye-line."),
    ("eye_line_right", "Click the right end of the eye-line."),
    ("jaw_left", "Click the widest structural point of the left jaw."),
    ("jaw_right", "Click the widest structural point of the right jaw."),
    ("chin", "Click the center of the chin."),
)


class LandmarkCollector:
    """Small UI-independent state machine for the ordered placement workflow."""

    def __init__(self):
        self._points = []

    @property
    def complete(self):
        return len(self._points) == len(LANDMARK_PROMPTS)

    @property
    def prompt(self):
        if self.complete:
            return "All landmarks placed. Review the markers, then continue."
        return LANDMARK_PROMPTS[len(self._points)][1]

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
        values = dict(zip((name for name, _ in LANDMARK_PROMPTS), self._points, strict=True))
        center = values.pop("cranium_center")
        edge = values.pop("cranium_edge")
        radius = math.dist(center, edge)
        if radius <= 0:
            raise ValueError("cranial center and edge must be distinct")
        return {"cranium_center": center, "cranium_radius": radius} | values
