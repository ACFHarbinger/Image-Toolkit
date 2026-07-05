from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QLabel


class _TagLabel(QLabel):
    """A small interactive label for individual tags that supports clicking to jump and right-click to edit/delete."""

    clicked = Signal(int)  # position_ms
    double_clicked = Signal(int)  # position_ms
    right_clicked = Signal(QPoint, int)  # global_pos, index

    def __init__(self, text, ms, index, parent=None):
        super().__init__(text, parent)
        self.ms = ms
        self.index = index
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "color: #FFC107; font-weight: bold; padding: 2px 6px; "
            "border: 1px solid #4f545c; border-radius: 4px; background-color: #1e1f22;"
        )
        self.setToolTip(f"Jump to {text}\nRight-click to edit/delete")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.ms)
        elif event.button() == Qt.MouseButton.RightButton:
            self.right_clicked.emit(event.globalPos(), self.index)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.ms)
        super().mouseDoubleClickEvent(event)
