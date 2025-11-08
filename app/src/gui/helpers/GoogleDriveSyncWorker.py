import time
import src.web.GoogleDriveSync as gds

from PySide6.QtCore import QObject, Signal


class GoogleDriveSyncWorker(QObject):
    """
    Worker to run the Google Drive synchronization logic in a separate thread.
    Calls the imported execute_sync function.
    """
    sync_finished = Signal(bool, str)  # (success, final_message)
    status_update = Signal(str)        # Log message for the UI

    def __init__(self, key_file: str, local_path: str, remote_path: str, dry_run: bool):
        super().__init__()
        self.key_file = key_file
        self.local_path = local_path
        self.remote_path = remote_path
        self.dry_run = dry_run
        
    def _log(self, message: str):
        """Emits a log message with a timestamp."""
        timestamp = time.strftime("[%H:%M:%S]")
        self.status_update.emit(f"{timestamp} {message}")

    # ==============================================================================
    # CORE SYNCHRONIZATION LOGIC (Now delegated to GoogleDriveSync.execute_sync)
    # ==============================================================================

    def run_sync(self):
        """
        Executes the full one-way sync logic by calling the external function.
        """
        self.status_update.emit("\n" + "="*50)
        self._log(f"--- Google Drive Sync Initiated ---")
        self._log(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        self.status_update.emit("="*50 + "\n")

        # Call the external, functional sync logic
        success, final_message = gds.execute_sync(
            key_file=self.key_file,
            local_path=self.local_path,
            remote_path=self.remote_path,
            dry_run=self.dry_run,
            logger=self._log
        )
            
        self.sync_finished.emit(success, final_message)
