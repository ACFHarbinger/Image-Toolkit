from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt, QMimeData, QUrl


class DraggableImageLabel(QLabel):
    """
    A simple QLabel that displays a thumbnail and can be dragged.
    The drag operation carries the file path.
    """
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
    