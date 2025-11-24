import os
import cv2

from pathlib import Path
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Signal, QRunnable, QObject
from backend.src.utils.definitions import SUPPORT_VIDEO_FORMATS


# --- Helper Worker for Asynchronous Video Scanning ---
class VideoScanSignals(QObject):
    thumbnail_ready = Signal(str, QPixmap) # path, pixmap
    finished = Signal()


class VideoScanWorker(QRunnable):
    """Scans a directory for videos/gifs and generates thumbnails."""
    def __init__(self, directory):
        super().__init__()
        self.directory = directory
        self.signals = VideoScanSignals()

    def run(self):
        if not os.path.isdir(self.directory):
            self.signals.finished.emit()
            return

        # Sort for consistent order
        try:
            entries = sorted(os.scandir(self.directory), key=lambda e: e.name.lower())
            for entry in entries:
                if entry.is_file():
                    ext = Path(entry.path).suffix.lower()
                    if ext in SUPPORT_VIDEO_FORMATS:
                        pixmap = self.generate_thumbnail(entry.path)
                        if pixmap:
                            self.signals.thumbnail_ready.emit(entry.path, pixmap)
        except Exception:
            pass
        
        self.signals.finished.emit()

    def generate_thumbnail(self, path):
        try:
            cap = cv2.VideoCapture(path)
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                # Convert BGR (OpenCV) to RGB (Qt)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = frame.shape
                bytes_per_line = ch * w
                q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                return QPixmap.fromImage(q_img)
        except Exception:
            pass
        return None
