import os

from typing import Optional
from screeninfo import Monitor
from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import (
    QPixmap, QDragEnterEvent, QDropEvent, QDragMoveEvent, QDragLeaveEvent,
    QMouseEvent, QDrag
)
from PySide6.QtWidgets import QLabel, QMenu, QApplication
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS


class MonitorDropWidget(QLabel):
    """
    A custom QLabel that acts as a drop target for images,
    displays monitor info, and shows a preview of the dropped image.
    
    Now supports being dragged itself for reordering.
    """
    # Emits (monitor_id, image_path) when an image is successfully dropped
    image_dropped = Signal(str, str) 
    
    # Emits monitor_id when the widget is double-clicked
    double_clicked = Signal(str)

    # Emits monitor_id when the 'Clear Monitor' right-click action is selected
    clear_requested_id = Signal(str)

    def __init__(self, monitor: Monitor, monitor_id: str):
        super().__init__()
        self.monitor = monitor
        self.monitor_id = monitor_id
        self.image_path: Optional[str] = None
        self.drag_start_position = None  # Track start position for reordering drag
        
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

    def contextMenuEvent(self, event):
        """Creates and executes a context menu on right-click."""
        menu = QMenu(self)
        clear_action = menu.addAction("Clear All Images (Current and Queue)")
        clear_action.triggered.connect(lambda: self.clear_requested_id.emit(self.monitor_id))
        menu.exec(event.globalPos())

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Overrides the double-click event to emit the custom signal."""
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self.monitor_id)
        super().mouseDoubleClickEvent(event)

    # --- DRAG INITIATION LOGIC (Reordering) ---

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.LeftButton):
            return
        if not self.drag_start_position:
            return

        # Ensure we've moved far enough to consider it a drag (prevents accidental drags on clicks)
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return

        # Create the drag object
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.monitor_id) # Identify this widget by monitor ID
        drag.setMimeData(mime_data)

        # Create a visual ghost of the widget
        pixmap = self.grab()
        drag.setPixmap(pixmap.scaledToWidth(200, Qt.SmoothTransformation))
        # Center the hot spot roughly where the click was, or center of widget
        drag.setHotSpot(event.pos())

        drag.exec(Qt.MoveAction)

    # --- DROP TARGET LOGIC (Receiving Images) ---

    def update_text(self):
        monitor_name = f"Monitor {self.monitor_id}"
        if self.monitor.name:
             monitor_name = f"{monitor_name} ({self.monitor.name})"
        
        self.setText(f"<b>{monitor_name}</b>\n\n"
                     "Drag and Drop Image Here")

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Event when a dragged item enters the widget."""
        # CRITICAL: If this is a reorder drag (MonitorDropWidget source), 
        # IGNORE it so it bubbles up to the parent container.
        if event.source() and isinstance(event.source(), MonitorDropWidget):
            event.ignore()
            return

        if self.has_valid_image_url(event.mimeData()):
            event.acceptProposedAction()
            self.setProperty("dragging", True)
            self.style().polish(self)
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        """Event when a dragged item moves over the widget."""
        if event.source() and isinstance(event.source(), MonitorDropWidget):
            event.ignore()
            return

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
                self.image_dropped.emit(self.monitor_id, file_path)
                event.acceptProposedAction()
                return
        
        event.ignore()

    def has_valid_image_url(self, mime_data: QMimeData) -> bool:
        """Checks if the MimeData contains a single, valid, local image file."""
        if not mime_data.hasUrls():
            return False
        
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
                self.setText("") 
            else:
                self.image_path = None
                self.update_text()
                monitor_name = f"Monitor {self.monitor_id}"
                if self.monitor.name:
                     monitor_name = f"{monitor_name} ({self.monitor.name})"
                
                self.setText(f"<b>{monitor_name}</b>\n\n"
                             "<b>Error:</b> Could not load image.")
        else:
             self.clear() 
             
    def clear(self):
        """Clears the displayed image and resets to placeholder text."""
        self.image_path = None
        self.setPixmap(QPixmap()) 
        self.update_text()
                         
    def resizeEvent(self, event):
        """Rescales the pixmap when the widget is resized."""
        super().resizeEvent(event)
        if self.image_path:
            pixmap = QPixmap(self.image_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.setPixmap(scaled_pixmap)