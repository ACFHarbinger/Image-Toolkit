import os

from PySide6.QtCore import QThread, Signal, QWaitCondition, QMutex
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS
from backend.src.core import FSETool, FileDeleter


class DeletionWorker(QThread):
    progress = Signal(int, int)  # (deleted, total)
    finished = Signal(int, str)  # (count, message)
    error = Signal(str)
    
    confirm_signal = Signal(str, int)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.confirmation_response = False
        self.wait_condition = QWaitCondition()
        self.mutex = QMutex()

    def set_confirmation_response(self, response: bool):
        self.mutex.lock()
        self.confirmation_response = response
        self.mutex.unlock()
        self.wait_condition.wakeOne()

    def run(self):
        try:
            target_path = self.config["target_path"]
            mode = self.config.get("mode", "files") 
            require_confirm = self.config["require_confirm"]

            if not target_path or not os.path.exists(target_path):
                self.error.emit("Target path does not exist.")
                return

            # --- DIRECTORY DELETION MODE ---
            if mode == 'directory':
                if not os.path.isdir(target_path):
                    self.error.emit(f"Error: Target path is not a directory: {target_path}")
                    return
                
                if require_confirm:
                    msg = f"Permanently delete the directory and all its contents: \n\n{target_path}\n\nThis cannot be undone!"
                    
                    self.mutex.lock()
                    self.confirm_signal.emit(msg, 1)
                    self.wait_condition.wait(self.mutex)
                    self.mutex.unlock()

                    if not self.confirmation_response:
                        self.finished.emit(0, "Directory deletion cancelled by user.")
                        return

                self.progress.emit(0, 1)
                
                # Core logic moved to FileDeleter
                if FileDeleter.delete_path(target_path):
                    self.finished.emit(1, f"Successfully deleted directory and its contents: {target_path}")
                else:
                    self.error.emit(f"Failed to delete directory {target_path}.")
                
                return 

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
                    files_to_delete.extend(FSETool.get_files_by_extension(target_path, ext, recursive=True))
                # Remove duplicates
                files_to_delete = sorted(list(set(files_to_delete)))

            total = len(files_to_delete)
            if total == 0:
                self.finished.emit(0, "No files found matching the selected extensions.")
                return

            if require_confirm:
                msg = f"Permanently delete {total} file(s) matching extensions?\n\nThis cannot be undone!"
                
                self.mutex.lock()
                self.confirm_signal.emit(msg, total)
                self.wait_condition.wait(self.mutex)
                self.mutex.unlock()

                if not self.confirmation_response:
                    self.finished.emit(0, "Deletion cancelled by user.")
                    return

            deleted = 0
            for file_path in files_to_delete:
                # Core logic for single file deletion
                if FileDeleter.delete_path(file_path):
                    deleted += 1
                
                self.progress.emit(deleted, total)
                
            self.finished.emit(deleted, f"Deleted {deleted} file(s).")
            
        except Exception as e:
            self.error.emit(str(e))
