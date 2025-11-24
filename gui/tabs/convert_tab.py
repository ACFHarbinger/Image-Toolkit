import os

from typing import Optional
from PySide6.QtWidgets import (
    QLineEdit, QPushButton, QFileDialog, QFormLayout, QHBoxLayout,
    QVBoxLayout, QWidget, QCheckBox, QMessageBox, 
    QLabel, QGroupBox, QScrollArea, QGridLayout, 
    QProgressBar, QComboBox
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, Slot
from ..classes import AbstractClassTwoGalleries
from ..helpers import ConversionWorker
from ..components import OptionalField, MarqueeScrollArea, ClickableLabel
from ..styles.style import apply_shadow_effect, SHARED_BUTTON_STYLE
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS


class ConvertTab(AbstractClassTwoGalleries):
    def __init__(self, dropdown=True):
        super().__init__()
        self.dropdown = dropdown
        self.worker = None
        
        # --- UI Setup ---
        main_layout = QVBoxLayout(self)

        # Page Scroll Area
        page_scroll = QScrollArea()
        page_scroll.setWidgetResizable(True)
        page_scroll.setStyleSheet("QScrollArea { border: none; }")
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # --- 1. Convert Targets Group ---
        target_group = QGroupBox("Convert Targets")
        target_layout = QFormLayout(target_group)
        v_input_group = QVBoxLayout()

        # Input path
        input_layout = QHBoxLayout()
        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText("Path to directory containing images for conversion...")
        input_layout.addWidget(self.input_path)

        btn_browse_scan = QPushButton("Browse...")
        btn_browse_scan.clicked.connect(self.browse_directory_and_scan)
        apply_shadow_effect(btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        input_layout.addWidget(btn_browse_scan)

        v_input_group.addLayout(input_layout)
        target_layout.addRow("Input path:", v_input_group)
        content_layout.addWidget(target_group)

        # --- 2. Convert Settings Group ---
        settings_group = QGroupBox("Convert Settings")
        settings_layout = QFormLayout(settings_group)

        # Output format
        self.output_format_combo = QComboBox()
        formatted_formats = [f for f in SUPPORTED_IMG_FORMATS]
        self.output_format_combo.addItems(formatted_formats)
        self.output_format_combo.setCurrentText("png")
        settings_layout.addRow("Output format:", self.output_format_combo)

        # Output path
        h_output = QHBoxLayout()
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Leave blank to save in the input directory")
        btn_output = QPushButton("Browse...")
        btn_output.clicked.connect(self.browse_output)
        apply_shadow_effect(btn_output, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        h_output.addWidget(self.output_path)
        h_output.addWidget(btn_output)
        
        output_path_container = QWidget()
        output_path_container.setLayout(h_output)
        self.output_field = OptionalField("Output path", output_path_container, start_open=False)
        settings_layout.addRow(self.output_field)
        
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
            self.formats_field = OptionalField("Input formats to filter", formats_container, start_open=False)
            settings_layout.addRow(self.formats_field)
        else:
            self.selected_formats = None
            self.input_formats = QLineEdit()
            self.input_formats.setPlaceholderText("e.g. jpg png gif — separate with commas or spaces")
            settings_layout.addRow("Input formats (optional):", self.input_formats)
        
        self.delete_checkbox = QCheckBox("Delete original files after conversion")
        self.delete_checkbox.setStyleSheet("""
            QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #555; border-radius: 3px; background-color: #333; }
            QCheckBox::indicator:checked { background-color: #4CAF50; border: 1px solid #4CAF50; image: url(./src/gui/assets/check.png); }
        """)
        self.delete_checkbox.setChecked(False)
        settings_layout.addRow(self.delete_checkbox)

        content_layout.addWidget(settings_group)
        
        # --- 3. Galleries ---
        
        # Progress Bar
        self.scan_progress_bar = QProgressBar()
        self.scan_progress_bar.setTextVisible(False)
        self.scan_progress_bar.hide()
        content_layout.addWidget(self.scan_progress_bar)

        # Found Files (Top)
        self.found_gallery_scroll = MarqueeScrollArea()
        self.found_gallery_scroll.setWidgetResizable(True)
        self.found_gallery_scroll.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")
        self.found_gallery_scroll.setMinimumHeight(600)
        
        self.gallery_widget = QWidget()
        self.gallery_widget.setStyleSheet("background-color: #2c2f33;")
        self.found_gallery_layout = QGridLayout(self.gallery_widget)
        self.found_gallery_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.found_gallery_scroll.setWidget(self.gallery_widget)
        
        # Connect Base logic
        self.found_gallery_scroll.selection_changed.connect(self.handle_marquee_selection)
        content_layout.addWidget(self.found_gallery_scroll, 1)
        
        # Selected Files (Bottom)
        self.selected_gallery_scroll = MarqueeScrollArea()
        self.selected_gallery_scroll.setWidgetResizable(True)
        self.selected_gallery_scroll.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")
        self.selected_gallery_scroll.setMinimumHeight(400)

        self.selected_widget = QWidget()
        self.selected_widget.setStyleSheet("background-color: #2c2f33;")
        self.selected_gallery_layout = QGridLayout(self.selected_widget)
        self.selected_gallery_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.selected_gallery_scroll.setWidget(self.selected_widget)
        content_layout.addWidget(self.selected_gallery_scroll, 1)

        content_layout.addStretch(1)

        # --- Buttons ---
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_convert_all = QPushButton("Convert All in Directory")
        self.btn_convert_all.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(self.btn_convert_all, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_convert_all.clicked.connect(lambda: self.start_conversion_worker(use_selection=False))
        button_layout.addWidget(self.btn_convert_all)

        self.btn_convert_contents = QPushButton("Convert Selected Files (0)")
        self.btn_convert_contents.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(self.btn_convert_contents, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_convert_contents.clicked.connect(lambda: self.start_conversion_worker(use_selection=True))
        button_layout.addWidget(self.btn_convert_contents)

        content_layout.addWidget(button_container)

        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #666; font-style: italic; padding: 8px;")
        content_layout.addWidget(self.status_label)

        page_scroll.setWidget(content_widget)
        main_layout.addWidget(page_scroll)

        # Initial Clear
        self.clear_galleries()

    # --- IMPLEMENTING ABSTRACT METHODS ---

    def create_card_widget(self, path: str, pixmap: Optional[QPixmap], is_selected: bool) -> QWidget:
        thumb_size = self.thumbnail_size
        card_wrapper = ClickableLabel(path)
        card_wrapper.setFixedSize(thumb_size + 10, thumb_size + 10)
        
        # Required for Base class to fetch pixmap later if needed
        card_wrapper.get_pixmap = lambda: img_label.pixmap()
        
        card_layout = QVBoxLayout(card_wrapper)
        card_layout.setContentsMargins(0, 0, 0, 0)
        
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignCenter)
        img_label.setFixedSize(thumb_size, thumb_size)

        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(thumb_size, thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            img_label.setPixmap(scaled)
        else:
            img_label.setText(f".{os.path.splitext(path)[1].lstrip('.')}") 
            img_label.setStyleSheet("color: #e74c3c; border: 1px solid #e74c3c;")
            
        card_layout.addWidget(img_label)
        card_wrapper.setLayout(card_layout)
        
        # Assign custom styling method for the Base class to call
        card_wrapper.set_selected_style = lambda selected: self._update_card_style(img_label, selected)
        
        # Apply initial style
        self._update_card_style(img_label, is_selected)
        return card_wrapper

    def _update_card_style(self, img_label: QLabel, is_selected: bool):
        if is_selected:
            img_label.setStyleSheet("border: 3px solid #5865f2; background-color: #36393f;")
        else:
            img_label.setStyleSheet("border: 1px solid #4f545c; background-color: #36393f;")

    def on_selection_changed(self):
        count = len(self.selected_files)
        self.btn_convert_contents.setText(f"Convert Selected Files ({count})")
        self.btn_convert_contents.setEnabled(count > 0)

    # --- INPUT LOGIC ---

    @Slot()
    def browse_directory_and_scan(self):
        directory = QFileDialog.getExistingDirectory(self, "Select input directory", self.last_browsed_dir)
        if directory:
            self.input_path.setText(directory)
            self.last_browsed_dir = directory
            self.scan_directory_visual()

    @Slot()
    def browse_output(self):
        directory = QFileDialog.getExistingDirectory(self, "Select output directory", "")
        if directory:
            self.output_path.setText(directory)

    def collect_paths(self) -> list[str]:
        p = self.input_path.text().strip()
        if not p or not os.path.isdir(p): return []
        
        input_formats = (
            list(self.selected_formats) if self.dropdown and self.selected_formats
            else self.join_list_str(self.input_formats.text().strip()) if not self.dropdown and hasattr(self, 'input_formats')
            else SUPPORTED_IMG_FORMATS
        )
        
        paths = []
        for root, _, files in os.walk(p):
            for file in files:
                file_ext = os.path.splitext(file)[1].lstrip('.').lower()
                if not input_formats or file_ext in input_formats:
                    paths.append(os.path.join(root, file))
        return paths

    @Slot()
    def scan_directory_visual(self):
        paths = self.collect_paths()
        if not paths:
            QMessageBox.information(self, "No Files", "No matching files found.")
            self.clear_galleries()
            return
        
        self.start_loading_thumbnails(paths)

    # --- FORMAT BUTTONS ---
    @Slot(str, bool)
    def toggle_format(self, fmt, checked):
        btn = self.format_buttons[fmt]
        if checked:
            self.selected_formats.add(fmt)
            btn.setStyleSheet("""
                QPushButton:checked { background-color: #3320b5; color: white; }
                QPushButton:hover { background-color: #00838a; }
            """)
            apply_shadow_effect(btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        else:
            self.selected_formats.discard(fmt)
            btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")
            apply_shadow_effect(btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)

    @Slot()
    def add_all_formats(self):
        for fmt, btn in self.format_buttons.items():
            btn.setChecked(True)
            self.toggle_format(fmt, True)

    @Slot()
    def remove_all_formats(self):
        for fmt, btn in self.format_buttons.items():
            btn.setChecked(False)
            self.toggle_format(fmt, False)

    # --- CONVERSION WORKER ---

    @Slot(bool)
    def start_conversion_worker(self, use_selection: bool = False):
        if self.worker and self.worker.isRunning():
            self.cancel_conversion()
            return

        p = self.input_path.text().strip()
        if not p or not os.path.isdir(p):
            QMessageBox.warning(self, "Invalid", "Please select a valid directory.")
            return

        files_for_conversion = self.selected_files if use_selection else self.collect_paths()

        if not files_for_conversion:
            QMessageBox.warning(self, "No Files", "No files to convert.")
            return
            
        config = self.collect()
        config["files_to_convert"] = files_for_conversion
        
        # UI Updates
        self.btn_convert_all.setEnabled(False)
        self.btn_convert_contents.setEnabled(False) 
        
        button_to_cancel = self.btn_convert_contents if use_selection else self.btn_convert_all
        button_to_cancel.setEnabled(True)
        button_to_cancel.setText("Cancel Conversion")
        button_to_cancel.setStyleSheet("""
            QPushButton { background-color: #cc3333; color: white; font-weight: bold; }
        """)
        
        self.status_label.setText(f"Converting {len(files_for_conversion)} files...")

        self.worker = ConversionWorker(config)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_conversion_done)
        self.worker.error.connect(self.on_conversion_error)
        self.worker.start()

    def cancel_conversion(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.on_conversion_done(0, "**Conversion cancelled**")
            self.worker = None

    @Slot(str)
    def update_progress(self, progress_message: str):
        self.status_label.setText(progress_message)

    @Slot(int, str)
    def on_conversion_done(self, count, msg):
        self.btn_convert_all.setEnabled(True)
        self.btn_convert_all.setText("Convert All in Directory")
        self.btn_convert_all.setStyleSheet(SHARED_BUTTON_STYLE)
        
        self.on_selection_changed() # Reset selected button text/state
        self.btn_convert_contents.setStyleSheet(SHARED_BUTTON_STYLE)

        self.status_label.setText(f"{msg}")
        self.worker = None
        if "cancelled" not in msg.lower():
            QMessageBox.information(self, "Complete", msg)

    @Slot(str)
    def on_conversion_error(self, msg):
        self.on_conversion_done(0, msg)
        QMessageBox.critical(self, "Error", msg)

    def collect(self) -> dict:
        input_formats = (
            list(self.selected_formats) if self.dropdown and self.selected_formats
            else self.join_list_str(self.input_formats.text().strip()) if not self.dropdown and hasattr(self, 'input_formats')
            else SUPPORTED_IMG_FORMATS
        )
        return {
            "output_format": self.output_format_combo.currentText().lower(),
            "input_path": self.input_path.text().strip(),
            "output_path": self.output_path.text().strip() or None,
            "input_formats": [f.strip().lstrip('.').lower() for f in input_formats if f.strip()],
            "delete": self.delete_checkbox.isChecked(),
        }
    
    def get_default_config(self):
        return {}

    def set_config(self, config):
        # Find index and set output format
        output_fmt = config.get("output_format", "png")
        index = self.output_format_combo.findText(output_fmt.lower())
        if index != -1:
            self.output_format_combo.setCurrentIndex(index)
        
        # [Remaining set_config logic would go here, updating input_path, output_path, etc.]
        # Since the user didn't provide the original set_config logic, I'll omit the rest
        # to avoid breaking other functionality. Assume only output_format is handled.
        pass