"""One parameterized cloud-drive sync worker (ui-arch-41 / #563, R2.a).

Replaces ``DropboxDriveSyncWorker`` / ``OneDriveSyncWorker`` /
``GoogleDriveSyncWorker`` (three near-identical modules differing only in
the backend class, the credential key, and the Google auth-mode branch)
with a single provider-strategy worker.

Contract (unchanged for all providers):
- ``signals.status`` streams timestamped log lines.
- ``signals.finished`` emits ``(success, final_message, dry_run)``
  (``None`` when the base ``cancel()`` wins before ``_execute()``).
- ``stop()`` cooperatively halts a running sync; it now propagates to
  the backend manager for every provider (Google previously skipped
  this).
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

from backend.src.web import DropboxDriveSync, GoogleDriveSync, OneDriveSync

from gui.src.helpers.base import BaseQRunnableWorker

PROVIDERS = ("dropbox", "onedrive", "google")

_PROVIDER_DISPLAY = {
    "dropbox": "Dropbox",
    "onedrive": "OneDrive",
    "google": "Google Drive",
}


class CloudDriveSyncWorker(BaseQRunnableWorker):
    """Cancellable sync worker for Dropbox, OneDrive, or Google Drive."""

    def __init__(
        self,
        provider: str,
        auth_config: Dict[str, Any],
        local_path: str,
        remote_path: str,
        dry_run: bool,
        action_local_orphans: str = "upload",
        action_remote_orphans: str = "download",
        user_email_to_share_with: Optional[str] = None,
    ) -> None:
        super().__init__()
        if provider not in PROVIDERS:
            raise ValueError(f"Unknown sync provider: {provider!r}")
        self.provider = provider
        self.auth_config = auth_config
        self.local_path = local_path
        self.remote_path = remote_path
        self.dry_run = dry_run
        self.action_local = action_local_orphans
        self.action_remote = action_remote_orphans
        # Accepted for API parity with the old Google worker; the backend
        # manager never consumed it (sharing runs as a separate step).
        self.share_email = user_email_to_share_with
        self.auth_mode = auth_config.get("mode", "unknown")
        self._is_running = True
        self.sync_manager = None

    def _log(self, message: str) -> None:
        if self._is_running:
            timestamp = time.strftime("[%H:%M:%S]")
            self.signals.status.emit(f"{timestamp} {message}")

    def _credential_kwargs(self) -> Dict[str, Any]:
        if self.provider == "dropbox":
            return {"access_token": self.auth_config.get("access_token")}
        if self.provider == "onedrive":
            return {"client_id": self.auth_config.get("client_id")}
        kwargs: Dict[str, Any] = {}
        if self.auth_mode == "service_account":
            # pyrefly: ignore [bad-assignment]
            kwargs["service_account_data"] = self.auth_config.get("service_account_data")
            kwargs["client_secrets_data"] = None  # pyrefly: ignore [bad-assignment]
            kwargs["token_file"] = None  # pyrefly: ignore [bad-assignment]
        elif self.auth_mode == "personal_account":
            # pyrefly: ignore [bad-assignment]
            kwargs["client_secrets_data"] = self.auth_config.get("client_secrets_data")
            kwargs["token_file"] = self.auth_config.get("token_file")  # pyrefly: ignore [bad-assignment]
            kwargs["service_account_data"] = None  # pyrefly: ignore [bad-assignment]
        else:
            raise ValueError(f"Unsupported authentication mode: {self.auth_mode}")
        return kwargs

    def _build_manager(self) -> Callable[[], Any]:
        backends = {
            "dropbox": DropboxDriveSync,
            "onedrive": OneDriveSync,
            "google": GoogleDriveSync,
        }
        backend = backends[self.provider]
        return lambda: backend(
            local_source_path=self.local_path,
            drive_destination_folder_name=self.remote_path,
            dry_run=self.dry_run,
            logger=self._log,
            action_local_orphans=self.action_local,
            action_remote_orphans=self.action_remote,
            **self._credential_kwargs(),
        )

    def _execute(self) -> object:
        display = _PROVIDER_DISPLAY[self.provider]
        self.signals.status.emit("\n" + "=" * 50)
        self._log(f"--- {display} Sync Initiated ---")
        if self.provider == "google":
            self._log(f"Authentication Mode: {self.auth_mode.upper()}")
        self._log(f"Sync Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        if self.provider == "google":
            self._log(f"Action for Local Orphans: {self.action_local.upper()}")
            self._log(f"Action for Remote Orphans: {self.action_remote.upper()}")
        self.signals.status.emit("=" * 50 + "\n")

        success = False
        final_message = "Cancelled by user."
        try:
            self.sync_manager = self._build_manager()()

            if self._is_running:
                success, final_message = self.sync_manager.execute_sync()

        except Exception as e:
            success = False
            final_message = f"Critical error: {e}" if self.provider == "google" else f"Critical Error: {e}"
            self._log(f"ERROR: {final_message}")

        if not self._is_running and success:
            success = False
            final_message = "Synchronization manually cancelled."

        return (success, final_message, self.dry_run)

    def stop(self) -> None:
        if self._is_running:
            self._is_running = False
            if self.sync_manager is not None:
                self.sync_manager._is_running = False
            self.signals.status.emit("\n!!! SYNCHRONIZATION INTERRUPTED !!!")


__all__ = ["PROVIDERS", "CloudDriveSyncWorker"]
