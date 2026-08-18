"""Widget construction for ``DriveSyncTab`` (``_build_ui``).

Extracted from ``drive_sync_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os
from pathlib import Path

import backend.src.constants as udef
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from ....constants import DRY_RUN
from ....styles import STYLE_SYNC_RUN, apply_shadow_effect


class _UIBuilderMixin:
    """Builds the config group, sync-behavior group, and sync button."""

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # ------------------ CONFIG GROUP ------------------
        config_group = QGroupBox("Cloud Sync Configuration")
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

        # Local and Remote paths
        local_layout = QHBoxLayout()
        self.local_path = QLineEdit(udef.LOCAL_SOURCE_PATH)
        self.local_path.setPlaceholderText("Local directory to synchronize")
        btn_browse_local = QPushButton("Browse Local Dir")
        apply_shadow_effect(btn_browse_local, "#000000", 8, 0, 3)
        btn_browse_local.clicked.connect(self.browse_local_directory)
        local_layout.addWidget(self.local_path)
        local_layout.addWidget(btn_browse_local)

        remote_layout = QHBoxLayout()
        self.remote_path = QLineEdit(udef.DRIVE_DESTINATION_FOLDER_NAME)
        self.remote_path.setPlaceholderText("Drive folder (e.g. Backups/2025)")
        remote_layout.addWidget(self.remote_path)

        # User Email to Share With
        share_layout = QHBoxLayout()
        self.share_email_label = QLabel("Share Folder With:")
        self.share_email_input = QLineEdit()
        self.share_email_input.setPlaceholderText(
            "Optional: User email to grant Editor access"
        )
        share_layout.addWidget(self.share_email_label)
        share_layout.addWidget(self.share_email_input)

        # Control Buttons Layout
        control_buttons_layout = QHBoxLayout()
        self.btn_view_remote = QPushButton("View Remote Files Map")
        apply_shadow_effect(self.btn_view_remote, "#000000", 8, 0, 3)
        self.btn_view_remote.clicked.connect(self.view_remote_map)
        control_buttons_layout.addWidget(self.btn_view_remote)

        self.btn_share_folder = QPushButton("Share Folder Now")
        apply_shadow_effect(self.btn_share_folder, "#000000", 8, 0, 3)
        self.btn_share_folder.clicked.connect(self.share_remote_folder)
        control_buttons_layout.addWidget(self.btn_share_folder)

        # Dry-run checkbox
        self.dry_run_checkbox = QCheckBox("Perform Dry Run (Simulate only)")
        self.dry_run_checkbox.setChecked(DRY_RUN)
        self.dry_run_checkbox.setStyleSheet(
            """
            QCheckBox { color: #f1c40f; }
            QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #555;
                                   border-radius: 3px; background: #333; }
            QCheckBox::indicator:checked { background: #f1c40f; border-color: #f1c40f; }
        """
        )

        # --- Assemble config ---
        config_layout.addWidget(self.key_file_label)
        config_layout.addLayout(key_layout)
        config_layout.addWidget(self.client_secrets_label)
        config_layout.addLayout(client_secrets_layout)
        config_layout.addWidget(self.token_file_label)
        config_layout.addLayout(token_file_layout)

        config_layout.addWidget(QLabel("Local Source Directory:"))
        config_layout.addLayout(local_layout)
        config_layout.addWidget(QLabel("Remote Destination Path:"))
        config_layout.addLayout(remote_layout)

        # Add share widgets directly to layout so we can toggle visibility
        config_layout.addWidget(self.share_email_label)
        config_layout.addWidget(self.share_email_input)

        # ------------------ SYNC BEHAVIOR GROUP ------------------
        behavior_group = QGroupBox("Sync Behavior")
        behavior_layout = QVBoxLayout(behavior_group)

        # 1. Local Orphans Action
        lbl_local_orphans = QLabel(
            "Action for files found ONLY Locally (Local Orphans):"
        )
        lbl_local_orphans.setStyleSheet("font-weight: bold; color: #3498db;")
        behavior_layout.addWidget(lbl_local_orphans)

        self.bg_local_orphans = QButtonGroup(self)
        self.rb_upload = QRadioButton("Upload to Remote (Merge)")
        self.rb_upload.setChecked(True)  # Default
        self.rb_delete_local = QRadioButton("Delete from Local (Mirror Remote)")
        self.rb_delete_local.setStyleSheet("color: #e74c3c;")
        self.rb_ignore_local = QRadioButton("Do Nothing (Ignore)")
        self.rb_ignore_local.setStyleSheet("color: #95a5a6;")

        self.bg_local_orphans.addButton(self.rb_upload)
        self.bg_local_orphans.addButton(self.rb_delete_local)
        self.bg_local_orphans.addButton(self.rb_ignore_local)

        lo_layout = QHBoxLayout()
        lo_layout.addWidget(self.rb_upload)
        lo_layout.addWidget(self.rb_delete_local)
        lo_layout.addWidget(self.rb_ignore_local)
        lo_layout.addStretch()
        behavior_layout.addLayout(lo_layout)

        # 2. Remote Orphans Action
        behavior_layout.addSpacing(10)
        lbl_remote_orphans = QLabel(
            "Action for files found ONLY on Remote (Remote Orphans):"
        )
        lbl_remote_orphans.setStyleSheet("font-weight: bold; color: #2ecc71;")
        behavior_layout.addWidget(lbl_remote_orphans)

        self.bg_remote_orphans = QButtonGroup(self)
        self.rb_download = QRadioButton("Download to Local (Merge)")
        self.rb_download.setChecked(True)  # Default
        self.rb_delete_remote = QRadioButton("Delete from Remote (Mirror Local)")
        self.rb_delete_remote.setStyleSheet("color: #e74c3c;")
        self.rb_ignore_remote = QRadioButton("Do Nothing (Ignore)")
        self.rb_ignore_remote.setStyleSheet("color: #95a5a6;")

        self.bg_remote_orphans.addButton(self.rb_download)
        self.bg_remote_orphans.addButton(self.rb_delete_remote)
        self.bg_remote_orphans.addButton(self.rb_ignore_remote)

        ro_layout = QHBoxLayout()
        ro_layout.addWidget(self.rb_download)
        ro_layout.addWidget(self.rb_delete_remote)
        ro_layout.addWidget(self.rb_ignore_remote)
        ro_layout.addStretch()
        behavior_layout.addLayout(ro_layout)

        config_layout.addWidget(behavior_group)
        # ---------------------------------------------------------

        config_layout.addLayout(control_buttons_layout)
        config_layout.addWidget(self.dry_run_checkbox)
        config_layout.addStretch(1)

        self.provider_combo.currentIndexChanged.connect(self.handle_provider_change)

        # ------------------ SYNC BUTTON ------------------
        self.sync_button = QPushButton("Run Synchronization Now")
        self.sync_button.setStyleSheet(STYLE_SYNC_RUN)
        apply_shadow_effect(self.sync_button, "#000000", 8, 0, 3)
        self.sync_button.clicked.connect(self.toggle_sync)

        # ------------------ LAYOUT ------------------
        main_layout.addWidget(config_group)
        main_layout.addWidget(self.sync_button)
        main_layout.addStretch(1)

        self.load_configuration_defaults()
        self.handle_provider_change(0)


__all__ = ["_UIBuilderMixin"]
