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

# Qt's GIF plugin registers socket notifiers on the *calling thread's* event
# loop.  When that thread is a QThreadPool worker, those notifiers point to a
# file descriptor that becomes invalid as soon as the pool recycles the thread
# -- Qt then logs "QSocketNotifier: Invalid socket N and type 'Read',
# disabling..." which corrupts the heap bookkeeping and triggers SIGABRT.
# ffmpeg-from-a-QThreadPool-worker is the same crash class (fork vs Qt
# Multimedia).  The fix for both is the same: never construct QImageReader for
# GIFs on a background thread.  load_qir_thumbnail routes ALL GIFs through
# _gif_first_frame_via_pillow, which uses Pillow's C-level file IO and never
# touches Qt's event dispatcher.  The 32 MB budget is kept as a documentation
# marker and for is_oversized_gif() (still used externally), but is no longer
# used as a branch condition inside load_qir_thumbnail.
QIR_GIF_BYTE_BUDGET = 32 * 1024 * 1024
_PILGIF_CACHE_PREFIX = "qir_pilgif"
_gif_decode_lock = threading.Lock()


def qir_cache_path(path: str, target_size: int, prefix: str = "qir") -> Path:
    key = hashlib.md5(f"{path}:{target_size}".encode("utf-8")).hexdigest()
    return THUMBNAIL_CACHE_DIR / f"{prefix}_{key}.png"


def load_qir_cached(path: str, target_size: int, prefix: str = "qir") -> QImage | None:
    """Return the cached decode, or ``None`` on a cache miss/corrupt entry."""
    cache_path = qir_cache_path(path, target_size, prefix=prefix)
    if not cache_path.exists():
        return None
    image = QImage(str(cache_path))
    return image if not image.isNull() else None


def save_qir_cached(path: str, target_size: int, image: QImage, prefix: str = "qir") -> None:
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
        image.save(str(qir_cache_path(path, target_size, prefix=prefix)), "PNG")
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


def _gif_first_frame_via_pillow(path: str, target_size: int) -> QImage:
    """Decode only frame 0 with Pillow and wrap the RGB buffer in QImage.

    Does not construct QImageReader, QMovie, or ffmpeg. ``n_frames`` is
    never read -- that would scan the whole file. ``Image.thumbnail``
    only downscales, so a 1280x720 frame requested at 1920 stays native.
    """
    from PIL import Image

    size = max(int(target_size), 8)
    with Image.open(path) as source:
        source.seek(0)
        frame = source.convert("RGB")
    frame.thumbnail((size, size), Image.Resampling.BILINEAR)
    width, height = frame.size
    if width <= 0 or height <= 0:
        return QImage()
    rgb = frame.tobytes()
    image = QImage(rgb, width, height, 3 * width, QImage.Format.Format_RGB888)
    return image.copy()


def gif_first_frame(path: str, max_edge: int = 1920) -> QImage:
    """Public first-frame decode for gallery thumbs and full-size preview."""
    with _gif_decode_lock:
        return _gif_first_frame_via_pillow(path, max_edge)


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

    All GIFs are decoded via Pillow (first frame), regardless of file size.
    QImageReader's GIF plugin registers socket notifiers on the calling
    thread's event loop; using it from a QThreadPool worker thread causes
    "QSocketNotifier: Invalid socket N and type 'Read', disabling..." →
    heap corruption → SIGABRT when the pool recycles the thread.
    Non-GIF images still use _qir_read (QImageReader), which is safe on
    worker threads for those formats.
    """
    is_gif = path.lower().endswith(".gif")
    # All GIFs share the Pillow-decoded cache namespace so existing cache
    # entries from either the old oversized branch or this new unified branch
    # are reused without a rebuild.
    cache_prefix = _PILGIF_CACHE_PREFIX if is_gif else "qir"
    cached = load_qir_cached(path, target_size, prefix=cache_prefix)
    if cached is not None:
        return cached

    try:
        if is_gif:
            # Pillow: C-level file IO only, no Qt event loop, no socket
            # notifiers.  Serialised by _gif_decode_lock so concurrent worker
            # threads don't race on the same GIF file.
            with _gif_decode_lock:
                image = _gif_first_frame_via_pillow(path, target_size)
        else:
            image = _qir_read(path, target_size)
    except Exception:
        logger.debug("Suppressed Exception in load_qir_thumbnail", exc_info=True)
        return QImage()

    if image.isNull():
        return image
    save_qir_cached(path, target_size, image, prefix=cache_prefix)
    return image


__all__ = [
    "QIR_GIF_BYTE_BUDGET",
    "qir_cache_path",
    "load_qir_cached",
    "save_qir_cached",
    "load_qir_thumbnail",
    "is_oversized_gif",
    "oversized_gif_placeholder",
    "gif_first_frame",
    "read_gif_logical_screen",
]
