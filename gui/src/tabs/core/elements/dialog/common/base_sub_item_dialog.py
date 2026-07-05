from pathlib import Path

from gui.src.components import DoubleClickableLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QFileDialog


class BaseSubItemDialog(QDialog):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        self.setStyleSheet("background:#2c2f33; color:white;")
        self.image_path = ""
        self.img_preview = DoubleClickableLabel()
        self.img_preview.setFixedSize(120, 120)
        self.img_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_preview.setStyleSheet("border:1px dashed #4f545c; border-radius:4px;")

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if path:
            self.image_path = path
            self._update_preview()

    def _update_preview(self):
        self.img_preview.set_image_path(self.image_path)
        if self.image_path and Path(self.image_path).exists():
            px = QPixmap(self.image_path).scaled(
                120,
                120,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.img_preview.setPixmap(px)
        else:
            self.img_preview.setText("No Image")
