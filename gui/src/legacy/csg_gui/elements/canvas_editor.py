"""Layered HITL canvas editor for cel_shaded_generator colorization (roadmap §5.1, issue #190).

Three layers, bottom to top:
  1. Generated/solved color (plain pixmap item)
  2. Line art (``Multiply`` composition mode -- absolute white leaves the
     color layer unchanged, absolute black stays black, so anti-aliased ink
     lines always stay crisp above whatever color sits underneath -- see
     ``research/Manga Colorization and Animation Research.md`` §9.2)
  3. Scribble overlay (normal blending, semi-transparent, drawn live as the
     user paints -- this is also the source of the scribble mask/colors fed
     to the colorization solver)

New feature, not code motion.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView


class _MultiplyPixmapItem(QGraphicsPixmapItem):
    """A QGraphicsPixmapItem painted with CompositionMode_Multiply so it
    darkens (never replaces) whatever is drawn beneath it."""

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: D102
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
        super().paint(painter, option, widget)
        painter.restore()


def qimage_to_rgb_array(image: QImage) -> np.ndarray:
    """Convert a QImage to an HxWx3 uint8 RGB numpy array."""
    img = image.convertToFormat(QImage.Format.Format_RGB888)
    w, h = img.width(), img.height()
    ptr = img.constBits()
    buf = bytes(ptr)[: h * img.bytesPerLine()]
    arr = np.frombuffer(buf, dtype=np.uint8).reshape(h, img.bytesPerLine())[:, : w * 3]
    return arr.reshape(h, w, 3).copy()


def qimage_alpha_to_mask(image: QImage) -> np.ndarray:
    """Convert a QImage's alpha channel to an HxW bool mask (True = opaque)."""
    img = image.convertToFormat(QImage.Format.Format_ARGB32)
    w, h = img.width(), img.height()
    ptr = img.constBits()
    buf = bytes(ptr)[: h * img.bytesPerLine()]
    arr = np.frombuffer(buf, dtype=np.uint8).reshape(h, img.bytesPerLine())[:, : w * 4]
    arr = arr.reshape(h, w, 4)
    return arr[:, :, 3] > 0  # alpha channel


def rgb_array_to_qpixmap(arr: np.ndarray) -> QPixmap:
    arr = np.ascontiguousarray(arr)
    h, w = arr.shape[:2]
    img = QImage(arr.data, w, h, arr.strides[0], QImage.Format.Format_RGB888)
    return QPixmap.fromImage(img.copy())


