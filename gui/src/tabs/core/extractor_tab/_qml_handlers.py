"""QML bridge slots (Video subtab).

Extracted from ``extractor_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Optional, cast

from PySide6.QtCore import QThreadPool, Slot
from PySide6.QtWidgets import QFileDialog, QWidget

from ....helpers import FrameExtractionWorker

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..protos.extractor_tab import VideoExtractorSubTabHostProtocol


class _QmlHandlersMixin:
    """QML bridge slots for the Video subtab."""

    active_extraction_worker: Optional[Any]

    @Slot(str)
    def browse_source_qml(self: "VideoExtractorSubTabHostProtocol", current_path=""):
        starting_dir = (
            current_path if os.path.isdir(current_path) else self.last_browsed_scan_dir
        )
        d = QFileDialog.getExistingDirectory(
            cast(QWidget, self), "Select Source Directory", starting_dir
        )
        if d:
            self.line_edit_dir.setText(d)  # Sync widget
            self.last_browsed_scan_dir = d
            self.qml_source_path_changed.emit(d)
            self.scan_directory(d)  # Triggers scanner
            # Note: The scanner populates self.source_grid (QWidget).
            # For QML, we might need to expose the file list via a model or JSON signal.
            # For now, we assume the QML side will use a FolderListModel or similar if it wants to show the list,
            # or we rely on the backend to just handle the logic.
            # Ideally, we should emit a list of found videos.
            return d
        return ""

    @Slot(str, int)
    def extract_single_frame_qml(self: "VideoExtractorSubTabHostProtocol", video_path, timestamp_ms):
        """Extracts a single frame at the given timestamp (ms)."""
        if not video_path or not os.path.exists(video_path):
            self.qml_extraction_status.emit("Error: Video not found")
            return

        # Use backend logic
        self.video_path = video_path  # Set current context

        output_dir = self.extraction_dir
        filename = f"{Path(video_path).stem}_{timestamp_ms}ms.png"
        out_path = output_dir / filename

        # Run in thread to not block UI
        QThreadPool.globalInstance().start(
            lambda: self._quick_extract(video_path, timestamp_ms, str(out_path))
        )

    def _quick_extract(self: "VideoExtractorSubTabHostProtocol", vid_path, ms, out_path):
        try:
            t_start = ms / 1000.0

            # Use FFmpeg for robustness against codec issues (like AV1 headers)
            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(t_start),
                "-i",
                vid_path,
                "-vframes",
                "1",
                "-q:v",
                "2",
                out_path,
            ]

            # Hide console on windows if needed (usually handled by subprocess)
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0 and os.path.exists(out_path):
                self.qml_extraction_status.emit(f"Saved: {os.path.basename(out_path)}")
            else:
                error = (
                    result.stderr if result.stderr else "FFmpeg failed to extract frame"
                )
                self.qml_extraction_status.emit(f"Error: {error}")

        except Exception as e:
            self.qml_extraction_status.emit(f"Error: {e}")

    @Slot(str, int, int, int)
    def extract_range_qml(self: "VideoExtractorSubTabHostProtocol", video_path, start_ms, end_ms, fps):
        """Extracts frames in range."""
        if not video_path or not os.path.exists(video_path):
            self.qml_extraction_status.emit("Error: Invalid video")
            return

        self.video_path = video_path

        # Setup worker
        worker = FrameExtractionWorker(video_path, str(self.extraction_dir), start_ms, end_ms, fps, output_format="png", target_resolution=None)
        self.active_extraction_worker = worker

        # Signals
        worker.signals.finished.connect(
            lambda: self.qml_extraction_status.emit("Extraction Finished")
        )
        worker.signals.error.connect(
            lambda e: self.qml_extraction_status.emit(f"Error: {e}")
        )
        worker.signals.progress.connect(
            lambda val, msg: self.qml_extraction_status.emit(f"Progress: {val}%")
        )

        QThreadPool.globalInstance().start(worker)


__all__ = ["_QmlHandlersMixin"]
