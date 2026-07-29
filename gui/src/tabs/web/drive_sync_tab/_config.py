"""Tab-config collect/get_default_config/set_config for DriveSyncTab.

Extracted from ``drive_sync_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os
from pathlib import Path

import backend.src.constants as udef
from PySide6.QtWidgets import QMessageBox


class _ConfigMixin:
    """Collects/restores the full DriveSyncTab UI state as a config dict."""

    def collect(self) -> dict:
        """Collects current settings from the UI."""
        # Determine sync behaviors based on checked radio buttons
        action_local = "upload"
        if self.rb_delete_local.isChecked():
            action_local = "delete_local"
        elif self.rb_ignore_local.isChecked():
            action_local = "ignore_local"

        action_remote = "download"
        if self.rb_delete_remote.isChecked():
            action_remote = "delete_remote"
        elif self.rb_ignore_remote.isChecked():
            action_remote = "ignore_remote"

        return {
            "provider": self.provider_combo.currentText(),
            "key_file": self.key_file_path.text().strip(),
            "client_secrets_file": self.client_secrets_path.text().strip(),
            "token_file": self.token_file_path.text().strip(),
            "local_path": self.local_path.text().strip(),
            "remote_path": self.remote_path.text().strip(),
            "dry_run": self.dry_run_checkbox.isChecked(),
            "share_email": self.share_email_input.text().strip(),
            "action_local_orphans": action_local,
            "action_remote_orphans": action_remote,
        }

    def get_default_config(self) -> dict:
        return {
            "provider": "Google Drive (Service Account)",
            "key_file": os.path.join(Path.home(), udef.SERVICE_ACCOUNT_FILE),
            "client_secrets_file": os.path.join(Path.home(), udef.CLIENT_SECRETS_FILE),
            "token_file": os.path.join(Path.home(), udef.TOKEN_FILE),
            "local_path": udef.LOCAL_SOURCE_PATH,
            "remote_path": udef.DRIVE_DESTINATION_FOLDER_NAME,
            "dry_run": True,
            "share_email": "",
            "action_local_orphans": "upload",
            "action_remote_orphans": "download",
        }

    def set_config(self, config: dict):
        try:
            provider = config.get("provider", "Google Drive (Service Account)")
            if self.provider_combo.findText(provider) != -1:
                self.provider_combo.setCurrentText(provider)

            self.key_file_path.setText(config.get("key_file", ""))
            self.client_secrets_path.setText(config.get("client_secrets_file", ""))
            self.token_file_path.setText(config.get("token_file", ""))
            self.local_path.setText(config.get("local_path", ""))
            self.remote_path.setText(config.get("remote_path", ""))
            self.dry_run_checkbox.setChecked(config.get("dry_run", True))
            self.share_email_input.setText(config.get("share_email", ""))

            # Restore Behavior Radio Buttons
            act_local = config.get("action_local_orphans", "upload")
            if act_local == "delete_local":
                self.rb_delete_local.setChecked(True)
            elif act_local == "ignore_local":
                self.rb_ignore_local.setChecked(True)
            else:
                self.rb_upload.setChecked(True)

            act_remote = config.get("action_remote_orphans", "download")
            if act_remote == "delete_remote":
                self.rb_delete_remote.setChecked(True)
            elif act_remote == "ignore_remote":
                self.rb_ignore_remote.setChecked(True)
            else:
                self.rb_download.setChecked(True)

            print("DriveSyncTab configuration loaded.")

        except Exception as e:
            print(f"Error applying DriveSyncTab config: {e}")
            QMessageBox.warning(
                self, "Config Error", f"Failed to apply some settings: {e}"
            )


__all__ = ["_ConfigMixin"]
