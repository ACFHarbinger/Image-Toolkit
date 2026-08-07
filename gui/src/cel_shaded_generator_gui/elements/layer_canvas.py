"""Zoomable/pannable canvas that renders an ``editor.LayerStack``'s
composite (standalone-editor first slice; see
``docs/moon/roadmaps/engine_architecture.md``'s gate-5 exception).

Read-only display for this slice -- no paint tools yet. The layer list panel
(``layer_list_panel.py``) is what mutates the bound ``LayerStack``; this
widget's only job is turning its current composite into a pixmap and
supporting mouse-wheel zoom / hand-drag pan, matching the roadmap's "canvas +
layer stack foundation" scope.

New feature, not code motion.
"""

from __future__ import annotations

import numpy as np
from editor import LayerStack
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

_MIN_SCALE = 0.05
_MAX_SCALE = 40.0


def rgba_array_to_qpixmap(arr: np.ndarray) -> QPixmap:
    arr = np.ascontiguousarray(arr)
    h, w = arr.shape[:2]
    image = QImage(arr.data, w, h, arr.strides[0], QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(image.copy())


class LayerCanvas(QGraphicsView):
    """Displays a ``LayerStack``'s live composite; zoom with the wheel, pan
    by dragging."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)
        self._layer_stack: LayerStack | None = None
        self._scale = 1.0

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
