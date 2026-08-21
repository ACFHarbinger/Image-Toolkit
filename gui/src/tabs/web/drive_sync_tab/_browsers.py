"""File/directory browse dialogs.

Extracted from ``drive_sync_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QFileDialog, QLineEdit


class _BrowsersMixin:
    """Browse dialogs for the auth key files and the local sync directory."""

    def browse_key_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Service Account Key", str(Path.home()), "JSON (*.json)"
        )
        if path:
            self.key_file_path.setText(path)

    def browse_client_secrets_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Client Secrets File", str(Path.home()), "JSON (*.json)"
        )
        if path:
            self.client_secrets_path.setText(path)

    def browse_local_directory(self):
        dir_ = QFileDialog.getExistingDirectory(
            self,
            "Select Local Source Folder",
            self.local_path.text() or str(Path.home()),
        )
        if dir_:
            self.local_path.setText(dir_)

    def browse_directory(self, line_edit: Optional[QLineEdit] = None):
        line_edit = line_edit or self.local_path
        dir_ = QFileDialog.getExistingDirectory(
            self, "Select Folder", line_edit.text() or str(Path.home())
        )
        if dir_:
            line_edit.setText(dir_)

    def browse_files(self):
        provider_text = self.provider_combo.currentText()
        if provider_text.startswith("Google Drive"):
            self.browse_key_file()

    def browse_input(self):
        self.browse_local_directory()

    def browse_output(self):
        pass


__all__ = ["_BrowsersMixin"]
