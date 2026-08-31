"""Widget construction for ``DriveSyncTab`` (container with subtabs)."""

from __future__ import annotations

import os
from pathlib import Path

import backend.src.constants as udef
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
)

from ....styles import apply_shadow_effect
from .local_dir_sync_subtab import LocalDirSyncSubtab
from .sync_data_subtab import SyncDataSubtab


class _UIBuilderMixin:
    """Builds the shared cloud auth group and hosting QTabWidget."""

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # ------------------ SHARED AUTH CONFIG GROUP ------------------
        config_group = QGroupBox("Cloud Provider & Authentication")
        config_layout = QVBoxLayout(config_group)

        # Provider dropdown
        provider_layout = QHBoxLayout()
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(
            [
                "Google Drive (Service Account)",
                "Google Drive (Personal Account)",
                "Dropbox",
                "OneDrive",
            ]
        )
        self.provider_combo.setStyleSheet("QComboBox { font-weight: bold; }")
        provider_layout.addWidget(QLabel("Cloud Provider:"))
        provider_layout.addWidget(self.provider_combo)
        config_layout.addLayout(provider_layout)

        # Service Account Key
        self.key_file_label = QLabel("Service Account Key File:")
        key_layout = QHBoxLayout()
        self.key_file_path = QLineEdit(
            os.path.join(Path.home(), udef.SERVICE_ACCOUNT_FILE)
        )
        self.key_file_path.setPlaceholderText("Path to service_account_key.json")
        self.btn_browse_key = QPushButton("Browse")
        apply_shadow_effect(self.btn_browse_key, "#000000", 8, 0, 3)
        self.btn_browse_key.clicked.connect(self.browse_key_file)
        key_layout.addWidget(self.key_file_path)
        key_layout.addWidget(self.btn_browse_key)

        # Personal Account: Client Secrets
        self.client_secrets_label = QLabel("Client Secrets File:")
        client_secrets_layout = QHBoxLayout()
        self.client_secrets_path = QLineEdit(
            os.path.join(Path.home(), udef.CLIENT_SECRETS_FILE)
        )
        self.client_secrets_path.setPlaceholderText("Path to client_secrets.json")
        self.btn_browse_client_secrets = QPushButton("Browse")
        apply_shadow_effect(self.btn_browse_client_secrets, "#000000", 8, 0, 3)
        self.btn_browse_client_secrets.clicked.connect(self.browse_client_secrets_file)
        client_secrets_layout.addWidget(self.client_secrets_path)
        client_secrets_layout.addWidget(self.btn_browse_client_secrets)

        # Personal Account: Token File
        self.token_file_label = QLabel("Token File (auto-generated):")
        token_file_layout = QHBoxLayout()
        self.token_file_path = QLineEdit(os.path.join(Path.home(), udef.TOKEN_FILE))
        self.token_file_path.setPlaceholderText("Path to store token.json")
        token_file_layout.addWidget(self.token_file_path)

        # Assemble shared auth layout
        config_layout.addWidget(self.key_file_label)
        config_layout.addLayout(key_layout)
        config_layout.addWidget(self.client_secrets_label)
        config_layout.addLayout(client_secrets_layout)
        config_layout.addWidget(self.token_file_label)
        config_layout.addLayout(token_file_layout)

        main_layout.addWidget(config_group)

        # ------------------ SUBTABS CONTAINER ------------------
        self.subtab_widget = QTabWidget()

        self.sync_data_subtab = SyncDataSubtab(
            get_auth_config=self._build_auth_config,
            get_provider_text=self.get_provider_text,
            parent=self,
        )
        self.local_dir_sync_subtab = LocalDirSyncSubtab(
            get_auth_config=self._build_auth_config,
            get_provider_text=self.get_provider_text,
            parent=self,
        )

        self.subtab_widget.addTab(self.sync_data_subtab, "Sync Data")
        self.subtab_widget.addTab(self.local_dir_sync_subtab, "Local Directory Sync")

        main_layout.addWidget(self.subtab_widget)

        # Compatibility proxies
        self.local_path = self.sync_data_subtab.local_path
        self.remote_path = self.sync_data_subtab.remote_path
        self.dry_run_checkbox = self.sync_data_subtab.dry_run_checkbox
        self.share_email_input = self.sync_data_subtab.share_email_input
        self.share_email_label = QLabel("Share Folder With:")
        self.btn_view_remote = self.sync_data_subtab.btn_view_remote
        self.btn_share_folder = self.sync_data_subtab.btn_share_folder
        self.sync_button = self.sync_data_subtab.sync_button
        self.rb_upload = self.sync_data_subtab.rb_upload
        self.rb_delete_local = self.sync_data_subtab.rb_delete_local
        self.rb_ignore_local = self.sync_data_subtab.rb_ignore_local
        self.rb_download = self.sync_data_subtab.rb_download
        self.rb_delete_remote = self.sync_data_subtab.rb_delete_remote
        self.rb_ignore_remote = self.sync_data_subtab.rb_ignore_remote

        self.provider_combo.currentIndexChanged.connect(self.handle_provider_change)

        self.load_configuration_defaults()
        self.handle_provider_change(0)


__all__ = ["_UIBuilderMixin"]
