"""Render normalized review redlines into a separate Krita 5.x paint layer."""

from __future__ import annotations

FEEDBACK_GROUP_NAME = "Tutor Feedback (locked)"
REDLINE_LAYER_PREFIX = "Tutor Redlines — "
PREVIEW_LAYER_PREFIX = "Tutor Preview — "
ACCEPTED_LAYER_PREFIX = "Tutor Accepted — "
REDLINE_BGRA = (123, 79, 255, 220)


def map_review_redlines_to_sheet(review, cell_index, cell_count=5):
    """Map selected-head local coordinates into one landscape-sheet cell."""
    if not isinstance(cell_index, int) or not 0 <= cell_index < cell_count:
        raise ValueError("orientation sheet cell is invalid")
    mapped = dict(review)
    mapped["redlines"] = []
    for redline in review.get("redlines", []):
        item = dict(redline)
        item["geometry"] = [
            [(cell_index + point[0]) / cell_count, point[1]]
            for point in redline.get("geometry", [])
        ]
        mapped["redlines"].append(item)
    return mapped


def render_review_redlines(document, review):
    """Add one tutor-owned raster layer; never write to an artist layer."""
    width = document.width()
    height = document.height()
    if width <= 0 or height <= 0:
        raise ValueError("active document has invalid dimensions")
    redlines = review.get("redlines")
    if not isinstance(redlines, list):
        raise ValueError("review redlines are missing")
    if not redlines:
        return None
    pixels = rasterize_redlines(width, height, redlines)
    group = document.nodeByName(FEEDBACK_GROUP_NAME)
    if group is None:
        raise RuntimeError("exercise is missing its Tutor Feedback group")
    is_preview = bool(review.get("suggestions"))
    prefix = PREVIEW_LAYER_PREFIX if is_preview else REDLINE_LAYER_PREFIX
    layer = document.createNode(prefix + review["id"][:8], "paintlayer")
    if layer is None:
        raise RuntimeError("Krita could not create the tutor redline layer")
    from PyQt5.QtCore import QByteArray

    group.setLocked(False)
    try:
        if not group.addChildNode(layer, None):
            raise RuntimeError("Krita could not attach the tutor redline layer")
        if not layer.setPixelData(QByteArray(pixels), 0, 0, width, height):
            group.removeChildNode(layer)
            raise RuntimeError("Krita could not write tutor redline pixels")
        layer.setLocked(True)
    finally:
        group.setLocked(True)
    document.refreshProjection()
    return layer


def accept_preview(layer):
    """Retain one owned preview as accepted feedback; repeated calls are harmless."""
    name = layer.name()
    if name.startswith(ACCEPTED_LAYER_PREFIX):
        return False
    if not name.startswith(PREVIEW_LAYER_PREFIX):
        raise ValueError("refusing to accept a layer not owned as a tutor preview")
    layer.setName(ACCEPTED_LAYER_PREFIX + name[len(PREVIEW_LAYER_PREFIX) :])
    layer.setLocked(True)
    return True


def reject_preview(layer):
    """Remove only an owned pending preview; repeated calls are harmless."""
    if layer is None:
        return False
    if not layer.name().startswith(PREVIEW_LAYER_PREFIX):
        raise ValueError("refusing to reject a layer not owned as a tutor preview")
    if not layer.remove():
        raise RuntimeError("Krita could not remove the tutor preview")
    return True


def rasterize_redlines(width, height, redlines):
    """Return transparent U8 RGBA/BGRA bytes with bounded line geometry."""
    if width <= 0 or height <= 0 or width * height > 100_000_000:
        raise ValueError("redline canvas dimensions are invalid or too large")
    pixels = bytearray(width * height * 4)
    for redline in redlines:
        geometry = redline.get("geometry") if isinstance(redline, dict) else None
        if not isinstance(geometry, list) or len(geometry) < 2:
            raise ValueError("redline geometry needs at least two points")
        points = [_pixel_point(point, width, height) for point in geometry]
        for start, end in zip(points, points[1:], strict=False):
            _draw_line(pixels, width, height, start, end)
    return bytes(pixels)


def _pixel_point(point, width, height):
    if (
        not isinstance(point, (list, tuple))
        or len(point) != 2
        or any(not isinstance(value, (int, float)) or not 0 <= value <= 1 for value in point)
    ):
        raise ValueError("redline points must use normalized coordinates")
    return round(point[0] * (width - 1)), round(point[1] * (height - 1))


def _draw_line(pixels, width, height, start, end):
    x0, y0 = start
    x1, y1 = end
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    error = dx + dy
    while True:
        _draw_dot(pixels, width, height, x0, y0)
        if x0 == x1 and y0 == y1:
            break
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x0 += sx
        if doubled <= dx:
            error += dx
            y0 += sy


def _draw_dot(pixels, width, height, x, y):
    for py in range(max(0, y - 2), min(height, y + 3)):
        for px in range(max(0, x - 2), min(width, x + 3)):
            offset = (py * width + px) * 4
            pixels[offset : offset + 4] = bytes(REDLINE_BGRA)
