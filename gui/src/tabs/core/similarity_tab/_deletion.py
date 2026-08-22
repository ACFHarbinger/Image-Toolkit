"""Standard deletion (single/batch files + whole directory) via DeletionWorker.

Extracted from ``similarity_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import os

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QApplication, QMessageBox
from send2trash import send2trash  # pyrefly: ignore [untyped-import]

from ....helpers import DeletionWorker


class _DeletionMixin:
    """Delete selected/single files or a whole directory, with progress/confirm."""

    def delete_selected_duplicates(self):
        if not self.selected_files:
            return
        count = len(self.selected_files)
        prefs = self._prefs()
        send_to_trash_enabled = prefs.get("send_to_trash", True)
        action_name = "Trash" if send_to_trash_enabled else "Permanent Delete"
        if self._confirm_deletions_enabled() and self.confirm_checkbox.isChecked():
            reply = QMessageBox.question(
                self, "Confirm Batch Delete",
                f"Move **{count}** selected files to {action_name}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
        deleted_count = 0
        errors = []
        for path in list(self.selected_files):
            try:
                if send_to_trash_enabled:
                    send2trash(path)
                else:
                    os.remove(path)
                deleted_count += 1
                if path in self.selected_files:
                    self.selected_files.remove(path)
                if path in self.found_files:
                    self.found_files.remove(path)
            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {str(e)}")
        self.refresh_found_gallery()
        self.refresh_selected_panel()
        self.on_selection_changed()
        msg = f"Moved {deleted_count} files to {action_name}."
        if errors:
            msg += "\nErrors:\n" + "\n".join(errors[:5])
        QMessageBox.information(self, f"Move to {action_name} Complete", msg)

    @Slot()
    def delete_selected_files_qml(self):
        self.delete_selected_duplicates()

    def delete_single_file(self, path: str):
        filename = os.path.basename(path)
        prefs = self._prefs()
        send_to_trash_enabled = prefs.get("send_to_trash", True)
        action_name = "Trash" if send_to_trash_enabled else "Permanent Delete"
        if self._confirm_deletions_enabled():
            reply = QMessageBox.question(
                self, "Confirm Deletion", f"Move to {action_name}:\n{filename}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
        try:
            if send_to_trash_enabled:
                send2trash(path)
            else:
                os.remove(path)
            if path in self.selected_files:
                self.selected_files.remove(path)
            if path in self.found_files:
                self.found_files.remove(path)
            self.refresh_found_gallery()
            self.refresh_selected_panel()
            self.on_selection_changed()
            self.status_label.setText(f"Moved to {action_name}: {filename}")
            QMessageBox.information(self, f"Moved to {action_name}", f"Moved to {action_name}: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Deletion Failed", f"Error: {e}")

    def start_deletion(self, mode: str):
        if not self.is_valid(mode):
            return
        config = self.collect(mode)
        config["require_confirm"] = (
            self._confirm_deletions_enabled() and self.confirm_checkbox.isChecked()
        )
        self.btn_delete_files.setEnabled(False)
        self.btn_delete_directory.setEnabled(False)
        self.status_label.setText(f"Starting {mode} deletion...")
        QApplication.processEvents()
        self.worker = DeletionWorker(config)
        self.worker.confirm_signal.connect(self.handle_confirmation_request)
        self.worker.progress.connect(self.update_progress)
        self.worker.sig_finished.connect(self.on_deletion_done)
        self.worker.error.connect(self.on_deletion_error)
        self.worker.start()

    @Slot(bool)
    def set_require_confirm(self, value: bool):
        self.confirm_checkbox.setChecked(bool(value))

    @Slot(str)
    def delete_directory_qml(self, target_dir=""):
        if target_dir:
            self.target_path.setText(target_dir)
        self.start_deletion(mode="directory")

    @Slot(str, result="QStringList")
    def list_directory_qml(self, target_dir):
        """List all supported files in a directory for the QML gallery."""
        if not target_dir or not os.path.isdir(target_dir):
            return []
        self.target_path.setText(target_dir)
        self._list_all_files(target_dir, self._current_extensions())
        return [p for paths in self.duplicate_results.values() for p in paths]

    @Slot(str, int)
    def handle_confirmation_request(self, message: str, total_items: int):
        if not self._confirm_deletions_enabled():
            self.worker.set_confirmation_response(True)
            return
        title = ("Confirm Directory Deletion"
                 if total_items == 1 and "directory" in message
                 else "Confirm File Deletion")
        reply = QMessageBox.question(
            self, title, message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        self.worker.set_confirmation_response(reply == QMessageBox.StandardButton.Yes)

    def update_progress(self, deleted, total):
        self.status_label.setText(f"Deleted {deleted} of {total}...")

    def on_deletion_done(self, count, msg):
        self.btn_delete_files.setEnabled(len(self.selected_files) > 0)
        self.btn_delete_directory.setEnabled(True)
        self.status_label.setText(msg)
        QMessageBox.information(self, "Complete", msg)
        self.worker = None

    def on_deletion_error(self, msg):
        self.btn_delete_files.setEnabled(True)
        self.btn_delete_directory.setEnabled(True)
        self.status_label.setText("Failed.")
        QMessageBox.critical(self, "Error", msg)
        self.worker = None


__all__ = ["_DeletionMixin"]
