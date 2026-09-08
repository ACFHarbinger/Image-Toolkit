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
import logging
import os
import threading
from pathlib import Path

from backend.src.constants import THUMBNAIL_CACHE_DIR
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QImageReader

logger = logging.getLogger(__name__)

# Qt's GIF plugin does not scaled-decode, and with
# QImageReader.setAllocationLimit(10000) it will try to materialize
# multi-GB extraction GIFs. ffmpeg-from-a-QThreadPool-worker is the
# same QSocketNotifier crash class (fork vs Qt Multimedia). Oversized
# GIFs therefore get a placeholder: no QImageReader, no ffmpeg.
QIR_GIF_BYTE_BUDGET = 32 * 1024 * 1024
_gif_decode_lock = threading.Lock()

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
        logger.debug("Suppressed Exception in save_qir_cached", exc_info=True)


def _file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _qir_read(path: str, target_size: int) -> QImage:
    reader = QImageReader(path)
    source_size = reader.size()
    target = QSize(target_size, target_size)
    if source_size.isValid():
        source_size.scale(target, Qt.AspectRatioMode.KeepAspectRatio)
        reader.setScaledSize(source_size)
    image = reader.read()
    if image.isNull():
        return QImage()
    if image.width() > target_size or image.height() > target_size:
        image = image.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return image


def is_oversized_gif(path: str) -> bool:
    return path.lower().endswith(".gif") and _file_size(path) > QIR_GIF_BYTE_BUDGET


def oversized_gif_placeholder(target_size: int) -> QImage:
    size = max(int(target_size), 8)
    image = QImage(size, size, QImage.Format.Format_RGB32)
    image.fill(0xFF2C2F33)
    return image


def read_gif_logical_screen(path: str) -> tuple[int, int] | None:
    """Width/height from the GIF header only -- never constructs QImageReader."""
    try:
        with open(path, "rb") as handle:
            header = handle.read(10)
    except OSError:
        return None
    if len(header) < 10 or header[:6] not in (b"GIF87a", b"GIF89a"):
        return None
    width = int.from_bytes(header[6:8], "little")
    height = int.from_bytes(header[8:10], "little")
    if width <= 0 or height <= 0:
        return None
    return width, height


def load_qir_thumbnail(path: str, target_size: int) -> QImage:
    """Load a thumbnail, using the QIR disk cache.

    Small GIFs still go through Qt's GIF plugin (first frame). Oversized
    GIFs never construct ``QImageReader`` and never spawn ffmpeg -- both
    of those paths SIGSEGV/SIGABRT this process on the Cinematography
    corpus. A cheap placeholder is cached instead.
    """
    cached = load_qir_cached(path, target_size)
    if cached is not None:
        return cached

    is_gif = path.lower().endswith(".gif")
    try:
        if is_gif:
            with _gif_decode_lock:
                if _file_size(path) > QIR_GIF_BYTE_BUDGET:
                    image = oversized_gif_placeholder(target_size)
                else:
                    image = _qir_read(path, target_size)
        else:
            image = _qir_read(path, target_size)
    except Exception:
        logger.debug("Suppressed Exception in load_qir_thumbnail", exc_info=True)
        return QImage()

    if not image.isNull():
        save_qir_cached(path, target_size, image)
    return image


__all__ = [
    "QIR_GIF_BYTE_BUDGET",
    "qir_cache_path",
    "load_qir_cached",
    "save_qir_cached",
    "load_qir_thumbnail",
    "is_oversized_gif",
    "oversized_gif_placeholder",
    "read_gif_logical_screen",
]
