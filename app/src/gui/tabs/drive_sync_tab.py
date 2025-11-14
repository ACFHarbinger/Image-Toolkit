import os
from pathlib import Path
from typing import Optional, Dict, Any

from PySide6.QtCore import QThreadPool, Slot
from PySide6.QtWidgets import (
    QApplication, QMessageBox, QHBoxLayout, QVBoxLayout,
    QLineEdit, QComboBox, QFileDialog, QPushButton, QLabel,
    QGroupBox, QCheckBox, QTextEdit,
)
from ..utils.app_definitions import DRY_RUN
from ...utils.definitions import (
    DRIVE_DESTINATION_FOLDER_NAME,
    CLIENT_SECRETS_FILE, TOKEN_FILE,
    SERVICE_ACCOUNT_FILE, LOCAL_SOURCE_PATH, 
)
from .base_tab import BaseTab
from ..helpers import GoogleDriveSyncWorker
from ..utils.styles import apply_shadow_effect, STYLE_SYNC_RUN, STYLE_SYNC_STOP


class DriveSyncTab(BaseTab):
    """GUI tab for Google Drive one-way sync (QRunnable + QThreadPool)."""
    def __init__(self, dropdown=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dropdown = dropdown
        self.current_worker: Optional[GoogleDriveSyncWorker] = None

        main_layout = QVBoxLayout(self)

        # ------------------ CONFIG GROUP ------------------
        config_group = QGroupBox("Cloud Sync Configuration")
        config_layout = QVBoxLayout(config_group)

        # Provider dropdown
        provider_layout = QHBoxLayout()
        self.provider_combo = QComboBox()
        self.provider_combo.addItems([
            "Google Drive (Service Account)",
            "Google Drive (Personal Account)", # <-- NEW OPTION
            "Dropbox (Not Yet Implemented)",
            "OneDrive (Not Yet Implemented)"
        ])
        self.provider_combo.setStyleSheet("QComboBox { font-weight: bold; }")
        provider_layout.addWidget(QLabel("Cloud Provider:"))
        provider_layout.addWidget(self.provider_combo)
        config_layout.addLayout(provider_layout)

        # --- Service Account Key (Group 1) ---
        self.key_file_label = QLabel("Service Account Key File:")
        key_layout = QHBoxLayout()
        self.key_file_path = QLineEdit(os.path.join(Path.home(), SERVICE_ACCOUNT_FILE))
        self.key_file_path.setPlaceholderText("Path to service_account_key.json")
        self.btn_browse_key = QPushButton("Browse")
        apply_shadow_effect(self.btn_browse_key, "#000000", 8, 0, 3)
        self.btn_browse_key.clicked.connect(self.browse_key_file)
        key_layout.addWidget(self.key_file_path)
        key_layout.addWidget(self.btn_browse_key)

        # --- Personal Account: Client Secrets (Group 2) ---
        self.client_secrets_label = QLabel("Client Secrets File:")
        client_secrets_layout = QHBoxLayout()
        self.client_secrets_path = QLineEdit(os.path.join(Path.home(), CLIENT_SECRETS_FILE))
        self.client_secrets_path.setPlaceholderText("Path to client_secrets.json")
        self.btn_browse_client_secrets = QPushButton("Browse")
        apply_shadow_effect(self.btn_browse_client_secrets, "#000000", 8, 0, 3)
        self.btn_browse_client_secrets.clicked.connect(self.browse_client_secrets_file)
        client_secrets_layout.addWidget(self.client_secrets_path)
        client_secrets_layout.addWidget(self.btn_browse_client_secrets)
        
        # --- Personal Account: Token File (Group 2) ---
        self.token_file_label = QLabel("Token File (auto-generated):")
        token_file_layout = QHBoxLayout()
        self.token_file_path = QLineEdit(os.path.join(Path.home(), TOKEN_FILE))
        self.token_file_path.setPlaceholderText("Path to store token.json")
        token_file_layout.addWidget(self.token_file_path)

        # Local & Remote paths
        local_layout = QHBoxLayout()
        self.local_path = QLineEdit(LOCAL_SOURCE_PATH)
        self.local_path.setPlaceholderText("Local directory to synchronize")
        btn_browse_local = QPushButton("Browse Local Dir")
        apply_shadow_effect(btn_browse_local, "#000000", 8, 0, 3)
        btn_browse_local.clicked.connect(self.browse_local_directory)
        local_layout.addWidget(self.local_path)
        local_layout.addWidget(btn_browse_local)

        remote_layout = QHBoxLayout()
        self.remote_path = QLineEdit(DRIVE_DESTINATION_FOLDER_NAME)
        self.remote_path.setPlaceholderText("Drive folder (e.g. Backups/2025)")
        remote_layout.addWidget(self.remote_path)
        
        # User Email to Share With (For Service Account)
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
        # Add all widgets, then show/hide them in handle_provider_change
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
        config_layout.addLayout(share_layout)
        config_layout.addLayout(control_buttons_layout)
        config_layout.addWidget(self.dry_run_checkbox)
        config_layout.addStretch(1)

        self.provider_combo.currentIndexChanged.connect(self.handle_provider_change)

        # ------------------ SYNC BUTTON ------------------
        self.sync_button = QPushButton("Run Synchronization Now")
        self.sync_button.setStyleSheet(STYLE_SYNC_RUN)
        apply_shadow_effect(self.sync_button, "#000000", 8, 0, 3)
        self.sync_button.clicked.connect(self.toggle_sync) 

        # ------------------ LOG AREA ------------------
        status_group = QGroupBox("Synchronization Status Log")
        status_layout = QVBoxLayout(status_group)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("background:#1e1e1e; color:#b9bbbe; border:none;")
        status_layout.addWidget(self.log_output)

        # ------------------ LAYOUT ------------------
        main_layout.addWidget(config_group)
        main_layout.addWidget(self.sync_button)
        main_layout.addWidget(status_group, 1)

        self.load_configuration_defaults()
        self.handle_provider_change(0) # Initial UI setup
        
    # ------------------------------------------------------------------ #
    #                         SYNC TOGGLE                              #
    # ------------------------------------------------------------------ #
    def toggle_sync(self):
        """Starts the sync if idle, or stops it if running."""
        if self.current_worker is None:
            self.run_sync_now(clear_log=True) # Clear log only on start
        else:
            self.stop_sync_now()

    def stop_sync_now(self):
        """Initiates the graceful stop of the running worker and immediately resets UI."""
        if self.current_worker:
            self.current_worker.stop()
            self.unlock_ui()
            self.log_output.append("\nManually interrupted. Resetting UI...")
            self.current_worker = None # Crucial: Allows re-run immediately

    # ------------------------------------------------------------------ #
    #                          PROVIDER SWITCH                          #
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
            w.setEnabled(is_google_service)
        
        # Toggle general Google buttons
        self.btn_view_remote.setEnabled(is_google)
        self.sync_button.setEnabled(is_google)

        if not is_google:
            self.sync_button.setEnabled(False)
            QMessageBox.information(
                self, "Not Ready",
                f"{self.provider_combo.currentText()} is not implemented yet.\n"
                "Please choose a 'Google Drive' option."
            )

    # ------------------------------------------------------------------ #
    #                    AUTH CONFIG BUILDER                           #
    # ------------------------------------------------------------------ #

    def _build_auth_config(self) -> Optional[Dict[str, Any]]:
        """
        Builds a configuration dictionary for the worker based on the
        selected provider.
        """
        provider_text = self.provider_combo.currentText()
        auth_config = {}

        if provider_text.startswith("Google Drive (Service Account)"):
            key_file = self.key_file_path.text().strip()
            if not os.path.isfile(key_file):
                QMessageBox.warning(self, "Error", f"Service Account Key file not found:\n{key_file}")
                return None
            
            auth_config = {
                "mode": "service_account",
                "key_file": key_file
            }
            
        elif provider_text.startswith("Google Drive (Personal Account)"):
            client_secrets = self.client_secrets_path.text().strip()
            token_file = self.token_file_path.text().strip()
            
            if not os.path.isfile(client_secrets):
                QMessageBox.warning(self, "Error", f"Client Secrets file not found:\n{client_secrets}")
                return None
            if not token_file:
                QMessageBox.warning(self, "Error", "Token File path cannot be empty.")
                return None
            
            auth_config = {
                "mode": "personal_account",
                "client_secrets_file": client_secrets,
                "token_file": token_file
            }
            
        else:
            QMessageBox.warning(self, "Error", "Selected provider is not supported.")
            return None
            
        return auth_config

    # ------------------------------------------------------------------ #
    #                           DEFAULTS                               #
    # ------------------------------------------------------------------ #
    def load_configuration_defaults(self):
        self.key_file_path.setText(SERVICE_ACCOUNT_FILE)
        self.client_secrets_path.setText(CLIENT_SECRETS_FILE)
        self.token_file_path.setText(TOKEN_FILE)
        self.local_path.setText(LOCAL_SOURCE_PATH)
        self.remote_path.setText(DRIVE_DESTINATION_FOLDER_NAME)
        self.share_email_input.setText("")

    # ------------------------------------------------------------------ #
    #                     VIEW REMOTE MAP ACTION                       #
    # ------------------------------------------------------------------ #
    def view_remote_map(self):
        """Action to initialize a worker to log the remote file map."""
        if self.current_worker:
            return # Ignore if sync is running
            
        auth_config = self._build_auth_config()
        if not auth_config:
            return

        remote_path = self.remote_path.text().strip()
        if not remote_path:
            QMessageBox.warning(self, "Error", "Remote path cannot be empty.")
            return

        # ---- UI lock ----
        self.lock_ui_minor(message="Viewing Remote Map…", clear_log=True)
        
        self.current_worker = GoogleDriveSyncWorker(
            auth_config=auth_config,
            local_path=self.local_path.text().strip(), 
            remote_path=remote_path, 
            dry_run=True, # Force Dry Run for viewing
            user_email_to_share_with=None # No sharing for this action
        )
        self.current_worker.signals.status_update.connect(self.handle_status_update)
        self.current_worker.signals.sync_finished.connect(self.handle_view_finished) 

        QThreadPool.globalInstance().start(self.current_worker)

    @Slot(bool, str)
    def handle_view_finished(self, success: bool, message: str):
        """Custom handler for the View Remote Map action."""
        self.unlock_ui_minor()
        final = f"\nFINAL STATUS: Remote Map View {'Completed' if success else 'Failed'}. {message}"
        self.log_output.append(final)
        
        if not success and "Dry Run incomplete" not in message and "Local file sync skipped" not in message:
            QMessageBox.critical(self, "Map View Failed", message)
        self.current_worker = None
        
    # ------------------------------------------------------------------ #
    #                     SHARE FOLDER ACTION                          #
    # ------------------------------------------------------------------ #
    def share_remote_folder(self):
        """Action to initialize a worker to perform ONLY the sharing action."""
        if self.current_worker:
            return # Ignore if sync is running
        
        # This button is disabled for personal, but double-check
        auth_config = self._build_auth_config()
        if not auth_config or auth_config["mode"] != "service_account":
            QMessageBox.warning(self, "Error", "Sharing is only available for Service Accounts.")
            return

        remote_path = self.remote_path.text().strip()
        share_email = self.share_email_input.text().strip()
        
        if not remote_path:
            QMessageBox.warning(self, "Error", "Remote path cannot be empty.")
            return
        if not share_email or '@' not in share_email:
            QMessageBox.warning(self, "Error", "Please enter a valid email address to share with.")
            return

        # ---- UI lock ----
        self.lock_ui_minor(message="Sharing Folder…", clear_log=True)
        
        self.current_worker = GoogleDriveSyncWorker(
            auth_config=auth_config,
            local_path=self.local_path.text().strip(), 
            remote_path=remote_path, 
            dry_run=self.dry_run_checkbox.isChecked(), 
            user_email_to_share_with=share_email 
        )
        self.current_worker.signals.status_update.connect(self.handle_status_update)
        self.current_worker.signals.sync_finished.connect(self.handle_share_finished) 

        QThreadPool.globalInstance().start(self.current_worker)

    @Slot(bool, str)
    def handle_share_finished(self, success: bool, message: str):
        """Custom handler for the Share Folder action."""
        self.unlock_ui_minor()
        final = f"\nFINAL STATUS: Share Action {'Completed' if success else 'Failed'}. {message}"
        self.log_output.append(final)
        
        if success:
            QMessageBox.information(self, "Share Success", "Folder sharing action completed.")
        else:
             QMessageBox.critical(self, "Share Failed", message)
        self.current_worker = None
        
    # ------------------------------------------------------------------ #
    #                           SYNC START                             #
    # ------------------------------------------------------------------ #
    def run_sync_now(self, clear_log: bool = True):
        """Initializes and runs the main synchronization job."""
        
        # 1. BUILD AUTH CONFIG AND VALIDATE AUTH FILES (MUST COME FIRST)
        auth_config = self._build_auth_config()
        if not auth_config:
            # _build_auth_config already shows a QMessageBox, just return.
            return
            
        local_path = self.local_path.text().strip()
        remote_path = self.remote_path.text().strip()
        dry_run = self.dry_run_checkbox.isChecked()
        share_email = None

        # 2. PERFORM PATH VALIDATION (STILL BEFORE UI LOCK)
        if not os.path.isdir(local_path):
            QMessageBox.warning(self, "Error", f"Local folder invalid:\n{local_path}")
            return
        if not remote_path:
            QMessageBox.warning(self, "Error", "Remote path cannot be empty.")
            return
        
        # Only set share_email if it's a service account and the field is filled
        if auth_config["mode"] == "service_account":
            email_text = self.share_email_input.text().strip()
            if email_text:
                share_email = email_text
        
        # 3. UI LOCK & SETUP (ONLY AFTER ALL VALIDATION PASSES)
        self.lock_ui(message="STOP", is_running=True, clear_log=clear_log)

        # 4. START WORKER
        self.current_worker = GoogleDriveSyncWorker(
            auth_config=auth_config,
            local_path=local_path, 
            remote_path=remote_path, 
            dry_run=dry_run, 
            user_email_to_share_with=share_email
        )
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
        self.sync_button.setEnabled(True) # Re-enable to allow STOP click

        # Disable configuration inputs and minor buttons
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
        
        # Buttons
        self.btn_view_remote.setEnabled(config_enabled)
        self.btn_share_folder.setEnabled(config_enabled)
        
        if clear_log: 
            self.log_output.clear()
        QApplication.processEvents()
        
    def unlock_ui(self):
        """Unlocks all UI elements and resets sync button state."""
        self.lock_ui(message="Run Synchronization Now", is_running=False)
        # Restore provider-specific UI state
        self.handle_provider_change(self.provider_combo.currentIndex())
        
    def lock_ui_minor(self, message: str, clear_log: bool = False):
        """Locks only minor action buttons while View/Share is running."""
        if clear_log:
            self.log_output.clear()
        self.btn_view_remote.setEnabled(False)
        self.btn_share_folder.setEnabled(False)
        self.sync_button.setEnabled(False)
        QApplication.processEvents()

    def unlock_ui_minor(self):
        """Unlocks minor action buttons."""
        self.btn_view_remote.setEnabled(True)
        self.btn_share_folder.setEnabled(True)
        self.sync_button.setEnabled(True)
        # Restore provider-specific UI state
        self.handle_provider_change(self.provider_combo.currentIndex())


    # ------------------------------------------------------------------ #
    #                           LOGGING                                #
    # ------------------------------------------------------------------ #
    @Slot(str)
    def handle_status_update(self, msg: str):
        self.log_output.append(msg)

    # ------------------------------------------------------------------ #
    #                           FINISHED                               #
    # ------------------------------------------------------------------ #
    @Slot(bool, str)
    def handle_sync_finished(self, success: bool, message: str):
        self.unlock_ui()
        final = f"\nFINAL STATUS: {message}"
        self.log_output.append(final)
        if not success and "manually cancelled" not in message:
            QMessageBox.critical(self, "Sync Failed", message)
        self.current_worker = None
        
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
    #                     BaseTab abstract methods                      #
    # ------------------------------------------------------------------ #
    def browse_files(self):      
        provider_text = self.provider_combo.currentText()
        if provider_text.startswith("Google Drive (Service Account)"):
            self.browse_key_file()
        elif provider_text.startswith("Google Drive (Personal Account)"):
            self.browse_client_secrets_file()
            
    def browse_input(self):      self.browse_local_directory()
    def browse_output(self):     pass

    def collect(self) -> dict:
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
