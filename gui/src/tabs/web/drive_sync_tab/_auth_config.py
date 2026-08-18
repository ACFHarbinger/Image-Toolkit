"""Per-provider auth-config dict construction for the sync workers.

Extracted from ``drive_sync_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import backend.src.constants as udef
from PySide6.QtWidgets import QMessageBox


class _AuthConfigMixin:
    """Builds the worker auth-config dict for the currently selected provider."""

    def _build_auth_config(self) -> Optional[Dict[str, Any]]:
        """
        Builds a configuration dictionary for the worker based on the
        selected provider.
        """
        provider_text = self.provider_combo.currentText()

        if provider_text.startswith("Google Drive (Service Account)"):
            SA_KEY_NAME = Path(udef.SERVICE_ACCOUNT_FILE).stem
            sa_data = self.vault_manager.api_credentials.get(SA_KEY_NAME)

            if not sa_data:
                QMessageBox.warning(
                    self, "Error", "Service Account Key data not loaded from vault."
                )
                return None

            return {"mode": "service_account", "service_account_data": sa_data}

        elif provider_text.startswith("Google Drive (Personal Account)"):
            CS_KEY_NAME = Path(udef.CLIENT_SECRETS_FILE).stem
            cs_data = self.vault_manager.api_credentials.get(CS_KEY_NAME)
            token_file = self.token_file_path.text().strip()

            if not cs_data:
                QMessageBox.warning(
                    self, "Error", "Client Secrets data not loaded from vault."
                )
                return None
            if not token_file:
                QMessageBox.warning(self, "Error", "Token File path cannot be empty.")
                return None

            return {
                "mode": "personal_account",
                "client_secrets_data": cs_data,
                "token_file": token_file,
            }

        elif provider_text == "Dropbox":
            # Placeholder: Assume 'dropbox_token' might be in vault or user manual entry
            token = self.vault_manager.api_credentials.get("dropbox_token")
            if not token:
                # Prompt user or handle missing token
                pass
            return {
                "provider": "dropbox",
                "access_token": token if token else "DUMMY_TOKEN_FOR_PLACEHOLDER",
            }

        elif provider_text == "OneDrive":
            # Placeholder
            return {
                "provider": "onedrive",
                "client_id": "DUMMY_ID",
                "client_secret": "DUMMY_SECRET",
            }

        return None


__all__ = ["_AuthConfigMixin"]
