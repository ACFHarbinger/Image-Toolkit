"""Download directory picker.

Follows the same pattern as ``image_crawler_tab``'s
``_directory_browse.py``.
"""

from __future__ import annotations

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFileDialog


class _DirectoryBrowseMixin:
    """Browse-for-directory handler for the download path."""

    @Slot()
    def browse_download_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Download Directory", self.last_browsed_download_dir
        )
        if directory:
            self.download_dir_path.setText(directory)
            self.last_browsed_download_dir = directory


__all__ = ["_DirectoryBrowseMixin"]
