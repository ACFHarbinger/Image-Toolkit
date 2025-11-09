import time
from typing import Optional
try:
    from app.src.web.google_drive_sync import GoogleDriveSync as GDS
except:
    from src.web.google_drive_sync import GoogleDriveSync as GDS

from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, QMutex


class GoogleDriveSyncWorkerSignals(QObject):
    status_update = Signal(str)
    sync_finished = Signal(bool, str)


class GoogleDriveSyncWorker(QRunnable):
    def __init__(self, 
                 key_file: str, 
                 local_path: str, 
                 remote_path: str, 
                 dry_run: bool, 
                 user_email_to_share_with: Optional[str] = None # NEW PARAMETER
    ):
        super().__init__()
        self.key_file = key_file
        self.local_path = local_path
        self.remote_path = remote_path
        self.dry_run = dry_run
        self.share_email = user_email_to_share_with # NEW ATTRIBUTE
        self.signals = GoogleDriveSyncWorkerSignals()
        self._is_running = True

    def _log(self, message: str):
        # Only log if still running
        if self._is_running:
            timestamp = time.strftime("[%H:%M:%S]")
            self.signals.status_update.emit(f"{timestamp} {message}")

    def run(self):
        self.signals.status_update.emit("\n" + "="*50)
        self._log(f"--- Google Drive Sync Initiated ---")
        self._log(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        self.signals.status_update.emit("="*50 + "\n")

        success = False
        final_message = "Cancelled by user." # Default message if self._is_running is set to False
        
        try:
            sync_manager = GDS(
                service_account_file=self.key_file,
                local_source_path=self.local_path,
                drive_destination_folder_name=self.remote_path,
                dry_run=self.dry_run,
                logger=self._log,
                # Pass new parameter to GDS
                user_email_to_share_with=self.share_email
            )
            # Only execute sync if we haven't been asked to stop immediately
            if self._is_running:
                 success, final_message = sync_manager.execute_sync()
            
        except Exception as e:
            success = False
            final_message = f"Critical error: {e}"
            self._log(f"ERROR: {final_message}")
        
        # Check if the process was cancelled by stop()
        if not self._is_running and success:
            success = False
            final_message = "Synchronization manually cancelled."

        # Emit result if still alive
        if self._is_running:
            self.signals.sync_finished.emit(success, final_message)

    def stop(self):
        # Set the flag to False and emit a log message
        if self._is_running:
            self._is_running = False
            # This is safe to emit as QRunnable signals are thread-safe (queued connection)
            self.signals.status_update.emit("\n!!! SYNCHRONIZATION INTERRUPTED !!!")
            # Note: We rely on the GDS code checking this flag or finishing its current API call quickly.
