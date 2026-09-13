from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
)

from gui.src.theming.theme_api import qss


class _FullImageViewerDialog(QDialog):
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Full Image Preview")
        self.setMinimumSize(600, 600)
        self.resize(800, 800)
        self.setStyleSheet(qss("full_image_dialog"))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Header with title and close button
        header = QHBoxLayout()
        title_lbl = QLabel(Path(image_path).name)
        title_lbl.setStyleSheet(qss("full_image_title"))
        header.addWidget(title_lbl)
        header.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(qss("full_image_close_btn"))
        close_btn.clicked.connect(self.accept)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # Scroll Area for image
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(qss("full_image_scroll"))

        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setStyleSheet(qss("transparent_bg"))

        # Load and set the full image
        self.pixmap = QPixmap(image_path)
        self.img_label.setPixmap(self.pixmap)

        scroll.setWidget(self.img_label)
        layout.addWidget(scroll)

        # Dimensions and File Size label
        try:
            sz = Path(image_path).stat().st_size
            size_kb = sz / 1024
            dim_str = (
                f"{self.pixmap.width()} x {self.pixmap.height()} px | {size_kb:.1f} KB"
            )
        except Exception:
            dim_str = ""

        status_lbl = QLabel(dim_str)
        status_lbl.setStyleSheet(qss("full_image_status"))
        layout.addWidget(status_lbl, alignment=Qt.AlignmentFlag.AlignRight)


class DoubleClickableLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_path = ""
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    @property
    def image_path(self) -> str:
        """Read-only accessor used by async thumbnail workers to guard stale updates."""
        return self._image_path

    def set_image_path(self, path: str):
        self._image_path = path
        if path and Path(path).exists():
            self.setToolTip("Double-click to view full image")
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setToolTip("")
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._image_path:
            if Path(self._image_path).exists():
                dlg = _FullImageViewerDialog(self._image_path, self)
                dlg.exec()
        else:
            super().mouseDoubleClickEvent(event)
