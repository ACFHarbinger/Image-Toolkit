"""Gallery card creation/pixmap updates/selection styling and preview highlight.

Extracted from ``abstract_class_single_gallery.py`` -- pure code motion, no
logic change.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Optional

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from gui.src.components.gallery.card_factory import (
    VIDEO_COLOR,
    apply_preview_highlight,
    create_gallery_card,
    reset_preview_highlight,
)
from gui.src.qt_object_guard import deleted_qobject_guard

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
                    f"border: 2px solid {VIDEO_COLOR}; background-color: transparent;"
                )
            else:
                label.setStyleSheet(
                    "border: 1px solid #4f545c; background-color: transparent;"
                )

    @Slot(str, str)
    def update_preview_highlight(self: "AbstractClassSingleGalleryHostProtocol", old_path: str, new_path: str):
        """Adds an amber highlight border to the card currently being viewed in
        the preview window (distinct from the indigo selection border)."""
        is_closing = new_path == "WINDOW_CLOSED"
        gallery = getattr(self, "gallery", None)

        def reset_card(path, card):
            try:
                reset_preview_highlight(
                    card,
                    path,
                    is_selected=self.is_path_selected(path) if path else False,
                    update_style=self.update_card_style,
                )
            except RuntimeError as exc:
                deleted_qobject_guard(exc, "_CardRenderingMixin.update_preview_highlight.reset_card")

        reset_card(old_path, self.path_to_card_widget.get(old_path))
        if gallery is not None and hasattr(gallery, "mark_preview"):
            gallery.mark_preview(old_path, False)

        if is_closing:
            sender_win = self.sender()
            if sender_win in self.open_preview_windows:
                with contextlib.suppress(ValueError):
                    self.open_preview_windows.remove(sender_win) # pyrefly: ignore [bad-argument-type]
            return

        def highlight_card(path, card):
            try:
                apply_preview_highlight(
                    card,
                    path,
                    is_selected=self.is_path_selected(path) if path else False,
                    update_style=self.update_card_style,
                )
            except RuntimeError as exc:
                deleted_qobject_guard(exc, "_CardRenderingMixin.update_preview_highlight.highlight_card")

        highlight_card(new_path, self.path_to_card_widget.get(new_path))
        if gallery is not None and hasattr(gallery, "mark_preview"):
            gallery.mark_preview(new_path, True)

    def create_card_widget(self: "AbstractClassSingleGalleryHostProtocol", path: str, pixmap: Optional[QPixmap]) -> QWidget:
        is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
        failed = hasattr(self, "_failed_paths") and path in self._failed_paths
        return create_gallery_card(
            path=path,
            pixmap=pixmap,
            thumb_size=self.thumbnail_size,
            selected=path in self.selected_files,
            variant="single",
            approx_item_width=self.approx_item_width,
            create_label=self.create_gallery_label,
            update_style=self.update_card_style,
            failed=bool(failed),
            is_video=is_video,
            apply_pixmap=lambda container, pix, label: self.update_card_pixmap(
                container, pix, label_ref=label
            ),
        )

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
                    f"border: 2px solid {VIDEO_COLOR}; color: {VIDEO_COLOR}; "
                    "font-weight: bold; background-color: rgba(20, 24, 32, 0.35);"
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
                    f"border: 2px solid {VIDEO_COLOR}; background-color: transparent;"
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
