"""UI lock/unlock helpers for the running sync job and minor actions.

Extracted from ``drive_sync_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from ....styles import STYLE_SYNC_RUN, STYLE_SYNC_STOP


class _UILockMixin:
    """Enables/disables config widgets while a sync job (or minor action) runs."""

    def lock_ui(self, message: str, is_running: bool = False, clear_log: bool = False):
        """Locks UI elements and updates sync button text/style."""
        self.sync_button.setText(message)
        self.sync_button.setStyleSheet(
            STYLE_SYNC_STOP if is_running else STYLE_SYNC_RUN
        )
        self.sync_button.setEnabled(True)

        config_enabled = not is_running

        # Auth inputs
        self.key_file_path.setEnabled(config_enabled)
        self.btn_browse_key.setEnabled(config_enabled)
        self.client_secrets_path.setEnabled(config_enabled)
        self.btn_browse_client_secrets.setEnabled(config_enabled)
        self.token_file_path.setEnabled(config_enabled)

        # Path inputs
        self.local_path.setEnabled(config_enabled)
        self.remote_path.setEnabled(config_enabled)
        self.share_email_input.setEnabled(config_enabled)
        self.dry_run_checkbox.setEnabled(config_enabled)

        # Behavior inputs
        self.rb_upload.setEnabled(config_enabled)
        self.rb_delete_local.setEnabled(config_enabled)
        self.rb_ignore_local.setEnabled(config_enabled)

        self.rb_download.setEnabled(config_enabled)
        self.rb_delete_remote.setEnabled(config_enabled)
        self.rb_ignore_remote.setEnabled(config_enabled)

        # Buttons
        self.btn_view_remote.setEnabled(config_enabled)
        self.btn_share_folder.setEnabled(config_enabled)

        if clear_log:
            self.log_window.clear_log()
        QApplication.processEvents()

    def unlock_ui(self):
        """Unlocks all UI elements and resets sync button state."""
        self.lock_ui(message="Run Synchronization Now", is_running=False)
        self.handle_provider_change(self.provider_combo.currentIndex())

    def lock_ui_minor(self, message: str, clear_log: bool = False):
        """Locks only minor action buttons while View/Share is running."""
        if clear_log:
            self.log_window.clear_log()
        self.btn_view_remote.setEnabled(False)
        self.btn_share_folder.setEnabled(False)
        self.sync_button.setEnabled(False)
        QApplication.processEvents()

    def unlock_ui_minor(self):
        """Unlocks minor action buttons."""
        self.btn_view_remote.setEnabled(True)
        self.btn_share_folder.setEnabled(True)
        self.sync_button.setEnabled(True)
        self.handle_provider_change(self.provider_combo.currentIndex())


__all__ = ["_UILockMixin"]
