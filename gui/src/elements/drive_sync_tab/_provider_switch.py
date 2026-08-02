"""Provider-combo change handler: toggles per-provider field visibility.

Extracted from ``drive_sync_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations


class _ProviderSwitchMixin:
    """Shows/hides provider-specific auth and sharing widgets."""

    def handle_provider_change(self, index: int):
        provider_text = self.provider_combo.currentText()
        is_google_service = provider_text.startswith("Google Drive (Service Account)")
        is_google_personal = provider_text.startswith("Google Drive (Personal Account)")
        is_google = is_google_service or is_google_personal

        # Toggle Service Account widgets
        for w in (self.key_file_label, self.key_file_path, self.btn_browse_key):
            w.setVisible(is_google_service)

        # Toggle Personal Account widgets
        for w in (
            self.client_secrets_label,
            self.client_secrets_path,
            self.btn_browse_client_secrets,
            self.token_file_label,
            self.token_file_path,
        ):
            w.setVisible(is_google_personal)

        # Toggle Sharing widgets (only for Service Account)
        for w in (
            self.share_email_label,
            self.share_email_input,
            self.btn_share_folder,
        ):
            w.setVisible(is_google_service)  # Changed from setEnabled to setVisible

        # View Map is specific to Google Drive implementation for now
        self.btn_view_remote.setEnabled(is_google)

        # Sync is now available for all implemented providers
        self.sync_button.setEnabled(True)


__all__ = ["_ProviderSwitchMixin"]
