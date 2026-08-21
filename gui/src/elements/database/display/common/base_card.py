from pathlib import Path

from gui.src.components import DoubleClickableLabel
from gui.src.constants.listings import CARD_SIZE
from gui.src.helpers.image.card_thumb_worker import _CARD_THUMB_CACHE
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import QMenu, QWidget


class BaseCard(QWidget):
    clicked = Signal(str)  # item id
    delete_requested = Signal(str)  # item id
    add_requested = Signal()
    image_remove_requested = Signal(str)  # item id (optional, for listings)

    _LABEL_COLORS = {
        "red": "#e74c3c",
        "orange": "#e67e22",
        "yellow": "#f1c40f",
        "green": "#2ecc71",
        "blue": "#3498db",
        "purple": "#9b59b6",
    }
    _LABEL_ICONS = {
        "red": "🔴",
        "orange": "🟠",
        "yellow": "🟡",
        "green": "🟢",
        "blue": "🔵",
        "purple": "🟣",
    }

    def __init__(
        self,
        item_id: str,
        image_path: str,
        placeholder: str,
        parent=None,
        card_size: int = CARD_SIZE,
    ):
        super().__init__(parent)
        self._id = item_id
        self._image_path = image_path
        self.placeholder = placeholder
        self.card_size = card_size
        self.thumb_size = max(64, card_size - 50)
        self._base_card_style = ""

        self.setFixedSize(card_size + 10, card_size + 50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self.thumb_label = DoubleClickableLabel()
        self.thumb_label.setFixedSize(self.thumb_size, self.thumb_size)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setStyleSheet("border:none;")
        self._apply_thumbnail(image_path)

    @property
    def _color_label_key(self) -> str:
        return f"database-card/{type(self).__name__}/{self._id}"

    def set_base_card_style(self, style: str) -> None:
        self._base_card_style = style
        self._refresh_color_label_style()

    def _refresh_color_label_style(self) -> None:
        from gui.src.windows.settings.app_settings import AppSettings

        color_key = AppSettings.label(self._color_label_key)
        color = self._LABEL_COLORS.get(color_key or "")
        suffix = ""
        if color and self.objectName():
            suffix = f"QWidget#{self.objectName()}{{border:3px solid {color};}}"
        self.setStyleSheet(self._base_card_style + suffix)

    def _set_color_label(self, color_key: str | None) -> None:
        from gui.src.windows.settings.app_settings import AppSettings

        if color_key:
            AppSettings.set_label(self._color_label_key, color_key)
        else:
            AppSettings.remove(f"labels/{self._color_label_key}")
        self._refresh_color_label_style()

    def _add_color_label_menu(self, menu: QMenu) -> None:
        labels = menu.addMenu("🏷 Color Label")
        for key, icon in self._LABEL_ICONS.items():
            action = QAction(f"{icon} {key.title()}", labels)
            action.triggered.connect(lambda _checked=False, value=key: self._set_color_label(value))
            labels.addAction(action)
        labels.addSeparator()
        clear = QAction("Clear Label", labels)
        clear.triggered.connect(lambda: self._set_color_label(None))
        labels.addAction(clear)

    def _apply_thumbnail(self, path: str) -> None:
        self.thumb_label.setProperty("_thumb_path", path or "")
        self.thumb_label.set_image_path(path)
        if not path or not Path(path).exists():
            self.thumb_label.setText(self.placeholder)
            self.thumb_label.setStyleSheet(
                "font-size:48px;color:#4f545c;background:#23272a;border-radius:6px;border:none;"
            )
            return

        cached = _CARD_THUMB_CACHE.get(path)
        if cached is not None:
            self.thumb_label.setPixmap(QPixmap.fromImage(cached))
            self.thumb_label.setStyleSheet("")
            return

        self.thumb_label.setText("")
        self.thumb_label.setStyleSheet("background:#23272a;border-radius:6px;border:none;")
        from gui.src.helpers.image.card_thumb_worker import _queue_thumbnail_load

        _queue_thumbnail_load(
            path,
            self.thumb_label,
            self.thumb_size,
            self.thumb_size,
            self.thumb_size,
        )

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._id)

    def _show_context_menu(self, pos):
        # To be implemented by subclasses
        pass
