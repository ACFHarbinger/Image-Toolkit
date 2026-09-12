"""Download/screenshot directory pickers.

Extracted from ``image_crawler_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFileDialog

from ._tab_bound import TabBoundController


class ImageCrawlDirectoryController(TabBoundController):
    """Browse-for-directory handlers for the download and screenshot paths."""

    @Slot()
    def browse_download_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self.tab, "Select Download Directory", self.tab.last_browsed_download_dir
        )
        if directory:
            self.download_dir_path.setText(directory)
            self.tab.last_browsed_download_dir = directory
            self.qml_settings_changed.emit()

    @Slot()
    def browse_screenshot_directory(self):
        d = QFileDialog.getExistingDirectory(self.tab, "Screenshot Dir", self.tab.last_browsed_screenshot_dir)
        if d:
            self.tab.last_browsed_screenshot_dir = d
            self.screenshot_dir_path.setText(d)


# COMPAT(ui-arch-23): legacy mixin alias
_DirectoryBrowseMixin = ImageCrawlDirectoryController

__all__ = ["ImageCrawlDirectoryController", "_DirectoryBrowseMixin"]
