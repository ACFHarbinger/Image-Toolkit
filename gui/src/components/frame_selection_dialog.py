import cv2
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QObject, QThread, QTimer, QSize
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
)


def extract_video_frame_via_ffmpeg(
    video_path: str, frame_idx: int, total_frames: int, fps: float
):
    if not fps or fps <= 0:
        fps = 24.0
    seconds = frame_idx / fps

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_name = tmp.name

    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{seconds:.3f}",
            "-i",
            video_path,
            "-vframes",
            "1",
            "-update",
            "1",
            tmp_name,
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0 and Path(tmp_name).exists():
            img = cv2.imread(tmp_name)
            if img is not None:
                return img
    except Exception as e:
        print(f"ffmpeg fallback failed: {e}")
    finally:
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except Exception:
            pass
    return None


class _FrameWorkerSignals(QObject):
    frame_ready = Signal(object)  # emits a numpy ndarray (BGR)
    failed = Signal()


class _FrameWorker(QThread):
    """Extracts a single video frame off the main thread via ffmpeg subprocess.

    Cancellable: if a new request arrives before the previous finishes, the
    caller sets `_cancelled = True` and the worker discards its result.
    """

    def __init__(self, video_path: str, frame_idx: int, total_frames: int, fps: float):
        super().__init__()
        self.video_path = video_path
        self.frame_idx = frame_idx
        self.total_frames = total_frames
        self.fps = fps
        self.signals = _FrameWorkerSignals()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        frame = extract_video_frame_via_ffmpeg(
            self.video_path, self.frame_idx, self.total_frames, self.fps
        )
        if self._cancelled:
            return
        if frame is not None:
            self.signals.frame_ready.emit(frame)
        else:
            self.signals.failed.emit()


