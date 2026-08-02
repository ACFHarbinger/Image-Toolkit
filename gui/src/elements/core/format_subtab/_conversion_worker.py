"""Conversion worker dispatch (start/cancel/progress/finished/error).

Extracted from ``format_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox

from ....helpers import ConversionWorker
from ....styles import SHARED_BUTTON_STYLE


class _ConversionWorkerMixin:
    """Starts/cancels the ConversionWorker and reacts to its progress/outcome."""

    @Slot(bool)
    def start_conversion_worker(self, use_selection: bool = False):
        if self.worker and self.worker.isRunning():
            self.cancel_conversion()
            return

        p = self.input_path.text().strip()
        if not p or not os.path.isdir(p):
            QMessageBox.warning(self, "Invalid", "Please select a valid directory.")
            return

        files_for_conversion = (
            self.selected_files if use_selection else self.collect_paths()
        )

        if not files_for_conversion:
            QMessageBox.warning(self, "No Files", "No files to convert.")
            return

        config = self.collect()
        config["files_to_convert"] = files_for_conversion

        # UI Updates
        self.btn_convert_all.setEnabled(False)
        self.btn_convert_contents.setEnabled(False)

        button_to_cancel = (
            self.btn_convert_contents if use_selection else self.btn_convert_all
        )
        button_to_cancel.setEnabled(True)
        button_to_cancel.setText("Cancel Conversion")
        button_to_cancel.setStyleSheet(
            """
            QPushButton { background-color: #cc3333; color: white; font-weight: bold; }
        """
        )

        self.status_label.setText(f"Converting {len(files_for_conversion)} files...") # pyrefly: ignore [missing-attribute]
        self.convert_progress_bar.show()  # Show the new progress bar

        self.worker = ConversionWorker(config)
        self.worker.finished_signal.connect(self.on_conversion_done)
        self.worker.error_signal.connect(self.on_conversion_error)
        self.worker.progress_signal.connect(self.update_progress_bar)
        self.worker.start()

    def cancel_conversion(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
            self.on_conversion_done(0, "**Conversion cancelled**")
            self.worker = None

    @Slot(int, int)
    def update_progress_bar(self, completed: int, total: int):
        self.convert_progress_bar.setMaximum(max(total, 1))
        self.convert_progress_bar.setValue(completed)
        percentage = int(completed / total * 100) if total else 0
        self.status_label.setText(f"Converting... {percentage}% complete") # pyrefly: ignore [missing-attribute]

    @Slot(int, str)
    def on_conversion_done(self, count, msg):
        # Reset UI elements
        self.btn_convert_all.setEnabled(True)
        self.btn_convert_all.setText("Convert All in Directory")
        self.btn_convert_all.setStyleSheet(SHARED_BUTTON_STYLE)

        self.on_selection_changed()
        self.btn_convert_contents.setStyleSheet(SHARED_BUTTON_STYLE)

        self.convert_progress_bar.hide()
        self.convert_progress_bar.setValue(0)  # Reset value
        self.status_label.setText(f"{msg}") # pyrefly: ignore [missing-attribute]
        self.worker = None
        if "cancelled" not in msg.lower():
            QMessageBox.information(self, "Complete", msg)

    @Slot(str)
    def on_conversion_error(self, msg):
        self.on_conversion_done(0, msg)
        QMessageBox.critical(self, "Error", msg)


__all__ = ["_ConversionWorkerMixin"]
