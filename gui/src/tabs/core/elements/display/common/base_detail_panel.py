import uuid
import shutil
from pathlib import Path
from PySide6.QtCore import Qt, Slot, QThreadPool
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import QWidget, QFileDialog

from gui.src.components import DoubleClickableLabel
from gui.src.constants.listings import LISTING_IMAGES_DIR
from gui.src.helpers.image import (
    _CARD_THUMB_CACHE,
    _ThumbWorker,
)


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
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)",
        )
        if path:
            LISTING_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            copied_id = item_id or str(uuid.uuid4())
            orig_p = Path(path)
            dest_p = LISTING_IMAGES_DIR / f"{copied_id}{orig_p.suffix}"
            try:
                shutil.copy2(path, dest_p)
                self._image_path = str(dest_p.absolute())
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
        cache_key = f"preview160:{path}"
        cached = _CARD_THUMB_CACHE.get(cache_key)
        if cached is not None:
            self.img_preview.setPixmap(QPixmap.fromImage(cached))
            self.img_preview.setStyleSheet(
                "border:2px solid #4f545c;border-radius:8px;"
            )
            return
        worker = _ThumbWorker(path, 160)
        worker.signals.ready.connect(self._on_preview_ready)
        QThreadPool.globalInstance().start(worker)

    @Slot(str, QImage)
    def _on_preview_ready(self, path: str, img: QImage) -> None:
        if path == self.img_preview.image_path:
            _CARD_THUMB_CACHE[f"preview160:{path}"] = img
            self.img_preview.setPixmap(QPixmap.fromImage(img))
            self.img_preview.setStyleSheet(
                "border:2px solid #4f545c;border-radius:8px;"
            )
