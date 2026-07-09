import shutil
import uuid
from pathlib import Path
from typing import Optional

from gui.src.components import DoubleClickableLabel
from gui.src.constants.listings import LISTING_IMAGES_DIR
from gui.src.helpers.image.card_thumb_worker import invalidate_thumbnail_cache
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox


class BaseSubItemDialog(QDialog):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        self.setStyleSheet("background:#2c2f33; color:white;")
        self.image_path = ""
        self._item_id = str(uuid.uuid4())
        self.img_preview = DoubleClickableLabel()
        self.img_preview.setFixedSize(120, 120)
        self.img_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_preview.setStyleSheet("border:1px dashed #4f545c; border-radius:4px;")

    def _listing_image_basename(self, source_path: str) -> Optional[str]:
        """Return a filename under LISTING_IMAGES_DIR, or None to skip copying."""
        return None

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)"
        )
        if not path:
            return

        basename = self._listing_image_basename(path)
        if basename:
            LISTING_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            dest_p = LISTING_IMAGES_DIR / basename
            try:
                shutil.copy2(path, dest_p)
                invalidate_thumbnail_cache(str(dest_p.absolute()))
                self.image_path = str(dest_p.absolute())
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to save image to listing storage: {e}"
                )
                return
        else:
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