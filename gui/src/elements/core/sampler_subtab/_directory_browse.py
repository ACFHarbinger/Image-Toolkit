"""Input/output directory browsing and the file-scan pipeline.

Extracted from ``sampler_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os

from backend.src.constants import SUPPORTED_IMG_FORMATS, SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox

from ....utils.sort_utils import natural_sort_key


class _DirectoryBrowseMixin:
    """Directory/file pickers and the supported-file scan pipeline."""

    @Slot()
    def _browse_input(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Select input directory",
            self.last_browsed_dir,
            QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self.input_path.setText(path)
            self.last_browsed_dir = path
            self._scan_and_load()

    @Slot()
    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Select output directory",
            "",
            QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self.out_dir_edit.setText(path)

    def _collect_paths(self) -> list:
        p = self.input_path.text().strip()
        if not p:
            return []
        if os.path.isfile(p):
            return [p]
        if not os.path.isdir(p):
            return []

        vid_exts = {f.lstrip(".").lower() for f in SUPPORTED_VIDEO_FORMATS}
        img_exts = {f.lower() for f in SUPPORTED_IMG_FORMATS} | {"gif"}
        all_exts = vid_exts | img_exts

        paths = []
        from gui.src.windows.settings.app_settings import AppSettings
        if AppSettings.recursive_scan():
            for root, _, files in os.walk(p):
                for f in files:
                    if os.path.splitext(f)[1].lstrip(".").lower() in all_exts:
                        paths.append(os.path.join(root, f))
        else:
            with os.scandir(p) as it:
                for entry in it:
                    if entry.is_file() and os.path.splitext(entry.name)[1].lstrip(".").lower() in all_exts:
                        paths.append(entry.path)
        return paths

    def _scan_and_load(self):
        paths = self._collect_paths()
        if not paths:
            QMessageBox.information(self, "No Files", "No supported files found.")
            self.clear_galleries()
            return
        self.start_loading_thumbnails(sorted(paths, key=natural_sort_key))


__all__ = ["_DirectoryBrowseMixin"]
