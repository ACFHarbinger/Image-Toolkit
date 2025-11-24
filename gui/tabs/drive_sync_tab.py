import os
import backend.src.utils.definitions as udef

from pathlib import Path
from typing import Optional, Dict, Any
from PySide6.QtCore import QThreadPool, Slot
from PySide6.QtWidgets import (
    QApplication, QMessageBox, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QGroupBox, QCheckBox,
    QLineEdit, QComboBox, QFileDialog, QRadioButton, QButtonGroup
)
from ..utils.app_definitions import DRY_RUN
from .base_tab import BaseTab
from ..windows import LogWindow
from ..helpers import GoogleDriveSyncWorker, DropboxDriveSyncWorker, OneDriveSyncWorker
from ..styles.style import apply_shadow_effect, STYLE_SYNC_RUN, STYLE_SYNC_STOP


class DriveSyncTab(BaseTab):
    """GUI tab for Cloud Drive one-way sync (QRunnable + QThreadPool)."""
    def __init__(self, vault_manager, dropdown=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dropdown = dropdown
        self.vault_manager = vault_manager
        self.current_worker: Optional[Any] = None
        
        self.log_window = LogWindow() 

        main_layout = QVBoxLayout(self)

        # ------------------ CONFIG GROUP ------------------
        config_group = QGroupBox("Cloud Sync Configuration")
        config_layout = QVBoxLayout(config_group)

        # Provider dropdown
        provider_layout = QHBoxLayout()
        self.provider_combo = QComboBox()
        self.provider_combo.addItems([
            "Google Drive (Service Account)",
            "Google Drive (Personal Account)",
            "Dropbox",
            "OneDrive"
        ])
        self.provider_combo.setStyleSheet("QComboBox { font-weight: bold; }")
        provider_layout.addWidget(QLabel("Cloud Provider:"))
        provider_layout.addWidget(self.provider_combo)
        config_layout.addLayout(provider_layout)

        # Service Account Key
        self.key_file_label = QLabel("Service Account Key File:")
        key_layout = QHBoxLayout()
        self.key_file_path = QLineEdit(os.path.join(Path.home(), udef.SERVICE_ACCOUNT_FILE))
        self.key_file_path.setPlaceholderText("Path to service_account_key.json")
        self.btn_browse_key = QPushButton("Browse")
        apply_shadow_effect(self.btn_browse_key, "#000000", 8, 0, 3)
        self.btn_browse_key.clicked.connect(self.browse_key_file)
        key_layout.addWidget(self.key_file_path)
        key_layout.addWidget(self.btn_browse_key)

        # Personal Account: Client Secrets
        self.client_secrets_label = QLabel("Client Secrets File:")
        client_secrets_layout = QHBoxLayout()
        self.client_secrets_path = QLineEdit(os.path.join(Path.home(), udef.CLIENT_SECRETS_FILE))
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

        # Local & Remote paths
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
        self.share_email_input.setPlaceholderText("Optional: User email to grant Editor access")
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
        self.dry_run_checkbox.setStyleSheet("""
            QCheckBox { color: #f1c40f; }
            QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #555;
                                   border-radius: 3px; background: #333; }
            QCheckBox::indicator:checked { background: #f1c40f; border-color: #f1c40f; }
        """)

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
        lbl_local_orphans = QLabel("Action for files found ONLY Locally (Local Orphans):")
        lbl_local_orphans.setStyleSheet("font-weight: bold; color: #3498db;")
        behavior_layout.addWidget(lbl_local_orphans)
        
        self.bg_local_orphans = QButtonGroup(self)
        self.rb_upload = QRadioButton("Upload to Remote (Merge)")
        self.rb_upload.setChecked(True) # Default
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
        lbl_remote_orphans = QLabel("Action for files found ONLY on Remote (Remote Orphans):")
        lbl_remote_orphans.setStyleSheet("font-weight: bold; color: #2ecc71;")
        behavior_layout.addWidget(lbl_remote_orphans)
        
        self.bg_remote_orphans = QButtonGroup(self)
        self.rb_download = QRadioButton("Download to Local (Merge)")
        self.rb_download.setChecked(True) # Default
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
        
    # ------------------------------------------------------------------ #
    #                         SYNC TOGGLE                              #
    # ------------------------------------------------------------------ #
    def toggle_sync(self):
        """Starts the sync if idle, or stops it if running."""
        if self.current_worker is None:
            self.run_sync_now(clear_log=True)
        else:
            self.stop_sync_now()

    def stop_sync_now(self):
        """Initiates the graceful stop of the running worker and immediately resets UI."""
        if self.current_worker:
            self.current_worker.stop()
            self.unlock_ui()
            self.log_window.append_log("\nManually interrupted. Resetting UI...")
            self.current_worker = None

    # ------------------------------------------------------------------ #
    #                          PROVIDER SWITCH                         #
    # ------------------------------------------------------------------ #
    def handle_provider_change(self, index: int):
        provider_text = self.provider_combo.currentText()
        is_google_service = provider_text.startswith("Google Drive (Service Account)")
        is_google_personal = provider_text.startswith("Google Drive (Personal Account)")
        is_google = is_google_service or is_google_personal

        # Toggle Service Account widgets
        for w in (self.key_file_label, self.key_file_path, self.btn_browse_key):
            w.setVisible(is_google_service)

        # Toggle Personal Account widgets
        for w in (self.client_secrets_label, self.client_secrets_path, 
                  self.btn_browse_client_secrets, self.token_file_label, 
                  self.token_file_path):
            w.setVisible(is_google_personal)

        # Toggle Sharing widgets (only for Service Account)
        for w in (self.share_email_label, self.share_email_input, self.btn_share_folder):
            w.setVisible(is_google_service) # Changed from setEnabled to setVisible
        
        # View Map is specific to Google Drive implementation for now
        self.btn_view_remote.setEnabled(is_google)
        
        # Sync is now available for all implemented providers
        self.sync_button.setEnabled(True)

    # ------------------------------------------------------------------ #
    #                    AUTH CONFIG BUILDER                           #
    # ------------------------------------------------------------------ #

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
                QMessageBox.warning(self, "Error", "Service Account Key data not loaded from vault.")
                return None
            
            return {
                "mode": "service_account",
                "service_account_data": sa_data
            }
            
        elif provider_text.startswith("Google Drive (Personal Account)"):
            CS_KEY_NAME = Path(udef.CLIENT_SECRETS_FILE).stem
            cs_data = self.vault_manager.api_credentials.get(CS_KEY_NAME)
            token_file = self.token_file_path.text().strip()
            
            if not cs_data:
                QMessageBox.warning(self, "Error", "Client Secrets data not loaded from vault.")
                return None
            if not token_file:
                QMessageBox.warning(self, "Error", "Token File path cannot be empty.")
                return None
            
            return {
                "mode": "personal_account",
                "client_secrets_data": cs_data,
                "token_file": token_file
            }
            
        elif provider_text == "Dropbox":
            # Placeholder: Assume 'dropbox_token' might be in vault or user manual entry
            token = self.vault_manager.api_credentials.get("dropbox_token")
            if not token:
                # Prompt user or handle missing token
                # For now, we allow it to proceed to the worker which will fail if token missing, 
                # or use a dummy one for dry runs.
                pass
            return {
                "provider": "dropbox",
                "access_token": token if token else "DUMMY_TOKEN_FOR_PLACEHOLDER"
            }
            
        elif provider_text == "OneDrive":
            # Placeholder
            return {
                "provider": "onedrive",
                "client_id": "DUMMY_ID",
                "client_secret": "DUMMY_SECRET"
            }
            
        return None

    # ------------------------------------------------------------------ #
    #                           DEFAULTS                               #
    # ------------------------------------------------------------------ #
    def load_configuration_defaults(self):
        self.key_file_path.setText(udef.SERVICE_ACCOUNT_FILE)
        self.client_secrets_path.setText(udef.CLIENT_SECRETS_FILE)
        self.token_file_path.setText(udef.TOKEN_FILE)
        self.local_path.setText(udef.LOCAL_SOURCE_PATH)
        self.remote_path.setText(udef.DRIVE_DESTINATION_FOLDER_NAME)
        self.share_email_input.setText("")

    # ------------------------------------------------------------------ #
    #                     VIEW REMOTE MAP ACTION                       #
    # ------------------------------------------------------------------ #
    def view_remote_map(self):
        if self.current_worker: return
        auth_config = self._build_auth_config()
        if not auth_config: return
        
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
            user_email_to_share_with=None
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
        
    # ------------------------------------------------------------------ #
    #                     SHARE FOLDER ACTION                          #
    # ------------------------------------------------------------------ #
    def share_remote_folder(self):
        if self.current_worker: return
        auth_config = self._build_auth_config()
        if not auth_config or auth_config.get("mode") != "service_account":
            QMessageBox.warning(self, "Error", "Sharing is only available for Google Service Accounts.")
            return

        remote_path = self.remote_path.text().strip()
        share_email = self.share_email_input.text().strip()
        if not remote_path or not share_email: return

        self.lock_ui_minor(message="Sharing Folder…", clear_log=True)
        self.log_window.show()
        
        self.current_worker = GoogleDriveSyncWorker(
            auth_config=auth_config,
            local_path=self.local_path.text().strip(), 
            remote_path=remote_path, 
            dry_run=self.dry_run_checkbox.isChecked(), 
            user_email_to_share_with=share_email 
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
            QMessageBox.information(self, "Share Success", "Folder sharing action completed.")
        else:
             QMessageBox.critical(self, "Share Failed", message)
        self.current_worker = None
        
    # ------------------------------------------------------------------ #
    #                           SYNC START                             #
    # ------------------------------------------------------------------ #
    def run_sync_now(self, clear_log: bool = True, force_live: bool = False):
        """Initializes and runs the main synchronization job."""
        
        auth_config = self._build_auth_config()
        if not auth_config:
            return
            
        local_path = self.local_path.text().strip()
        remote_path = self.remote_path.text().strip()
        
        # Logic for Dry Run Checkbox vs Force Live argument
        is_dry_run = self.dry_run_checkbox.isChecked()
        if force_live:
            is_dry_run = False
            
        share_email = None

        if not os.path.isdir(local_path):
            QMessageBox.warning(self, "Error", f"Local folder invalid:\n{local_path}")
            return
        if not remote_path:
            QMessageBox.warning(self, "Error", "Remote path cannot be empty.")
            return
        
        if auth_config.get("mode") == "service_account":
            email_text = self.share_email_input.text().strip()
            if email_text:
                share_email = email_text
        
        # DETERMINE SYNC ACTIONS
        if self.rb_delete_local.isChecked(): act_local = "delete_local"
        elif self.rb_ignore_local.isChecked(): act_local = "ignore_local"
        else: act_local = "upload"
            
        if self.rb_delete_remote.isChecked(): act_remote = "delete_remote"
        elif self.rb_ignore_remote.isChecked(): act_remote = "ignore_remote"
        else: act_remote = "download"

        # 3. UI LOCK & SETUP 
        msg = "STOP" if not is_dry_run else "STOP (Dry Run)"
        self.lock_ui(message=msg, is_running=True, clear_log=clear_log)
        self.log_window.show()

        # 4. START WORKER BASED ON PROVIDER
        provider_text = self.provider_combo.currentText()
        
        common_args = {
            "auth_config": auth_config,
            "local_path": local_path, 
            "remote_path": remote_path, 
            "dry_run": is_dry_run,
            "action_local_orphans": act_local,
            "action_remote_orphans": act_remote
        }

        if provider_text.startswith("Google Drive"):
            self.current_worker = GoogleDriveSyncWorker(
                **common_args,
                user_email_to_share_with=share_email
            )
        elif provider_text == "Dropbox":
            self.current_worker = DropboxDriveSyncWorker(**common_args)
        elif provider_text == "OneDrive":
            self.current_worker = OneDriveSyncWorker(**common_args)
        
        self.current_worker.signals.status_update.connect(self.handle_status_update)
        self.current_worker.signals.sync_finished.connect(self.handle_sync_finished)

        QThreadPool.globalInstance().start(self.current_worker)

    # ------------------------------------------------------------------ #
    #                           UI CONTROL                             #
    # ------------------------------------------------------------------ #
    def lock_ui(self, message: str, is_running: bool = False, clear_log: bool = False):
        """Locks UI elements and updates sync button text/style."""
        self.sync_button.setText(message)
        self.sync_button.setStyleSheet(STYLE_SYNC_STOP if is_running else STYLE_SYNC_RUN)
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


    # ------------------------------------------------------------------ #
    #                           LOGGING                                #
    # ------------------------------------------------------------------ #
    @Slot(str)
    def handle_status_update(self, msg: str):
        self.log_window.append_log(msg)

    # ------------------------------------------------------------------ #
    #                           FINISHED                               #
    # ------------------------------------------------------------------ #
    @Slot(bool, str, bool)
    def handle_sync_finished(self, success: bool, message: str, was_dry_run: bool):
        self.unlock_ui()
        status_str = "Completed" if success else "Failed"
        mode_str = "DRY RUN" if was_dry_run else "LIVE"
        
        final = f"\nFINAL STATUS: {mode_str} Sync {status_str}. {message}"
        self.log_window.append_log(final)
        
        self.current_worker = None

        if not success and "manually cancelled" not in message:
            QMessageBox.critical(self, "Sync Failed", message)
            return

        # --- DRY RUN CONFIRMATION LOGIC ---
        if success and was_dry_run:
            reply = QMessageBox.question(
                self, 
                "Dry Run Completed", 
                "The Dry Run finished successfully.\n\n"
                "Do you want to apply these changes now (Execute LIVE Sync)?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.log_window.append_log("\nUser confirmed application of changes. Starting LIVE run...")
                self.run_sync_now(clear_log=False, force_live=True)

    # ------------------------------------------------------------------ #
    #                           BROWSERS                               #
    # ------------------------------------------------------------------ #
    def browse_key_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Service Account Key", str(Path.home()), "JSON (*.json)"
        )
        if path:
            self.key_file_path.setText(path)

    def browse_client_secrets_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Client Secrets File", str(Path.home()), "JSON (*.json)"
        )
        if path:
            self.client_secrets_path.setText(path)

    def browse_local_directory(self):
        dir_ = QFileDialog.getExistingDirectory(
            self, "Select Local Source Folder", self.local_path.text() or str(Path.home())
        )
        if dir_:
            self.local_path.setText(dir_)

    def browse_directory(self, line_edit: QLineEdit = None):
        line_edit = line_edit or self.local_path
        dir_ = QFileDialog.getExistingDirectory(
            self, "Select Folder", line_edit.text() or str(Path.home())
        )
        if dir_:
            line_edit.setText(dir_)

    # ------------------------------------------------------------------ #
    #                     BaseTab abstract methods                     #
    # ------------------------------------------------------------------ #
    def browse_files(self):      
        provider_text = self.provider_combo.currentText()
        if provider_text.startswith("Google Drive"):
            self.browse_key_file()
            
    def browse_input(self):      self.browse_local_directory()
    def browse_output(self):     pass

    def collect(self) -> dict:
        """Collects current settings from the UI."""
        return {
            "provider": self.provider_combo.currentText(),
            "key_file": self.key_file_path.text().strip() or None,
            "client_secrets_file": self.client_secrets_path.text().strip() or None,
            "token_file": self.token_file_path.text().strip() or None,
            "local_path": self.local_path.text().strip() or None,
            "remote_path": self.remote_path.text().strip() or None,
            "dry_run": self.dry_run_checkbox.isChecked(),
            "share_email": self.share_email_input.text().strip() or None,
        }

    def get_default_config(self) -> dict:
        return {
            "provider": "Google Drive (Service Account)",
            "key_file": "C:/path/to/service_account_key.json",
            "client_secrets_file": "C:/path/to/client_secrets.json",
            "token_file": "C:/path/to/token.json",
            "local_path": "C:/path/to/local_source_folder",
            "remote_path": "My_App_Backups",
            "dry_run": True,
            "share_email": "user@example.com"
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
            
            print(f"DriveSyncTab configuration loaded.")
            
        except Exception as e:
            print(f"Error applying DriveSyncTab config: {e}")
            QMessageBox.warning(self, "Config Error", f"Failed to apply some settings: {e}")
