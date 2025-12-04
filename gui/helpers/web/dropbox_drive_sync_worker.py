import time

from typing import Dict, Any
from PySide6.QtCore import QRunnable
from backend.src.web import DropboxDriveSync
from .cloud_drive_sync_signals import CloudDriveSyncWorkerSignals


class DropboxDriveSyncWorker(QRunnable):
    def __init__(
        self,
        auth_config: Dict[str, Any],
        local_path: str,
        remote_path: str,
        dry_run: bool,
        action_local_orphans: str = "upload",
        action_remote_orphans: str = "download",
    ):
        super().__init__()
        self.auth_config = auth_config
        self.local_path = local_path
        self.remote_path = remote_path
        self.dry_run = dry_run
        self.action_local = action_local_orphans
        self.action_remote = action_remote_orphans
        self.signals = CloudDriveSyncWorkerSignals()
        self._is_running = True
        self.sync_manager = None

    def _log(self, message: str):
        if self._is_running:
            timestamp = time.strftime("[%H:%M:%S]")
            self.signals.status_update.emit(f"{timestamp} {message}")

    def run(self):
        self.signals.status_update.emit("\n" + "=" * 50)
        self._log(f"--- Dropbox Sync Initiated ---")
        self._log(f"Sync Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        self.signals.status_update.emit("=" * 50 + "\n")

        success = False
        final_message = "Cancelled by user."

        try:
            token = self.auth_config.get("access_token")

            self.sync_manager = DropboxDriveSync(
                local_source_path=self.local_path,
                drive_destination_folder_name=self.remote_path,
                access_token=token,
                dry_run=self.dry_run,
                logger=self._log,
                action_local_orphans=self.action_local,
                action_remote_orphans=self.action_remote,
            )

            if self._is_running:
                success, final_message = self.sync_manager.execute_sync()

        except Exception as e:
            success = False
            final_message = f"Critical Error: {e}"
            self._log(f"ERROR: {final_message}")

        if not self._is_running and success:
            success = False
            final_message = "Synchronization manually cancelled."

        if self._is_running:
            self.signals.sync_finished.emit(success, final_message, self.dry_run)

    def stop(self):
        if self._is_running:
            self._is_running = False
            if self.sync_manager:
                self.sync_manager._is_running = False
            self.signals.status_update.emit("\n!!! SYNCHRONIZATION INTERRUPTED !!!")
