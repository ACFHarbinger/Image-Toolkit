import logging
import os
from typing import Any, Dict, Union

from backend.src.constants import SUPPORTED_IMG_FORMATS
from backend.src.core import FileDeleter, FSETool
from PySide6.QtCore import QMutex, QWaitCondition, Signal
from send2trash import send2trash  # pyrefly: ignore [untyped-import]

from gui.src.helpers.base import BaseQThreadWorker
from gui.src.helpers.core.config_types import DeletionConfig

logger = logging.getLogger(__name__)

class DeletionWorker(BaseQThreadWorker):
    progress = Signal(int, int)  # (deleted, total)
    finished = Signal(tuple)  # (count, message)

    confirm_signal = Signal(str, int)

    def __init__(self, config: Union[DeletionConfig, Dict[str, Any]]):
        super().__init__()
        self.config = config
        self.confirmation_response = False
        self.wait_condition = QWaitCondition()
        self.mutex = QMutex()

    def stop(self):
        """Signals the worker to stop."""
        super().cancel()
        self.requestInterruption()
        # Wake up if waiting for confirmation
        self.wait_condition.wakeAll()

    def set_confirmation_response(self, response: bool):
        self.mutex.lock()
        self.confirmation_response = response
        self.mutex.unlock()
        self.wait_condition.wakeOne()

    def _execute(self) -> object:  # noqa: C901
        target_path = self.config["target_path"]
        mode = self.config.get("mode", "files")
        require_confirm = self.config["require_confirm"]

        if not target_path or not os.path.exists(target_path):
            raise RuntimeError("Target path does not exist.")

        # --- DIRECTORY DELETION MODE ---
        if mode == "directory":
            if not os.path.isdir(target_path):
                raise RuntimeError(
                    f"Error: Target path is not a directory: {target_path}"
                )

            if require_confirm:
                action_name = "send to trash" if self.config.get("send_to_trash", True) else "permanently delete"
                msg = f"{action_name.capitalize()} the directory and all its contents: \n\n{target_path}\n\nThis cannot be undone!"

                self.mutex.lock()
                self.confirm_signal.emit(msg, 1)
                self.wait_condition.wait(self.mutex)
                self.mutex.unlock()

                if not self.confirmation_response:
                    return (0, "Directory deletion cancelled by user.")

            self.progress.emit(0, 1)

            # Core logic moved to FileDeleter
            if self.config.get("send_to_trash", True):
                try:
                    send2trash(target_path)
                    return (1, f"Successfully sent directory to trash: {target_path}")
                except Exception as e:
                    raise RuntimeError(f"Failed to send directory to trash {target_path}: {e}") from e
            else:
                if FileDeleter.delete_path(target_path):
                    return (
                        1,
                        f"Successfully deleted directory and its contents: {target_path}",
                    )
                raise RuntimeError(f"Failed to delete directory {target_path}.")

        # --- FILE DELETION MODE ---

        extensions = self.config["target_extensions"] or SUPPORTED_IMG_FORMATS
        exts = {f".{ext.lstrip('.').lower()}" for ext in extensions}

        # Resolve files to delete upfront using FSETool
        files_to_delete = []

        if os.path.isfile(target_path):
            if any(target_path.lower().endswith(ext) for ext in exts):
                files_to_delete.append(target_path)
        else:
            # Recursively search the directory
            for ext in extensions:
                files_to_delete.extend(
                    FSETool.get_files_by_extension(target_path, ext, recursive=True)
                )
            # Remove duplicates
            files_to_delete = sorted(list(set(files_to_delete)))

        total = len(files_to_delete)
        if total == 0:
            return (
                0, "No files found matching the selected extensions."
            )

        if require_confirm:
            action_name = "send to trash" if self.config.get("send_to_trash", True) else "permanently delete"
            msg = f"{action_name.capitalize()} {total} file(s) matching extensions?\n\nThis cannot be undone!"

            self.mutex.lock()
            self.confirm_signal.emit(msg, total)
            self.wait_condition.wait(self.mutex)
            self.mutex.unlock()

            if not self.confirmation_response:
                return (0, "Deletion cancelled by user.")

        deleted = 0
        for file_path in files_to_delete:
            if self.isInterruptionRequested():
                break
            # Core logic for single file deletion
            if self.config.get("send_to_trash", True):
                try:
                    send2trash(file_path)
                    deleted += 1
                except Exception:
                    logger.debug("Suppressed Exception in DeletionWorker.run", exc_info=True)
            else:
                if FileDeleter.delete_path(file_path):
                    deleted += 1

            self.progress.emit(deleted, total)

        return (deleted, f"Deleted {deleted} file(s).")
