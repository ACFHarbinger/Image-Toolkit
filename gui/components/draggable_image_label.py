from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtCore import Qt, QMimeData, QUrl, Signal


class DraggableImageLabel(QLabel):
    """
    A QLabel that displays a thumbnail and can be dragged.
    The drag operation carries the file path.
    """
    # Signal that emits the file path (Single Click)
    path_clicked = Signal(str)
    # Signal for Double Click
    path_double_clicked = Signal(str) 
    def __init__(self, path: str, size: int):
        super().__init__()
        self.file_path = path
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self.setText("Loading...")
        self.setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;")

    def mouseMoveEvent(self, event):
        """Initiates a drag-and-drop operation."""
        if not self.file_path or self.pixmap().isNull():
            return # Don't drag if not a valid image

        drag = QDrag(self)
        mime_data = QMimeData()
        
        # Set the file path as a URL
        mime_data.setUrls([QUrl.fromLocalFile(self.file_path)])
        
        drag.setMimeData(mime_data)
        
        # Set a pixmap for the drag preview
        drag.setPixmap(self.pixmap().scaled(
            self.width() // 2, self.height() // 2, 
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))
        
        drag.exec(Qt.MoveAction)
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.path_clicked.emit(self.file_path)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
         """Emits the double-click signal."""
         if event.button() == Qt.LeftButton:
            self.path_double_clicked.emit(self.file_path)
         super().mouseDoubleClickEvent(event)
    