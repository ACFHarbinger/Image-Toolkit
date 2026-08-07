import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QImageReader
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

class MetadataOverlay(QFrame):
    """Semi-transparent overlay showing file info on hover (GUI/UX §2.14B)."""
    
    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet("background-color: transparent;")
        self.hide()
        
        self._setup_ui()
        self._load_metadata()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        
        self.filename_label = QLabel()
        self.filename_label.setStyleSheet("color: white; font-weight: bold; font-size: 11px;")
        self.filename_label.setWordWrap(True)
        
        self.dim_label = QLabel()
        self.dim_label.setStyleSheet("color: #cccccc; font-size: 10px;")
        
        self.size_label = QLabel()
        self.size_label.setStyleSheet("color: #cccccc; font-size: 10px;")
        
        layout.addWidget(self.filename_label)
        layout.addWidget(self.dim_label)
        layout.addWidget(self.size_label)
        layout.addStretch()
        
    def _load_metadata(self):
        # Filename
        basename = os.path.basename(self.file_path)
        self.filename_label.setText(basename)
        
        # Dimensions (lazy load)
        if os.path.exists(self.file_path):
            reader = QImageReader(self.file_path)
            size = reader.size()
            if size.isValid():
                self.dim_label.setText(f"{size.width()} × {size.height()}")
            else:
                self.dim_label.setText("Unknown dims")
            
            # File size
            try:
                size_bytes = os.path.getsize(self.file_path)
                self.size_label.setText(self._format_size(size_bytes))
            except OSError:
                self.size_label.setText("Unknown size")
        else:
            self.dim_label.setText("Unknown dims")
            self.size_label.setText("Unknown size")
            
    def _format_size(self, size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        path = QPainterPath()
        rect = self.rect()
        path.addRoundedRect(rect, 4, 4)
        
        bg_color = QColor(0, 0, 0, 180)  # Semi-transparent dark background
        painter.fillPath(path, bg_color)
        super().paintEvent(event)