class FrameSelectionDialog(QDialog):
    def __init__(self, file_path: str, start_ms: int = -1, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Representative Frame / Thumbnail")
        self.setMinimumSize(500, 600)
        self.file_path = file_path
        self.start_ms = start_ms
        self.selected_image = None
        self.selected_frame_idx = -1

        self.p = Path(file_path)
        self.suffix = self.p.suffix.lower()

        self.cap = None
        self.pdf_doc = None
        self.total_frames = 0
        self.fps = 24.0

        # Debounce timer + current worker for async frame extraction
        self._frame_timer = QTimer(self)
        self._frame_timer.setSingleShot(True)
        self._frame_timer.setInterval(180)  # ms idle before firing
        self._frame_timer.timeout.connect(self._start_frame_worker)
        self._frame_worker: Optional[_FrameWorker] = None

        self._init_ui()
        self._load_file()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #2c2f33;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QPushButton {
                background-color: #7289da;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #677bc4;
            }
            QSlider::groove:horizontal {
                border: 1px solid #4f545c;
                height: 8px;
                background: #1a1c1e;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #00bcd4;
                border: 1px solid #0097a7;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QSpinBox {
                background-color: #1a1c1e;
                color: white;
                border: 1px solid #4f545c;
                border-radius: 4px;
                padding: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.info_lbl = QLabel(f"File: {self.p.name}")
        self.info_lbl.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #00bcd4;"
        )
        layout.addWidget(self.info_lbl)

        self.preview_lbl = QLabel("Loading preview...")
        self.preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_lbl.setMinimumSize(400, 400)
        self.preview_lbl.setStyleSheet(
            "background-color: #1a1c1e; border: 2px solid #4f545c; border-radius: 8px;"
        )
        layout.addWidget(self.preview_lbl, 1)

        self.controls_layout = QHBoxLayout()
        layout.addLayout(self.controls_layout)

        btns_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("background-color: #4f545c;")
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton("Select Frame / Page")
        self.save_btn.clicked.connect(self.accept)

        btns_layout.addStretch()
        btns_layout.addWidget(self.cancel_btn)
        btns_layout.addWidget(self.save_btn)
        layout.addLayout(btns_layout)

    def _load_file(self):
        if self.suffix == ".pdf":
            try:
                from PySide6.QtPdf import QPdfDocument

                self.pdf_doc = QPdfDocument()
                if (
                    self.pdf_doc.load(str(self.p.absolute()))
                    == QPdfDocument.Status.Ready
                ):
                    page_count = self.pdf_doc.pageCount()

                    self.page_spin = QSpinBox()
                    self.page_spin.setRange(1, page_count)
                    self.page_spin.setValue(1)
                    self.page_spin.valueChanged.connect(self._update_pdf_preview)

                    self.controls_layout.addWidget(QLabel("Page:"))
                    self.controls_layout.addWidget(self.page_spin)
                    self.controls_layout.addWidget(QLabel(f"of {page_count}"))
                    self.controls_layout.addStretch()

                    self._update_pdf_preview()
                else:
                    self.preview_lbl.setText("Failed to load PDF.")
            except Exception as e:
                self.preview_lbl.setText(f"Error loading PDF: {e}")

        elif self.suffix in (".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".m4v"):
            try:
                # Use OpenCV only to probe metadata (no actual decoding)
                try:
                    probe = cv2.VideoCapture(
                        str(self.p.absolute()),
                        cv2.CAP_FFMPEG,
                        [cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_NONE],
                    )
                except Exception:
                    probe = cv2.VideoCapture(str(self.p.absolute()))

                if probe.isOpened():
                    self.total_frames = int(probe.get(cv2.CAP_PROP_FRAME_COUNT)) or 1000
                    self.fps = probe.get(cv2.CAP_PROP_FPS) or 24.0
                    probe.release()

                    self.slider = QSlider(Qt.Orientation.Horizontal)
                    self.slider.setRange(0, self.total_frames - 1)
                    
                    if self.start_ms >= 0:
                        start_frame = int(self.start_ms / 1000.0 * self.fps)
                        start_frame = min(max(0, start_frame), self.total_frames - 1)
                    else:
                        start_frame = min(
                            max(1, self.total_frames // 10), self.total_frames - 1
                        )
                        
                    self.slider.setValue(start_frame)
                    # Debounce: slider movement restarts the timer instead of
                    # calling the (slow) extraction synchronously each tick
                    self.slider.valueChanged.connect(self._schedule_video_preview)

                    self.frame_spin = QSpinBox()
                    self.frame_spin.setRange(0, self.total_frames - 1)
                    self.frame_spin.setValue(start_frame)
                    self.frame_spin.valueChanged.connect(self.slider.setValue)
                    self.slider.valueChanged.connect(self.frame_spin.setValue)

                    self.controls_layout.addWidget(QLabel("Frame:"))
                    self.controls_layout.addWidget(self.slider, 1)
                    self.controls_layout.addWidget(self.frame_spin)

                    # Kick off the first frame immediately (no debounce needed)
                    self._start_frame_worker()
                else:
                    self.preview_lbl.setText("Failed to open Video.")
            except Exception as e:
                self.preview_lbl.setText(f"Error opening Video: {e}")
        else:
            self.preview_lbl.setText("Unsupported format.")
            self.save_btn.setEnabled(False)

    def _update_pdf_preview(self):
        if not self.pdf_doc:
            return
        page_index = self.page_spin.value() - 1
        qimg = self.pdf_doc.render(page_index, QSize(400, 500))
        if not qimg.isNull():
            self.selected_image = qimg
            self.selected_frame_idx = page_index
            px = QPixmap.fromImage(qimg).scaled(
                380, 380, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.preview_lbl.setPixmap(px)

    def _schedule_video_preview(self):
        """Called on every slider tick — just restarts the debounce timer."""
        self._frame_timer.start()

    def _clear_worker(self, worker):
        if self._frame_worker is worker:
            self._frame_worker = None

    def _start_frame_worker(self):
        """Fired by the debounce timer; cancels any in-flight worker and starts a new one."""
        # Cancel previous extraction if still running
        if self._frame_worker is not None:
            try:
                if self._frame_worker.isRunning():
                    self._frame_worker.cancel()
                    self._frame_worker.signals.frame_ready.disconnect()
                    self._frame_worker.signals.failed.disconnect()
            except RuntimeError:
                pass
            self._frame_worker = None

        frame_idx = self.slider.value()
        self.preview_lbl.setText("Loading…")

        worker = _FrameWorker(
            str(self.p.absolute()), frame_idx, self.total_frames, self.fps
        )
        worker.signals.frame_ready.connect(self._on_frame_ready)
        worker.signals.failed.connect(self._on_frame_failed)
        # Clear local reference when finished, then clean up the C++ object
        worker.finished.connect(lambda: self._clear_worker(worker))
        worker.finished.connect(worker.deleteLater)
        self._frame_worker = worker
        worker.start()

    def _on_frame_ready(self, frame):
        """Slot called from worker signal (marshalled to main thread by Qt)."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
        self.selected_image = qimg
        self.selected_frame_idx = self.slider.value()
        px = QPixmap.fromImage(qimg).scaled(
            380, 380, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.preview_lbl.setPixmap(px)

    def _on_frame_failed(self):
        self.preview_lbl.setText("Failed to decode frame from video.")

    def closeEvent(self, event):
        # Stop debounce timer and cancel any running worker cleanly
        self._frame_timer.stop()
        if self._frame_worker is not None:
            try:
                if self._frame_worker.isRunning():
                    self._frame_worker.cancel()
                    self._frame_worker.wait(500)  # give it up to 500 ms to exit
            except RuntimeError:
                pass
        if self.cap:
            self.cap.release()
        super().closeEvent(event)
