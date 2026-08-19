"""Card rendering, pixmap updates, and default selection/style callbacks.

Promoted from per-tab copies into AbstractClassTwoGalleries (§Issue 446).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ....components import ClickableLabel

if TYPE_CHECKING:
    from ..protos.abstract_class_two_galleries import AbstractClassTwoGalleriesHostProtocol


class _CardRenderingMixin:
    """Card widget creation, pixmap updating, and card border/state styling."""

    def create_gallery_label(
        self: "AbstractClassTwoGalleriesHostProtocol", path: str, size: int
    ) -> QLabel:
        """Factory method for card container label; subclasses may override."""
        label = ClickableLabel(path)
        label.setFixedSize(size + 10, size + 10)
        return label

    def create_card_widget(
        self: "AbstractClassTwoGalleriesHostProtocol",
        path: str,
        pixmap: Optional[QPixmap],
        is_selected: bool,
    ) -> QWidget:
        thumb_size = self.thumbnail_size
        card_wrapper = self.create_gallery_label(path, thumb_size)

        if isinstance(card_wrapper, ClickableLabel):
            card_layout = QVBoxLayout(card_wrapper)
            card_layout.setContentsMargins(0, 0, 0, 0)

            img_label = QLabel()
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_label.setFixedSize(thumb_size, thumb_size)

            card_wrapper.set_image_label(img_label)
            card_layout.addWidget(img_label)
            card_wrapper.setLayout(card_layout)
            target_label = img_label
        else:
            target_label = card_wrapper

        if hasattr(card_wrapper, "set_selected_style"):
            card_wrapper.style_callback = self._update_card_style

        if pixmap and not pixmap.isNull():
            scaled = (
                pixmap.scaled(
                    thumb_size,
                    thumb_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                if (pixmap.width() > thumb_size or pixmap.height() > thumb_size)
                else pixmap
            )
            target_label.setPixmap(scaled)
        else:
            target_label.setText("Loading...")
            if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                target_label.setStyleSheet("color: #3498db; border: 2px dashed #3498db;")
            else:
                target_label.setStyleSheet("color: #999; border: 1px dashed #666;")

        card_wrapper.setProperty("gallery_path", path)
        self._update_card_style(target_label, is_selected)

        if hasattr(card_wrapper, "path_double_clicked"):
            card_wrapper.path_double_clicked.connect(self._open_preview_for)
        if hasattr(card_wrapper, "path_right_clicked"):
            card_wrapper.path_right_clicked.connect(self._on_found_card_right_clicked)

        return card_wrapper

    def update_card_pixmap(
        self: "AbstractClassTwoGalleriesHostProtocol",
        widget: QWidget,
        pixmap: Optional[QPixmap],
    ) -> None:
        if not widget:
            return
        img_label = widget.findChild(QLabel) if not isinstance(widget, QLabel) else widget
        if not img_label:
            return

        if pixmap and not pixmap.isNull():
            if isinstance(pixmap, QImage):
                pixmap = QPixmap.fromImage(pixmap)

            thumb_size = self.thumbnail_size
            scaled = (
                pixmap.scaled(
                    thumb_size,
                    thumb_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                if (pixmap.width() > thumb_size or pixmap.height() > thumb_size)
                else pixmap
            )
            img_label.setPixmap(scaled)
            img_label.setText("")
        else:
            img_label.clear()
            img_label.setText("Loading...")

        path = (
            getattr(widget, "path", None)
            or getattr(widget, "file_path", None)
            or widget.property("gallery_path")
            or ""
        )
        is_selected = path in self.selected_files if (path and hasattr(self, "selected_files")) else False
        self._update_card_style(img_label, is_selected)

    def _update_card_style(
        self: "AbstractClassTwoGalleriesHostProtocol",
        img_label: QLabel,
        is_selected: bool,
    ) -> None:
        parent_widget = img_label.parentWidget()
        is_in_db = bool(
            img_label.property("in_db")
            or (parent_widget and parent_widget.property("in_db"))
        )
        path = (
            img_label.property("gallery_path")
            or (parent_widget and (getattr(parent_widget, "path", None) or parent_widget.property("gallery_path")))
            or getattr(img_label, "path", getattr(img_label, "file_path", ""))
            or ""
        )

        if is_selected:
            img_label.setStyleSheet(
                "border: 3px solid #5865f2; background-color: #36393f;"
            )
        elif is_in_db:
            img_label.setStyleSheet(
                "border: 3px solid #2ecc71; background-color: #36393f;"
            )
        else:
            label_color = self._LABEL_COLORS.get(self._get_color_label(path) or "", "") if path else ""
            if label_color:
                img_label.setStyleSheet(f"border: 2px solid {label_color}; background-color: #36393f;")
            elif img_label.pixmap() and not img_label.pixmap().isNull():
                img_label.setStyleSheet(
                    "border: 1px solid #4f545c; background-color: #36393f;"
                )
            else:
                if img_label.text() in ("Loading...", "Loading…", "Error"):
                    pass
                else:
                    img_label.setStyleSheet("border: 1px dashed #666; color: #999;")

    def _update_found_card_styles(self: "AbstractClassTwoGalleriesHostProtocol") -> None:
        """Re-evaluate and apply style to all currently visible found cards."""
        for path, widget in self.path_to_label_map.items():
            if widget:
                is_selected = path in self.selected_files
                self.update_card_style(widget, is_selected)

    def on_selection_changed(self: "AbstractClassTwoGalleriesHostProtocol") -> None:
        """Hook called when selection changes."""
        pass


__all__ = ["_CardRenderingMixin"]
