from pathlib import Path

from gui.src.components import DoubleClickableLabel
from gui.src.constants.listings import CARD_SIZE, THUMB_SIZE
from gui.src.helpers.image import (
    _CARD_THUMB_CACHE,
    _ThumbWorker,
)
from PySide6.QtCore import Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QWidget


class BaseCard(QWidget):
    clicked = Signal(str)  # item id
    delete_requested = Signal(str)  # item id
    add_requested = Signal()
    image_remove_requested = Signal(str)  # item id (optional, for listings)

    def __init__(self, item_id: str, image_path: str, placeholder: str, parent=None):
        super().__init__(parent)
        self._id = item_id
        self._image_path = image_path
        self.placeholder = placeholder

        self.setFixedSize(CARD_SIZE + 10, CARD_SIZE + 50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self.thumb_label = DoubleClickableLabel()
        self.thumb_label.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setStyleSheet("border:none;")
        self._apply_thumbnail(image_path)

    def _apply_thumbnail(self, path: str) -> None:
        self.thumb_label.set_image_path(path)
        if not path or not Path(path).exists():
            self.thumb_label.setText(self.placeholder)
            self.thumb_label.setStyleSheet(
                "font-size:48px;color:#4f545c;background:#23272a;"
                "border-radius:6px;border:none;"
            )
            return

        cached = _CARD_THUMB_CACHE.get(path)
        if cached is not None:
            self.thumb_label.setPixmap(QPixmap.fromImage(cached))
            self.thumb_label.setStyleSheet("")
            return

        self.thumb_label.setText("")
        self.thumb_label.setStyleSheet(
            "background:#23272a;border-radius:6px;border:none;"
        )
        worker = _ThumbWorker(path, THUMB_SIZE)
        worker.signals.ready.connect(self._on_thumb_ready)
        QThreadPool.globalInstance().start(worker)

    @Slot(str, QImage)
    def _on_thumb_ready(self, path: str, img: QImage) -> None:
        if path == self.thumb_label.image_path:
            self.thumb_label.setPixmap(QPixmap.fromImage(img))
            self.thumb_label.setStyleSheet("")

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._id)

    def _show_context_menu(self, pos):
        # To be implemented by subclasses
        pass
