"""Gallery card creation/pixmap updates/selection styling and preview highlight.

Extracted from ``abstract_class_single_gallery.py`` -- pure code motion, no
logic change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from ..protos.abstract_class_single_gallery import AbstractClassSingleGalleryHostProtocol


class _CardRenderingMixin:
    """create_card_widget/update_card_pixmap/update_card_style and previews."""

    def update_card_style(self, widget: QWidget, is_selected: bool):
        """Updates the visual style of a card based on selection state."""
        label = widget.findChild(QLabel)
        if not label:
            return

        if is_selected:
            label.setStyleSheet(
                "border: 2px solid #5865f2; background-color: rgba(88, 101, 242, 0.2);"
            )
        else:
            path = getattr(label, "file_path", getattr(label, "path", ""))
            is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
            if is_video:
                label.setStyleSheet(
                    "border: 2px solid #3498db; background-color: transparent;"
                )
            else:
                label.setStyleSheet(
                    "border: 1px solid #4f545c; background-color: transparent;"
                )

    @Slot(str, str)
    def update_preview_highlight(self: "AbstractClassSingleGalleryHostProtocol", old_path: str, new_path: str):
        """Adds a blue highlight border to the card currently being viewed in the preview window."""
        is_closing = new_path == "WINDOW_CLOSED"

        def reset_card(path, card):
            if not card or not path:
                return
            try:
                orig = card.property("original_style")
                if orig is not None:
                    card.setStyleSheet(orig)
                    card.setProperty("original_style", None)
                else:
                    self.update_card_style(card, self.is_path_selected(path))
            except RuntimeError:
                pass

        reset_card(old_path, self.path_to_card_widget.get(old_path))

        if is_closing:
            sender_win = self.sender()
            if sender_win in self.open_preview_windows:
                self.open_preview_windows.remove(sender_win) # pyrefly: ignore [bad-argument-type]
            return

        def highlight_card(path, card):
            if not card or not path:
                return
            try:
                self.update_card_style(card, self.is_path_selected(path))
                if card.property("original_style") is None:
                    card.setProperty("original_style", card.styleSheet())
                current = card.styleSheet().strip()
                sep = "" if not current or current.endswith(";") else ";"
                card.setStyleSheet(f"{current}{sep} border: 4px solid #3498db;")
            except RuntimeError:
                pass

        highlight_card(new_path, self.path_to_card_widget.get(new_path))

    def create_card_widget(self: "AbstractClassSingleGalleryHostProtocol", path: str, pixmap: Optional[QPixmap]) -> QWidget:
        container = QWidget()
        container.setFixedSize(self.approx_item_width, self.approx_item_width)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Factory method
        label = self.create_gallery_label(path, self.thumbnail_size)
        # label.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent) # Removed to fix artifacts

        # Initial State
        is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))

        if (pixmap and not pixmap.isNull()) or (
            hasattr(self, "_failed_paths") and path in self._failed_paths
        ):
            self.update_card_pixmap(container, pixmap, label_ref=label)
        else:
            # Default "Loading..." State
            label.clear()
            label.setText("Loading...")
            if is_video:
                label.setStyleSheet(
                    "border: 2px solid #3498db; color: #3498db; "
                    "font-weight: bold; background-color: rgba(20, 24, 32, 0.35);"
                )
            else:
                label.setStyleSheet(
                    "border: 1px dashed rgba(255, 255, 255, 0.20); color: #888; "
                    "font-size: 10px; background-color: rgba(20, 24, 32, 0.35);"
                )

        layout.addWidget(label)

        # Apply Initial Style
        is_selected = path in self.selected_files
        self.update_card_style(container, is_selected)

        return container

    def update_card_pixmap(
        self: "AbstractClassSingleGalleryHostProtocol",
        widget: QWidget,
        pixmap: Optional[QPixmap],
        label_ref: Optional[QLabel] = None,
    ):
        label = label_ref if label_ref is not None else widget.findChild(QLabel)

        if not label:
            return

        # Resolve 'path' vs 'file_path' attribute inconsistency between different Label classes
        path = getattr(label, "file_path", getattr(label, "path", ""))
        is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))

        # 1. Check Failure State
        if hasattr(self, "_failed_paths") and path in self._failed_paths:
            label.clear()
            label.setScaledContents(False)

            if is_video:
                # Match ExtractorTab style ("VIDEO" text, Blue border)
                label.setText("VIDEO")
                label.setStyleSheet(
                    "border: 2px solid #3498db; color: #3498db; font-weight: bold; background-color: rgba(20, 24, 32, 0.35);"
                )
            else:
                label.setText("No Thumbnail")
                label.setStyleSheet(
                    "border: 2px solid #e74c3c; color: #e74c3c; font-weight: bold; background-color: rgba(20, 24, 32, 0.35);"
                )

            label.show()
            return

        # 2. Check Success State
        if pixmap and not pixmap.isNull():
            if (
                pixmap.width() > self.thumbnail_size
                or pixmap.height() > self.thumbnail_size
            ):
                scaled = pixmap.scaled(
                    self.thumbnail_size,
                    self.thumbnail_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            else:
                # Loader thumbnails already fit the target size — avoid a
                # second smooth rescale on the GUI thread for every image.
                scaled = pixmap
            label.setPixmap(scaled)
            label.setText("")

            if is_video:
                label.setStyleSheet(
                    "border: 2px solid #3498db; background-color: transparent;"
                )
            else:
                label.setStyleSheet(
                    "border: 1px solid rgba(255, 255, 255, 0.15); background-color: transparent;"
                )

        # 3. Loading/Empty State
        else:
            label.setText("Load Failed")
            label.setStyleSheet(
                "border: 1px solid #e74c3c; color: #e74c3c; font-size: 10px; background-color: rgba(20, 24, 32, 0.35);"
            )

    def _generate_error_pixmap(self: "AbstractClassSingleGalleryHostProtocol") -> QPixmap:
        """Generates a visual placeholder for failed loads."""
        size = self.thumbnail_size
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor("#2c2f33"))

        painter = QPainter(pixmap)
        # Red border
        painter.setPen(QColor("#e74c3c"))
        painter.drawRect(0, 0, size - 1, size - 1)

        # Text
        painter.setPen(QColor("#e74c3c"))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "No Thumbnail")
        painter.end()

        return pixmap


__all__ = ["_CardRenderingMixin"]
