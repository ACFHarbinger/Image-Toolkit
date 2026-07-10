import shutil
import uuid
from pathlib import Path

from gui.src.components import DoubleClickableLabel
from gui.src.constants.listings import LISTING_IMAGES_DIR
from gui.src.helpers.image.card_thumb_worker import (
    _CARD_THUMB_CACHE,
    invalidate_thumbnail_cache,
)
from gui.src.utils.image_load import IMAGE_FILE_DIALOG_FILTER, load_qimage
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFileDialog, QWidget


class BaseDetailPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_path = ""
        self.img_preview = DoubleClickableLabel()
        self.img_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _browse_image_helper(self, item_id: str) -> str:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Reference Image",
            "",
            IMAGE_FILE_DIALOG_FILTER,
        )
        if path:
            LISTING_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            copied_id = item_id or str(uuid.uuid4())
            orig_p = Path(path)
            dest_p = LISTING_IMAGES_DIR / f"{copied_id}{orig_p.suffix}"
            try:
                shutil.copy2(path, dest_p)
                self._image_path = str(dest_p.absolute())
                invalidate_thumbnail_cache(self._image_path)
            except Exception as e:
                print(f"Failed to copy image: {e}")
                self._image_path = path
            self._refresh_image()
        return self._image_path

    def _refresh_image(self):
        path = self._image_path
        self.img_preview.set_image_path(path)
        if not path or not Path(path).exists():
            self.img_preview.clear()
            self.img_preview.setText("No Image")
            self.img_preview.setStyleSheet(
                "border:2px dashed #4f545c;border-radius:8px;color:#888;font-size:12px;"
            )
            return

        img = load_qimage(path)
        if not img.isNull():
            scaled = QPixmap.fromImage(img).scaled(
                160,
                160,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.img_preview.setPixmap(scaled)
            self.img_preview.setStyleSheet(
                "border:2px solid #4f545c;border-radius:8px;"
            )
            thumb = img.scaled(
                160,
                160,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            _CARD_THUMB_CACHE[path] = thumb
            _CARD_THUMB_CACHE[f"preview160:{path}"] = thumb