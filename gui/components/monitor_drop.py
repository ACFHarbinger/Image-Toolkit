import os

from typing import Optional
from screeninfo import Monitor
from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import (
    QPixmap, QDragEnterEvent, QDropEvent, QDragMoveEvent, QDragLeaveEvent,
    QMouseEvent
)
from PySide6.QtWidgets import QLabel, QMenu
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS


class MonitorDropWidget(QLabel):
    """
    A custom QLabel that acts as a drop target for images,
    displays monitor info, and shows a preview of the dropped image.
    When no image is set, it displays a simplified placeholder.
    """
    # Emits (monitor_id, image_path) when an image is successfully dropped
    image_dropped = Signal(str, str) 
    
    # Emits monitor_id when the widget is double-clicked
    double_clicked = Signal(str)

    # NEW SIGNAL: Emits monitor_id when the 'Clear Monitor' right-click action is selected
    clear_requested_id = Signal(str)

    def __init__(self, monitor: Monitor, monitor_id: str):
        super().__init__()
        self.monitor = monitor
        self.monitor_id = monitor_id
        self.image_path: Optional[str] = None
        
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(220, 160)
        self.setWordWrap(True)
        
        # Try to set a reasonable aspect ratio, but allow stretch
        self.setFixedHeight(160)
        
        self.update_text()
        self.setStyleSheet("""
            QLabel {
                background-color: #36393f;
                border: 2px dashed #4f545c;
                border-radius: 8px;
                color: #b9bbbe;
                font-size: 14px;
            }
            QLabel[dragging="true"] {
                border: 2px solid #5865f2; /* Highlight on drag over */
                background-color: #40444b;
            }
        """)

    # NEW METHOD: Handles the right-click event to show a context menu
    def contextMenuEvent(self, event):
        """Creates and executes a context menu on right-click."""
        menu = QMenu(self)
        
        # Action to clear the monitor
        clear_action = menu.addAction("Clear All Images (Current and Queue)")
        clear_action.triggered.connect(lambda: self.clear_requested_id.emit(self.monitor_id))
        
        # We enable it anytime to allow clearing empty queues as well.
        
        menu.exec(event.globalPos())

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Overrides the double-click event to emit the custom signal."""
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self.monitor_id)
        super().mouseDoubleClickEvent(event)

    def update_text(self):
        """
        Sets the default placeholder text, removing the monitor dimensions
        to prioritize the current background image display via set_image().
        """
        monitor_name = f"Monitor {self.monitor_id}"
        if self.monitor.name:
             monitor_name = f"{monitor_name} ({self.monitor.name})"
        
        # MODIFICATION: Removed the line that displayed monitor dimensions (width x height)
        self.setText(f"<b>{monitor_name}</b>\n\n"
                     "Drag and Drop Image Here")

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Event when a dragged item enters the widget."""
        if self.has_valid_image_url(event.mimeData()):
            event.acceptProposedAction()
            self.setProperty("dragging", True)
            self.style().polish(self)
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        """Event when a dragged item moves over the widget."""
        if self.has_valid_image_url(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent):
        """Event when a dragged item leaves the widget."""
        self.setProperty("dragging", False)
        self.style().polish(self)

    def dropEvent(self, event: QDropEvent):
        """Event when an item is dropped on the widget."""
        self.setProperty("dragging", False)
        self.style().polish(self)
        
        if self.has_valid_image_url(event.mimeData()):
            url = event.mimeData().urls()[0]
            file_path = url.toLocalFile()
            
            if os.path.isfile(file_path):
                # wallpaper_tab.py's on_image_dropped handles queue logic
                self.image_dropped.emit(self.monitor_id, file_path)
                event.acceptProposedAction()
                return
        
        event.ignore()

    def has_valid_image_url(self, mime_data: QMimeData) -> bool:
        """Checks if the MimeData contains a single, valid, local image file."""
        if not mime_data.hasUrls():
            return False
        if len(mime_data.urls()) > 1:
            pass # We only care about the first one in this context
        
        url = mime_data.urls()[0]
        if not url.isLocalFile():
            return False
            
        file_path = url.toLocalFile().lower()
        if not any(file_path.endswith(fmt) for fmt in SUPPORTED_IMG_FORMATS):
            return False
            
        return True

    def set_image(self, file_path: Optional[str]):
        """Sets the widget's pixmap to a scaled preview of the image."""
        self.image_path = file_path
        if file_path:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.setPixmap(scaled_pixmap)
                self.setText("") # Clear text when image is shown
            else:
                self.image_path = None
                self.update_text()
                # Use simplified error text since dimensions are removed from update_text
                monitor_name = f"Monitor {self.monitor_id}"
                if self.monitor.name:
                     monitor_name = f"{monitor_name} ({self.monitor.name})"
                
                self.setText(f"<b>{monitor_name}</b>\n\n"
                             "<b>Error:</b> Could not load image.")
        else:
             self.clear() # Call the internal clear for consistency
             
    def clear(self):
        """Clears the displayed image and resets to placeholder text."""
        self.image_path = None
        self.setPixmap(QPixmap()) # Clear the pixmap
        self.update_text()
                         
    def resizeEvent(self, event):
        """Rescales the pixmap when the widget is resized."""
        super().resizeEvent(event)
        if self.image_path:
            pixmap = QPixmap(self.image_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.setPixmap(scaled_pixmap)
