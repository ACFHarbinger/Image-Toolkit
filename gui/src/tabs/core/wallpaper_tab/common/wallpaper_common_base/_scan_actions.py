"""Scan-error handling, results display, and directory browsing.

Extracted from ``wallpaper_common_base.py`` -- pure code motion, no logic
change (see ``_monitor_selection.py``'s docstring).
"""

from __future__ import annotations

from gui.src.helpers import ImageScannerWorker
from typing import cast

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from ......utils.sort_utils import natural_sort_key

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ....protos.wallpaper_common_base import WallpaperCommonBaseHostProtocol


class _ScanActionsMixin:
    """Cancel scanning, apply scan results, handle scan errors, browse directory."""

    def cancel_scanning(self: "WallpaperCommonBaseHostProtocol"):
        if self.img_scanner_thread and self.img_scanner_thread.isRunning():
            self.img_scanner_thread.quit()
        if self.vid_scanner_thread and self.vid_scanner_thread.isRunning():
            self.vid_scanner_thread.quit()

    @Slot(list)
    def display_scan_results(self: "WallpaperCommonBaseHostProtocol", image_paths: list):
        if self.background_type == "Solid Color":
            return
        self.clear_gallery_widgets()
        self.path_to_label_map.clear()
        self.check_all_monitors_set()
        final_paths = sorted(list(set(image_paths)), key=natural_sort_key)
        if not final_paths:
            return
        self.start_loading_gallery(final_paths)

    def handle_scan_error(self: "WallpaperCommonBaseHostProtocol", message: str, _worker=None):
        if _worker is not None and _worker is not self.img_scanner_worker and _worker is not self.img_scanner_thread:
            return
        self.clear_gallery_widgets()
        QMessageBox.warning(cast(QWidget, self), "Error Scanning", message)
        # An image-scan error means _on_image_scan_finished() will never
        # fire (and settle the pipeline) for this switch -- this is the
        # pipeline's actual end for this switch.
        self._settle_scan_pipeline()

    def browse_scan_directory(self: "WallpaperCommonBaseHostProtocol"):
        if self.background_type == "Solid Color":
            QMessageBox.warning(
                cast(QWidget, self),
                "Mode Conflict",
                "Cannot browse directory while Solid Color background is selected.",
            )
            return

        if ImageScannerWorker is None:
            QMessageBox.warning(
                cast(QWidget, self),
                "Missing Helpers",
                "The ImageScannerWorker or ImageLoaderWorker could not be imported.",
            )
            return

        start_dir = self.last_browsed_scan_dir
        options = (
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        directory = QFileDialog.getExistingDirectory(
            cast(QWidget, self), "Select directory to scan", start_dir, options
        )

        if directory:
            self.last_browsed_scan_dir = directory
            path_edit = getattr(self, "scan_directory_path", None)
            if path_edit is not None:
                path_edit.setText(directory)
            self.populate_scan_image_gallery(directory)


__all__ = ["_ScanActionsMixin"]
