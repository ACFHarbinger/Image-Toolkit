"""Pixel Value Mode's foreground painting for ``ImagePanel``.

This is the feature that was a complete no-op before the rebuild (issue #123
defect 1): ``set_display_mode()`` stored a string that nothing ever read, and
``PIXEL_GRID_ZOOM_THRESHOLD`` was imported and unused.

Free functions over the panel rather than methods on it, so ``image_panel.py``
stays within the repo's 500-LoC file budget (§5.17 / issues #121-#122) and the
painting logic — the part with the subtle coordinate-space rules below — can be
read on its own.

Two rules that are easy to get wrong here:

- **Labels are drawn in device coordinates, with the world transform reset.**
  Sizing a font in *scene* units means its device size gets multiplied by the
  view scale, and past ~30x native that asks FreeType for enormous glyphs, which
  fails outright (``render glyph failed err=62``) and takes the process down.
  That was a real crash, found by the offscreen tests.
- **Both thresholds are in native scale, not zoom factor.** Zoom is relative to
  the fitted view, so the same zoom factor is a wildly different pixel size on a
  1703x1704 panorama than on a 300px crop.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from ..constants.user_interface import (
    COL_POINT,
    DISPLAY_PIXEL,
    PIXEL_GRID_ZOOM_THRESHOLD,
    PIXEL_TEXT_MAX_CELLS,
    PIXEL_TEXT_ZOOM_THRESHOLD,
)

# Luma above which a cell is light enough to need dark text.
_DARK_TEXT_LUMA = 140


def draw(panel, painter: QPainter, rect: QRectF) -> None:
    """Paint the pinned-probe marker and, in Pixel Value Mode, the pixel grid."""
    if panel._pinned is not None:
        draw_pin(panel, painter)
    if panel._display_mode != DISPLAY_PIXEL or panel._image_bgr is None:
        return
    scale = panel.native_scale()
    if scale < PIXEL_GRID_ZOOM_THRESHOLD:
        return

    bounds = _visible_cells(panel, rect)
    if bounds is None:
        return
    x0, y0, x1, y1 = bounds

    painter.save()
    painter.setPen(QPen(QColor(255, 255, 255, 45), 0))
    for x in range(x0, x1 + 1):
        painter.drawLine(QPointF(x, y0), QPointF(x, y1))
    for y in range(y0, y1 + 1):
        painter.drawLine(QPointF(x0, y), QPointF(x1, y))

    cells = (x1 - x0) * (y1 - y0)
    if scale >= PIXEL_TEXT_ZOOM_THRESHOLD and cells <= PIXEL_TEXT_MAX_CELLS:
        draw_pixel_values(panel, painter, x0, y0, x1, y1, scale)
    painter.restore()


def _visible_cells(panel, rect: QRectF):
    """The exposed rect clipped to the image, as integer pixel bounds."""
    h, w = panel._image_bgr.shape[:2]
    x0 = max(0, int(np.floor(rect.left())))
    y0 = max(0, int(np.floor(rect.top())))
    x1 = min(w, int(np.ceil(rect.right())) + 1)
    y1 = min(h, int(np.ceil(rect.bottom())) + 1)
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


def draw_pixel_values(panel, painter: QPainter, x0: int, y0: int, x1: int, y1: int, scale: float) -> None:
    """Draw each visible pixel's RGB triple inside its grid cell.

    Device coordinates, world transform reset — see the module docstring for why
    a scene-space font is a crash rather than a cosmetic problem.
    """
    painter.save()
    painter.resetTransform()
    font = QFont("monospace")
    # Three stacked lines have to fit in a cell `scale` device px tall.
    font.setPixelSize(max(5, min(28, int(scale / 4.5))))
    painter.setFont(font)
    region = panel._image_bgr[y0:y1, x0:x1]
    luma = region[..., 0] * 0.114 + region[..., 1] * 0.587 + region[..., 2] * 0.299
    for j in range(y1 - y0):
        for i in range(x1 - x0):
            b, g, r = (int(v) for v in region[j, i])
            top_left = panel.mapFromScene(QPointF(x0 + i, y0 + j))
            bottom_right = panel.mapFromScene(QPointF(x0 + i + 1, y0 + j + 1))
            # Flip the label against the cell's own brightness so the text stays
            # readable over both flat white and flat black cels.
            painter.setPen(QColor(0, 0, 0) if luma[j, i] > _DARK_TEXT_LUMA else QColor(255, 255, 255))
            painter.drawText(
                QRectF(top_left, bottom_right),
                Qt.AlignmentFlag.AlignCenter,
                f"{r}\n{g}\n{b}",
            )
    painter.restore()


def draw_pin(panel, painter: QPainter) -> None:
    """Crosshair on the pinned probe pixel, sized in scene units so its arms
    stay a constant on-screen length as the zoom changes."""
    x, y = panel._pinned
    painter.save()
    painter.setPen(QPen(QColor(COL_POINT), 0))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(QRectF(x, y, 1, 1))
    span = 6.0 / max(panel.native_scale(), 1e-6)
    cx, cy = x + 0.5, y + 0.5
    painter.drawLine(QPointF(cx - span, cy), QPointF(cx - 1, cy))
    painter.drawLine(QPointF(cx + 1, cy), QPointF(cx + span, cy))
    painter.drawLine(QPointF(cx, cy - span), QPointF(cx, cy - 1))
    painter.drawLine(QPointF(cx, cy + 1), QPointF(cx, cy + span))
    painter.restore()
