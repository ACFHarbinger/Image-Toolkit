"""QML-facing wrapper slots for directory browsing and conversion start.

Extracted from ``format_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os

from backend.src.constants import SUPPORTED_IMG_FORMATS, SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFileDialog

from .....helpers import ConversionWorker


class _QmlHandlersMixin:
    """QML @Slot wrappers around directory browsing and conversion start."""

    @Slot(str)
    def browse_directory_and_scan_qml(self, current_path=""):
        starting_dir = (
            current_path if os.path.isdir(current_path) else self.last_browsed_dir
        )
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select input directory",
            starting_dir,
        )
        if directory:
            self.input_path.setText(directory)
            self.last_browsed_dir = directory
            self.qml_input_path_changed.emit(directory)
            self.scan_directory_visual()
            return directory
        return ""

    @Slot(str, str, str, bool)
    def start_conversion_worker_qml(
        self, input_path, output_format, output_dir, delete_original
    ):
        """Wrapper for QML to start conversion."""
        if self.worker and self.worker.isRunning():
            self.cancel_conversion()
            return

        if not input_path or not os.path.isdir(input_path):
            return

        # Prepare simple config from QML params
        config = {
            "output_format": output_format,
            "delete_original": delete_original,
            "ar_enabled": False,
            "output_path": output_dir,
            "filename_prefix": "",
            "engine": "Auto (Recommended)",
        }

        # Collect files
        files_for_conversion = []
        input_formats = [f.lower() for f in SUPPORTED_IMG_FORMATS] + [
            f.lstrip(".").lower() for f in SUPPORTED_VIDEO_FORMATS
        ]

        from gui.src.windows.settings.app_settings import AppSettings
        if AppSettings.recursive_scan():
            for root, _, files in os.walk(input_path):
                for file in files:
                    file_ext = os.path.splitext(file)[1].lstrip(".").lower()
                    if file_ext in input_formats:
                        files_for_conversion.append(os.path.join(root, file))
        else:
            with os.scandir(input_path) as it:
                for entry in it:
                    if entry.is_file():
                        file_ext = os.path.splitext(entry.name)[1].lstrip(".").lower()
                        if file_ext in input_formats:
                            files_for_conversion.append(entry.path)

        config["files_to_convert"] = files_for_conversion

        if not files_for_conversion:
            return

        self.btn_convert_all.setEnabled(False)
        self.convert_progress_bar.show()
        self.convert_progress_bar.setValue(0)
        self.status_label.setText("Starting conversion (QML)...") # pyrefly: ignore [missing-attribute]

        self.worker = ConversionWorker(config)
        self.worker.progress_signal.connect(self.update_progress_bar)
        self.worker.finished_signal.connect(self.on_conversion_done)
        self.worker.start()


__all__ = ["_QmlHandlersMixin"]
