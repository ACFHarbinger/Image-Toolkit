"""Directory browsing (source/reference/QML), validation, and extension toggles.

Extracted from ``similarity_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import os

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox

from ....styles import apply_shadow_effect


class _DirectoryBrowseMixin:
    """Browse source/reference directories, validate targets, toggle extensions."""

    def browse_directory(self):
        start = getattr(self, "last_browsed_dir", "") or ""
        d = QFileDialog.getExistingDirectory(
            self, "Select Source Directory", start,
            QFileDialog.Option.DontUseNativeDialog)
        if d:
            self.target_path.setText(d)
            self.last_browsed_dir = d
            self.browse_and_populate()

    def browse_and_populate(self):
        """Browsing just lists the directory into the gallery (fast, main-thread).
        The heavy tiered similarity scan is a separate, explicit action so simply
        picking a folder never launches background compute."""
        target_dir = self.target_path.text().strip()
        if not target_dir or not os.path.isdir(target_dir):
            return
        self._list_all_files(target_dir, self._current_extensions())

    def browse_reference_directory(self):
        start = self.reference_path.text() if os.path.isdir(self.reference_path.text()) else ""
        d = QFileDialog.getExistingDirectory(
            self, "Select Source / Reference Directory", start,
            QFileDialog.Option.DontUseNativeDialog)
        if d:
            self.reference_path.setText(d)
            self._sim_config.reference_dir = d
            self.reference_dir_changed.emit(d)

    def _clear_reference_widget(self):
        self.reference_path.clear()
        self._sim_config.reference_dir = None
        self.reference_dir_changed.emit("")

    @Slot(str)
    def browse_target_qml(self, current_path=""):
        starting_dir = current_path if os.path.isdir(current_path) else ""
        d = QFileDialog.getExistingDirectory(
            self, "Select Directory to Scan", starting_dir,
            QFileDialog.Option.DontUseNativeDialog)
        if d:
            self.target_path.setText(d)
            self.qml_input_path_changed.emit(d)
            return d
        return ""

    def is_valid(self, mode: str):
        p = self.target_path.text().strip()
        if not p or not os.path.exists(p):
            QMessageBox.warning(self, "Invalid", "Select valid file/folder.")
            return False
        if mode == "directory" and not os.path.isdir(p):
            QMessageBox.warning(self, "Invalid", "Directory required.")
            return False
        return True

    def toggle_extension(self, ext, checked):
        btn = self.extension_buttons[ext]
        if checked:
            self.selected_extensions.add(ext)
            btn.setStyleSheet("QPushButton:checked {  color: white; }")
            apply_shadow_effect(btn, "#000000", 8, 0, 3)
        else:
            self.selected_extensions.discard(ext)
            btn.setStyleSheet("QPushButton:hover {  }")
            apply_shadow_effect(btn, "#000000", 8, 0, 3)

    def add_all_extensions(self):
        for ext, btn in self.extension_buttons.items():
            btn.setChecked(True)
            self.toggle_extension(ext, True)

    def remove_all_extensions(self):
        for ext, btn in self.extension_buttons.items():
            btn.setChecked(False)
            self.toggle_extension(ext, False)


__all__ = ["_DirectoryBrowseMixin"]
