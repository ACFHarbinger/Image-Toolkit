"""Provider-combo change handler: toggles per-provider field visibility."""

from __future__ import annotations


class _ProviderSwitchMixin:
    """Shows/hides provider-specific auth widgets and updates subtabs."""

    def get_provider_text(self) -> str:
        return self.provider_combo.currentText()

    def handle_provider_change(self, index: int):
        provider_text = self.provider_combo.currentText()
        is_google_service = provider_text.startswith("Google Drive (Service Account)")
        is_google_personal = provider_text.startswith("Google Drive (Personal Account)")

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

        # Notify subtabs
        if hasattr(self, "sync_data_subtab"):
            self.sync_data_subtab.update_provider_visibility(provider_text)
        if hasattr(self, "local_dir_sync_subtab"):
            self.local_dir_sync_subtab.update_provider_visibility(provider_text)


__all__ = ["_ProviderSwitchMixin"]
