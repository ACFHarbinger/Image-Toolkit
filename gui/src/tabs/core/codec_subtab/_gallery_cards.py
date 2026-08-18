"""Gallery card rendering/selection (implements AbstractClassTwoGalleries hooks).

Extracted from ``codec_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ....components import ClickableLabel


class _GalleryCardsMixin:
    """create_card_widget/update_card_pixmap/on_selection_changed and styling."""

    def create_card_widget(
        self, path: str, pixmap: Optional[QPixmap], is_selected: bool
    ) -> QWidget:
        thumb_size = self.thumbnail_size
        card_wrapper = ClickableLabel(path)
        card_wrapper.setFixedSize(thumb_size + 10, thumb_size + 10)
        card_wrapper.get_pixmap = lambda: img_label.pixmap()

        card_layout = QVBoxLayout(card_wrapper)
        card_layout.setContentsMargins(0, 0, 0, 0)

        img_label = QLabel()
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setFixedSize(thumb_size, thumb_size)

        card_wrapper.set_image_label(img_label)
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                thumb_size,
                thumb_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            img_label.setPixmap(scaled)
        else:
            img_label.setText("Loading...")
            img_label.setStyleSheet("color: #3498db; border: 2px dashed #3498db;")

        card_layout.addWidget(img_label)
        card_wrapper.setLayout(card_layout)

        self._update_card_style(img_label, is_selected)

        card_wrapper.path_double_clicked.connect(self.handle_full_image_preview)
        card_wrapper.path_right_clicked.connect(self.show_image_context_menu)

        return card_wrapper

    def update_card_pixmap(self, widget: QWidget, pixmap: Optional[QPixmap]):
        if not isinstance(widget, ClickableLabel):
            return

        img_label = widget.findChild(QLabel)
        if not img_label:
            return

        if pixmap and not pixmap.isNull():
            if isinstance(pixmap, QImage):
                pixmap = QPixmap.fromImage(pixmap)

            thumb_size = self.thumbnail_size
            scaled = pixmap.scaled(
                thumb_size,
                thumb_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            img_label.setPixmap(scaled)
            img_label.setText("")
        else:
            img_label.clear()
            img_label.setText("Loading...")

        is_selected = widget.path in self.selected_files
        self._update_card_style(img_label, is_selected)

    def _update_card_style(self, img_label: QLabel, is_selected: bool):
        if is_selected:
            img_label.setStyleSheet(
                "border: 3px solid #5865f2; background-color: #36393f;"
            )
        else:
            if img_label.pixmap() and not img_label.pixmap().isNull():
                img_label.setStyleSheet(
                    "border: 1px solid #4f545c; background-color: #36393f;"
                )
            else:
                img_label.setStyleSheet("border: 1px dashed #666; color: #999;")

    def on_selection_changed(self):
        count = len(self.selected_files)
        self.btn_convert_contents.setText(f"Convert Selected Files ({count})")
        self.btn_convert_contents.setEnabled(count > 0)


__all__ = ["_GalleryCardsMixin"]
