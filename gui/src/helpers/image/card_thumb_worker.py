"""Async thumbnail infrastructure for listing/entity cards."""

from typing import List, Optional, Tuple

from gui.src.utils.lru_image_cache import LRUImageCache
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QLabel

# Shared LRU cache: stores scaled QImages keyed by absolute path.
# 250 entries ≈ ~30 MB at 130×130 RGBA — well within budget.
_CARD_THUMB_CACHE: LRUImageCache = LRUImageCache(maxsize=250)

# path -> [(label, width, height), ...]
_ThumbWaiter = Tuple[QLabel, int, int]
_THUMB_WAITERS: dict[str, List[_ThumbWaiter]] = {}
_INFLIGHT_PATHS: set[str] = set()


class _ThumbSignalHub(QObject):
    """Persistent signal hub — keeps callbacks alive across QRunnable auto-delete."""

    ready = Signal(str, QImage)  # (absolute_path, scaled QImage)


_THUMB_SIGNAL_HUB: Optional[_ThumbSignalHub] = None


def _thumb_signal_hub() -> _ThumbSignalHub:
    global _THUMB_SIGNAL_HUB
    if _THUMB_SIGNAL_HUB is None:
        _THUMB_SIGNAL_HUB = _ThumbSignalHub()
        app = QApplication.instance()
        if app is not None:
            _THUMB_SIGNAL_HUB.setParent(app)
        _THUMB_SIGNAL_HUB.ready.connect(_dispatch_thumbnail)
    return _THUMB_SIGNAL_HUB


def invalidate_thumbnail_cache(path: str) -> None:
    """Drop cached thumbnails for *path* after the underlying file changes."""
    if not path:
        return
    _CARD_THUMB_CACHE.pop(path, None)
    _CARD_THUMB_CACHE.pop(f"preview160:{path}", None)


class _ThumbWorker(QRunnable):
    """Load and scale a card thumbnail off the main thread."""

    def __init__(self, path: str, size: int):
        super().__init__()
        self.setAutoDelete(True)
        self._path = path
        self._size = size

    @Slot()
    def run(self) -> None:
        try:
            img = QImage(self._path)
            if img.isNull():
                return
            img = img.scaled(
                self._size,
                self._size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            _CARD_THUMB_CACHE[self._path] = img
            _thumb_signal_hub().ready.emit(self._path, img)
        except Exception:
            pass
        finally:
            _INFLIGHT_PATHS.discard(self._path)


def _scale_to_label(pix: QPixmap, width: int, height: int) -> QPixmap:
    return pix.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _dispatch_thumbnail(path: str, img: QImage) -> None:
    waiters = _THUMB_WAITERS.pop(path, [])
    pix = QPixmap.fromImage(img)
    for label, width, height in waiters:
        if label.property("_thumb_path") == path:
            label.setPixmap(_scale_to_label(pix, width, height))
            label.setStyleSheet("")


def _queue_thumbnail_load(path: str, label: QLabel, width: int, height: int, worker_size: int) -> None:
    _thumb_signal_hub()
    _THUMB_WAITERS.setdefault(path, []).append((label, width, height))
    if path in _INFLIGHT_PATHS:
        return
    _INFLIGHT_PATHS.add(path)
    QThreadPool.globalInstance().start(_ThumbWorker(path, worker_size))


def apply_thumbnail_to_label(
    label: QLabel,
    path: str,
    width: int,
    height: int,
    *,
    worker_size: Optional[int] = None,
    placeholder_text: str = "",
    placeholder_style: str = "",
    loading_style: str = "background:#1a1c1e; border-radius:3px;",
) -> None:
    """Populate *label* with a thumbnail for *path*, using cache or async load."""
    label.setProperty("_thumb_path", path or "")

    if not path:
        label.clear()
        label.setText(placeholder_text)
        if placeholder_style:
            label.setStyleSheet(placeholder_style)
        return

    from pathlib import Path

    if not Path(path).exists():
        label.clear()
        label.setText(placeholder_text)
        if placeholder_style:
            label.setStyleSheet(placeholder_style)
        return

    cached = _CARD_THUMB_CACHE.get(path)
    if cached is not None:
        label.setPixmap(_scale_to_label(QPixmap.fromImage(cached), width, height))
        label.setStyleSheet("")
        return

    label.clear()
    label.setText("")
    label.setStyleSheet(loading_style)
    _queue_thumbnail_load(path, label, width, height, worker_size or max(width, height))