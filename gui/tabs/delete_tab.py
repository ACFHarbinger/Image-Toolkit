import os
from pathlib import Path
from typing import Dict, Any, Optional

from PySide6.QtWidgets import (
    QLineEdit, QPushButton, QCheckBox, QFileDialog,
    QFormLayout, QHBoxLayout, QVBoxLayout, QWidget,
    QMessageBox, QLabel, QGroupBox, QApplication
)
from PySide6.QtCore import Qt, Slot
from .base_tab import BaseTab
from ..helpers import DeletionWorker
from ..components import OptionalField
from ..styles.style import apply_shadow_effect
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS


class DeleteTab(BaseTab):
    def __init__(self, dropdown=True):
        super().__init__()
        self.dropdown = dropdown
        self.worker: Optional[DeletionWorker] = None

        # --- Main Layout ---
        main_layout = QVBoxLayout(self)

        # --- Delete Targets Group ---
        target_group = QGroupBox("Delete Targets")
        target_layout = QFormLayout(target_group)

        # Target path
        v_target_group = QVBoxLayout()
        self.target_path = QLineEdit()
        v_target_group.addWidget(self.target_path)

        h_buttons = QHBoxLayout()
        btn_target_file = QPushButton("Choose file...")
        apply_shadow_effect(btn_target_file, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        btn_target_file.clicked.connect(self.browse_file)
        btn_target_dir = QPushButton("Choose directory...")
        apply_shadow_effect(btn_target_dir, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        btn_target_dir.clicked.connect(self.browse_directory)
        h_buttons.addWidget(btn_target_file)
        h_buttons.addWidget(btn_target_dir)
        v_target_group.addLayout(h_buttons)
        target_layout.addRow("Target path (file or dir):", v_target_group)
        
        main_layout.addWidget(target_group)

        # --- Delete Settings Group ---
        settings_group = QGroupBox("Delete Settings")
        settings_layout = QFormLayout(settings_group)

        # Extensions
        if self.dropdown:
            self.selected_extensions = set()
            ext_layout = QVBoxLayout()

            btn_layout = QHBoxLayout()
            self.extension_buttons = {}
            for ext in SUPPORTED_IMG_FORMATS:
                btn = QPushButton(ext)
                btn.setCheckable(True)
                btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")
                apply_shadow_effect(btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
                btn.clicked.connect(lambda checked, e=ext: self.toggle_extension(e, checked))
                btn_layout.addWidget(btn)
                self.extension_buttons[ext] = btn
            ext_layout.addLayout(btn_layout)

            all_btn_layout = QHBoxLayout()
            btn_add_all = QPushButton("Add All")
            btn_add_all.setStyleSheet("background-color: green; color: white;")
            apply_shadow_effect(btn_add_all, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
            btn_add_all.clicked.connect(self.add_all_extensions)
            btn_remove_all = QPushButton("Remove All")
            btn_remove_all.setStyleSheet("background-color: red; color: white;")
            apply_shadow_effect(btn_remove_all, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
            btn_remove_all.clicked.connect(self.remove_all_extensions)
            all_btn_layout.addWidget(btn_add_all)
            all_btn_layout.addWidget(btn_remove_all)
            ext_layout.addLayout(all_btn_layout)

            ext_container = QWidget()
            ext_container.setLayout(ext_layout)
            self.extensions_field = OptionalField("Target extensions", ext_container, start_open=False)
            settings_layout.addRow(self.extensions_field)
        else:
            self.selected_extensions = None
            self.target_extensions = QLineEdit()
            self.target_extensions.setPlaceholderText("e.g. .txt .jpg or txt jpg")
            settings_layout.addRow("Target extensions (optional):", self.target_extensions)

        # Confirmation
        self.confirm_checkbox = QCheckBox("Require confirmation before delete (recommended)")
        self.confirm_checkbox.setChecked(True)
        settings_layout.addRow(self.confirm_checkbox)

        main_layout.addWidget(settings_group)
        
        # Add a stretch to push button/status to the bottom
        main_layout.addStretch(1)

        # --- Run Buttons Layout (Replaces single run_button) ---
        run_buttons_layout = QHBoxLayout()

        # Define the shared style for the gradient button
        SHARED_BUTTON_STYLE = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white; font-weight: bold; font-size: 14px;
                padding: 14px 8px; border-radius: 10px; min-height: 44px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #764ba2, stop:1 #667eea); }
            QPushButton:disabled { background: #718096; }
            QPushButton:pressed { background: #5a67d8; }
        """

        # 1. Delete Files Only Button (Existing logic)
        self.btn_delete_files = QPushButton("Delete Files Only")
        self.btn_delete_files.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(self.btn_delete_files, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_delete_files.clicked.connect(lambda: self.start_deletion(mode='files'))
        run_buttons_layout.addWidget(self.btn_delete_files)

        # 2. Delete Directory & Contents Button (Now using the SHARED_BUTTON_STYLE)
        self.btn_delete_directory = QPushButton("Delete Directory and Contents")
        self.btn_delete_directory.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(self.btn_delete_directory, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_delete_directory.clicked.connect(lambda: self.start_deletion(mode='directory'))
        run_buttons_layout.addWidget(self.btn_delete_directory)

        main_layout.addLayout(run_buttons_layout)

        # --- Status ---
        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)

    def toggle_extension(self, ext, checked):
        btn = self.extension_buttons[ext]
        if checked:
            self.selected_extensions.add(ext)
            btn.setStyleSheet("""
                QPushButton:checked { background-color: #3320b5; color: white; }
                QPushButton:hover { background-color: #00838a; }
            """)
            apply_shadow_effect(btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        else:
            self.selected_extensions.discard(ext)
            btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")
            apply_shadow_effect(btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)

    def add_all_extensions(self):
        for ext, btn in self.extension_buttons.items():
            btn.setChecked(True)
            self.toggle_extension(ext, True)

    def remove_all_extensions(self):
        for ext, btn in self.extension_buttons.items():
            btn.setChecked(False)
            self.toggle_extension(ext, False)

    def _get_starting_dir(self) -> str:
        """Helper to determine a reasonable starting directory."""
        path = Path(os.getcwd())
        parts = path.parts
        try:
            # Attempt to find a 'data' folder inside an 'Image-Toolkit' folder
            start_dir = os.path.join(Path(*parts[:parts.index('Image-Toolkit') + 1]), 'data')
            if not Path(start_dir).is_dir():
                 return os.getcwd()
            return start_dir
        except ValueError:
            return os.getcwd()

    def browse_file(self):
        # Determine starting directory
        start_dir = self._get_starting_dir()
        
        # Use getOpenFileName for selecting a file
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select File", 
            start_dir, 
            f"Image Files ({' '.join(['*' + ext for ext in SUPPORTED_IMG_FORMATS])});;All Files (*)"
        )
        if file_path:
            self.target_path.setText(file_path)

    def browse_directory(self):
        start_dir = self._get_starting_dir()
            
        # Use getExistingDirectory, which is designed to select directories.
        directory = QFileDialog.getExistingDirectory(
            self, 
            "Select Directory to Delete", 
            start_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if directory:
            self.target_path.setText(directory)

    def is_valid(self, mode: str):
        path = self.target_path.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Invalid Path", "Please select a valid file or folder.")
            return False
        
        # Directory mode requires the path to be a directory
        if mode == 'directory' and not os.path.isdir(path):
            QMessageBox.warning(self, "Invalid Target", "The 'Delete Directory & Contents' action requires a directory path.")
            return False
            
        return True

    def start_deletion(self, mode: str):
        if not self.is_valid(mode):
            return

        config = self.collect(mode)
        config["require_confirm"] = self.confirm_checkbox.isChecked()

        # Disable both buttons
        self.btn_delete_files.setEnabled(False)
        self.btn_delete_directory.setEnabled(False)
        self.status_label.setText(f"Starting {mode} deletion...")
        QApplication.processEvents() # Ensure UI updates

        self.worker = DeletionWorker(config)
        
        # Connect signals for confirmation and results
        self.worker.confirm_signal.connect(self.handle_confirmation_request)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_deletion_done)
        self.worker.error.connect(self.on_deletion_error)
        
        self.worker.start()

    @Slot(str, int)
    def handle_confirmation_request(self, message: str, total_items: int):
        """Shows the QMessageBox on the main thread and sends the result back to the worker."""
        # Determine the correct title based on the action
        title = "Confirm Directory Deletion" if total_items == 1 and "directory" in message else "Confirm File Deletion"
        
        reply = QMessageBox.question(
            self, title,
            message,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        # Send boolean result back to the worker's slot
        response = (reply == QMessageBox.Yes)
        self.worker.set_confirmation_response(response)


    def update_progress(self, deleted, total):
        self.status_label.setText(f"Deleted {deleted} of {total}...")

    def on_deletion_done(self, count, msg):
        self.btn_delete_files.setEnabled(True)
        self.btn_delete_directory.setEnabled(True)
        self.status_label.setText(msg)
        QMessageBox.information(self, "Complete", msg)
        self.worker = None # Clear worker reference

    def on_deletion_error(self, msg):
        self.btn_delete_files.setEnabled(True)
        self.btn_delete_directory.setEnabled(True)
        self.status_label.setText("Failed.")
        QMessageBox.critical(self, "Error", msg)
        self.worker = None # Clear worker reference

    def collect(self, mode: str) -> Dict[str, Any]:
        extensions = []
        if mode == 'files':
            if self.dropdown and self.selected_extensions:
                extensions = list(self.selected_extensions)
            elif not self.dropdown:
                extensions = self.join_list_str(self.target_extensions.text().strip())
            else:
                extensions = SUPPORTED_IMG_FORMATS
        
        return {
            "target_path": self.target_path.text().strip(),
            "mode": mode, 
            "target_extensions": [e.strip().lstrip('.') for e in extensions if e.strip()],
        }

    def get_default_config(self) -> dict:
        """Returns the default configuration dictionary for this tab."""
        return {
            "target_path": "C:\\Default\\Target\\Path",
            "mode": "files",
            "target_extensions": ["jpg", "png"],
            "require_confirm": True
        }

    def set_config(self, config: dict):
        """Applies a configuration dictionary to the UI fields."""
        try:
            self.target_path.setText(config.get("target_path", ""))
            self.confirm_checkbox.setChecked(config.get("require_confirm", True))

            target_extensions = config.get("target_extensions", [])
            if self.dropdown:
                self.remove_all_extensions()
                for ext in target_extensions:
                    if ext in self.extension_buttons:
                        self.extension_buttons[ext].setChecked(True)
                        self.toggle_extension(ext, True)
            else:
                self.target_extensions.setText(", ".join(target_extensions))
        except Exception as e:
            print(f"Error applying DeleteTab config: {e}")
            QMessageBox.warning(self, "Config Error", f"Failed to apply some settings: {e}")

    @staticmethod
    def join_list_str(text: str):
        return [item.strip().lstrip('.') for item in text.replace(',', ' ').split() if item.strip()]
