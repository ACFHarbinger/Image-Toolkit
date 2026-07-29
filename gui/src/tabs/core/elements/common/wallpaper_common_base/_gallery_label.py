"""Draggable gallery label creation and thumbnail cache helpers.

Extracted from ``wallpaper_common_base.py`` -- pure code motion, no logic
change (see ``_monitor_selection.py``'s docstring).
"""

from __future__ import annotations

import os
from typing import Optional

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel

from ......components import DraggableLabel


class _GalleryLabelMixin:
    """Build draggable gallery labels; resolve/generate their thumbnails."""

    def create_gallery_label(self, path: str, size: int) -> QLabel:
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

    def _cache_get_thumb(self, path: str) -> Optional[QPixmap]:
        img = self._initial_pixmap_cache.get(path)
        if img is None:
            return None
        return QPixmap.fromImage(img) if isinstance(img, QImage) else img

    def _get_or_generate_thumbnail(self, path: str) -> Optional[QPixmap]:
        if not path:
            return None
        thumb = self._cache_get_thumb(path)
        if not thumb:
            if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                thumb = self._generate_video_thumbnail(path)
                if thumb:
                    self._initial_pixmap_cache[path] = thumb.toImage()
            elif os.path.exists(path):
                thumb = QPixmap(path)
        return thumb


__all__ = ["_GalleryLabelMixin"]
