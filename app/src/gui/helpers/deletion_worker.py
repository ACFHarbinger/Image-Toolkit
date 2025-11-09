import os
import shutil 

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QThread, Signal, QWaitCondition, QMutex # Added QWaitCondition, QMutex
from ...utils.definitions import SUPPORTED_IMG_FORMATS


class DeletionWorker(QThread):
    progress = Signal(int, int)  # (deleted, total)
    finished = Signal(int, str)  # (count, message)
    error = Signal(str)
    
    # NEW SIGNAL: Requests confirmation from the main thread
    confirm_signal = Signal(str, int) # (message, total_items)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.confirmation_response = False # Stores Yes/No reply
        self.wait_condition = QWaitCondition() # Used to pause execution
        self.mutex = QMutex() # Used to protect shared variables

    # NEW: Slot to receive the user's decision from the main thread
    def set_confirmation_response(self, response: bool):
        self.mutex.lock()
        self.confirmation_response = response
        self.mutex.unlock()
        self.wait_condition.wakeOne() # Resume the worker thread

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
                    self.confirm_signal.emit(msg, 1) # Emit signal to main thread
                    self.wait_condition.wait(self.mutex) # PAUSE worker until main thread responds
                    self.mutex.unlock()

                    if not self.confirmation_response:
                        self.finished.emit(0, "Directory deletion cancelled by user.")
                        return

                self.progress.emit(0, 1) 
                try:
                    shutil.rmtree(target_path)
                    self.finished.emit(1, f"Successfully deleted directory and its contents: {target_path}")
                except Exception as e:
                    self.error.emit(f"Failed to delete directory {target_path}: {e}")
                
                return 

            # --- FILE DELETION MODE (Existing Logic) ---
            
            extensions = self.config["target_extensions"] or SUPPORTED_IMG_FORMATS
            
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
                self.finished.emit(0, "No files found matching the selected extensions.")
                return

            if require_confirm:
                msg = f"Permanently delete {total} file(s) matching extensions?\n\nThis cannot be undone!"
                
                self.mutex.lock()
                self.confirm_signal.emit(msg, total) # Emit signal to main thread
                self.wait_condition.wait(self.mutex) # PAUSE worker until main thread responds
                self.mutex.unlock()

                if not self.confirmation_response:
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
