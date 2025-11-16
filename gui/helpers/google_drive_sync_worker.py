import time

from typing import Optional, Dict, Any
from PySide6.QtCore import QObject, Signal, QRunnable
from backend.src.web.google_drive_sync import GoogleDriveSync as GDS


class GoogleDriveSyncWorkerSignals(QObject):
    status_update = Signal(str)
    sync_finished = Signal(bool, str)


class GoogleDriveSyncWorker(QRunnable):
    def __init__(self, 
                 auth_config: Dict[str, Any],
                 local_path: str, 
                 remote_path: str, 
                 dry_run: bool, 
                 user_email_to_share_with: Optional[str] = None
    ):
        super().__init__()
        self.auth_config = auth_config
        self.auth_mode = auth_config.get("mode", "unknown")
        self.local_path = local_path
        self.remote_path = remote_path
        self.dry_run = dry_run
        # Share email is only used/relevant for Service Accounts
        self.share_email = user_email_to_share_with 
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
        self._log(f"Authentication Mode: {self.auth_mode.upper()}")
        self._log(f"Sync Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        self.signals.status_update.emit("="*50 + "\n")

        success = False
        final_message = "Cancelled by user."
        
        try:
            # --- CRITICAL CHANGE: DYNAMIC GDS INITIALIZATION ---
            gds_kwargs = {
                "local_source_path": self.local_path,
                "drive_destination_folder_name": self.remote_path,
                "dry_run": self.dry_run,
                "logger": self._log,
                "user_email_to_share_with": self.share_email # Only used by Service Account GDS
            }

            if self.auth_mode == "service_account":
                gds_kwargs["service_account_file"] = self.auth_config.get("key_file")
            
            elif self.auth_mode == "personal_account":
                # Remove sharing for personal account flow since it's redundant
                gds_kwargs.pop("user_email_to_share_with", None) 
                gds_kwargs["client_secrets_file"] = self.auth_config.get("client_secrets_file")
                gds_kwargs["token_file"] = self.auth_config.get("token_file")
            
            else:
                 raise ValueError(f"Unsupported authentication mode: {self.auth_mode}")

            sync_manager = GDS(**gds_kwargs)
            # --------------------------------------------------
            
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
        if self._is_running:
            self._is_running = False
            self.signals.status_update.emit("\n!!! SYNCHRONIZATION INTERRUPTED !!!")
