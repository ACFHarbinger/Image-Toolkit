"""On-disk video-thumbnail cache path and synchronous fallback generation.

Extracted from ``abstract_class_single_gallery.py`` -- pure code motion, no
logic change.
"""

from __future__ import annotations

import hashlib
import os
from typing import Optional

from backend.src.constants import THUMBNAIL_CACHE_DIR
from PySide6.QtGui import QImage, QPixmap

from ...helpers.video.video_scan_worker import VideoThumbnailer


class _DiskCacheMixin:
    """Disk-backed video thumbnail cache path derivation and generation."""

    def _get_disk_cache_path(self, video_path: str) -> str:
        THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path_hash = hashlib.md5(video_path.encode('utf-8')).hexdigest()
        return str(THUMBNAIL_CACHE_DIR / f"{path_hash}.jpg")

    def _generate_video_thumbnail(self, path: str) -> Optional[QPixmap]:
        """
        Generates a video thumbnail synchronously on demand.
        Used for fallback or when immediate preview is needed.
        """
        try:
            # 1. Check disk cache first
            cache_path = self._get_disk_cache_path(path)
            if os.path.exists(cache_path):
                img = QImage(cache_path)
                if not img.isNull():
                    return QPixmap.fromImage(img)

            # 2. Generate new
            thumbnailer = VideoThumbnailer()
            image = thumbnailer.generate(path, self.thumbnail_size)
            if image and not image.isNull():
                # 3. Save to disk cache
                image.save(cache_path, "JPG") # pyrefly: ignore [no-matching-overload]
                return QPixmap.fromImage(image)
        except Exception as e:
            print(f"Failed to generate explicit video thumbnail for {path}: {e}")
        return None


__all__ = ["_DiskCacheMixin"]
