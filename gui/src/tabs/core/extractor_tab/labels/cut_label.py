from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QLabel

from .....theming.theme_api import qss


class _CutLabel(QLabel):
    """A small interactive label for individual cuts that supports right-click."""

    right_clicked = Signal(QPoint, int)  # global_pos, index

    def __init__(self, text, index, parent=None):
        super().__init__(text, parent)
        self.index = index
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(qss("extractor_cut_label"))
        self.setToolTip("Right-click to delete this cut")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.right_clicked.emit(event.globalPos(), self.index)
        super().mousePressEvent(event)
