import os

from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import Qt, Signal, QPoint


class ClickableLabel(QLabel):
    """A QLabel that emits a signal with its associated file path when clicked."""

    path_clicked = Signal(str)
    path_double_clicked = Signal(str)
    path_right_clicked = Signal(QPoint, str)

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.path = file_path
        self.setCursor(Qt.PointingHandCursor)
        self.setAlignment(Qt.AlignCenter)
        self.setToolTip(os.path.basename(self.path))
        self.setFixedSize(100, 100)

        # --- FIX: Set initial style with dark background for opacity ---
        self.setStyleSheet(
            "background-color: #2c2f33; border: 1px dashed #4f545c; color: #b9bbbe;"
        )

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.setMouseTracking(True)
        # Ensure the widget declares itself fully opaque for painting stability
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

        self.customContextMenuRequested.connect(self._emit_right_click_signal)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.path_clicked.emit(self.path)

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.path_double_clicked.emit(self.path)
        super().mouseDoubleClickEvent(event)

    def _emit_right_click_signal(self, pos: QPoint):
        """
        Internal slot to emit the custom path_right_clicked signal
        when the native customContextMenuRequested signal fires.
        """
        self.path_right_clicked.emit(self.mapToGlobal(pos), self.path)
