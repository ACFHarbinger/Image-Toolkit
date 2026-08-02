"""Share Folder Now action (Google Service-Account-only sharing).

Extracted from ``drive_sync_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import QThreadPool, Slot
from PySide6.QtWidgets import QMessageBox

from ...helpers import GoogleDriveSyncWorker


class _ShareFolderMixin:
    """Dispatches and handles the remote-folder sharing action."""

    def share_remote_folder(self):
        if self.current_worker:
            return
        auth_config = self._build_auth_config()
        if not auth_config or auth_config.get("mode") != "service_account":
            QMessageBox.warning(
                self, "Error", "Sharing is only available for Google Service Accounts."
            )
            return

        remote_path = self.remote_path.text().strip()
        share_email = self.share_email_input.text().strip()
        if not remote_path or not share_email:
            return

        self.lock_ui_minor(message="Sharing Folder…", clear_log=True)
        self.log_window.show()

        self.current_worker = GoogleDriveSyncWorker(
            auth_config=auth_config,
            local_path=self.local_path.text().strip(),
            remote_path=remote_path,
            dry_run=self.dry_run_checkbox.isChecked(),
            user_email_to_share_with=share_email,
        )
        self.current_worker.signals.status_update.connect(self.handle_status_update)
        self.current_worker.signals.sync_finished.connect(
            lambda s, m, d: self.handle_share_finished(s, m)
        )

        QThreadPool.globalInstance().start(self.current_worker)

    @Slot(bool, str)
    def handle_share_finished(self, success: bool, message: str):
        self.unlock_ui_minor()
        final = f"\nFINAL STATUS: Share Action {'Completed' if success else 'Failed'}. {message}"
        self.log_window.append_log(final)
        if success:
            QMessageBox.information(
                self, "Share Success", "Folder sharing action completed."
            )
        else:
            QMessageBox.critical(self, "Share Failed", message)
        self.current_worker = None


__all__ = ["_ShareFolderMixin"]
