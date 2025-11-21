from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout
from pathlib import Path


class QueueItemWidget(QWidget):
    """A widget to display an image preview and its name in the queue."""
    def __init__(self, path: str, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.path = path
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Image Preview Label
        img_label = QLabel()
        img_label.setPixmap(pixmap.scaled(
            QSize(80, 60), 
            Qt.KeepAspectRatio, 
            Qt.SmoothTransformation
        ))
        img_label.setFixedSize(80, 60)
        img_label.setStyleSheet("border: 1px solid #4f545c; border-radius: 4px;")
        layout.addWidget(img_label)
        
        # Filename Label
        filename = Path(path).name
        file_label = QLabel(filename)
        file_label.setToolTip(path)
        file_label.setStyleSheet("color: #b9bbbe; font-size: 12px;")
        file_label.setWordWrap(True)
        layout.addWidget(file_label, 1)
        
        self.setLayout(layout)
        self.setFixedSize(QSize(350, 70))
