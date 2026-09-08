"""Play GIFs by seeking Pillow frames on a QTimer.

Qt's QMovie/QImageReader GIF plugin materializes multi-hundred-MB files
and SIGSEGVs this process. Pillow seek() is sequential and keeps one
frame in memory. No Qt image plugin, no ffmpeg.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QImage


class PillowGifPlayer(QObject):
    """Loop a GIF as static QImage frames. GUI-thread timer, Pillow decode."""

    frame_ready = Signal(QImage)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance)
        self._im = None
        self._index = 0
        self._max_edge = 1920

    def is_running(self) -> bool:
        return self._im is not None

    def start(self, path: str, max_edge: int = 1920) -> bool:
        self.stop()
        from PIL import Image

        try:
            image = Image.open(path)
            image.seek(0)
        except Exception:
            return False
        self._im = image
        self._index = 0
        self._max_edge = max(int(max_edge), 8)
        self._emit_current()
        return True

    def stop(self) -> None:
        self._timer.stop()
        if self._im is not None:
            try:
                self._im.close()
            except Exception:
                pass
            self._im = None
        self._index = 0

    def _frame_to_qimage(self) -> QImage:
        frame = self._im.convert("RGB")
        frame.thumbnail((self._max_edge, self._max_edge))
        width, height = frame.size
        if width <= 0 or height <= 0:
            return QImage()
        rgb = frame.tobytes()
        image = QImage(rgb, width, height, 3 * width, QImage.Format.Format_RGB888)
        return image.copy()

    def _emit_current(self) -> None:
        if self._im is None:
            return
        image = self._frame_to_qimage()
        if not image.isNull():
            self.frame_ready.emit(image)
        duration = int(self._im.info.get("duration") or 100)
        if duration < 20:
            duration = 100
        self._timer.start(duration)

    def _advance(self) -> None:
        if self._im is None:
            return
        try:
            self._im.seek(self._index + 1)
            self._index += 1
        except EOFError:
            try:
                self._im.seek(0)
                self._index = 0
            except Exception:
                self.stop()
                return
        self._emit_current()


__all__ = ["PillowGifPlayer"]
