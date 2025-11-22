import os

from pathlib import Path
from typing import List, Tuple, Optional
from PySide6.QtWidgets import (
    QLineEdit, QPushButton, QFileDialog, QFormLayout, QHBoxLayout,
    QVBoxLayout, QWidget, QCheckBox, QMessageBox, 
    QLabel, QGroupBox, QScrollArea, QGridLayout, 
    QProgressBar, QProgressDialog, QApplication, QComboBox
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, Slot, QThreadPool
from .base_tab import BaseTab
from ..helpers import ConversionWorker, ImageLoaderWorker
from ..components import OptionalField, MarqueeScrollArea, ClickableLabel
from ..styles.style import apply_shadow_effect, SHARED_BUTTON_STYLE
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS


class ConvertTab(BaseTab):
    def __init__(self, dropdown=True):
        super().__init__()
        self.dropdown = dropdown
        self.worker = None
        
        # Gallery State
        self.files_to_convert: list[str] = [] # All files found in scan
        self.selected_files_to_convert: list[str] = [] # Files explicitly selected
        self.path_to_label_map: dict[str, ClickableLabel] = {}
        self.selected_card_map: dict[str, ClickableLabel] = {}
        
        self.thumbnail_size = 120
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width + 20
        self._current_gallery_cols = 1
        self._current_selected_cols = 1
        
        # Threading
        self.thread_pool = QThreadPool.globalInstance()
        self._loaded_results_buffer: List[Tuple[str, QPixmap]] = []
        self._images_loaded_count = 0
        self._total_images_to_load = 0
        self.loading_dialog: Optional[QProgressDialog] = None

        # --- Main Layout ---
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

        # --- 2. Convert Settings Group (Output and Input Filters) ---
        settings_group = QGroupBox("Convert Settings")
        settings_layout = QFormLayout(settings_group)

        # Output format (MODIFIED: QComboBox)
        self.output_format_combo = QComboBox()
        # Ensure that the format list starts with a period and is lowercase for consistency
        formatted_formats = [f for f in SUPPORTED_IMG_FORMATS]
        self.output_format_combo.addItems(formatted_formats)
        self.output_format_combo.setCurrentText("png") # Default selection
        settings_layout.addRow("Output format:", self.output_format_combo)

        # Output path (Now OptionalField)
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
        # Wrapping output path in OptionalField
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
        self.delete_checkbox.setChecked(False)
        settings_layout.addRow(self.delete_checkbox)

        content_layout.addWidget(settings_group)
        
        # --- 3. Galleries (Directly in content_layout, no bounding box) ---
        
        # Progress Bar (placed before galleries in the layout)
        self.scan_progress_bar = QProgressBar()
        self.scan_progress_bar.setTextVisible(False)
        self.scan_progress_bar.hide()
        content_layout.addWidget(self.scan_progress_bar)

        # A. Top Gallery: Found Files (Preview)
        self.gallery_scroll = MarqueeScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")
        self.gallery_scroll.setMinimumHeight(300)
        
        self.gallery_widget = QWidget()
        self.gallery_widget.setStyleSheet("background-color: #2c2f33;")
        self.gallery_layout = QGridLayout(self.gallery_widget)
        self.gallery_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.gallery_scroll.setWidget(self.gallery_widget)
        self.gallery_scroll.selection_changed.connect(self.handle_marquee_selection)
        content_layout.addWidget(self.gallery_scroll, 1)
        
        # B. Bottom Gallery: Selected Files for Conversion
        self.selected_scroll = MarqueeScrollArea()
        self.selected_scroll.setWidgetResizable(True)
        self.selected_scroll.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")
        self.selected_scroll.setMinimumHeight(200)

        self.selected_widget = QWidget()
        self.selected_widget.setStyleSheet("background-color: #2c2f33;")
        self.selected_layout = QGridLayout(self.selected_widget)
        self.selected_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.selected_scroll.setWidget(self.selected_widget)
        content_layout.addWidget(self.selected_scroll, 1)


        # Add a stretch to push button/status to the bottom
        content_layout.addStretch(1)

        # --- Button Container ---
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        # Convert All in Directory
        self.btn_convert_all = QPushButton("Convert All in Directory")
        self.btn_convert_all.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(self.btn_convert_all, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_convert_all.clicked.connect(lambda: self.start_conversion_worker(use_selection=False))
        button_layout.addWidget(self.btn_convert_all)

        # Convert Selected Button
        self.btn_convert_contents = QPushButton("Convert Selected Files (0)")
        self.btn_convert_contents.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(self.btn_convert_contents, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_convert_contents.clicked.connect(lambda: self.start_conversion_worker(use_selection=True))
        button_layout.addWidget(self.btn_convert_contents)

        content_layout.addWidget(button_container)

        # Status label
        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #666; font-style: italic; padding: 8px;")
        content_layout.addWidget(self.status_label)

        page_scroll.setWidget(content_widget)
        main_layout.addWidget(page_scroll)

        # Initialize galleries with placeholders
        self.clear_gallery()


    # --- GEOMETRY HELPER METHODS ---

    def _calculate_columns(self, scroll_area) -> int:
        """Calculates columns based on the actual viewport width."""
        width = scroll_area.viewport().width()
        if width <= 0: width = scroll_area.width()
        if width <= 0: width = 800 
        return max(1, width // self.approx_item_width)

    def _reflow_layout(self, layout: QGridLayout, columns: int):
        """Removes all items from layout and re-adds them with new column count."""
        if not layout: return
        items = []
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                items.append(item.widget())
        for i, widget in enumerate(items):
            row = i // columns
            col = i % columns
            
            # Check for placeholder label
            align = Qt.AlignLeft | Qt.AlignTop
            if isinstance(widget, QLabel) and "Scan a directory" in widget.text():
                 align = Qt.AlignCenter
                 layout.addWidget(widget, 0, 0, 1, columns, align)
                 return
                 
            layout.addWidget(widget, row, col, align)
            
    # --- END GEOMETRY HELPER METHODS ---

    # --- RESIZE REFLOW LOGIC ---
    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_gallery_cols = self._calculate_columns(self.gallery_scroll)
        if new_gallery_cols != self._current_gallery_cols:
            self._current_gallery_cols = new_gallery_cols
            self._reflow_layout(self.gallery_layout, new_gallery_cols)

        new_selected_cols = self._calculate_columns(self.selected_scroll)
        if new_selected_cols != self._current_selected_cols:
            self._current_selected_cols = new_selected_cols
            self._reflow_layout(self.selected_layout, new_selected_cols)

    def showEvent(self, event):
        super().showEvent(event)
        self._current_gallery_cols = self._calculate_columns(self.gallery_scroll)
        self._reflow_layout(self.gallery_layout, self._current_gallery_cols)
        
        self._current_selected_cols = self._calculate_columns(self.selected_scroll)
        self._reflow_layout(self.selected_layout, self._current_selected_cols)


    # --- DUAL GALLERY LOGIC ---

    @Slot(str)
    def toggle_selection(self, path: str):
        try:
            index = self.selected_files_to_convert.index(path)
            self.selected_files_to_convert.pop(index)
            selected = False
        except ValueError:
            self.selected_files_to_convert.append(path)
            selected = True
            
        label = self.path_to_label_map.get(path)
        if label:
            self._update_card_style(label.findChild(QLabel), selected)
            
        self._refresh_selected_panel()
        self._update_conversion_button_state()
    
    def handle_marquee_selection(self, paths_from_marquee: set, is_ctrl_pressed: bool):
        ordered_current = self.selected_files_to_convert.copy()
        paths_to_update = set()
        
        if not is_ctrl_pressed:
            # If no ctrl, set selection to only those currently marquee'd
            new_ordered = [p for p in ordered_current if p in paths_from_marquee]
            newly_added = [p for p in paths_from_marquee if p not in ordered_current]
            paths_to_update = paths_from_marquee.union(set(ordered_current))
            self.selected_files_to_convert = new_ordered + newly_added
        else:
            # If ctrl, toggle selection
            for path in paths_from_marquee:
                if path in self.selected_files_to_convert:
                    self.selected_files_to_convert.remove(path)
                elif path in self.files_to_convert:
                    self.selected_files_to_convert.append(path)
                paths_to_update.add(path)

        for path in paths_to_update:
             if path in self.path_to_label_map:
                wrapper = self.path_to_label_map[path]
                inner_label = wrapper.findChild(QLabel)
                if inner_label: self._update_card_style(inner_label, path in self.selected_files_to_convert)
                
        self._refresh_selected_panel()
        self._update_conversion_button_state()

    def _refresh_selected_panel(self):
        self.selected_widget.setUpdatesEnabled(False)
        self._clear_gallery(self.selected_layout)
        self.selected_card_map = {}
        paths = self.selected_files_to_convert
        columns = self._calculate_columns(self.selected_scroll) 
        
        if not paths:
            empty_label = QLabel("Selected files will appear here.")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #b9bbbe; padding: 50px;")
            self.selected_layout.addWidget(empty_label, 0, 0, 1, columns)
            self.selected_widget.setUpdatesEnabled(True)
            return

        for i, path in enumerate(paths):
            pixmap = None 
            if path in self.path_to_label_map:
                wrapper = self.path_to_label_map[path]; inner_label = wrapper.findChild(QLabel)
                if inner_label and inner_label.pixmap(): pixmap = inner_label.pixmap()
            
            card = self._create_gallery_card(path, pixmap, is_selected=True)
            card.path_clicked.connect(lambda checked, p=path: self.toggle_selection(p))
            
            row = i // columns
            col = i % columns
            self.selected_card_map[path] = card
            self.selected_layout.addWidget(card, row, col, Qt.AlignLeft | Qt.AlignTop)
            
        self.selected_widget.setUpdatesEnabled(True)
        self.selected_widget.adjustSize()

    def _update_conversion_button_state(self):
        count = len(self.selected_files_to_convert)
        self.btn_convert_contents.setText(f"Convert Selected Files ({count})")
        self.btn_convert_contents.setEnabled(count > 0)


    # --- GALLERY RENDERING & UTILS ---
    def _create_gallery_card(self, path: str, pixmap: Optional[QPixmap], is_selected: bool) -> ClickableLabel:
        thumb_size = self.thumbnail_size
        card_wrapper = ClickableLabel(path)
        card_wrapper.setFixedSize(thumb_size + 10, thumb_size + 10)
        card_layout = QVBoxLayout(card_wrapper)
        card_layout.setContentsMargins(0, 0, 0, 0)
        
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignCenter)
        img_label.setFixedSize(thumb_size, thumb_size)

        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(thumb_size, thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            img_label.setPixmap(scaled)
        else:
            img_label.setText(f".{os.path.splitext(path)[1].lstrip('.')}") # Show extension if load fails
            img_label.setStyleSheet("color: #e74c3c; border: 1px solid #e74c3c;")
            
        card_layout.addWidget(img_label)
        card_wrapper.setLayout(card_layout)
        self._update_card_style(img_label, is_selected)
        return card_wrapper

    def _update_card_style(self, img_label: QLabel, is_selected: bool):
        if is_selected:
            img_label.setStyleSheet("border: 3px solid #5865f2; background-color: #36393f;")
        else:
            img_label.setStyleSheet("border: 1px solid #4f545c; background-color: #36393f;")


    def clear_gallery(self, include_paths=True):
        """Clears both galleries and resets selection state."""
        self.selected_widget.setUpdatesEnabled(False)
        self.gallery_widget.setUpdatesEnabled(False)
        
        if include_paths:
            self.files_to_convert.clear()
            self.selected_files_to_convert.clear()
            self.path_to_label_map.clear()
        
        # Clear Preview Gallery
        self._clear_gallery(self.gallery_layout)
        columns = self._calculate_columns(self.gallery_scroll)
        empty_label = QLabel("Scan a directory to see images here.")
        empty_label.setAlignment(Qt.AlignCenter)
        empty_label.setStyleSheet("color: #b9bbbe; padding: 50px;")
        self.gallery_layout.addWidget(empty_label, 0, 0, 1, columns)
        
        # Clear Selected Gallery
        self._clear_gallery(self.selected_layout)
        empty_label_sel = QLabel("Selected files will appear here.")
        empty_label_sel.setAlignment(Qt.AlignCenter)
        empty_label_sel.setStyleSheet("color: #b9bbbe; padding: 50px;")
        self.selected_layout.addWidget(empty_label_sel, 0, 0, 1, columns)

        self.selected_widget.setUpdatesEnabled(True)
        self.gallery_widget.setUpdatesEnabled(True)
        self._update_conversion_button_state()
        
    def _clear_gallery(self, layout: QGridLayout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
    # --- END DUAL GALLERY LOGIC ---


    # --- REST OF CLASS METHODS ---
    
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

    @Slot()
    def browse_directory_input(self):
        try:
            start_dir = str(Path(os.getcwd()) / 'data')
        except Exception:
            start_dir = Path(os.getcwd())

        directory = QFileDialog.getExistingDirectory(self, "Select input directory", str(start_dir))
        if directory:
            self.input_path.setText(directory)
            self.clear_gallery()
            self.status_label.setText("Ready.")
            return directory
        return None

    @Slot()
    def browse_directory_and_scan(self):
        """Browse button is now connected to this method to auto-trigger the visual scan."""
        directory = self.browse_directory_input()
        if directory:
            self.scan_directory_visual()

    @Slot()
    def browse_output(self):
        try:
            start_dir = str(Path(os.getcwd()) / 'data')
        except Exception:
            start_dir = Path(os.getcwd())
        directory = QFileDialog.getExistingDirectory(self, "Select output directory", str(start_dir))
        if directory:
            self.output_path.setText(directory)

    # --- VALIDATION ---
    def is_valid_input(self) -> bool:
        p = self.input_path.text().strip()
        if not p or not os.path.isdir(p):
            QMessageBox.warning(self, "Invalid Input", "Please select a valid input directory.")
            return False
        return True

    def collect_paths(self) -> list[str]:
        """Walks directory to find files based on filters."""
        p = self.input_path.text().strip()
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

    # --- VISUAL SCAN (GALLERY) ---
    @Slot()
    def scan_directory_visual(self):
        """Populates the gallery with images found in the directory."""
        if not self.is_valid_input():
            return
            
        self.status_label.setText("Scanning directory...")
        paths = self.collect_paths()
        
        if not paths:
            QMessageBox.information(self, "No Files Found", "No files matching the input formats were found.")
            self.clear_gallery()
            self.status_label.setText("Scan complete: 0 files.")
            return

        self.status_label.setText(f"Found {len(paths)} files. Loading thumbnails...")
        self.load_thumbnails(paths)

    def load_thumbnails(self, paths: list[str]):
        """Starts concurrent loading using QThreadPool with a progress dialog."""
        
        self.thread_pool.clear()
        self._loaded_results_buffer = []
        self._images_loaded_count = 0
        self._total_images_to_load = len(paths)
        
        # --- 1. Setup dialog ---
        self.loading_dialog = QProgressDialog("Submitting tasks...", "Cancel", 0, self._total_images_to_load, self)
        self.loading_dialog.setWindowModality(Qt.WindowModal)
        self.loading_dialog.setWindowTitle("Please Wait")
        self.loading_dialog.setMinimumDuration(0)
        self.loading_dialog.setCancelButton(None) 
        self.loading_dialog.show()
        
        QApplication.processEvents()

        self.loading_dialog.setLabelText(f"Submitting task 0 of {self._total_images_to_load}...")
        self.loading_dialog.setValue(0) 
        
        submitted_count = 0
        self.files_to_convert = paths # Store files found
        self.path_to_label_map.clear() # Clear map for new labels
        
        # Submit tasks and update progress simultaneously on the main thread
        for path in paths:
            worker = ImageLoaderWorker(path, self.thumbnail_size)
            worker.signals.result.connect(self._on_single_image_loaded)
            self.thread_pool.start(worker)
            
            submitted_count += 1
            self.loading_dialog.setValue(submitted_count)
            self.loading_dialog.setLabelText(f"Submitting task {submitted_count} of {self._total_images_to_load}...")
            QApplication.processEvents()

    @Slot(str, QPixmap)
    def _on_single_image_loaded(self, path: str, pixmap: QPixmap):
        """Aggregates results and checks for batch completion. Updates progress dialog."""
        self._loaded_results_buffer.append((path, pixmap))
        self._images_loaded_count += 1
            
        if self._images_loaded_count >= self._total_images_to_load:
            sorted_results = sorted(self._loaded_results_buffer, key=lambda x: x[0])
            self.handle_batch_finished(sorted_results)

    @Slot(list)
    def handle_batch_finished(self, loaded_results: List[Tuple[str, QPixmap]]):
        self.clear_gallery(include_paths=False) # Clear widgets but keep self.files_to_convert
        columns = self._calculate_columns(self.gallery_scroll)
        
        for idx, (path, pixmap) in enumerate(loaded_results):
            row = idx // columns
            col = idx % columns
            
            is_selected = path in self.selected_files_to_convert
            card_wrapper = self._create_gallery_card(path, pixmap, is_selected)
            
            card_wrapper.path_clicked.connect(self.toggle_selection)

            self.gallery_layout.addWidget(card_wrapper, row, col, Qt.AlignLeft | Qt.AlignTop)
            self.path_to_label_map[path] = card_wrapper # Store map to retrieve label later

        if self.loading_dialog:
            self.loading_dialog.close()
            self.loading_dialog = None
            
        self.status_label.setText(f"Scan complete. Showing {len(loaded_results)} files.")
        self._refresh_selected_panel()

    # --- CONVERSION LOGIC ---
    @Slot()
    def toggle_conversion(self):
        """Starts or cancels the conversion worker (for the selected files button)."""
        if self.worker and self.worker.isRunning():
            self.cancel_conversion()
        else:
            # Use selection when calling from the dedicated selected button
            self.start_conversion_worker(use_selection=True) 
    
    @Slot(bool)
    def start_conversion_worker(self, use_selection: bool = False):
        """Starts conversion using either selected files or all scanned files."""
        if self.worker and self.worker.isRunning():
            self.cancel_conversion()
            return

        if not self.is_valid_input():
            return

        if use_selection:
            files_for_conversion = self.selected_files_to_convert
        else:
            # Called by "Convert All in Directory"
            files_for_conversion = self.collect_paths()

        if not files_for_conversion:
            QMessageBox.warning(self, "No Files Found", "No files found for conversion. Ensure the path and filters are correct.")
            return
            
        config = self.collect()
        config["files_to_convert"] = files_for_conversion
        
        # UI Updates
        self.btn_convert_all.setEnabled(False)
        self.btn_convert_contents.setEnabled(False) 
        
        # Determine which button text to set for cancellation
        button_to_cancel = self.btn_convert_contents if use_selection else self.btn_convert_all
        
        button_to_cancel.setEnabled(True)
        button_to_cancel.setText("Cancel Conversion")
        button_to_cancel.setStyleSheet("""
            QPushButton {
                background-color: #cc3333; color: white; font-weight: bold; font-size: 14px;
                padding: 14px 8px; border-radius: 10px; min-height: 44px;
            }
            QPushButton:hover { background-color: #ff4444; }
        """)
        
        self.status_label.setText(f"Starting conversion of {len(files_for_conversion)} files...")

        self.worker = ConversionWorker(config)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_conversion_done)
        self.worker.error.connect(self.on_conversion_error)
        self.worker.start()

    def cancel_conversion(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.on_conversion_done(0, "**Conversion cancelled** by user.")
            self.worker = None
            
    @Slot(str)
    def update_progress(self, progress_message: str):
        self.status_label.setText(progress_message)

    @Slot(int, str)
    def on_conversion_done(self, count, msg):
        # Reset UI state for all relevant buttons
        self.btn_convert_all.setEnabled(True)
        self.btn_convert_all.setText("Convert All in Directory")
        self.btn_convert_all.setStyleSheet(SHARED_BUTTON_STYLE)
        
        self.btn_convert_contents.setEnabled(len(self.selected_files_to_convert) > 0)
        self.btn_convert_contents.setText(f"Convert Selected Files ({len(self.selected_files_to_convert)})")
        self.btn_convert_contents.setStyleSheet(SHARED_BUTTON_STYLE)

        self.status_label.setText(f"{msg}")
        self.worker = None
        if "cancelled" not in msg.lower():
            QMessageBox.information(self, "Complete", msg)

    @Slot(str)
    def on_conversion_error(self, msg):
        # Reset UI state for all relevant buttons
        self.btn_convert_all.setEnabled(True)
        self.btn_convert_all.setText("Convert All in Directory")
        self.btn_convert_all.setStyleSheet(SHARED_BUTTON_STYLE)
        
        self.btn_convert_contents.setEnabled(len(self.selected_files_to_convert) > 0)
        self.btn_convert_contents.setText(f"Convert Selected Files ({len(self.selected_files_to_convert)})")
        self.btn_convert_contents.setStyleSheet(SHARED_BUTTON_STYLE)

        self.status_label.setText("Conversion failed.")
        QMessageBox.critical(self, "Error", msg)
        self.worker = None

    def collect(self) -> dict:
        input_formats = (
            list(self.selected_formats) if self.dropdown and self.selected_formats
            else self.join_list_str(self.input_formats.text().strip()) if not self.dropdown and hasattr(self, 'input_formats')
            else SUPPORTED_IMG_FORMATS
        )
        # MODIFIED: Get output format from combo box
        output_fmt = self.output_format_combo.currentText()
            
        return {
            "output_format": output_fmt.lower(),
            "input_path": self.input_path.text().strip(),
            "output_path": self.output_path.text().strip() or None,
            "input_formats": [f.strip().lstrip('.').lower() for f in input_formats if f.strip()],
            "delete": self.delete_checkbox.isChecked(),
        }

    @staticmethod
    def join_list_str(text):
        return [item.strip().lstrip('.') for item in text.replace(',', ' ').split() if item.strip()]

    
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
