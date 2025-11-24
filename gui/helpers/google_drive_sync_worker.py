import time

from typing import Optional, Dict, Any
from PySide6.QtCore import QRunnable
from backend.src.web import GoogleDriveSync
from .cloud_drive_sync_signals import CloudDriveSyncWorkerSignals


class GoogleDriveSyncWorker(QRunnable):
    def __init__(self, 
                 auth_config: Dict[str, Any],
                 local_path: str, 
                 remote_path: str, 
                 dry_run: bool, 
                 user_email_to_share_with: Optional[str] = None,
                 action_local_orphans: str = "upload",
                 action_remote_orphans: str = "download"
    ):
        super().__init__()
        self.auth_config = auth_config
        self.auth_mode = auth_config.get("mode", "unknown")
        self.local_path = local_path
        self.remote_path = remote_path
        self.dry_run = dry_run
        # Share email is only used/relevant for Service Accounts
        self.share_email = user_email_to_share_with 
        self.action_local = action_local_orphans
        self.action_remote = action_remote_orphans
        
        self.signals = CloudDriveSyncWorkerSignals()
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
        self._log(f"Action for Local Orphans: {self.action_local.upper()}")
        self._log(f"Action for Remote Orphans: {self.action_remote.upper()}")
        self.signals.status_update.emit("="*50 + "\n")

        success = False
        final_message = "Cancelled by user."
        try:
            gds_kwargs = {
                "local_source_path": self.local_path,
                "drive_destination_folder_name": self.remote_path,
                "dry_run": self.dry_run,
                "logger": self._log,
                "user_email_to_share_with": self.share_email,
                "action_local_orphans": self.action_local,
                "action_remote_orphans": self.action_remote
            }

            if self.auth_mode == "service_account":
                gds_kwargs["service_account_data"] = self.auth_config.get("service_account_data")
                gds_kwargs["client_secrets_data"] = None
                gds_kwargs["token_file"] = None 
            
            elif self.auth_mode == "personal_account":
                gds_kwargs["client_secrets_data"] = self.auth_config.get("client_secrets_data")
                gds_kwargs["token_file"] = self.auth_config.get("token_file")
                gds_kwargs["service_account_data"] = None
            
            else:
                raise ValueError(f"Unsupported authentication mode: {self.auth_mode}")

            sync_manager = GoogleDriveSync(**gds_kwargs)
            
            if self._is_running:
                success, final_message = sync_manager.execute_sync()
            
        except Exception as e:
            success = False
            final_message = f"Critical error: {e}"
            self._log(f"ERROR: {final_message}")
        
        if not self._is_running and success:
            success = False
            final_message = "Synchronization manually cancelled."

        if self._is_running:
            # Pass self.dry_run status back to UI
            self.signals.sync_finished.emit(success, final_message, self.dry_run)

    def stop(self):
        if self._is_running:
            self._is_running = False
            self.signals.status_update.emit("\n!!! SYNCHRONIZATION INTERRUPTED !!!")
