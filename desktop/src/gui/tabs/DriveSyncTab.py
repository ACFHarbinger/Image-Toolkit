import os

from PySide6.QtCore import QThread, QThreadPool
from PySide6.QtWidgets import (
    QApplication, QMessageBox, QHBoxLayout, 
    QVBoxLayout, QLineEdit, QComboBox,
    QFileDialog, QPushButton, QLabel, 
    QGroupBox, QCheckBox, QTextEdit,
)
from pathlib import Path
from ..app_definitions import (
    SERVICE_ACCOUNT_FILE, LOCAL_SOURCE_PATH, 
    DRY_RUN, DRIVE_DESTINATION_FOLDER_NAME
) 
from ..helpers import GoogleDriveSyncWorker
from .BaseTab import BaseTab
from ..styles import apply_shadow_effect


class DriveSyncTab(BaseTab):
    """
    A GUI tab for configuring and executing the Cloud Drive synchronization script.
    """
    def __init__(self, dropdown=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dropdown = dropdown
        
        self.threadpool = QThreadPool.globalInstance()
        self.current_worker = None
        self.current_thread = None
        
        main_layout = QVBoxLayout(self)
        
        # --- 2.1. Configuration Group ---
        config_group = QGroupBox("Cloud Sync Configuration")
        config_layout = QVBoxLayout(config_group)
        
        # --- NEW: Cloud Provider Dropdown ---
        provider_layout = QHBoxLayout()
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Google Drive (Service Account)"]) # Only Google is supported now
        self.provider_combo.addItems(["Dropbox (Not Yet Implemented)", "OneDrive (Not Yet Implemented)"])
        self.provider_combo.setStyleSheet("QComboBox { font-weight: bold; }")
        
        provider_layout.addWidget(QLabel("Cloud Provider:"))
        provider_layout.addWidget(self.provider_combo)
        
        config_layout.addLayout(provider_layout)
        
        # Service Account File (Only relevant for Google Service Account)
        key_layout = QHBoxLayout()
        self.key_file_path = QLineEdit(os.path.join(Path.home(), SERVICE_ACCOUNT_FILE))
        self.key_file_path.setPlaceholderText("Path to service_account_key.json")
        btn_browse_key = QPushButton("Browse Key File")
        apply_shadow_effect(btn_browse_key, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        btn_browse_key.clicked.connect(self.browse_key_file)
        
        # Key File elements stored as attributes for later enabling/disabling
        self.key_file_label = QLabel("Service Account Key File:")
        self.key_file_edit_widget = self.key_file_path
        self.key_file_browse_button = btn_browse_key

        key_layout.addWidget(self.key_file_edit_widget)
        key_layout.addWidget(self.key_file_browse_button)
        
        # Local Source Path
        local_layout = QHBoxLayout()
        self.local_path = QLineEdit(LOCAL_SOURCE_PATH)
        self.local_path.setPlaceholderText("Local directory to synchronize")
        btn_browse_local = QPushButton("Browse Local Dir")
        apply_shadow_effect(btn_browse_local, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        btn_browse_local.clicked.connect(self.browse_local_directory)
        local_layout.addWidget(self.local_path)
        local_layout.addWidget(btn_browse_local)
        
        # Remote Destination Path
        remote_layout = QHBoxLayout()
        self.remote_path = QLineEdit(DRIVE_DESTINATION_FOLDER_NAME)
        self.remote_path.setPlaceholderText("Drive/Remote folder path (e.g., Scheduled_Backups/Current_Month)")
        remote_layout.addWidget(self.remote_path)

        # Dry Run Checkbox
        self.dry_run_checkbox = QCheckBox("Perform Dry Run (Simulate only, no files changed)")
        self.dry_run_checkbox.setChecked(DRY_RUN)
        self.dry_run_checkbox.setStyleSheet("""
            QCheckBox { 
                color: #f1c40f; 
            }
            QCheckBox::indicator {
                width: 16px; 
                height: 16px; 
                border: 1px solid #555;
                border-radius: 3px; 
                background-color: #333;
            }
            QCheckBox::indicator:checked {
                background-color: #f1c40f; 
                border: 1px solid #f1c40f; 
            }
        """)
        
        # Add components to config layout
        config_layout.addWidget(self.key_file_label)
        config_layout.addLayout(key_layout)
        config_layout.addWidget(QLabel("Local Source Directory:"))
        config_layout.addLayout(local_layout)
        config_layout.addWidget(QLabel("Remote Destination Path:")) # <-- RENAMED LABEL
        config_layout.addLayout(remote_layout)
        config_layout.addWidget(self.dry_run_checkbox)
        config_layout.addStretch(1)
        
        # --- Connect Provider Change Handler ---
        self.provider_combo.currentIndexChanged.connect(self.handle_provider_change)
        
        # --- 2.2. Sync Action Button ---
        self.sync_button = QPushButton("🚀 Run Synchronization Now")
        self.sync_button.setStyleSheet("""
            QPushButton { 
                background-color: #2ecc71; /* Green for GO */
                color: white; 
                padding: 12px 16px; 
                font-size: 14pt;
                border-radius: 8px;
                font-weight: bold;
            } 
            QPushButton:hover { 
                background-color: #1e8449; 
            }
            QPushButton:disabled {
                background-color: #4f545c;
                color: #a0a0a0;
            }
        """)
        apply_shadow_effect(self.sync_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.sync_button.clicked.connect(self.run_sync_now)
        
        # --- 2.3. Status Log Group ---
        status_group = QGroupBox("Synchronization Status Log")
        status_layout = QVBoxLayout(status_group)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("QTextEdit { background-color: #1e1e1e; color: #b9bbbe; border: none; }")
        status_layout.addWidget(self.log_output)
        
        # --- 2.4. Main Layout Assembly ---
        main_layout.addWidget(config_group)
        main_layout.addWidget(self.sync_button)
        main_layout.addWidget(status_group, 1) # Status log takes extra space
        
        # Ensure configuration defaults are loaded
        self.load_configuration_defaults()
        
    def handle_provider_change(self, index: int):
        """
        Handles changes in the cloud provider dropdown, enabling/disabling relevant fields.
        """
        provider_text = self.provider_combo.currentText()
        is_google_sa = provider_text.startswith("Google Drive")
        
        # Disable if provider is not Google Drive (Service Account)
        self.key_file_label.setEnabled(is_google_sa)
        self.key_file_edit_widget.setEnabled(is_google_sa)
        self.key_file_browse_button.setEnabled(is_google_sa)
        
        if not is_google_sa:
            self.key_file_path.setText("Authentication handled via web login (not yet implemented)")
            self.sync_button.setEnabled(False)
            QMessageBox.information(
                self, "Provider Not Ready", 
                f"Synchronization for {provider_text} is not yet implemented. Please select 'Google Drive (Service Account)'."
            )
        else:
            # Restore default path if switching back to Google
            self.key_file_path.setText(SERVICE_ACCOUNT_FILE)
            self.sync_button.setEnabled(True) # Re-enable sync button

    def load_configuration_defaults(self):
        """Attempts to load configuration from the global script constants."""
        global SERVICE_ACCOUNT_FILE, LOCAL_SOURCE_PATH, DRIVE_DESTINATION_FOLDER_NAME
        
        self.key_file_path.setText(SERVICE_ACCOUNT_FILE)
        self.local_path.setText(LOCAL_SOURCE_PATH)
        self.remote_path.setText(DRIVE_DESTINATION_FOLDER_NAME)
        
    def run_sync_now(self):
        """Starts the synchronization worker thread."""
        provider = self.provider_combo.currentText()
        if not provider.startswith("Google Drive"):
             QMessageBox.warning(self, "Provider Error", "Only Google Drive is currently supported.")
             return

        key_file = self.key_file_path.text().strip()
        local_path = self.local_path.text().strip()
        remote_path = self.remote_path.text().strip()
        dry_run = self.dry_run_checkbox.isChecked()
        
        # Basic validation
        if not os.path.isfile(key_file):
            QMessageBox.warning(self, "Configuration Error", f"Service Account Key file not found: {key_file}")
            return
        if not os.path.isdir(local_path):
            QMessageBox.warning(self, "Configuration Error", f"Local Source path is not a valid directory: {local_path}")
            return
        if not remote_path:
            QMessageBox.warning(self, "Configuration Error", "Drive Destination Folder cannot be empty.")
            return

        self.log_output.clear()
        self.sync_button.setEnabled(False)
        self.sync_button.setText("Syncing... Please Wait")
        QApplication.processEvents()

        # 1. Create worker and thread
        self.current_worker = GoogleDriveSyncWorker(key_file, local_path, remote_path, dry_run)
        self.current_thread = QThread()
        self.current_worker.moveToThread(self.current_thread)
        
        # 2. Connect signals
        self.current_thread.started.connect(self.current_worker.run_sync)
        self.current_worker.status_update.connect(self.handle_status_update)
        self.current_worker.sync_finished.connect(self.handle_sync_finished)
        
        # 3. Cleanup connections
        self.current_worker.sync_finished.connect(self.current_thread.quit)
        self.current_worker.sync_finished.connect(self.current_worker.deleteLater)
        self.current_thread.finished.connect(self.current_thread.deleteLater)
        
        # 4. Start thread
        self.current_thread.start()

    def handle_status_update(self, message: str):
        """Appends status messages to the log area."""
        self.log_output.append(message)
        
    def handle_sync_finished(self, success: bool, message: str):
        """Handles cleanup after the worker finishes."""
        self.sync_button.setEnabled(True)
        self.sync_button.setText("🚀 Run Synchronization Now")
        
        if success:
            self.log_output.append(f"\nFINAL STATUS: {message}")
        else:
            QMessageBox.critical(self, "Sync Failed", message)
            self.log_output.append(f"\nFINAL STATUS: {message}")
            
        self.current_worker = None
        self.current_thread = None

    # --- BaseTab Abstract Method Implementations ---

    def browse_key_file(self):
        """Browse for the Service Account JSON key file."""
        initial_dir = os.path.dirname(self.key_file_path.text()) or str(Path.home())
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Service Account Key File", initial_dir, "JSON Files (*.json)"
        )
        if filepath:
            self.key_file_path.setText(filepath)

    def browse_local_directory(self):
        """Browse for the Local Source Directory."""
        self.browse_directory(self.local_path)
    
    def browse_files(self):
        """Not used directly, mapped to browse_key_file."""
        self.browse_key_file()

    def browse_directory(self, line_edit: QLineEdit = None):
        """Select directory for a given QLineEdit."""
        line_edit = line_edit or self.local_path
        initial_dir = line_edit.text() or str(Path.home())
        directory = QFileDialog.getExistingDirectory(
            self, "Select Local Source Directory", initial_dir
        )
        if directory:
            line_edit.setText(directory)

    def browse_input(self):
        """Mapped to browse_local_directory."""
        self.browse_local_directory()

    def browse_output(self):
        """Not used for this tab."""
        pass

    def collect(self) -> dict:
        """Collect current configuration inputs."""
        return {
            "provider": self.provider_combo.currentText(),
            "key_file": self.key_file_path.text().strip() or None,
            "local_path": self.local_path.text().strip() or None,
            "remote_path": self.remote_path.text().strip() or None,
            "dry_run": self.dry_run_checkbox.isChecked(),
        }
