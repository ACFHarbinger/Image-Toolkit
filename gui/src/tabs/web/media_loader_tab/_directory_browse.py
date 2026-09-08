"""Download directory picker.

Follows the same pattern as ``image_crawler_tab``'s
``_directory_browse.py``.
"""

from __future__ import annotations

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFileDialog

from ._tab_bound import TabBoundController


class MediaLoaderDirectoryController(TabBoundController):
    """Browse-for-directory handler for the download path."""

    @Slot()
    def browse_download_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self.tab, "Select Download Directory", self.last_browsed_download_dir
        )
        if directory:
            self.download_dir_path.setText(directory)
            self.last_browsed_download_dir = directory


_DirectoryBrowseMixin = MediaLoaderDirectoryController  # COMPAT(ui-arch-23): remove after callers drop the mixin name

__all__ = ["MediaLoaderDirectoryController", "_DirectoryBrowseMixin"]
