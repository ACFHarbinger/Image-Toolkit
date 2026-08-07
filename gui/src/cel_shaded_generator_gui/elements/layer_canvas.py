"""Zoomable/pannable canvas that renders an ``editor.LayerStack``'s
composite, with a brush paint tool (standalone-editor paint-tools slice;
see ``docs/moon/roadmaps/engine_architecture.md``'s gate-5 exception).

The layer list panel (``layer_list_panel.py``) still owns add/remove/
reorder/visibility; this widget owns turning the composite into a pixmap,
mouse-wheel zoom / hand-drag pan, and now painting onto whichever layer is
the bound "active" one, via ``editor.brush``'s pure-numpy stamping. Pan and
Brush are separate explicit tools (``set_tool``) rather than overloading
left-click, since ``QGraphicsView.DragMode.ScrollHandDrag`` already claims
left-click-drag for panning. If bound with ``set_history``, records one
undo checkpoint per stroke, at the moment the mouse is pressed -- not per
dot -- so a whole stroke undoes as a single step.

New feature, not code motion.
"""

from __future__ import annotations

import numpy as np
from editor import EditHistory, LayerStack, stamp_dot, stamp_line
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

_MIN_SCALE = 0.05
_MAX_SCALE = 40.0
_DEFAULT_BRUSH_COLOR = (0, 0, 0, 255)
_DEFAULT_BRUSH_RADIUS = 4


def rgba_array_to_qpixmap(arr: np.ndarray) -> QPixmap:
    arr = np.ascontiguousarray(arr)
    h, w = arr.shape[:2]
    image = QImage(arr.data, w, h, arr.strides[0], QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(image.copy())


class LayerCanvas(QGraphicsView):
    """Displays a ``LayerStack``'s live composite; zoom with the wheel, pan
    or paint depending on the active tool."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)
        self._layer_stack: LayerStack | None = None
        self._scale = 1.0
        self._tool = "pan"
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._active_layer_id: str | None = None
        self._brush_color = _DEFAULT_BRUSH_COLOR
        self._brush_radius = _DEFAULT_BRUSH_RADIUS
        self._painting = False
        self._last_point: tuple[int, int] | None = None
        self._history: EditHistory | None = None

    def set_layer_stack(self, layer_stack: LayerStack | None) -> None:
        self._layer_stack = layer_stack
        self._scale = 1.0
        self.resetTransform()
        self.refresh()
        if layer_stack is not None:
            self._scene.setSceneRect(0, 0, layer_stack.width, layer_stack.height)
            self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def layer_stack(self) -> LayerStack | None:
        return self._layer_stack

    def refresh(self) -> None:
        """Re-render the bound layer stack's current composite."""
        if self._layer_stack is None:
            self._pixmap_item.setPixmap(QPixmap())
            return
        self._pixmap_item.setPixmap(rgba_array_to_qpixmap(self._layer_stack.composite()))
        self._pixmap_item.setPos(0, 0)

    def current_scale(self) -> float:
        return self._scale

    # ------------------------------------------------------------------
    # Tool / paint configuration
    # ------------------------------------------------------------------
    def set_tool(self, tool: str) -> None:
        if tool not in ("pan", "brush"):
            raise ValueError(f"unsupported tool: {tool}")
        self._tool = tool
        self.setDragMode(
            QGraphicsView.DragMode.ScrollHandDrag
            if tool == "pan"
            else QGraphicsView.DragMode.NoDrag
        )

    def tool(self) -> str:
        return self._tool

    def set_active_layer_id(self, layer_id: str | None) -> None:
        self._active_layer_id = layer_id

    def active_layer_id(self) -> str | None:
        return self._active_layer_id

    def set_brush_color(self, color: tuple[int, int, int, int]) -> None:
        self._brush_color = color

    def brush_color(self) -> tuple[int, int, int, int]:
        return self._brush_color

    def set_brush_radius(self, radius: int) -> None:
        self._brush_radius = max(0, radius)

    def brush_radius(self) -> int:
        return self._brush_radius

    def set_history(self, history: EditHistory | None) -> None:
        self._history = history

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------
    def _active_layer_pixels(self) -> np.ndarray | None:
        if self._layer_stack is None or self._active_layer_id is None:
            return None
        layer = self._layer_stack.layer(self._active_layer_id)
        return None if layer is None else layer.pixels

    def _paint_dot_at_pixel(self, x: int, y: int) -> None:
        pixels = self._active_layer_pixels()
        if pixels is None:
            return
        stamp_dot(pixels, x, y, self._brush_radius, self._brush_color)
        self.refresh()

    def _paint_line_at_pixel(self, x0: int, y0: int, x1: int, y1: int) -> None:
        pixels = self._active_layer_pixels()
        if pixels is None:
            return
        stamp_line(pixels, x0, y0, x1, y1, self._brush_radius, self._brush_color)
        self.refresh()

    def _scene_point_to_pixel(self, event) -> tuple[int, int]:
        point = self.mapToScene(event.pos())
        return int(round(point.x())), int(round(point.y()))

    def mousePressEvent(self, event) -> None:
        if self._tool == "brush" and event.button() == Qt.MouseButton.LeftButton:
            if self._history is not None and self._active_layer_pixels() is not None:
                self._history.record()
            self._painting = True
            self._last_point = self._scene_point_to_pixel(event)
            self._paint_dot_at_pixel(*self._last_point)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._tool == "brush" and self._painting and self._last_point is not None:
            point = self._scene_point_to_pixel(event)
            self._paint_line_at_pixel(*self._last_point, *point)
            self._last_point = point
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._tool == "brush" and event.button() == Qt.MouseButton.LeftButton:
            self._painting = False
            self._last_point = None
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        if self._layer_stack is None:
            return
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        new_scale = self._scale * factor
        if not _MIN_SCALE <= new_scale <= _MAX_SCALE:
            return
        self._scale = new_scale
        self.scale(factor, factor)


__all__ = ["LayerCanvas", "rgba_array_to_qpixmap"]
