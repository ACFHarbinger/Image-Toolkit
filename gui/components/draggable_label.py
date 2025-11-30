from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt, QMimeData, QUrl, Signal, QPoint
from PySide6.QtGui import QDrag, QMouseEvent, QPixmap, QPainter, QColor


class DraggableLabel(QLabel):
    """
    A QLabel that displays a thumbnail and can be dragged.
    The drag operation carries the file path.
    """
    # Signal that emits the file path (Single Click)
    path_clicked = Signal(str)
    # Signal for Double Click
    path_double_clicked = Signal(str) 
    # NEW: Signal for Right Click
    path_right_clicked = Signal(QPoint, str) 

    def __init__(self, path: str, size: int):
        super().__init__()
        self.file_path = path
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self.setText("Loading...")
        self.setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;")
        self.setCursor(Qt.PointingHandCursor) # Ensure cursor hints at clickability
        
        # Set context menu policy to CustomContextMenu to enable right-click signal
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu) 
        self.customContextMenuRequested.connect(self._emit_right_click_signal)

    def _emit_right_click_signal(self, pos: QPoint):
        """
        Internal slot to emit the custom path_right_clicked signal 
        when the native customContextMenuRequested signal fires.
        """
        # Emits the global position (required for QMenu.exec) and the file path
        self.path_right_clicked.emit(self.mapToGlobal(pos), self.file_path)

    def mouseMoveEvent(self, event):
        """Initiates a drag-and-drop operation."""
        # CHANGE 1: Remove self.pixmap().isNull() check. 
        # Allow drag as long as file_path exists.
        if not self.file_path:
            return 

        drag = QDrag(self)
        mime_data = QMimeData()
        
        # Set the file path as a URL
        mime_data.setUrls([QUrl.fromLocalFile(self.file_path)])
        
        drag.setMimeData(mime_data)
        
        # CHANGE 2: Handle drag preview generation
        if self.pixmap() and not self.pixmap().isNull():
            # If we have an image, use it as the drag preview
            drag.setPixmap(self.pixmap().scaled(
                self.width() // 2, self.height() // 2, 
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
        else:
            # If no image (e.g., Video Placeholder), draw a generic "VIDEO" icon
            preview = QPixmap(100, 100)
            preview.fill(QColor("#3498db")) # Blue background
            
            painter = QPainter(preview)
            painter.setPen(Qt.white)
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(preview.rect(), Qt.AlignCenter, "VIDEO")
            painter.end()
            
            drag.setPixmap(preview)
        
        drag.exec(Qt.MoveAction)
    
    def mousePressEvent(self, event: QMouseEvent):
        # We only handle left click here, allowing right click to propagate 
        # to the contextMenuEvent mechanism.
        if event.button() == Qt.LeftButton:
            self.path_clicked.emit(self.file_path)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
         """Emits the double-click signal."""
         if event.button() == Qt.LeftButton:
            self.path_double_clicked.emit(self.file_path)
         super().mouseDoubleClickEvent(event)