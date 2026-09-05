"""Disk-cache read/write for the QImageReader decode path.

``native_load_batch`` (``base.load_image_batch``) writes/reads
``THUMBNAIL_CACHE_DIR`` itself, in C++. The QImageReader fallback path
(``_load_via_qimagereader`` in ``image_loader_worker.py`` and
``_load_one_via_qimage`` in ``batch_image_loader_worker.py`` -- used for
every GIF, since GIFs never touch the native decoder) had no disk-cache
participation at all: every view/scroll re-decoded from scratch. This
gives it its own cache entries, namespaced separately (``qir_`` prefix)
so they can never collide with whatever key scheme the native side uses
internally.

Deliberately as simple as the existing video-thumbnail disk cache
(``abstract_class_single_gallery/_disk_cache.py``): keyed on
``path + target_size`` only, no mtime invalidation. Matches that
established convention rather than introducing a new one.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from backend.src.constants import THUMBNAIL_CACHE_DIR
from PySide6.QtGui import QImage


def qir_cache_path(path: str, target_size: int) -> Path:
    key = hashlib.md5(f"{path}:{target_size}".encode("utf-8")).hexdigest()
    return THUMBNAIL_CACHE_DIR / f"qir_{key}.png"


def load_qir_cached(path: str, target_size: int) -> QImage | None:
    """Return the cached decode, or ``None`` on a cache miss/corrupt entry."""
    cache_path = qir_cache_path(path, target_size)
    if not cache_path.exists():
        return None
    image = QImage(str(cache_path))
    return image if not image.isNull() else None


def save_qir_cached(path: str, target_size: int, image: QImage) -> None:
    """Best-effort write; a failed cache write must never fail the load."""
    if image.isNull():
        return
    try:
        THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        # NOTE: `format` must be `str` ("PNG"), not `bytes` (b"PNG") -- the
        # latter raises ValueError under this PySide6 version's overload
        # resolution (verified empirically). The existing video-thumbnail
        # disk cache (_disk_cache.py) uses the bytes form and silently
        # swallows the resulting exception the same way -- flagged
        # separately, not fixed here.
        image.save(str(qir_cache_path(path, target_size)), "PNG")
    except Exception:
        pass


__all__ = ["qir_cache_path", "load_qir_cached", "save_qir_cached"]
