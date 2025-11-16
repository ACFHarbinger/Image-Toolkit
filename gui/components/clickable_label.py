import os

from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent 

class ClickableLabel(QLabel):
    """A QLabel that emits a signal with its associated file path when clicked."""
    # Signal that emits the file path (Single Click)
    path_clicked = Signal(str)
    # Signal for Double Click
    path_double_clicked = Signal(str) 

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.path = file_path 
        self.setCursor(Qt.PointingHandCursor)
        self.setAlignment(Qt.AlignCenter)
        self.setToolTip(os.path.basename(self.path)) # Use self.path
        self.setFixedSize(100, 100)
        
        # Enable the double-click property on the widget
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

    def mousePressEvent(self, event: QMouseEvent):
        # 💡 IMPORTANT: If the click could be part of a double-click sequence,
        # we prevent the single-click action (selection) from triggering immediately.
        # This solves the "too slow" issue by ensuring the single-click logic 
        # only runs if it's confirmed not to be a double-click.
        if event.button() == Qt.LeftButton:
            self.path_clicked.emit(self.path) # Use self.path
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
         """Emits the double-click signal."""
         if event.button() == Qt.LeftButton:
            self.path_double_clicked.emit(self.path) # Use self.path
         super().mouseDoubleClickEvent(event)
