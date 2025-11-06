import os
from pathlib import Path
from typing import Dict, Any
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QLineEdit, QFileDialog, QWidget, QLabel, QPushButton,
    QComboBox, QSpinBox, QGroupBox, QFormLayout, QHBoxLayout,
    QVBoxLayout, QMessageBox
)
from .BaseTab import BaseTab
from ..helpers import MergeWorker
from ..components import OptionalField
from ...utils.definitions import SUPPORTED_IMG_FORMATS


class MergeTab(BaseTab):
    def __init__(self, dropdown=True):
        super().__init__()
        self.dropdown = dropdown
        self.worker = None

        layout = QFormLayout()

        # Direction
        self.direction = QComboBox()
        self.direction.addItems(["horizontal", "vertical", "grid"])
        self.direction.currentTextChanged.connect(self.toggle_grid_visibility)
        layout.addRow("Direction:", self.direction)

        # Input paths
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)

        label = QLabel("Input paths (files or single directory):")
        label.setAlignment(Qt.AlignTop)
        row_layout.addWidget(label)

        v_input_group = QVBoxLayout()
        self.input_path = QLineEdit()
        v_input_group.addWidget(self.input_path)

        h_buttons = QHBoxLayout()
        btn_input_files = QPushButton("Add files...")
        btn_input_files.clicked.connect(self.browse_files)
        btn_input_dir = QPushButton("Choose directory...")
        btn_input_dir.clicked.connect(self.browse_directory)
        h_buttons.addWidget(btn_input_files)
        h_buttons.addWidget(btn_input_dir)
        v_input_group.addLayout(h_buttons)

        field_widget = QWidget()
        field_widget.setLayout(v_input_group)
        row_layout.addWidget(field_widget)
        layout.addRow(row_widget)

        # Output path
        h_output = QHBoxLayout()
        self.output_path = QLineEdit()
        btn_output = QPushButton("Browse...")
        btn_output.clicked.connect(self.browse_output)
        h_output.addWidget(self.output_path)
        h_output.addWidget(btn_output)
        if self.dropdown:
            output_container = QWidget()
            output_container.setLayout(h_output)
            self.output_field = OptionalField("Output path", output_container, start_open=False)
            layout.addRow(self.output_field)
        else:
            layout.addRow("Output path (optional):", h_output)

        # Formats
        if self.dropdown:
            self.selected_formats = set()
            formats_layout = QVBoxLayout()
            btn_layout = QHBoxLayout()
            self.format_buttons = {}
            for fmt in SUPPORTED_IMG_FORMATS:
                btn = QPushButton(fmt)
                btn.setCheckable(True)
                btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")
                btn.clicked.connect(lambda checked, f=fmt: self.toggle_format(f, checked))
                btn_layout.addWidget(btn)
                self.format_buttons[fmt] = btn
            formats_layout.addLayout(btn_layout)

            all_btn_layout = QHBoxLayout()
            btn_add_all = QPushButton("Add All")
            btn_add_all.setStyleSheet("background-color: green; color: white;")
            btn_add_all.clicked.connect(self.add_all_formats)
            btn_remove_all = QPushButton("Remove All")
            btn_remove_all.setStyleSheet("background-color: red; color: white;")
            btn_remove_all.clicked.connect(self.remove_all_formats)
            all_btn_layout.addWidget(btn_add_all)
            all_btn_layout.addWidget(btn_remove_all)
            formats_layout.addLayout(all_btn_layout)

            formats_container = QWidget()
            formats_container.setLayout(formats_layout)
            self.formats_field = OptionalField("Input formats", formats_container, start_open=False)
            layout.addRow(self.formats_field)
        else:
            self.selected_formats = None
            self.input_formats = QLineEdit()
            self.input_formats.setPlaceholderText("e.g. jpg png")
            layout.addRow("Input formats (optional):", self.input_formats)

        # Spacing
        self.spacing = QSpinBox()
        self.spacing.setRange(0, 1000)
        self.spacing.setValue(10)
        layout.addRow("Spacing (px):", self.spacing)

        # Grid size
        self.grid_group = QGroupBox("Grid size")
        grid_layout = QHBoxLayout()
        self.grid_rows = QSpinBox()
        self.grid_rows.setRange(1, 100)
        self.grid_cols = QSpinBox()
        self.grid_cols.setRange(1, 100)
        grid_layout.addWidget(QLabel("Rows:"))
        grid_layout.addWidget(self.grid_rows)
        grid_layout.addWidget(QLabel("Cols:"))
        grid_layout.addWidget(self.grid_cols)
        self.grid_group.setLayout(grid_layout)
        self.grid_row_index = layout.rowCount()
        layout.addRow(self.grid_group)
        self.grid_group.hide()
        layout.removeWidget(self.grid_group)
        self.grid_group.setParent(None)

        # RUN MERGE BUTTON
        self.run_button = QPushButton("Run Merge")
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
        self.run_button.clicked.connect(self.start_merge)
        layout.addRow("", self.run_button)

        # Status
        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
        layout.addRow("", self.status_label)

        self.setLayout(layout)

    def toggle_grid_visibility(self, direction):
        layout = self.layout()
        if direction == "grid":
            if self.grid_group.parent() is None:
                layout.insertRow(self.grid_row_index, self.grid_group)
            self.grid_group.show()
        else:
            layout.removeWidget(self.grid_group)
            self.grid_group.setParent(None)
            self.grid_group.hide()

        if hasattr(self, "_resize_timer"):
            self._resize_timer.stop()
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._resize_hierarchy)
        self._resize_timer.start(100)

    def _resize_hierarchy(self):
        win = self.window()
        if win:
            w = win.width()
            h = 680 if self.direction.currentText() == "grid" else 540
            if abs(win.height() - h) > 10:
                win.resize(w, h)

    def toggle_format(self, fmt, checked):
        btn = self.format_buttons[fmt]
        if checked:
            self.selected_formats.add(fmt)
            btn.setStyleSheet("""
                QPushButton:checked { background-color: #3320b5; color: white; }
                QPushButton:hover { background-color: #00838a; }
            """)
        else:
            self.selected_formats.discard(fmt)
            btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")

    def add_all_formats(self):
        for fmt, btn in self.format_buttons.items():
            btn.setChecked(True)
            self.toggle_format(fmt, True)

    def remove_all_formats(self):
        for fmt, btn in self.format_buttons.items():
            btn.setChecked(False)
            self.toggle_format(fmt, False)

    def browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select images", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)"
        )
        if files:
            current = [p.strip() for p in self.input_path.text().split(",") if p.strip()]
            current.extend(files)
            self.input_path.setText(", ".join(current))

    def browse_directory(self):
        path = Path(os.getcwd())
        parts = path.parts
        start_dir = os.path.join(Path(*parts[:parts.index('Image-Toolkit') + 1]), 'data')
        directory = QFileDialog.getExistingDirectory(self, "Select directory", start_dir)
        if directory:
            self.input_path.setText(directory)

    def browse_output(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save merged image", "", "PNG (*.png);;JPEG (*.jpg);;All Files (*)"
        )
        if file_path:
            self.output_path.setText(file_path)

    def is_valid(self):
        paths = [p.strip() for p in self.input_path.text().split(",") if p.strip()]
        return len(paths) >= 1 and any(os.path.exists(p) for p in paths)

    def start_merge(self):
        if not self.is_valid():
            QMessageBox.warning(self, "Invalid Input", "Please select at least 2 images or a folder.")
            return

        config = self.collect()
        if not config["input_path"] or len(config["input_path"]) < 2:
            QMessageBox.warning(self, "Not Enough Images", "Select at least 2 images.")
            return

        self.run_button.setEnabled(False)
        self.run_button.setText("Merging...")
        self.status_label.setText("Loading images...")

        self.worker = MergeWorker(config)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_merge_done)
        self.worker.error.connect(self.on_merge_error)
        self.worker.start()

    def update_progress(self, current, total):
        self.status_label.setText(f"Merging {current}/{total}...")

    def on_merge_done(self, output_path):
        self.run_button.setEnabled(True)
        self.run_button.setText("Run Merge")
        self.status_label.setText(f"Saved: {os.path.basename(output_path)}")
        QMessageBox.information(self, "Success", f"Merge complete!\nSaved to:\n{output_path}")

    def on_merge_error(self, msg):
        self.run_button.setEnabled(True)
        self.run_button.setText("Run Merge")
        self.status_label.setText("Failed.")
        QMessageBox.critical(self, "Error", msg)

    def collect(self) -> Dict[str, Any]:
        raw = self.input_path.text().strip()
        paths = [p.strip() for p in raw.split(",") if p.strip()] if raw else []

        formats = (
            list(self.selected_formats) if self.dropdown and self.selected_formats
            else self.join_list_str(self.input_formats.text().strip())
            if not self.dropdown else SUPPORTED_IMG_FORMATS
        )

        return {
            "direction": self.direction.currentText(),
            "input_path": paths,
            "output_path": self.output_path.text().strip() or None,
            "input_formats": [f.strip().lstrip('.') for f in formats if f.strip()],
            "spacing": self.spacing.value(),
            "grid_size": (
                self.grid_rows.value(), self.grid_cols.value()
            ) if self.direction.currentText() == "grid" else None
        }

    @staticmethod
    def join_list_str(text: str):
        return [item.strip().lstrip('.') for item in text.replace(',', ' ').split() if item.strip()]