class MangaCanvasEditor(QGraphicsView):
    """Interactive scribble canvas: load line art, paint colored scribbles,
    display a solved colorization result."""

    scribble_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

        self._color_item = QGraphicsPixmapItem()
        self._line_art_item = _MultiplyPixmapItem()
        self._scribble_item = QGraphicsPixmapItem()
        self._scribble_item.setOpacity(0.6)
        for item in (self._color_item, self._line_art_item, self._scribble_item):
            self._scene.addItem(item)

        self._line_art_qimage: QImage | None = None
        self._scribble_qimage: QImage | None = None
        self._image_size: tuple[int, int] = (0, 0)

        self._pen_color = QColor(220, 40, 40)
        self._pen_width = 12
        self._painting = False
        self._last_point: QPointF | None = None

        # Pixel-space bounding box of the stroke currently being painted
        # (accumulated across mousePressEvent/mouseMoveEvent, finalized on
        # mouseReleaseEvent) -- issue #191's quadtree-incremental-resolve
        # consumer needs this to know which region actually changed.
        self._stroke_bbox: tuple[int, int, int, int] | None = None
        self._last_stroke_bbox: tuple[int, int, int, int] | None = None

    # ------------------------------------------------------------------
    # Loading / clearing
    # ------------------------------------------------------------------
    def set_line_art(self, image: QImage) -> None:
        """Load a new grayscale/line-art image, resetting scribbles and any
        previous colorization result."""
        self._line_art_qimage = image
        w, h = image.width(), image.height()
        self._image_size = (w, h)

        self._line_art_item.setPixmap(QPixmap.fromImage(image))
        self._line_art_item.setPos(0, 0)

        self._scribble_qimage = QImage(w, h, QImage.Format.Format_ARGB32)
        self._scribble_qimage.fill(Qt.GlobalColor.transparent)
        self._scribble_item.setPixmap(QPixmap.fromImage(self._scribble_qimage))
        self._scribble_item.setPos(0, 0)

        self._color_item.setPixmap(QPixmap())
        self._color_item.setPos(0, 0)

        self._stroke_bbox = None
        self._last_stroke_bbox = None

        self._scene.setSceneRect(QRectF(0, 0, w, h))
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def clear_scribbles(self) -> None:
        if self._scribble_qimage is None:
            return
        self._scribble_qimage.fill(Qt.GlobalColor.transparent)
        self._scribble_item.setPixmap(QPixmap.fromImage(self._scribble_qimage))
        self._last_stroke_bbox = None
        self.scribble_changed.emit()

    def set_result(self, rgb_array: np.ndarray) -> None:
        """Display a solved colorization result in the color layer."""
        self._color_item.setPixmap(rgb_array_to_qpixmap(rgb_array))

    def get_result_pixmap(self) -> QPixmap:
        """The currently-displayed colorization result (null if none yet)."""
        return self._color_item.pixmap()

    # ------------------------------------------------------------------
    # Pen configuration
    # ------------------------------------------------------------------
    def set_pen_color(self, color: QColor) -> None:
        self._pen_color = color

    def pen_color(self) -> QColor:
        return self._pen_color

    def set_pen_width(self, width: int) -> None:
        self._pen_width = max(1, width)

    # ------------------------------------------------------------------
    # Scribble data extraction (for the colorization solver)
    # ------------------------------------------------------------------
    def has_line_art(self) -> bool:
        return self._line_art_qimage is not None and not self._line_art_qimage.isNull()

    def has_scribbles(self) -> bool:
        return self._scribble_qimage is not None and bool(self.get_scribble_mask().any())

    def get_line_art_gray(self) -> np.ndarray:
        """HxW uint8 grayscale array of the loaded line art."""
        if self._line_art_qimage is None:
            raise RuntimeError("No line art loaded")
        rgb = qimage_to_rgb_array(self._line_art_qimage)
        # BT.601 luma weights (RGB order) -- same standard weighting as
        # LUMINANCE_WEIGHTS in backend/src/constants (BGR order there).
        return (rgb.astype(np.float64) @ [0.299, 0.587, 0.114]).astype(np.uint8)

    def get_scribble_rgb(self) -> np.ndarray:
        if self._scribble_qimage is None:
            raise RuntimeError("No line art loaded")
        return qimage_to_rgb_array(self._scribble_qimage)

    def get_scribble_mask(self) -> np.ndarray:
        if self._scribble_qimage is None:
            raise RuntimeError("No line art loaded")
        return qimage_alpha_to_mask(self._scribble_qimage)

    # ------------------------------------------------------------------
    # Mouse painting
    # ------------------------------------------------------------------
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.has_line_art():
            self._painting = True
            self._last_point = self.mapToScene(event.pos())
            self._stroke_bbox = None
            self._accumulate_stroke_bbox(self._last_point)
            self._paint_dot(self._last_point)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._painting and self._last_point is not None:
            point = self.mapToScene(event.pos())
            self._accumulate_stroke_bbox(point)
            self._paint_line(self._last_point, point)
            self._last_point = point
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._painting:
            self._painting = False
            self._last_point = None
            self._last_stroke_bbox = self._stroke_bbox
            self._stroke_bbox = None
            self.scribble_changed.emit()
        else:
            super().mouseReleaseEvent(event)

    def _accumulate_stroke_bbox(self, point: QPointF) -> None:
        """Expand the in-progress stroke's pixel-space bounding box to
        include ``point``, padded by half the pen width (a stroke's visible
        extent reaches beyond its path centerline) and clipped to the
        canvas bounds."""
        w, h = self._image_size
        if w == 0 or h == 0:
            return
        radius = self._pen_width / 2
        x0 = max(0, int(point.x() - radius))
        y0 = max(0, int(point.y() - radius))
        x1 = min(w, int(point.x() + radius) + 1)
        y1 = min(h, int(point.y() + radius) + 1)

        if self._stroke_bbox is None:
            self._stroke_bbox = (y0, x0, y1, x1)
        else:
            sy0, sx0, sy1, sx1 = self._stroke_bbox
            self._stroke_bbox = (min(sy0, y0), min(sx0, x0), max(sy1, y1), max(sx1, x1))

    def get_last_stroke_bbox(self) -> tuple[int, int, int, int] | None:
        """The completed stroke's ``(y0, x0, y1, x1)`` pixel-space bounding
        box, or ``None`` if no stroke has finished yet (e.g. right after
        loading a fresh image, or after :meth:`clear_scribbles`)."""
        return self._last_stroke_bbox

    def _paint_dot(self, point: QPointF) -> None:
        self._paint_line(point, point)

    def _paint_line(self, p1: QPointF, p2: QPointF) -> None:
        if self._scribble_qimage is None:
            return
        painter = QPainter(self._scribble_qimage)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if p1 == p2:
            # QPainter.drawLine() renders nothing for a zero-length line --
            # even with a RoundCap pen, there's no length to cap along --
            # so a single click (mousePress with no subsequent move) would
            # silently paint nothing. Draw a filled circle instead.
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._pen_color)
            radius = self._pen_width / 2
            painter.drawEllipse(p1, radius, radius)
        else:
            pen = QPen(self._pen_color, self._pen_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(p1, p2)
        painter.end()
        self._scribble_item.setPixmap(QPixmap.fromImage(self._scribble_qimage))


__all__ = [
    "MangaCanvasEditor",
    "qimage_to_rgb_array",
    "qimage_alpha_to_mask",
    "rgb_array_to_qpixmap",
]
