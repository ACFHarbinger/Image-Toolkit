import os
import cv2
import time

from pathlib import Path
from PySide6.QtCore import QRunnable, Signal, QObject
from typing import Optional, Tuple


# --- Worker Signals ---
class ExtractorSignals(QObject):
    started = Signal()
    progress = Signal(int)
    finished = Signal(list)  # Returns list of saved paths
    error = Signal(str)


# --- Worker Logic (OpenCV) ---
class FrameExtractionWorker(QRunnable):
    """
    Background worker to extract frames using OpenCV to ensure
    frame-accurate extraction without freezing the UI.
    """

    def __init__(
        self,
        video_path: str,
        output_dir: str,
        start_ms: int,
        end_ms: int = -1,
        is_range: bool = False,
        target_resolution: Optional[Tuple[int, int]] = None,
    ):
        super().__init__()
        self.video_path = video_path
        self.output_dir = output_dir
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.is_range = is_range
        self.target_resolution = target_resolution  # (width, height)
        self.signals = ExtractorSignals()
        self._is_cancelled = False

    def run(self):
        self.signals.started.emit()
        saved_files = []

        try:
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                self.signals.error.emit("Could not open video file.")
                return

            # Seek to start
            cap.set(cv2.CAP_PROP_POS_MSEC, self.start_ms)

            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30  # Fallback

            # Generate Base Filename
            video_name = Path(self.video_path).stem
            timestamp = int(time.time())

            while not self._is_cancelled:
                ret, frame = cap.read()
                if not ret:
                    break

                # --- RESIZE LOGIC ---
                if self.target_resolution:
                    # Resize the frame to the requested dimensions
                    frame = cv2.resize(
                        frame, self.target_resolution, interpolation=cv2.INTER_AREA
                    )

                current_ms = cap.get(cv2.CAP_PROP_POS_MSEC)

                # Save Frame
                filename = f"{video_name}_{timestamp}_{int(current_ms)}ms.jpg"
                save_path = os.path.join(self.output_dir, filename)
                cv2.imwrite(save_path, frame)
                saved_files.append(save_path)

                # If Single Snapshot mode, break immediately
                if not self.is_range:
                    break

                # If Range mode, check end condition
                if self.end_ms != -1 and current_ms >= self.end_ms:
                    break

            cap.release()
            self.signals.finished.emit(saved_files)

        except Exception as e:
            self.signals.error.emit(str(e))

    def cancel(self):
        self._is_cancelled = True
