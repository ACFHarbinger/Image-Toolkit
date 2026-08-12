"""Reusable image/video canvas viewport for embedded and standalone HIE."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPixmap
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
        self._pixmap_item = None

    def show_status(self, message: str) -> None:
        """Clear the canvas and center a status message — the empty-document state."""
        self._pixmap_item = None
        self.scene().clear()
        text = self.scene().addText(message)
        text.setDefaultTextColor(QColor("#8ed8df"))
        rect = text.boundingRect()
        text.setPos(-rect.width() / 2, -rect.height() / 2)
        self.setSceneRect(-960, -540, 1920, 1080)
        self.resetTransform()
        self.centerOn(0, 0)

    def load_image(self, path: str) -> bool:
        """Load `path` as a pixmap and fit it to the viewport. Returns success."""
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.show_status(f"Could not load image: {path}")
            return False

        self.scene().clear()
        self.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        self._pixmap_item = self.scene().addPixmap(pixmap)
        self.resetTransform()
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        return True

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt API
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)
