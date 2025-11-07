import os
from pathlib import Path
from typing import Dict, Any
from PySide6.QtWidgets import (
    QLineEdit, QPushButton, QCheckBox, QFileDialog,
    QFormLayout, QHBoxLayout, QVBoxLayout, QWidget,
    QMessageBox, QLabel
)
from PySide6.QtCore import Qt
from .BaseTab import BaseTab
from ..helpers import DeletionWorker
from ..components import OptionalField
from ..styles import apply_shadow_effect
from ...utils.definitions import SUPPORTED_IMG_FORMATS


class DeleteTab(BaseTab):
    def __init__(self, dropdown=True):
        super().__init__()
        self.dropdown = dropdown
        self.worker = None

        layout = QFormLayout()

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
        layout.addRow("Target path (file or dir):", v_target_group)

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
            layout.addRow(self.extensions_field)
        else:
            self.selected_extensions = None
            self.target_extensions = QLineEdit()
            self.target_extensions.setPlaceholderText("e.g. .txt .jpg or txt jpg")
            layout.addRow("Target extensions (optional):", self.target_extensions)

        # Confirmation
        self.confirm_checkbox = QCheckBox("Require confirmation before delete (recommended)")
        self.confirm_checkbox.setChecked(True)
        layout.addRow("", self.confirm_checkbox)

        # Run Button
        self.run_button = QPushButton("Run Deletion")
        self.run_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white; font-weight: bold; font-size: 16px;
                padding: 14px; border-radius: 10px; min-height: 44px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #764ba2, stop:1 #667eea); }
            QPushButton:disabled { background: #718096; }
            QPushButton:pressed { background: #5a67d8; }
        """)
        apply_shadow_effect(self.run_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.run_button.clicked.connect(self.start_deletion)
        layout.addRow("", self.run_button)

        # Status
        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
        layout.addRow("", self.status_label)

        self.setLayout(layout)

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

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select file", "", "All Files (*)")
        if file_path:
            self.target_path.setText(file_path)

    def browse_directory(self):
        path = Path(os.getcwd())
        parts = path.parts
        start_dir = os.path.join(Path(*parts[:parts.index('Image-Toolkit') + 1]), 'data')
        directory = QFileDialog.getExistingDirectory(self, "Select directory", start_dir)
        if directory:
            self.target_path.setText(directory)

    def is_valid(self):
        path = self.target_path.text().strip()
        return path and os.path.exists(path)

    def start_deletion(self):
        if not self.is_valid():
            QMessageBox.warning(self, "Invalid Path", "Please select a valid file or folder.")
            return

        config = self.collect()
        config["require_confirm"] = self.confirm_checkbox.isChecked()

        self.run_button.setEnabled(False)
        self.run_button.setText("Deleting...")
        self.status_label.setText("Scanning files...")

        self.worker = DeletionWorker(config)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_deletion_done)
        self.worker.error.connect(self.on_deletion_error)
        self.worker.start()

    def update_progress(self, deleted, total):
        self.status_label.setText(f"Deleted {deleted} of {total}...")

    def on_deletion_done(self, count, msg):
        self.run_button.setEnabled(True)
        self.run_button.setText("Run Deletion")
        self.status_label.setText(msg)
        QMessageBox.information(self, "Complete", msg)

    def on_deletion_error(self, msg):
        self.run_button.setEnabled(True)
        self.run_button.setText("Run Deletion")
        self.status_label.setText("Failed.")
        QMessageBox.critical(self, "Error", msg)

    def collect(self) -> Dict[str, Any]:
        extensions = (
            list(self.selected_extensions) if self.dropdown and self.selected_extensions
            else self.join_list_str(self.target_extensions.text().strip())
            if not self.dropdown else SUPPORTED_IMG_FORMATS
        )
        return {
            "target_path": self.target_path.text().strip(),
            "target_extensions": [e.strip().lstrip('.') for e in extensions if e.strip()],
        }

    @staticmethod
    def join_list_str(text: str):
        return [item.strip().lstrip('.') for item in text.replace(',', ' ').split() if item.strip()]
