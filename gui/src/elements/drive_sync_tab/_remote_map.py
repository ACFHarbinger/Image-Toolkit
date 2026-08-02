"""View Remote Files Map action (dry-run listing via GoogleDriveSyncWorker).

Extracted from ``drive_sync_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import QThreadPool, Slot
from PySide6.QtWidgets import QMessageBox

from ...helpers import GoogleDriveSyncWorker


class _RemoteMapMixin:
    """Dispatches and handles the read-only remote-map dry-run action."""

    def view_remote_map(self):
        if self.current_worker:
            return
        auth_config = self._build_auth_config()
        if not auth_config:
            return

        remote_path = self.remote_path.text().strip()
        if not remote_path:
            QMessageBox.warning(self, "Error", "Remote path cannot be empty.")
            return

        self.lock_ui_minor(message="Viewing Remote Map…", clear_log=True)
        self.log_window.show()

        self.current_worker = GoogleDriveSyncWorker(
            auth_config=auth_config,
            local_path=self.local_path.text().strip(),
            remote_path=remote_path,
            dry_run=True,
            user_email_to_share_with=None,
        )
        self.current_worker.signals.status_update.connect(self.handle_status_update)
        self.current_worker.signals.sync_finished.connect(
            # Proxy lambda to ignore the dry_run boolean for this specific action
            lambda s, m, d: self.handle_view_finished(s, m)
        )

        QThreadPool.globalInstance().start(self.current_worker)

    @Slot(bool, str)
    def handle_view_finished(self, success: bool, message: str):
        self.unlock_ui_minor()
        final = f"\nFINAL STATUS: Remote Map View {'Completed' if success else 'Failed'}. {message}"
        self.log_window.append_log(final)
        if not success and "Dry Run incomplete" not in message:
            QMessageBox.critical(self, "Map View Failed", message)
        self.current_worker = None


__all__ = ["_RemoteMapMixin"]
