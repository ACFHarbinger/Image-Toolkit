import os
import cv2

from pathlib import Path
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Signal, QRunnable, QObject
from backend.src.utils.definitions import SUPPORTED_VIDEO_FORMATS

try:
    import base
    HAS_NATIVE_IMAGING = True
except ImportError:
    HAS_NATIVE_IMAGING = False


class VideoScanSignals(QObject):
    thumbnail_ready = Signal(str, QPixmap)  # path, pixmap
    finished = Signal()


class VideoScannerWorker(QRunnable):
    """
    Scans a directory for videos/gifs and generates thumbnails.
    """

    def __init__(self, directory):
        super().__init__()
        self.directory = directory
        self.signals = VideoScanSignals()
        self.is_cancelled = False
        self.batch_size = 8  # Process 8 videos at a time in Rust

    def stop(self):
        """Signals the worker to stop scanning."""
        self.is_cancelled = True

    def run(self):
        if self.is_cancelled:
            return

        if not os.path.isdir(self.directory):
            self.signals.finished.emit()
            return

        try:
            if HAS_NATIVE_IMAGING:
                video_paths = base.scan_files(
                    [self.directory], list(SUPPORTED_VIDEO_FORMATS), False
                )
            else:
                entries = sorted(os.scandir(self.directory), key=lambda e: e.name.lower())
                video_paths = [
                    e.path
                    for e in entries
                    if e.is_file() and Path(e.path).suffix.lower() in SUPPORTED_VIDEO_FORMATS
                ]

            if not video_paths:
                self.signals.finished.emit()
                return

            if HAS_NATIVE_IMAGING:
                # Process in batches using the new Rust worker
                for i in range(0, len(video_paths), self.batch_size):
                    if self.is_cancelled:
                        return
                    
                    batch = video_paths[i : i + self.batch_size]
                    
                    results = base.extract_video_thumbnails_batch(batch, 180)
                    for path, buf, w, h in results:
                        if self.is_cancelled:
                            return
                        
                        q_img = QImage(buf, w, h, QImage.Format_RGBA8888)
                        pixmap = QPixmap.fromImage(q_img.copy())
                        self.signals.thumbnail_ready.emit(path, pixmap)
            else:
                # Fallback to sequential OpenCV
                for path in video_paths:
                    if self.is_cancelled:
                        return
                    pixmap = self._generate_thumbnail_opencv(path)
                    if pixmap:
                        self.signals.thumbnail_ready.emit(path, pixmap)

        except Exception:
            pass

        self.signals.finished.emit()

    def _generate_thumbnail_opencv(self, path):
        try:
            cap = cv2.VideoCapture(path)
            cap.set(cv2.CAP_PROP_POS_FRAMES, 300)
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 30)
                ret, frame = cap.read()
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
            cap.release()
            
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = frame.shape
                bytes_per_line = ch * w
                q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
                return QPixmap.fromImage(q_img)
        except Exception:
            pass
        return None
