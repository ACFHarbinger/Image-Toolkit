"""Main sync-job start/stop, status/finished handling, and dry-run confirm.

Extracted from ``drive_sync_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QThreadPool, Slot
from PySide6.QtWidgets import QMessageBox

from ...helpers import DropboxDriveSyncWorker, GoogleDriveSyncWorker, OneDriveSyncWorker


class _SyncWorkerMixin:
    """Starts/stops the main sync job and reacts to status/finished signals."""

    def toggle_sync(self):
        """Starts the sync if idle, or stops it if running."""
        if self.current_worker is None:
            self.run_sync_now(clear_log=True)
        else:
            self.stop_sync_now()

    def stop_sync_now(self):
        """Initiates the graceful stop of the running worker and immediately resets UI."""
        if self.current_worker:
            self.current_worker.stop()
            self.unlock_ui()
            self.log_window.append_log("\nManually interrupted. Resetting UI...")
            self.current_worker = None

    def run_sync_now(self, clear_log: bool = True, force_live: bool = False):
        """Initializes and runs the main synchronization job."""

        auth_config = self._build_auth_config()
        if not auth_config:
            return

        local_path = self.local_path.text().strip()
        remote_path = self.remote_path.text().strip()

        # Logic for Dry Run Checkbox vs Force Live argument
        is_dry_run = self.dry_run_checkbox.isChecked()
        if force_live:
            is_dry_run = False

        share_email = None

        if not os.path.isdir(local_path):
            QMessageBox.warning(self, "Error", f"Local folder invalid:\n{local_path}")
            return
        if not remote_path:
            QMessageBox.warning(self, "Error", "Remote path cannot be empty.")
            return

        if auth_config.get("mode") == "service_account":
            email_text = self.share_email_input.text().strip()
            if email_text:
                share_email = email_text

        # DETERMINE SYNC ACTIONS
        if self.rb_delete_local.isChecked():
            act_local = "delete_local"
        elif self.rb_ignore_local.isChecked():
            act_local = "ignore_local"
        else:
            act_local = "upload"

        if self.rb_delete_remote.isChecked():
            act_remote = "delete_remote"
        elif self.rb_ignore_remote.isChecked():
            act_remote = "ignore_remote"
        else:
            act_remote = "download"

        # 3. UI LOCK and SETUP
        msg = "STOP" if not is_dry_run else "STOP (Dry Run)"
        self.lock_ui(message=msg, is_running=True, clear_log=clear_log)
        self.log_window.show()

        # 4. START WORKER BASED ON PROVIDER
        provider_text = self.provider_combo.currentText()

        common_args = {
            "auth_config": auth_config,
            "local_path": local_path,
            "remote_path": remote_path,
            "dry_run": is_dry_run,
            "action_local_orphans": act_local,
            "action_remote_orphans": act_remote,
        }

        if provider_text.startswith("Google Drive"):
            self.current_worker = GoogleDriveSyncWorker(
                **common_args, user_email_to_share_with=share_email
            )
        elif provider_text == "Dropbox":
            self.current_worker = DropboxDriveSyncWorker(**common_args)
        elif provider_text == "OneDrive":
            self.current_worker = OneDriveSyncWorker(**common_args)

        self.current_worker.signals.status_update.connect(self.handle_status_update) # pyrefly: ignore [missing-attribute]
        self.current_worker.signals.sync_finished.connect(self.handle_sync_finished) # pyrefly: ignore [missing-attribute]

        QThreadPool.globalInstance().start(self.current_worker) # pyrefly: ignore [no-matching-overload]

    @Slot(str)
    def handle_status_update(self, msg: str):
        super().handle_status_update(msg) if hasattr(super(), 'handle_status_update') else None # pyrefly: ignore [missing-attribute]
        self.log_window.append_log(msg)
        self._log_text += msg + "\n"
        self.qml_log_changed.emit()

    @Slot(bool, str, bool)
    def handle_sync_finished(self, success: bool, message: str, was_dry_run: bool):
        self.unlock_ui()
        status_str = "Completed" if success else "Failed"
        mode_str = "DRY RUN" if was_dry_run else "LIVE"

        final = f"\nFINAL STATUS: {mode_str} Sync {status_str}. {message}"
        self.log_window.append_log(final)

        self.current_worker = None

        if not success and "manually cancelled" not in message:
            QMessageBox.critical(self, "Sync Failed", message)
            return

        # --- DRY RUN CONFIRMATION LOGIC ---
        if success and was_dry_run:
            reply = QMessageBox.question(
                self,
                "Dry Run Completed",
                "The Dry Run finished successfully.\n\n"
                "Do you want to apply these changes now (Execute LIVE Sync)?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.log_window.append_log(
                    "\nUser confirmed application of changes. Starting LIVE run..."
                )
                self.run_sync_now(clear_log=False, force_live=True)


__all__ = ["_SyncWorkerMixin"]
