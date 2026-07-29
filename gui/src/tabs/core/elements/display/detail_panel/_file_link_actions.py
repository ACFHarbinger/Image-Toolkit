"""Browse/open local-file and open web-link actions.

Extracted from ``detail_panel.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from pathlib import Path

from gui.src.tabs.core.elements.common.listings_common import open_file_location, open_web_link
from PySide6.QtWidgets import QFileDialog, QMessageBox


class _FileLinkActionsMixin:
    """Browse-for/open the local file field and open the web-link field."""

    def _browse_local_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Local File",
            "",
            "All Files (*.*)",
        )
        if path:
            self.f_local_file.setText(path)

    def _open_local_file(self):
        path = self.f_local_file.text().strip()
        if not path:
            QMessageBox.warning(self, "No File", "Please select or enter a local file path first.")
            return
        p = Path(path)
        if not p.exists():
            QMessageBox.warning(self, "File Not Found", f"The file at '{path}' does not exist.")
            return
        open_file_location(path)

    def _open_web_link(self):
        url = self.f_web_link.text().strip()
        if not url:
            QMessageBox.warning(self, "No Link", "Please enter a web link first.")
            return
        open_web_link(url)


__all__ = ["_FileLinkActionsMixin"]
