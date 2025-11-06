import os

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QThread, Signal
from ...utils.definitions import SUPPORTED_IMG_FORMATS


class DeletionWorker(QThread):
    progress = Signal(int, int)  # (deleted, total)
    finished = Signal(int, str)  # (count, message)
    error = Signal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config

    def run(self):
        try:
            target_path = self.config["target_path"]
            extensions = self.config["target_extensions"] or SUPPORTED_IMG_FORMATS
            require_confirm = self.config["require_confirm"]

            if not target_path or not os.path.exists(target_path):
                self.error.emit("Target path does not exist.")
                return

            # Normalize extensions
            exts = {f".{ext.lstrip('.').lower()}" for ext in extensions}
            files_to_delete = []

            if os.path.isfile(target_path):
                if any(target_path.lower().endswith(ext) for ext in exts):
                    files_to_delete.append(target_path)
            else:
                for root, _, files in os.walk(target_path):
                    for file in files:
                        if any(file.lower().endswith(ext) for ext in exts):
                            files_to_delete.append(os.path.join(root, file))

            total = len(files_to_delete)
            if total == 0:
                self.error.emit("No files found matching the selected extensions.")
                return

            if require_confirm:
                reply = QMessageBox.question(
                    None, "Confirm Deletion",
                    f"Permanently delete {total} file(s)?\n\nThis cannot be undone!",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    self.finished.emit(0, "Deletion cancelled by user.")
                    return

            deleted = 0
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    deleted += 1
                    self.progress.emit(deleted, total)
                except Exception as e:
                    print(f"Failed to delete {file_path}: {e}")

            self.finished.emit(deleted, f"Deleted {deleted} file(s).")
        except Exception as e:
            self.error.emit(str(e))
