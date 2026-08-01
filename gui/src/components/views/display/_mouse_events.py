"""Click/double-click/drag-start mouse event handling.

Extracted from ``monitor_drop_view.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import QApplication


class _MouseEventsMixin:
    """Single/double click reporting and outgoing drag (monitor-swap) initiation."""

    def _handle_single_click(self):
        self.clicked.emit(self.monitor_id)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.monitor_id)
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.pos()
            self.clicked.emit(self.monitor_id)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if not self.drag_start_position:
            return
        if (
            event.pos() - self.drag_start_position
        ).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.monitor_id)
        drag.setMimeData(mime_data)

        pixmap = self.grab()
        drag.setPixmap(pixmap.scaledToWidth(200, Qt.TransformationMode.SmoothTransformation))
        drag.setHotSpot(event.pos())
        drag.exec(Qt.DropAction.MoveAction)


__all__ = ["_MouseEventsMixin"]
