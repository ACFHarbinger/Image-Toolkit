"""Scan-directory browsing + gallery population for ``MergeTab``.

Extracted from ``merge_tab.py`` -- pure code motion, no logic change
(see ``_ui_config.py``'s docstring).
"""

from __future__ import annotations

import contextlib
import os

from PySide6.QtCore import QEventLoop, QTimer, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox

from gui.src.helpers import ImageScannerWorker


class _ScanInputMixin:
    """Browse/scan the input directory and drive the resulting gallery load."""

    @Slot()
    def handle_scan_directory_return(self):
        d = self.scan_directory_path.text().strip()
        if d and os.path.isdir(d):
            self.populate_scan_gallery(d)
        else:
            QMessageBox.warning(
                self, "Invalid Path", "The entered path is not a valid directory."
            )

    @Slot()
    def browse_and_scan_directory(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Directory to Scan", self.last_browsed_scan_dir
        )
        if d:
            self.scan_directory_path.setText(d)
            self.last_browsed_scan_dir = d
            self.populate_scan_gallery(d)

    @Slot()
    def browse_output_directory(self):
        start_dir = (
            self.last_output_dir if self.last_output_dir else self.last_browsed_scan_dir
        )
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory", start_dir)
        if d:
            self.output_directory_path.setText(d)
            self.output_dir = d
            self.last_output_dir = d

    @Slot(str)
    def _update_output_dir_state(self, path: str):
        self.output_dir = path.strip() if path.strip() else None

    def populate_scan_gallery(self, directory: str):
        self.scanned_dir = directory
        if self.current_scan_worker:
            with contextlib.suppress(Exception):
                self.current_scan_worker.scan_finished.disconnect()
            with contextlib.suppress(Exception):
                self.current_scan_worker.stop()
                self.current_scan_worker.requestInterruption()
                self.current_scan_worker.quit()
                self.current_scan_worker.wait()
            self.current_scan_worker = None
            self.current_scan_thread = None

        self.cancel_loading()

        loop = QEventLoop()
        QTimer.singleShot(1, loop.quit)
        loop.exec()

        worker = ImageScannerWorker(directory)
        self.current_scan_worker = worker
        self.current_scan_thread = worker
        worker.scan_finished.connect(self.on_scan_finished)
        worker.finished.connect(self.cleanup_scan_thread_ref)
        worker.start()

    @Slot()
    def cleanup_scan_thread_ref(self):
        sender = self.sender()
        if sender:
            sender.deleteLater()
        if self.current_scan_thread == sender:
            self.current_scan_thread = None
        if self.current_scan_worker == sender:
            self.current_scan_worker = None

    def _track_and_cleanup_thread(self, thread):
        if not thread:
            return
        if thread.isFinished():
            thread.deleteLater()
            return
        self._threads_to_cleanup.add(thread)
        with contextlib.suppress(Exception):
            thread.finished.disconnect(self.cleanup_scan_thread_ref)

        def clean_up_func(t=thread):
            self._threads_to_cleanup.discard(t)
            t.deleteLater()

        thread.finished.connect(clean_up_func)

    @Slot(list)
    def on_scan_finished(self, paths):
        if not paths:
            QMessageBox.information(
                self, "No Files", f"No supported images found in {self.scanned_dir}"
            )
            self.clear_gallery_widgets()
            return
        self.start_loading_gallery(paths)
        self.status_label.setText(f"Scan complete. Loaded {len(paths)} files.")


__all__ = ["_ScanInputMixin"]
