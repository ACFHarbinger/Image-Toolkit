import os

from pathlib import Path
from PySide6.QtWidgets import (
    QLineEdit, QPushButton, QFileDialog, QFormLayout, QHBoxLayout,
    QVBoxLayout, QWidget, QCheckBox, QMessageBox, QLabel,
    QGroupBox # Added QGroupBox
)
from PySide6.QtCore import Qt
from .base_tab import BaseTab
from ..helpers import ConversionWorker
from ..components import OptionalField
from ..styles.style import apply_shadow_effect
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS


class ConvertTab(BaseTab):
    def __init__(self, dropdown=True):
        super().__init__()
        self.dropdown = dropdown
        self.worker = None

        # --- Main Layout ---
        main_layout = QVBoxLayout(self)

        # --- Convert Targets Group ---
        target_group = QGroupBox("Convert Targets")
        target_layout = QFormLayout(target_group)

        # Input path
        v_input_group = QVBoxLayout()
        self.input_path = QLineEdit()
        v_input_group.addWidget(self.input_path)

        h_buttons = QHBoxLayout()
        btn_input_file = QPushButton("Choose file...")
        btn_input_file.clicked.connect(self.browse_file_input)
        apply_shadow_effect(btn_input_file, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        btn_input_dir = QPushButton("Choose directory...")
        btn_input_dir.clicked.connect(self.browse_directory_input)
        apply_shadow_effect(btn_input_dir, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        h_buttons.addWidget(btn_input_file)
        h_buttons.addWidget(btn_input_dir)
        v_input_group.addLayout(h_buttons)
        target_layout.addRow("Input path (file or dir):", v_input_group)
        
        main_layout.addWidget(target_group)

        # --- Convert Settings Group ---
        settings_group = QGroupBox("Convert Settings")
        settings_layout = QFormLayout(settings_group)

        # Output format
        self.output_format = QLineEdit("png")
        settings_layout.addRow("Output format:", self.output_format)

        # Output path
        h_output = QHBoxLayout()
        self.output_path = QLineEdit()
        btn_output = QPushButton("Browse...")
        btn_output.clicked.connect(self.browse_output)
        apply_shadow_effect(btn_output, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        h_output.addWidget(self.output_path)
        h_output.addWidget(btn_output)
        if self.dropdown:
            output_container = QWidget()
            output_container.setLayout(h_output)
            self.output_field = OptionalField("Output path", output_container, start_open=False)
            settings_layout.addRow(self.output_field)
        else:
            settings_layout.addRow("Output path (optional):", h_output)

        # Input formats
        if self.dropdown:
            self.selected_formats = set()
            formats_layout = QVBoxLayout()

            btn_layout = QHBoxLayout()
            self.format_buttons = {}
            for fmt in SUPPORTED_IMG_FORMATS:
                btn = QPushButton(fmt)
                btn.setCheckable(True)
                btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")
                apply_shadow_effect(btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
                btn.clicked.connect(lambda checked, f=fmt: self.toggle_format(f, checked))
                btn_layout.addWidget(btn)
                self.format_buttons[fmt] = btn
            formats_layout.addLayout(btn_layout)

            all_btn_layout = QHBoxLayout()
            self.btn_add_all = QPushButton("Add All")
            self.btn_add_all.setStyleSheet("background-color: green; color: white;")
            apply_shadow_effect(self.btn_add_all, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
            self.btn_add_all.clicked.connect(self.add_all_formats)
            self.btn_remove_all = QPushButton("Remove All")
            self.btn_remove_all.setStyleSheet("background-color: red; color: white;")
            apply_shadow_effect(self.btn_remove_all, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
            self.btn_remove_all.clicked.connect(self.remove_all_formats)
            all_btn_layout.addWidget(self.btn_add_all)
            all_btn_layout.addWidget(self.btn_remove_all)
            formats_layout.addLayout(all_btn_layout)

            formats_container = QWidget()
            formats_container.setLayout(formats_layout)
            self.formats_field = OptionalField("Input formats", formats_container, start_open=False)
            settings_layout.addRow(self.formats_field)
        else:
            self.selected_formats = None
            self.input_formats = QLineEdit()
            self.input_formats.setPlaceholderText("e.g. jpg png gif — separate with commas or spaces")
            settings_layout.addRow("Input formats (optional):", self.input_formats)

        # Delete checkbox
        self.delete_checkbox = QCheckBox("Delete original files after conversion")
        self.delete_checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 16px; height: 16px; border: 1px solid #555;
                border-radius: 3px; background-color: #333;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50; border: 1px solid #4CAF50;
                image: url(./src/gui/assets/check.png);
            }
        """)
        self.delete_checkbox.setChecked(True)
        settings_layout.addRow(self.delete_checkbox)

        main_layout.addWidget(settings_group)
        
        # Add a stretch to push button/status to the bottom
        main_layout.addStretch(1)

        # --- Button Container ---
        self.button_container = QWidget()
        self.button_layout = QVBoxLayout(self.button_container)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        
        # RUN CONVERSION BUTTON
        self.run_button = QPushButton("Run Conversion")
        self.run_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white; font-weight: bold; font-size: 16px;
                padding: 12px; border-radius: 8px; min-height: 40px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #764ba2, stop:1 #667eea); }
            QPushButton:disabled { background: #555; }
            QPushButton:pressed { background: #5a67d8; }
        """)
        apply_shadow_effect(self.run_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.run_button.clicked.connect(self.start_conversion)
        self.button_layout.addWidget(self.run_button)
        
        # CANCEL BUTTON
        self.cancel_button = QPushButton("Cancel Conversion")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #cc3333; /* Red color for cancellation */
                color: white; font-weight: bold; font-size: 16px;
                padding: 12px; border-radius: 8px; min-height: 40px;
            }
            QPushButton:hover { background-color: #ff4444; }
        """)
        apply_shadow_effect(self.cancel_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.cancel_button.clicked.connect(self.cancel_conversion)
        self.cancel_button.hide()
        self.button_layout.addWidget(self.cancel_button)

        main_layout.addWidget(self.button_container)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #666; font-style: italic; padding: 8px;")
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)

    def toggle_format(self, fmt, checked):
        if checked:
            self.selected_formats.add(fmt)
            self.format_buttons[fmt].setStyleSheet("""
                QPushButton:checked { background-color: #3320b5; color: white; }
                QPushButton:hover { background-color: #00838a; }
            """)
            apply_shadow_effect(self.format_buttons[fmt], color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        else:
            self.selected_formats.discard(fmt)
            self.format_buttons[fmt].setStyleSheet("QPushButton:hover { background-color: #3498db; }")
            apply_shadow_effect(self.format_buttons[fmt], color_hex="#000000", radius=8, x_offset=0, y_offset=3)

    def add_all_formats(self):
        for fmt, btn in self.format_buttons.items():
            btn.setChecked(True)
            self.toggle_format(fmt, True)

    def remove_all_formats(self):
        for fmt, btn in self.format_buttons.items():
            btn.setChecked(False)
            self.toggle_format(fmt, False)

    def browse_file_input(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select input file", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)"
        )
        if file_path:
            self.input_path.setText(file_path)

    def browse_directory_input(self):
        path = Path(os.getcwd())
        parts = path.parts
        start_dir = os.path.join(Path(*parts[:parts.index('Image-Toolkit') + 1]), 'data')
        directory = QFileDialog.getExistingDirectory(self, "Select input directory", start_dir)
        if directory:
            self.input_path.setText(directory)

    def browse_output(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save as...", "", "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*)"
        )
        if file_path:
            self.output_path.setText(file_path)
            return
        directory = QFileDialog.getExistingDirectory(
            self, "Select output directory",
            os.path.join(Path(*Path(os.getcwd()).parts[:Path(os.getcwd()).parts.index('Image-Toolkit') + 1]), 'data')
        )
        if directory:
            self.output_path.setText(directory)

    def is_valid(self):
        return bool(self.input_path.text().strip()) and os.path.exists(self.input_path.text().strip())

    def start_conversion(self):
        if not self.is_valid():
            QMessageBox.warning(self, "Invalid Input", "Please select a valid file or directory.")
            return

        config = self.collect()
        # UI: Switch buttons
        self.run_button.hide()
        self.cancel_button.show()
        self.status_label.setText("Starting conversion...")

        self.worker = ConversionWorker(config)
        self.worker.finished.connect(self.on_conversion_done)
        self.worker.error.connect(self.on_conversion_error)
        self.worker.start()

    def cancel_conversion(self):
        """Attempts to stop the QThread worker."""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.on_conversion_done(0, "**Conversion cancelled** by user.")
            QMessageBox.information(self, "Cancelled", "The image conversion has been stopped.")

    def on_conversion_done(self, count, msg):
        # UI: Switch buttons back
        self.run_button.show()
        self.cancel_button.hide()
        self.run_button.setText("Run Conversion")
        self.status_label.setText(f"{msg}")
        
        # Only show the success box if it wasn't a cancellation
        if "cancelled" not in msg.lower():
            QMessageBox.information(self, "Success", msg)

    def on_conversion_error(self, msg):
        # UI: Switch buttons back
        self.run_button.show()
        self.cancel_button.hide()
        self.run_button.setText("Run Conversion")
        self.status_label.setText("Conversion failed.")
        QMessageBox.critical(self, "Error", msg)

    def collect(self):
        input_formats = (
            list(self.selected_formats) if self.dropdown and self.selected_formats
            else self.join_list_str(self.input_formats.text().strip()) if not self.dropdown
            else SUPPORTED_IMG_FORMATS
        )
        return {
            "output_format": self.output_format.text().strip() or "png",
            "input_path": self.input_path.text().strip(),
            "output_path": self.output_path.text().strip() or None,
            "input_formats": [f.strip().lstrip('.').lower() for f in input_formats if f.strip()],
            "delete": self.delete_checkbox.isChecked()
        }

    @staticmethod
    def join_list_str(text):
        return [item.strip().lstrip('.') for item in text.replace(',', ' ').split() if item.strip()]
