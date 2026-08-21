"""Download/screenshot directory pickers.

Extracted from ``image_crawler_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFileDialog


class _DirectoryBrowseMixin:
    """Browse-for-directory handlers for the download and screenshot paths."""

    @Slot()
    def browse_download_directory(self):
        super().browse_download_directory() if hasattr(super(), 'browse_download_directory') else None # pyrefly: ignore [missing-attribute]
        directory = QFileDialog.getExistingDirectory(self, "Select Download Directory", self.last_browsed_download_dir)
        if directory:
            self.download_dir_path.setText(directory)
            self.last_browsed_download_dir = directory
            self.qml_settings_changed.emit()

    @Slot()
    def browse_screenshot_directory(self):
        d = QFileDialog.getExistingDirectory(
            self, "Screenshot Dir", self.last_browsed_screenshot_dir
        )
        if d:
            self.last_browsed_screenshot_dir = d
            self.screenshot_dir_path.setText(d)


__all__ = ["_DirectoryBrowseMixin"]
