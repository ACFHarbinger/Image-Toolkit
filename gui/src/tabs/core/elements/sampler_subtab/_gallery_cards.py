"""Gallery card rendering/selection (implements AbstractClassTwoGalleries hooks).

Extracted from ``sampler_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .....components import ClickableLabel


class _GalleryCardsMixin:
    """create_card_widget/update_card_pixmap/on_selection_changed and styling."""

    def create_card_widget(self, path: str, pixmap, is_selected: bool) -> QWidget:
        thumb_size = self.thumbnail_size
        card = ClickableLabel(path)
        card.setFixedSize(thumb_size + 10, thumb_size + 10)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setFixedSize(thumb_size, thumb_size)
        if pixmap and not pixmap.isNull():
            img_label.setPixmap(
                pixmap.scaled(
                    thumb_size,
                    thumb_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            img_label.setText("Loading…")
            img_label.setStyleSheet("color: #999; border: 1px dashed #666;")

        card_layout.addWidget(img_label)

        # Initialize the label's internal references
        card.set_image_label(img_label)
        card.style_callback = self._update_card_style

        # Trigger the style
        card.set_selected_style(is_selected)

        card.path_double_clicked.connect(self._preview_image)
        card.path_right_clicked.connect(self._context_menu)
        return card

    def update_card_pixmap(self, widget: QWidget, pixmap):
        if not isinstance(widget, ClickableLabel):
            return
        img_label = widget.findChild(QLabel)
        if not img_label:
            return
        if pixmap and not pixmap.isNull():
            if isinstance(pixmap, QImage):
                pixmap = QPixmap.fromImage(pixmap)
            img_label.setPixmap(
                pixmap.scaled(
                    self.thumbnail_size,
                    self.thumbnail_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            img_label.setText("")
        else:
            img_label.clear()
            img_label.setText("Loading…")
        self._update_card_style(img_label, widget.path in self.selected_files)

    def _update_card_style(self, img_label: QLabel, is_selected: bool):
        if is_selected:
            img_label.setStyleSheet(
                "border: 3px solid #5865f2; background-color: #36393f;"
            )
        elif img_label.pixmap() and not img_label.pixmap().isNull():
            img_label.setStyleSheet(
                "border: 1px solid #4f545c; background-color: #36393f;"
            )
        else:
            img_label.setStyleSheet("border: 1px dashed #666; color: #999;")

    def on_selection_changed(self):
        n = len(self.selected_files)
        self.btn_selected.setText(f"Resample Selected ({n})")
        self.btn_selected.setEnabled(n > 0)


__all__ = ["_GalleryCardsMixin"]
