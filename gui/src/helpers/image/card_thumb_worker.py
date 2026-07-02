"""Async thumbnail infrastructure for listing/entity cards."""

from PySide6.QtCore import Qt, Signal, Slot, QObject, QRunnable
from PySide6.QtGui import QImage

from gui.src.utils.lru_image_cache import LRUImageCache


# Shared LRU cache: stores scaled QImages keyed by absolute path.
# 250 entries ≈ ~30 MB at 130×130 RGBA — well within budget.
_CARD_THUMB_CACHE: LRUImageCache = LRUImageCache(maxsize=250)


class _ThumbWorkerSignals(QObject):
    ready = Signal(str, QImage)  # (absolute_path, scaled QImage)


class _ThumbWorker(QRunnable):
    """Load and scale a card thumbnail off the main thread."""

    def __init__(self, path: str, size: int):
        super().__init__()
        self.setAutoDelete(True)
        self._path = path
        self._size = size
        self.signals = _ThumbWorkerSignals()

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
            self.signals.ready.emit(self._path, img)
        except Exception:
            pass
