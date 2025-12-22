from PySide6.QtWidgets import QLabel, QApplication
from PySide6.QtCore import Qt, QMimeData, QUrl, Signal, QPoint
from PySide6.QtGui import QDrag, QMouseEvent, QPixmap, QPainter, QColor, QCursor
from .drag_preview_window import DragPreviewWindow


class DraggableLabel(QLabel):
    """
    A QLabel that displays a thumbnail and can be dragged.
    Uses a custom drag system to allow wheel scrolling during drag.
    """

    # Signal that emits the file path (Single Click)
    path_clicked = Signal(str)
    # Signal for Double Click
    path_double_clicked = Signal(str)
    # NEW: Signal for Right Click
    path_right_clicked = Signal(QPoint, str)
    
    # Custom drag signals
    drag_started = Signal(str)  # file_path
    drag_finished = Signal()

    def __init__(self, path: str, size: int):
        super().__init__()
        self.file_path = path
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self.setText("Loading...")
        self.setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;")
        self.setCursor(Qt.PointingHandCursor)

        # Set context menu policy to CustomContextMenu to enable right-click signal
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._emit_right_click_signal)
        
        # Custom drag state
        self.is_dragging = False
        self.drag_start_pos = None
        self.drag_preview_window = None

    def _emit_right_click_signal(self, pos: QPoint):
        """
        Internal slot to emit the custom path_right_clicked signal
        when the native customContextMenuRequested signal fires.
        """
        # Emits the global position (required for QMenu) and the file path
        self.path_right_clicked.emit(self.mapToGlobal(pos), self.file_path)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press - start tracking potential drag."""
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.pos()
            self.path_clicked.emit(self.file_path)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move - initiate custom drag if threshold exceeded."""
        if not self.file_path:
            return
            
        # Check if we should start dragging
        if not self.is_dragging and self.drag_start_pos:
            # Check if moved enough to start drag (Qt default threshold is ~4 pixels)
            if (event.pos() - self.drag_start_pos).manhattanLength() < 4:
                return
                
            # Start custom drag
            self._start_custom_drag()
            
        if self.is_dragging:
            # Update drag preview position
            if self.drag_preview_window:
                self.drag_preview_window.update_position(QCursor.pos())

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release - end custom drag."""
        if event.button() == Qt.LeftButton and self.is_dragging:
            self._finish_custom_drag(QCursor.pos())
        super().mouseReleaseEvent(event)

    def _start_custom_drag(self):
        """Start the custom drag operation."""
        self.is_dragging = True
        
        # Create drag preview
        preview_pixmap = self._create_drag_preview()
        self.drag_preview_window = DragPreviewWindow(preview_pixmap)
        self.drag_preview_window.update_position(QCursor.pos())
        self.drag_preview_window.show()
        
        # Grab mouse to track movement even outside widget
        self.grabMouse()
        
        # Emit drag started signal
        self.drag_started.emit(self.file_path)

    def _finish_custom_drag(self, drop_pos: QPoint):
        """Finish the custom drag operation."""
        self.is_dragging = False
        self.drag_start_pos = None
        
        # Release mouse
        self.releaseMouse()
        
        # Hide and delete preview window
        if self.drag_preview_window:
            self.drag_preview_window.hide()
            self.drag_preview_window.deleteLater()
            self.drag_preview_window = None
        
        # Find widget under cursor and try to drop
        widget_under_cursor = QApplication.widgetAt(drop_pos)
        if widget_under_cursor:
            self._try_drop_on_widget(widget_under_cursor)
        
        # Emit drag finished signal
        self.drag_finished.emit()

    def _try_drop_on_widget(self, widget):
        """Try to drop the file on the target widget."""
        # Import here to avoid circular dependency
        from .monitor_drop_widget import MonitorDropWidget
        
        # Check if widget or any of its parents is a MonitorDropWidget
        current = widget
        while current:
            if isinstance(current, MonitorDropWidget):
                # Simulate a drop by calling the widget's method directly
                current.handle_custom_drop(self.file_path)
                return
            current = current.parentWidget()

    def _create_drag_preview(self) -> QPixmap:
        """Create a pixmap for the drag preview."""
        if self.pixmap() and not self.pixmap().isNull():
            # If we have an image, use it as the drag preview
            return self.pixmap().scaled(
                self.width() // 2,
                self.height() // 2,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        else:
            # If no image (e.g., Video Placeholder), draw a generic "VIDEO" icon
            preview = QPixmap(100, 100)
            preview.fill(QColor("#3498db"))  # Blue background

            painter = QPainter(preview)
            painter.setPen(Qt.white)
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(preview.rect(), Qt.AlignCenter, "VIDEO")
            painter.end()

            return preview

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Emits the double-click signal."""
        if event.button() == Qt.LeftButton:
            self.path_double_clicked.emit(self.file_path)
        super().mouseDoubleClickEvent(event)
