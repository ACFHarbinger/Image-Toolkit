"""Reusable image/video canvas viewport for embedded and standalone HIE."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView


class HieViewport(QGraphicsView):
    """Minimal hardware-friendly canvas with a clear empty-document state."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._scene.setBackgroundBrush(QBrush(QColor("#10151b")))
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setMinimumSize(420, 300)

    def show_status(self, message: str) -> None:
        self.scene().clear()
        text = self.scene().addText(message)
        text.setDefaultTextColor(QColor("#8ed8df"))
        text.setPos(24, 24)

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt API
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)
