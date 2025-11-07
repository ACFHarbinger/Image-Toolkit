import os
from pathlib import Path
from typing import Dict, Any, Set, List
from PySide6.QtCore import Qt, QTimer, QThread, QObject
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QLineEdit, QFileDialog, QWidget, QLabel, QPushButton,
    QComboBox, QSpinBox, QGroupBox, QFormLayout, QHBoxLayout,
    QVBoxLayout, QMessageBox, QApplication, QGridLayout,
)
from .BaseTab import BaseTab
from ..helpers import MergeWorker, ImageScannerWorker, BatchThumbnailLoaderWorker
from ..components import OptionalField, ClickableLabel, MarqueeScrollArea
from ..styles import apply_shadow_effect
from ...utils.definitions import SUPPORTED_IMG_FORMATS


class MergeTab(BaseTab):
    """
    GUI tab for merging images, replacing the list input with a file selection gallery
    similar to the ScanFSETab.
    """
    # NOTE: These QThread/QObject members are used for background operations
    _scan_thread: QThread = None
    _scan_worker: QObject = None
    _load_thread: QThread = None
    _load_worker: QObject = None

    def __init__(self, dropdown=True):
        super().__init__()
        self.dropdown = dropdown
        self.worker = None

        self.selected_image_paths: Set[str] = set()
        self.merge_image_list: List[str] = []
        self.path_to_label_map: Dict[str, ClickableLabel] = {}
        self.last_browsed_dir = str(Path.home())

        # Fixed dimensions for dynamic layout calculation
        self.thumbnail_size = 150
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width
        
        main_layout = QVBoxLayout(self)

        # --- 1. Top Configuration Group (Direction, Spacing, Grid) ---
        config_group = QGroupBox("Merge Settings")
        config_layout = QFormLayout(config_group)

        # Direction
        self.direction = QComboBox()
        self.direction.addItems(["horizontal", "vertical", "grid"])
        self.direction.currentTextChanged.connect(self.toggle_grid_visibility)
        config_layout.addRow("Direction:", self.direction)

        # Spacing
        self.spacing = QSpinBox()
        self.spacing.setRange(0, 1000)
        self.spacing.setValue(10)
        config_layout.addRow("Spacing (px):", self.spacing)

        # Grid size (Initially hidden)
        self.grid_group = QGroupBox("Grid Size")
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
        config_layout.addRow(self.grid_group)
        self.grid_group.hide()

        main_layout.addWidget(config_group)

        # --- 2. Input/Selection Gallery Group ---
        gallery_group = QGroupBox("Select Images to Merge")
        gallery_vbox = QVBoxLayout(gallery_group)

        # Input Buttons (Browse Files / Browse Directory)
        input_controls = QHBoxLayout()
        self.input_path_info = QLineEdit()
        self.input_path_info.setPlaceholderText("Use buttons to select images or scan multiple directories.")
        self.input_path_info.setReadOnly(True)
        self.input_path_info.setStyleSheet("background-color: #333; color: #b9bbbe;")

        btn_input_files = QPushButton("Add Files")
        apply_shadow_effect(btn_input_files, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        btn_input_files.clicked.connect(self._browse_files_logic) 
        
        btn_input_dir = QPushButton("Scan Directories")
        apply_shadow_effect(btn_input_dir, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        btn_input_dir.clicked.connect(self._browse_directories_logic) 

        input_controls.addWidget(self.input_path_info)
        input_controls.addWidget(btn_input_files)
        input_controls.addWidget(btn_input_dir)
        gallery_vbox.addLayout(input_controls)
        
        # Selection Counter
        self.selection_label = QLabel("0 images selected.")
        gallery_vbox.addWidget(self.selection_label)

        # Gallery Area (MarqueeScrollArea)
        self.merge_scroll_area = MarqueeScrollArea()
        self.merge_scroll_area.setWidgetResizable(True)
        self.merge_scroll_area.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")

        self.merge_thumbnail_widget = QWidget()
        self.merge_thumbnail_widget.setStyleSheet("QWidget { background-color: #2c2f33; }")
        self.merge_thumbnail_layout = QGridLayout(self.merge_thumbnail_widget)
        self.merge_thumbnail_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.merge_scroll_area.setWidget(self.merge_thumbnail_widget)
        self.merge_scroll_area.selection_changed.connect(self.handle_marquee_selection)

        gallery_vbox.addWidget(self.merge_scroll_area, 1)

        main_layout.addWidget(gallery_group)

        # --- 3. Output and Action Group ---
        action_group = QGroupBox("Output & Execution")
        action_vbox = QVBoxLayout(action_group)

        # Output path
        h_output = QHBoxLayout()
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Select output merged file (.png or .jpg)")
        btn_output = QPushButton("Browse Output...")
        apply_shadow_effect(btn_output, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        btn_output.clicked.connect(self._browse_output_logic) 
        h_output.addWidget(self.output_path)
        h_output.addWidget(btn_output)
        action_vbox.addLayout(h_output)

        # Formats (OptionalField)
        if self.dropdown:
            self.selected_formats = set()
            formats_layout = QVBoxLayout()
            formats_container = QWidget()
            self.formats_field = OptionalField("Filter Input Formats (Defaults to All)", formats_container, start_open=False)
            action_vbox.addWidget(self.formats_field)
            
            # Button logic setup (placed in a widget for cleaner OptionalField)
            formats_widget = QWidget()
            formats_inner_vbox = QVBoxLayout(formats_widget)
            
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
            
            all_btn_layout = QHBoxLayout()
            btn_add_all = QPushButton("Select All")
            btn_add_all.setStyleSheet("background-color: #2ecc71; color: white;")
            apply_shadow_effect(btn_add_all, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
            btn_add_all.clicked.connect(self.add_all_formats)
            btn_remove_all = QPushButton("Clear All")
            btn_remove_all.setStyleSheet("background-color: #e74c3c; color: white;")
            apply_shadow_effect(btn_remove_all, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
            btn_remove_all.clicked.connect(self.remove_all_formats)
            all_btn_layout.addWidget(btn_add_all)
            all_btn_layout.addWidget(btn_remove_all)
            
            formats_inner_vbox.addLayout(btn_layout)
            formats_inner_vbox.addLayout(all_btn_layout)
            formats_container.setLayout(formats_inner_vbox)
        
        # RUN MERGE BUTTON
        self.run_button = QPushButton("Run Merge")
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #5865f2;
                color: white; font-weight: bold; font-size: 16px;
                padding: 14px; border-radius: 10px; min-height: 44px;
            }
            QPushButton:hover { background-color: #4754c4; }
            QPushButton:disabled { background: #718096; }
            QPushButton:pressed { background: #3f479a; }
        """)
        apply_shadow_effect(self.run_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.run_button.clicked.connect(self.start_merge)
        action_vbox.addWidget(self.run_button)

        # Status
        self.status_label = QLabel("Ready. Select at least 2 images.")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #b9bbbe; font-style: italic; padding: 10px;")
        action_vbox.addWidget(self.status_label)
        
        main_layout.addWidget(action_group)
        
        self.update_run_button_state()
        self.toggle_grid_visibility(self.direction.currentText()) # Initial setup

    # --- GALLERY HANDLING METHODS (Copied/Adapted from ScanFSETab) ---
    
    def _cleanup_thumbnail_thread_ref(self):
        """Slot to clear the QThread and QObject references after the thread finishes its work."""
        if self._load_thread:
            self._load_thread.deleteLater()
        if self._load_worker:
            self._load_worker.deleteLater()
        
        self._load_thread = None
        self._load_worker = None
        
    def _cleanup_scan_thread_ref(self):
        """Helper for cleaning up the ImageScannerWorker thread references."""
        if self._scan_thread:
            self._scan_thread.deleteLater()
        if self._scan_worker:
            self._scan_worker.deleteLater()
            
        self._scan_thread = None
        self._scan_worker = None

    def clear_merge_gallery(self):
        """Removes all widgets from the merge gallery layout and cleans up the active thread."""
        
        # 1. Ensure any active thumbnail loading is stopped
        if self._load_thread and self._load_thread.isRunning():
            self._load_thread.quit()
        self._cleanup_thumbnail_thread_ref() # Clean up refs

        # 2. Ensure any active scanning is stopped
        if self._scan_thread and self._scan_thread.isRunning():
            self._scan_thread.quit()
        self._cleanup_scan_thread_ref()
        
        # 3. Clear visual widgets
        self.path_to_label_map = {} 
        while self.merge_thumbnail_layout.count():
            item = self.merge_thumbnail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        
        # 4. Reset state
        self.merge_image_list = []
        self.selected_image_paths = set()
        self.input_path_info.setText("")
        self.update_run_button_state()

    def calculate_columns(self) -> int:
        """Calculates the maximum number of thumbnail columns that fit in the widget."""
        widget_width = self.merge_thumbnail_widget.width()
        if widget_width <= 0:
            widget_width = self.merge_thumbnail_widget.parentWidget().width()
        if widget_width <= 0:
            return 4 # Absolute fallback
        
        columns = widget_width // self.approx_item_width
        return max(1, columns)

    def populate_merge_gallery(self, image_paths: list[str], source_desc: str):
        """
        Receives image paths, creates placeholders, and starts 
        a single BatchThumbnailLoaderWorker to progressively load and display images.
        """
        # Ensure cleanup before repopulating
        self.clear_merge_gallery()

        # Update the list
        self.merge_image_list = image_paths
        
        self.input_path_info.setText(f"Source: {source_desc} | Found: {len(self.merge_image_list)} images")
        
        columns = self.calculate_columns()
        
        if not self.merge_image_list:
            no_images_label = QLabel("No supported images found in the selected source.")
            no_images_label.setAlignment(Qt.AlignCenter)
            no_images_label.setStyleSheet("color: #b9bbbe;")
            self.merge_thumbnail_layout.addWidget(no_images_label, 0, 0, 1, columns)
            return

        # 1. Create ALL Placeholders immediately
        for i, path in enumerate(self.merge_image_list):
            row = i // columns
            col = i % columns

            clickable_label = ClickableLabel(path) 
            clickable_label.setText("Loading...")
            clickable_label.setAlignment(Qt.AlignCenter)
            clickable_label.setFixedSize(self.thumbnail_size, self.thumbnail_size)
            clickable_label.setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;")
            # Single click for selection/deselection toggle
            clickable_label.path_clicked.connect(self.select_merge_image) 
            clickable_label.path_double_clicked.connect(lambda p: QMessageBox.information(self, "Image Path", p)) # Preview not implemented
            
            self.merge_thumbnail_layout.addWidget(clickable_label, row, col)
            self.path_to_label_map[path] = clickable_label 

        # 2. Kick off the SINGLE asynchronous worker for batch loading
        worker = BatchThumbnailLoaderWorker(self.merge_image_list, self.thumbnail_size)
        thread = QThread()
        
        self._load_worker = worker
        self._load_thread = thread
        
        worker.moveToThread(thread)
        
        thread.started.connect(worker.run_load_batch)
        worker.thumbnail_loaded.connect(self._update_thumbnail_slot)
        
        # --- Robust Cleanup ---
        worker.loading_finished.connect(thread.quit)
        thread.finished.connect(self._cleanup_thumbnail_thread_ref) # Triggers worker/thread deleteLater
        
        thread.start()
    
    def _update_thumbnail_slot(self, index: int, pixmap: QPixmap, path: str):
        """Slot executed on the main thread to update a specific thumbnail widget."""
        label = self.path_to_label_map.get(path)
        if label is None: return

        is_selected = path in self.selected_image_paths
        
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                self.thumbnail_size, self.thumbnail_size, 
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            label.setPixmap(scaled_pixmap)
            label.setText("") 
            
            if is_selected:
                label.setStyleSheet("border: 3px solid #5865f2;")
            else:
                label.setStyleSheet("border: 1px solid #4f545c;")
        else:
            label.setText("Load Error")
            if is_selected:
                label.setStyleSheet("border: 3px solid #5865f2; background-color: #4f545c; font-size: 8px;") 
            else:
                label.setStyleSheet("border: 1px solid #e74c3c; background-color: #4f545c; font-size: 8px;")

    def select_merge_image(self, file_path: str):
        """Toggles the selection status of a single image."""
        clicked_widget = self.path_to_label_map.get(file_path)
        if not clicked_widget: return

        mods = QApplication.keyboardModifiers()
        is_ctrl_pressed = bool(mods & Qt.ControlModifier)

        is_currently_selected = file_path in self.selected_image_paths

        if not is_ctrl_pressed:
            # No Ctrl: Deselect all others, select/keep this one
            paths_to_deselect = self.selected_image_paths - {file_path}
            for path in paths_to_deselect:
                label = self.path_to_label_map.get(path)
                if label:
                    # Apply deselected style (using helper logic for image vs error)
                    self._update_label_style(label, path, False)

            # If not already selected, select it
            if not is_currently_selected:
                self.selected_image_paths = {file_path}
            # If already selected, leave it selected (single click without Ctrl means this is the sole selection)
            else:
                 self.selected_image_paths = {file_path}

        else:
            # Ctrl is pressed: Toggle this item
            if is_currently_selected:
                self.selected_image_paths.remove(file_path)
            else:
                self.selected_image_paths.add(file_path)

        # Update the style for the *clicked* item
        self._update_label_style(clicked_widget, file_path, file_path in self.selected_image_paths)

        self.update_run_button_state()
        
    def _update_label_style(self, label: ClickableLabel, path: str, is_selected: bool):
        """Helper to apply the correct style based on selection and load status."""
        if is_selected:
            if "Error" in label.text():
                label.setStyleSheet("border: 3px solid #5865f2; background-color: #4f545c; font-size: 8px;")
            else:
                label.setStyleSheet("border: 3px solid #5865f2;")
        else:
            if not label.pixmap().isNull():
                label.setStyleSheet("border: 1px solid #4f545c;")
            else:
                if "Error" in label.text():
                    label.setStyleSheet("border: 1px solid #e74c3c; background-color: #4f545c; font-size: 8px;")
                else:
                    label.setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;")

    def handle_marquee_selection(self, paths_from_marquee: set, is_ctrl_pressed: bool):
        """Handles the selection update from the MarqueeScrollArea."""
        paths_to_update: Set[str] = set()

        if not is_ctrl_pressed:
            paths_to_deselect = self.selected_image_paths - paths_from_marquee
            paths_to_select = paths_from_marquee - self.selected_image_paths
            
            self.selected_image_paths = paths_from_marquee
            paths_to_update = paths_to_deselect.union(paths_to_select)
        else:
            paths_to_update = paths_from_marquee - self.selected_image_paths
            self.selected_image_paths.update(paths_from_marquee)

        # Update the visual style for all affected labels
        for path in paths_to_update:
            label = self.path_to_label_map.get(path)
            if label:
                is_selected = path in self.selected_image_paths
                self._update_label_style(label, path, is_selected)

        self.update_run_button_state()

    # --- INPUT/BROWSE METHODS ---
    
    def _browse_files_logic(self):
        """Internal logic for 'Add Files' button."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select images to merge", self.last_browsed_dir,
            "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)"
        )
        if files:
            self.last_browsed_dir = os.path.dirname(files[0]) if files else self.last_browsed_dir
            current_paths = set(self.merge_image_list)
            new_paths = [f for f in files if f not in current_paths]
            updated_list = self.merge_image_list + new_paths
            
            # Repopulate the gallery with the combined list
            self.populate_merge_gallery(updated_list, f"Manual: {len(updated_list)} files added")

    def _browse_directories_logic(self):
        """
        Internal logic for 'Scan Directories' button. Prompts for multiple directories
        and aggregates images from all of them.
        """
        selected_directories = []
        last_dir = self.last_browsed_dir
        
        # We use a loop, prompting the user repeatedly until they cancel
        while True:
            directory = QFileDialog.getExistingDirectory(
                self, 
                f"Select Directory {len(selected_directories) + 1} (Click Cancel when done)", 
                last_dir
            )
            if directory:
                if directory not in selected_directories:
                    selected_directories.append(directory)
                    last_dir = directory
                else:
                    QMessageBox.information(self, "Directory Already Added", f"'{directory}' has already been selected.")
            else:
                break # User clicked cancel

        if not selected_directories:
            return

        self.last_browsed_dir = selected_directories[-1]
        self.input_path_info.setText("Scanning directories, please wait...")
        
        # --- Aggregation Logic ---
        worker = ImageScannerWorker(selected_directories) 
        thread = QThread()

        # --- FIX: Use internal class members for thread/worker tracking ---
        self._scan_worker = worker
        self._scan_thread = thread
        
        worker.moveToThread(thread)
        
        thread.started.connect(worker.run_scan)
        
        # 2. The scan_finished signal returns the aggregated list of paths
        worker.scan_finished.connect(
            lambda paths: self.populate_merge_gallery(
                paths, 
                f"Aggregated: {len(selected_directories)} directories"
            )
        )
        worker.scan_error.connect(lambda msg: QMessageBox.critical(self, "Scan Error", msg))
        
        # --- Robust Cleanup ---
        worker.scan_finished.connect(thread.quit)
        worker.scan_error.connect(thread.quit)
        thread.finished.connect(self._cleanup_scan_thread_ref) # Triggers worker/thread deleteLater
        
        thread.start()

    def _browse_output_logic(self):
        """Internal logic for 'Browse Output' button."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save merged image", "", "PNG (*.png);;JPEG (*.jpg);;All Files (*)"
        )
        if file_path:
            self.output_path.setText(file_path)
            
    # --- UTILITY METHODS ---

    def update_run_button_state(self):
        """Updates the status label and merge button based on selection count."""
        count = len(self.selected_image_paths)
        self.selection_label.setText(f"{count} images selected.")
        
        if count < 2:
            self.run_button.setEnabled(False)
            self.status_label.setText("Select at least 2 images to merge.")
            self.run_button.setText("Run Merge")
        else:
            self.run_button.setEnabled(True)
            self.status_label.setText(f"Ready to merge {count} images.")
            self.run_button.setText(f"Run Merge ({count} images)")

    def toggle_grid_visibility(self, direction):
        """Toggles visibility of grid controls and resizes the window."""
        layout = self.layout()
        is_grid = (direction == "grid")
        
        # This logic ensures the widget is correctly added/removed from the layout
        if is_grid:
            if self.grid_group.parent() is None:
                config_layout = self.findChild(QFormLayout)
                if config_layout:
                    # Insert before the run button group in the form layout
                    config_layout.addRow(self.grid_group)
            self.grid_group.show()
        else:
            self.grid_group.hide()
            
        # Add a delay for resizing to ensure layout update is complete
        if hasattr(self, "_resize_timer"):
            self._resize_timer.stop()
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._resize_hierarchy)
        self._resize_timer.start(100)

    def _resize_hierarchy(self):
        """Helper to resize the parent window slightly if the grid settings appear/disappear."""
        win = self.window()
        if win:
            # Simple placeholder adjustment, usually handled better by container widgets
            pass 

    def toggle_format(self, fmt, checked):
        """Handles format button toggle state."""
        btn = self.format_buttons.get(fmt)
        if btn is None: return

        if checked:
            self.selected_formats.add(fmt)
            btn.setStyleSheet("QPushButton:checked { background-color: #3320b5; color: white; } QPushButton:hover { background-color: #00838a; }")
            apply_shadow_effect(btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        else:
            self.selected_formats.discard(fmt)
            btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")
            apply_shadow_effect(btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)

    def add_all_formats(self):
        """Selects all supported input formats."""
        for fmt, btn in self.format_buttons.items():
            if not btn.isChecked():
                btn.setChecked(True)
                self.toggle_format(fmt, True)

    def remove_all_formats(self):
        """Deselects all supported input formats."""
        for fmt, btn in self.format_buttons.items():
            if btn.isChecked():
                btn.setChecked(False)
                self.toggle_format(fmt, False)

    # --- MERGE EXECUTION METHODS ---

    def is_valid(self):
        """Checks if the minimum requirements for merging are met."""
        if len(self.selected_image_paths) < 2:
            return False
        if not self.output_path.text().strip():
            return False
        return True

    def start_merge(self):
        """
        Validates input, collects configuration, and starts the merge worker.
        Includes robust thread handling for the MergeWorker.
        """
        if not self.is_valid():
            QMessageBox.warning(self, "Invalid Input", "Please select at least 2 images AND define an output path.")
            return

        config = self.collect()
        
        self.run_button.setEnabled(False)
        self.run_button.setText("Merging...")
        self.status_label.setText("Processing request...")
        QApplication.processEvents() # Ensure UI updates

        # --- MergeWorker Threading Setup (Robust Cleanup) ---
        worker = MergeWorker(config)
        thread = QThread()
        
        # Use simple self.worker for this one since it's short-lived
        self.worker = worker
        self.worker.moveToThread(thread)

        thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_merge_done)
        self.worker.error.connect(self.on_merge_error)
        
        # 1. When worker finishes/errors, quit the thread
        self.worker.finished.connect(thread.quit)
        self.worker.error.connect(thread.quit)
        
        # 2. When worker finishes/errors, schedule worker for deletion
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)
        
        # 3. When thread quits, schedule thread for deletion
        thread.finished.connect(thread.deleteLater)
        
        thread.start()

    def update_progress(self, current, total):
        self.status_label.setText(f"Merging image {current}/{total}...")

    def on_merge_done(self, output_path):
        self.update_run_button_state()
        self.status_label.setText(f"Saved: {os.path.basename(output_path)}")
        QMessageBox.information(self, "Success", f"Merge complete!\nSaved to:\n{output_path}")

    def on_merge_error(self, msg):
        self.update_run_button_state()
        self.status_label.setText("Failed.")
        QMessageBox.critical(self, "Error", msg)

    def collect(self) -> Dict[str, Any]:
        """Collects all configuration inputs for the MergeWorker."""
        
        # The input paths are the currently selected paths from the gallery
        input_paths = list(self.selected_image_paths)

        # Get formats (using selected buttons if dropdown is enabled, otherwise use all supported)
        formats = (
            list(self.selected_formats) if self.dropdown and self.selected_formats
            else SUPPORTED_IMG_FORMATS
        )

        return {
            "direction": self.direction.currentText(),
            "input_path": input_paths, # List of selected absolute paths
            "output_path": self.output_path.text().strip() or None,
            "input_formats": [f.strip().lstrip('.') for f in formats if f.strip()],
            "spacing": self.spacing.value(),
            "grid_size": (
                self.grid_rows.value(), self.grid_cols.value()
            ) if self.direction.currentText() == "grid" else None
        }

    # --- BASE TAB ABSTRACT METHOD IMPLEMENTATIONS (FIXED RECURSION) ---

    def browse_files(self):
        """Implements abstract method: Calls the internal logic for file selection."""
        self._browse_files_logic()
    
    def browse_directory(self):
        """Implements abstract method: Calls the internal logic for directory scanning."""
        self._browse_directories_logic()

    def browse_input(self):
        """Abstract method: Currently maps to file selection."""
        self._browse_files_logic()

    def browse_output(self):
        """Implements abstract method: Calls the internal logic for output path selection."""
        self._browse_output_logic()