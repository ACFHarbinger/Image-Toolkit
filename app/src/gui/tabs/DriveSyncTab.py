# app/src/gui/tabs/DriveSyncTab.py
import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThreadPool, Slot
from PySide6.QtWidgets import (
    QApplication, QMessageBox, QHBoxLayout, QVBoxLayout,
    QLineEdit, QComboBox, QFileDialog, QPushButton, QLabel,
    QGroupBox, QCheckBox, QTextEdit,
)
from ..app_definitions import DRY_RUN
from ...utils.definitions import (
    SERVICE_ACCOUNT_FILE, LOCAL_SOURCE_PATH, DRIVE_DESTINATION_FOLDER_NAME
)
from ..helpers import GoogleDriveSyncWorker  # <-- QRunnable version
from .BaseTab import BaseTab
from ..styles import apply_shadow_effect


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
            "Dropbox (Not Yet Implemented)",
            "OneDrive (Not Yet Implemented)"
        ])
        self.provider_combo.setStyleSheet("QComboBox { font-weight: bold; }")
        provider_layout.addWidget(QLabel("Cloud Provider:"))
        provider_layout.addWidget(self.provider_combo)
        config_layout.addLayout(provider_layout)

        # Service Account Key
        key_layout = QHBoxLayout()
        self.key_file_path = QLineEdit(os.path.join(Path.home(), SERVICE_ACCOUNT_FILE))
        self.key_file_path.setPlaceholderText("Path to service_account_key.json")
        btn_browse_key = QPushButton("Browse Key File")
        apply_shadow_effect(btn_browse_key, "#000000", 8, 0, 3)
        btn_browse_key.clicked.connect(self.browse_key_file)

        self.key_file_label = QLabel("Service Account Key File:")
        self.key_file_edit_widget = self.key_file_path
        self.key_file_browse_button = btn_browse_key

        key_layout.addWidget(self.key_file_edit_widget)
        key_layout.addWidget(self.key_file_browse_button)

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
        
        # NEW: User Email to Share With
        share_layout = QHBoxLayout()
        self.share_email_input = QLineEdit()
        self.share_email_input.setPlaceholderText("Optional: User email to grant Editor access")
        share_layout.addWidget(QLabel("Share Folder With:"))
        share_layout.addWidget(self.share_email_input)
        
        # NEW: Control Buttons Layout
        control_buttons_layout = QHBoxLayout()
        
        # View Remote Files Button
        self.btn_view_remote = QPushButton("View Remote Files Map")
        apply_shadow_effect(self.btn_view_remote, "#000000", 8, 0, 3)
        self.btn_view_remote.clicked.connect(self.view_remote_map)
        control_buttons_layout.addWidget(self.btn_view_remote)

        # Share Folder Button (New Button)
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

        # Assemble config
        config_layout.addWidget(self.key_file_label)
        config_layout.addLayout(key_layout)
        config_layout.addWidget(QLabel("Local Source Directory:"))
        config_layout.addLayout(local_layout)
        config_layout.addWidget(QLabel("Remote Destination Path:"))
        config_layout.addLayout(remote_layout)
        config_layout.addLayout(share_layout)
        config_layout.addLayout(control_buttons_layout) # Use the new layout for buttons
        config_layout.addWidget(self.dry_run_checkbox)
        config_layout.addStretch(1)

        self.provider_combo.currentIndexChanged.connect(self.handle_provider_change)

        # ------------------ SYNC BUTTON ------------------
        self.sync_button = QPushButton("Run Synchronization Now")
        self.sync_button.setStyleSheet("""
            QPushButton { background:#2ecc71; color:white; padding:12px 16px;
                          font-size:14pt; border-radius:8px; font-weight:bold; }
            QPushButton:hover { background:#1e8449; }
            QPushButton:disabled { background:#4f545c; color:#a0a0a0; }
        """)
        apply_shadow_effect(self.sync_button, "#000000", 8, 0, 3)
        self.sync_button.clicked.connect(self.run_sync_now)

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

    # ------------------------------------------------------------------ #
    #                          PROVIDER SWITCH                          #
    # ------------------------------------------------------------------ #
    def handle_provider_change(self, index: int):
        is_google = self.provider_combo.currentText().startswith("Google Drive")
        for w in (self.key_file_label, self.key_file_edit_widget,
                  self.key_file_browse_button):
            w.setEnabled(is_google)
        
        self.btn_view_remote.setEnabled(is_google)
        self.btn_share_folder.setEnabled(is_google) # Enable/disable new share button

        if not is_google:
            self.key_file_path.setText("Web login not implemented")
            self.sync_button.setEnabled(False)
            QMessageBox.information(
                self, "Not Ready",
                f"{self.provider_combo.currentText()} is not implemented yet.\n"
                "Choose 'Google Drive (Service Account)'."
            )
        else:
            self.key_file_path.setText(SERVICE_ACCOUNT_FILE)
            self.sync_button.setEnabled(True)

    # ------------------------------------------------------------------ #
    #                           DEFAULTS                               #
    # ------------------------------------------------------------------ #
    def load_configuration_defaults(self):
        self.key_file_path.setText(SERVICE_ACCOUNT_FILE)
        self.local_path.setText(LOCAL_SOURCE_PATH)
        self.remote_path.setText(DRIVE_DESTINATION_FOLDER_NAME)
        self.share_email_input.setText("")

    # ------------------------------------------------------------------ #
    #                     VIEW REMOTE MAP ACTION                       #
    # ------------------------------------------------------------------ #
    def view_remote_map(self):
        """Action to initialize a worker to log the remote file map."""
        if not self.provider_combo.currentText().startswith("Google Drive"):
            QMessageBox.warning(self, "Error", "Only Google Drive is supported.")
            return

        key_file = self.key_file_path.text().strip()
        remote_path = self.remote_path.text().strip()
        
        # ---- validation ----
        if not os.path.isfile(key_file):
            QMessageBox.warning(self, "Error", f"Key file not found:\n{key_file}")
            return
        if not remote_path:
            QMessageBox.warning(self, "Error", "Remote path cannot be empty.")
            return

        # ---- UI lock ----
        self.lock_ui(message="Viewing Remote Map…")
        
        # Start worker. Use dry_run=True. Set local_path to current value. 
        # The core logic will recognize the invalid local path and skip file sync after logging remote map.
        self.current_worker = GoogleDriveSyncWorker(
            key_file, 
            self.local_path.text().strip(), 
            remote_path, 
            True, # Force Dry Run for viewing
            None 
        )
        self.current_worker.signals.status_update.connect(self.handle_status_update)
        # Use a custom finish handler for the view action
        self.current_worker.signals.sync_finished.connect(self.handle_view_finished) 

        QThreadPool.globalInstance().start(self.current_worker)

    @Slot(bool, str)
    def handle_view_finished(self, success: bool, message: str):
        """Custom handler for the View Remote Map action."""
        self.unlock_ui()

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
        if not self.provider_combo.currentText().startswith("Google Drive"):
            QMessageBox.warning(self, "Error", "Only Google Drive is supported.")
            return

        key_file = self.key_file_path.text().strip()
        remote_path = self.remote_path.text().strip()
        share_email = self.share_email_input.text().strip()
        
        # ---- validation ----
        if not os.path.isfile(key_file):
            QMessageBox.warning(self, "Error", f"Key file not found:\n{key_file}")
            return
        if not remote_path:
            QMessageBox.warning(self, "Error", "Remote path cannot be empty.")
            return
        if not share_email or '@' not in share_email:
            QMessageBox.warning(self, "Error", "Please enter a valid email address to share with.")
            return

        # ---- UI lock ----
        self.lock_ui(message="Sharing Folder…")
        
        # Start worker. The core logic handles the invalid local path gracefully after sharing.
        self.current_worker = GoogleDriveSyncWorker(
            key_file, 
            self.local_path.text().strip(), # Use the real, possibly invalid, local path
            remote_path=remote_path, 
            dry_run=self.dry_run_checkbox.isChecked(), # Use current dry run setting
            user_email_to_share_with=share_email 
        )
        self.current_worker.signals.status_update.connect(self.handle_status_update)
        self.current_worker.signals.sync_finished.connect(self.handle_share_finished) 

        QThreadPool.globalInstance().start(self.current_worker)

    @Slot(bool, str)
    def handle_share_finished(self, success: bool, message: str):
        """Custom handler for the Share Folder action."""
        self.unlock_ui()

        # The message will indicate if the share was successful and that sync was skipped.
        final = f"\nFINAL STATUS: Share Action {'Completed' if success else 'Failed'}. {message}"
        self.log_output.append(final)
        
        if success:
            QMessageBox.information(self, "Share Success", "Folder sharing action completed. Check the log for confirmation and the destination URL.")
        else:
             QMessageBox.critical(self, "Share Failed", message)
             
        self.current_worker = None
        
    # ------------------------------------------------------------------ #
    #                           SYNC START                             #
    # ------------------------------------------------------------------ #
    def run_sync_now(self):
        if not self.provider_combo.currentText().startswith("Google Drive"):
            QMessageBox.warning(self, "Error", "Only Google Drive is supported.")
            return

        key_file = self.key_file_path.text().strip()
        local_path = self.local_path.text().strip()
        remote_path = self.remote_path.text().strip()
        dry_run = self.dry_run_checkbox.isChecked()
        share_email = self.share_email_input.text().strip()

        # ---- validation ----
        if not os.path.isfile(key_file):
            QMessageBox.warning(self, "Error", f"Key file not found:\n{key_file}")
            return
        # Note: We skip the local path validation here as it's handled in GDS.execute_sync 
        # (It will return failure if local path is invalid AND no other actions like share/dry-run were requested)
        if not remote_path:
            QMessageBox.warning(self, "Error", "Remote path cannot be empty.")
            return

        # ---- UI lock ----
        self.lock_ui(message="Syncing…")

        # ---- start worker (QRunnable) ----
        self.current_worker = GoogleDriveSyncWorker(
            key_file, 
            local_path, 
            remote_path, 
            dry_run, 
            share_email
        )
        self.current_worker.signals.status_update.connect(self.handle_status_update)
        self.current_worker.signals.sync_finished.connect(self.handle_sync_finished)

        QThreadPool.globalInstance().start(self.current_worker)

    # ------------------------------------------------------------------ #
    #                           UI CONTROL                             #
    # ------------------------------------------------------------------ #
    def lock_ui(self, message: str):
        """Locks UI elements and updates button text."""
        self.log_output.clear()
        self.sync_button.setEnabled(False)
        self.btn_view_remote.setEnabled(False)
        self.btn_share_folder.setEnabled(False)
        self.sync_button.setText(message)
        QApplication.processEvents()
        
    def unlock_ui(self):
        """Unlocks UI elements and resets button text."""
        self.sync_button.setEnabled(True)
        self.sync_button.setText("Run Synchronization Now")
        self.btn_view_remote.setEnabled(True)
        self.btn_share_folder.setEnabled(True)

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

        if not success:
            QMessageBox.critical(self, "Sync Failed", message)

        self.current_worker = None   # QRunnable cleans itself up

    # ------------------------------------------------------------------ #
    #                           BROWSERS                               #
    # ------------------------------------------------------------------ #
    def browse_key_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Service Account Key", str(Path.home()), "JSON (*.json)"
        )
        if path:
            self.key_file_path.setText(path)

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
    def browse_files(self):      self.browse_key_file()
    def browse_input(self):      self.browse_local_directory()
    def browse_output(self):     pass

    def collect(self) -> dict:
        return {
            "provider": self.provider_combo.currentText(),
            "key_file": self.key_file_path.text().strip() or None,
            "local_path": self.local_path.text().strip() or None,
            "remote_path": self.remote_path.text().strip() or None,
            "dry_run": self.dry_run_checkbox.isChecked(),
            "share_email": self.share_email_input.text().strip() or None,
        }
