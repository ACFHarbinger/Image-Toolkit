"""Tab-config collect/get_default_config/set_config for DriveSyncTab."""

from __future__ import annotations

import os
from pathlib import Path

import backend.src.constants as udef
from PySide6.QtWidgets import QMessageBox


class _ConfigMixin:
    """Collects/restores the full DriveSyncTab UI state as a config dict."""

    def collect(self) -> dict:
        """Collects current settings from the UI."""
        data_cfg = self.sync_data_subtab.collect()
        local_cfg = self.local_dir_sync_subtab.collect()

        cfg = {
            "provider": self.provider_combo.currentText(),
            "key_file": self.key_file_path.text().strip(),
            "client_secrets_file": self.client_secrets_path.text().strip(),
            "token_file": self.token_file_path.text().strip(),
            # Legacy top-level mapping for sync data
            "local_path": data_cfg.get("local_path", ""),
            "remote_path": data_cfg.get("remote_path", ""),
            "dry_run": data_cfg.get("dry_run", True),
            "share_email": data_cfg.get("share_email", ""),
            "action_local_orphans": data_cfg.get("action_local_orphans", "upload"),
            "action_remote_orphans": data_cfg.get("action_remote_orphans", "download"),
            # Structured subtab configs
            "sync_data": data_cfg,
            "local_dir_sync": local_cfg,
        }
        return cfg

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

            # Restore subtabs
            sync_data_cfg = config.get("sync_data", config)
            self.sync_data_subtab.set_config(sync_data_cfg)

            if "local_dir_sync" in config:
                self.local_dir_sync_subtab.set_config(config["local_dir_sync"])

            print("DriveSyncTab configuration loaded.")

        except Exception as e:
            print(f"Error applying DriveSyncTab config: {e}")
            QMessageBox.warning(
                self, "Config Error", f"Failed to apply some settings: {e}"
            )


__all__ = ["_ConfigMixin"]
