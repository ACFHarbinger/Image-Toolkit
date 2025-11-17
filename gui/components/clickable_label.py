import os

from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QMouseEvent 
from PySide6.QtCore import Qt, Signal, QPoint


class ClickableLabel(QLabel):
    """A QLabel that emits a signal with its associated file path when clicked."""
    # Signal that emits the file path (Single Click)
    path_clicked = Signal(str)
    # Signal for Double Click
    path_double_clicked = Signal(str) 
    # NEW: Signal for Right Click
    path_right_clicked = Signal(QPoint, str) 

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.path = file_path 
        self.setCursor(Qt.PointingHandCursor)
        self.setAlignment(Qt.AlignCenter)
        self.setToolTip(os.path.basename(self.path)) # Use self.path
        self.setFixedSize(100, 100)
        
        # Set context menu policy to CustomContextMenu, allowing the parent 
        # to intercept the event via the customContextMenuRequested signal.
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu) 
        
        # Enable the double-click property on the widget
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        
        # NEW: Connect the standard Qt signal to our custom right-click signal
        self.customContextMenuRequested.connect(self._emit_right_click_signal)

    def mousePressEvent(self, event: QMouseEvent):
        # Only emit path_clicked for the left button.
        if event.button() == Qt.LeftButton:
            self.path_clicked.emit(self.path) 
        
        # We allow other buttons (like right button) to propagate for contextMenuEvent
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
         """Emits the double-click signal."""
         if event.button() == Qt.LeftButton:
            self.path_double_clicked.emit(self.path)
         super().mouseDoubleClickEvent(event)

    def _emit_right_click_signal(self, pos: QPoint):
        """
        Internal slot to emit the custom path_right_clicked signal 
        when the native customContextMenuRequested signal fires.
        """
        # Emits the global position and the file path
        self.path_right_clicked.emit(self.mapToGlobal(pos), self.path)
