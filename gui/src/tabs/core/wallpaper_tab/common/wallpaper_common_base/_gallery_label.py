"""Draggable gallery label creation and thumbnail cache helpers.

Extracted from ``wallpaper_common_base.py`` -- pure code motion, no logic
change (see ``_monitor_selection.py``'s docstring).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QImageReader, QPixmap
from PySide6.QtWidgets import QLabel

from ......components import DraggableLabel

if TYPE_CHECKING:
    from ....protos.wallpaper_common_base import WallpaperCommonBaseHostProtocol


class _GalleryLabelMixin:
    """Build draggable gallery labels; resolve/generate their thumbnails."""

    def create_gallery_label(self: "WallpaperCommonBaseHostProtocol", path: str, size: int) -> QLabel:
        draggable_label = DraggableLabel(
            path, size, selection_provider=lambda: self.selected_files
        )
        draggable_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        draggable_label.path_clicked.connect(self.toggle_selection)
        draggable_label.path_double_clicked.connect(self.handle_thumbnail_double_click)
        draggable_label.path_right_clicked.connect(self.show_image_context_menu)

        self.path_to_label_map[path] = draggable_label
        return draggable_label

    # ---- Thumbnail helpers -----------------------------------------------

    def _cache_get_thumb(self: "WallpaperCommonBaseHostProtocol", path: str) -> Optional[QPixmap]:
        img = self._initial_pixmap_cache.get(path)
        if img is None:
            return None
        return QPixmap.fromImage(img) if isinstance(img, QImage) else img

    def _get_or_generate_thumbnail(self: "WallpaperCommonBaseHostProtocol", path: str) -> Optional[QPixmap]:
        if not path:
            return None
        thumb = self._cache_get_thumb(path)
        if not thumb:
            if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                thumb = self._generate_video_thumbnail(path)
                if thumb:
                    self._initial_pixmap_cache[path] = thumb.toImage()
            elif os.path.exists(path):
                reader = QImageReader(path)
                source_size = reader.size()
                target_size = QSize(self.thumbnail_size, self.thumbnail_size)
                if source_size.isValid():
                    source_size.scale(
                        target_size, Qt.AspectRatioMode.KeepAspectRatio
                    )
                    reader.setScaledSize(source_size)
                image = reader.read()
                if not image.isNull():
                    if image.width() > self.thumbnail_size or image.height() > self.thumbnail_size:
                        image = image.scaled(
                            target_size,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    self._initial_pixmap_cache[path] = image
                    thumb = QPixmap.fromImage(image)
        return thumb


__all__ = ["_GalleryLabelMixin"]
