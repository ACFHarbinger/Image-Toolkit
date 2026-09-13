import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImageReader, QPainter, QPainterPath
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from gui.src.theming.theme_api import qss


class MetadataOverlay(QFrame):
    """Semi-transparent overlay showing file info on hover (GUI/UX §2.14B)."""

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet(qss("transparent_bg"))
        self.hide()

        self._setup_ui()
        # Set filename immediately (cheap string operation, no I/O)
        self.filename_label.setText(os.path.basename(self.file_path))
        self._metadata_loaded = False

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        self.filename_label = QLabel()
        self.filename_label.setStyleSheet(qss("metadata_filename"))
        self.filename_label.setWordWrap(True)

        self.dim_label = QLabel()
        self.dim_label.setStyleSheet(qss("metadata_detail"))

        self.size_label = QLabel()
        self.size_label.setStyleSheet(qss("metadata_detail"))

        layout.addWidget(self.filename_label)
        layout.addWidget(self.dim_label)
        layout.addWidget(self.size_label)
        layout.addStretch()

    def showEvent(self, event):
        if not self._metadata_loaded:
            self._load_metadata()
            self._metadata_loaded = True
        super().showEvent(event)

    def _load_metadata(self):
        # Filename
        basename = os.path.basename(self.file_path)
        self.filename_label.setText(basename)

        # Dimensions (lazy load). Huge GIFs must not go through
        # QImageReader -- that is the gallery browse crash.
        if os.path.exists(self.file_path):
            from gui.src.helpers.image._qimagereader_disk_cache import (
                is_oversized_gif,
                read_gif_logical_screen,
            )

            gif_screen = (
                read_gif_logical_screen(self.file_path)
                if self.file_path.lower().endswith(".gif")
                else None
            )
            if gif_screen is not None:
                self.dim_label.setText(f"{gif_screen[0]} × {gif_screen[1]}")
            elif is_oversized_gif(self.file_path):
                self.dim_label.setText("GIF")
            else:
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
