import os
from pathlib import Path
from typing import Dict, Any, Set, List
from PySide6.QtCore import Qt, QTimer, QThread, QObject
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QLineEdit, QFileDialog, QWidget, QLabel, QPushButton,
    QComboBox, QSpinBox, QGroupBox, QFormLayout, QHBoxLayout,
    QVBoxLayout, QMessageBox, QApplication, QGridLayout, QFrame,
    QScrollArea
)
from .base_tab import BaseTab
from ..components import ClickableLabel, MarqueeScrollArea
from ..helpers import MergeWorker, ImageScannerWorker, BatchThumbnailLoaderWorker
from ..utils.styles import apply_shadow_effect
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
        
        # --- MODIFICATION: Initialize last_browsed_dir robustly (same as ScanMetadataTab) ---
        try:
            base_dir = Path.cwd()
            while base_dir.name != 'Image-Toolkit' and base_dir.parent != base_dir:
                base_dir = base_dir.parent
            if base_dir.name == 'Image-Toolkit':
                self.last_browsed_dir = str(base_dir / 'data')
            else:
                self.last_browsed_dir = str(Path.cwd() / 'data')
        except Exception:
             self.last_browsed_dir = os.getcwd() 
        # ----------------------------------------------------------------------------------

        # Thumbnail size remains 200 (as requested, only gallery size increases)
        self.thumbnail_size = 200 
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width
        
        # --- MODIFICATION: Add map for bottom panel ---
        self.selected_card_map: Dict[str, ClickableLabel] = {}
        
        main_layout = QVBoxLayout(self)

        # ------------------------------------------------------------------
        # --- NEW: Scrollable Content Setup ---
        # ------------------------------------------------------------------
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        # ESCAPED NEWLINE FIX: Ensuring stylesheet is parseable
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        
        scroll_content = QWidget()
        # Set a QVBoxLayout for the content that will be placed inside the QScrollArea
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 0, 0, 0) # No extra margin on the scroll content

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

        # Add Configuration Group to the scrollable content layout
        content_layout.addWidget(config_group)

        # --- 2. Input/Selection Gallery Group ---
        gallery_group = QGroupBox("Select Images to Merge")
        gallery_vbox = QVBoxLayout(gallery_group)
        
        # INCREASE MINIMUM HEIGHT FACTOR OF 2 (600 -> 1200)
        gallery_group.setMinimumHeight(1200) 

        # Input Buttons (Browse Files / Browse Directory)
        input_controls = QHBoxLayout()
        self.input_path_info = QLineEdit()
        self.input_path_info.setPlaceholderText("Use buttons to select images or scan a directory.")
        self.input_path_info.setReadOnly(True)
        self.input_path_info.setStyleSheet("background-color: #333; color: #b9bbbe;")

        btn_input_files = QPushButton("Add Files")
        apply_shadow_effect(btn_input_files, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        btn_input_files.clicked.connect(self._browse_files_logic) 
        # Make the Add Files button clickable with Enter
        btn_input_files.setDefault(True) 
        
        btn_input_dir = QPushButton("Scan Directory")
        apply_shadow_effect(btn_input_dir, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        btn_input_dir.clicked.connect(self._browse_directories_logic) 

        input_controls.addWidget(self.input_path_info)
        input_controls.addWidget(btn_input_files)
        input_controls.addWidget(btn_input_dir)
        gallery_vbox.addLayout(input_controls)
        
        # Selection Counter
        self.selection_label = QLabel("0 images selected.")
        gallery_vbox.addWidget(self.selection_label)

        # Gallery Area (MarqueeScrollArea) - Top Panel
        self.merge_scroll_area = MarqueeScrollArea()
        self.merge_scroll_area.setWidgetResizable(True)
        # ESCAPED NEWLINE FIX: Ensuring stylesheet is parseable
        self.merge_scroll_area.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")

        self.merge_thumbnail_widget = QWidget()
        # ESCAPED NEWLINE FIX: Ensuring stylesheet is parseable
        self.merge_thumbnail_widget.setStyleSheet("QWidget { background-color: #2c2f33; }")
        self.merge_thumbnail_layout = QGridLayout(self.merge_thumbnail_widget)
        self.merge_thumbnail_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.merge_scroll_area.setWidget(self.merge_thumbnail_widget)
        self.merge_scroll_area.selection_changed.connect(self.handle_marquee_selection)

        # Inner stretch factor set to 1 (for equal division with the selected area)
        gallery_vbox.addWidget(self.merge_scroll_area, 1) 

        # --- 2.5. Selected Images Area --- (Bottom Panel)
        self.selected_images_area = MarqueeScrollArea() 
        self.selected_images_area.setWidgetResizable(True)
        # ESCAPED NEWLINE FIX: Ensuring stylesheet is parseable
        self.selected_images_area.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")
        
        self.selected_images_widget = QWidget()
        # ESCAPED NEWLINE FIX: Ensuring stylesheet is parseable
        self.selected_images_widget.setStyleSheet("QWidget { background-color: #2c2f33; }")
        self.selected_grid_layout = QGridLayout(self.selected_images_widget)
        self.selected_grid_layout.setSpacing(10)
        self.selected_grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft) # Align items to top-left
        
        self.selected_images_area.setWidget(self.selected_images_widget)
        
        self.selected_images_area.setVisible(True) 
        # Inner stretch factor set to 1 (for equal division with the merge area)
        gallery_vbox.addWidget(self.selected_images_area, 1) 
        # --------------------------------------------------------

        # Add Gallery Group to the scrollable content layout, giving it stretch
        content_layout.addWidget(gallery_group, 6) 
        
        # Set the scrollable content widget to the QScrollArea
        scroll_area.setWidget(scroll_content)
        
        # Add the QScrollArea to the main layout
        main_layout.addWidget(scroll_area)

        # ------------------------------------------------------------------
        # --- 3. Action Group (Fixed at the bottom, outside scroll area) ---
        # ------------------------------------------------------------------
        action_vbox = QVBoxLayout() 
        
        # RUN MERGE BUTTON
        self.run_button = QPushButton("Run Merge")
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #5865f2; \n
                color: white; font-weight: bold; font-size: 16px; \n
                padding: 14px; border-radius: 10px; min-height: 44px; \n
            }
            QPushButton:hover { background-color: #4754c4; } \n
            QPushButton:disabled { background: #718096; } \n
            QPushButton:pressed { background: #3f479a; }
        """)
        apply_shadow_effect(self.run_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.run_button.clicked.connect(self.start_merge)
        # Ensure Run Merge is the default button if it's enabled (if not, Add Files will be)
        self.run_button.setDefault(True) 
        action_vbox.addWidget(self.run_button)

        # Status Label: Kept for merge progress, initialized as clear
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #b9bbbe; font-style: italic; padding: 10px;")
        action_vbox.addWidget(self.status_label)
        
        # Add the fixed action group to the main layout
        main_layout.addLayout(action_vbox)
        
        self.update_run_button_state()
        self.toggle_grid_visibility(self.direction.currentText()) # Initial setup
        
        self.populate_selected_images_gallery() # Initial population to show placeholder

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
        
        # 3. Clear visual widgets (Top Gallery)
        self.path_to_label_map = {} 
        while self.merge_thumbnail_layout.count():
            item = self.merge_thumbnail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        
        # 4. Clear bottom gallery
        while self.selected_grid_layout.count():
            item = self.selected_grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.selected_card_map = {}
        
        # 5. Reset state
        self.merge_image_list = []
        self.selected_image_paths = set()
        self.input_path_info.setText("")
        self.update_run_button_state()
        
        self.populate_selected_images_gallery() # Reset placeholder

    def calculate_columns(self) -> int:
        """Calculates the maximum number of thumbnail columns that fit in the widget."""
        widget_width = self.merge_thumbnail_widget.width()
        if widget_width <= 0:
            widget_width = self.merge_thumbnail_widget.parentWidget().width()
        if widget_width <= 0:
            return 4 # Absolute fallback
        
        columns = widget_width // self.approx_item_width
        return max(1, columns)

    def _create_thumbnail_placeholder(self, index: int, path: str):
        """
        Slot executed on the main thread to create and add a single placeholder
        for an image path *before* it is loaded by the worker.
        """
        columns = self.calculate_columns()
        row = index // columns
        col = index % columns

        clickable_label = ClickableLabel(path) 
        clickable_label.setText("Loading...")
        clickable_label.setAlignment(Qt.AlignCenter)
        clickable_label.setFixedSize(self.thumbnail_size, self.thumbnail_size)
        clickable_label.setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;")
        clickable_label.path_clicked.connect(self.select_merge_image) 
        clickable_label.path_double_clicked.connect(lambda p: QMessageBox.information(self, "Image Path", p))
        
        # Add widget to layout
        self.merge_thumbnail_layout.addWidget(clickable_label, row, col)
        self.path_to_label_map[path] = clickable_label 
        
        # Ensure the layout is updated immediately to show the new placeholder
        self.merge_thumbnail_widget.update()
        QApplication.processEvents()

    def populate_merge_gallery(self, image_paths: list[str], source_desc: str):
        """
        Receives image paths, creates placeholders progressively, and starts 
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

        # 1. Kick off the SINGLE asynchronous worker for batch loading
        worker = BatchThumbnailLoaderWorker(self.merge_image_list, self.thumbnail_size)
        thread = QThread()
        
        self._load_worker = worker
        self._load_thread = thread
        
        worker.moveToThread(thread)
        
        thread.started.connect(worker.run_load_batch)
        
        # Connect for progressive placeholder creation
        worker.create_placeholder.connect(self._create_thumbnail_placeholder)
        
        # Existing connection to update the placeholder with the image
        worker.thumbnail_loaded.connect(self._update_thumbnail_slot)
        
        # Robust Cleanup
        worker.loading_finished.connect(thread.quit)
        worker.loading_finished.connect(worker.deleteLater)
        thread.finished.connect(self._cleanup_thumbnail_thread_ref) 
        
        thread.start()
    
    def _update_thumbnail_slot(self, index: int, pixmap: QPixmap, path: str):
        """Slot executed on the main thread to update a specific thumbnail widget."""
        label = self.path_to_label_map.get(path)
        if label is None: return

        is_selected = path in self.selected_image_paths
        
        if not pixmap.isNull():
            label.setPixmap(pixmap) 
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
        """Toggles the selection status of a single image in the TOP panel."""
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
                    self._update_label_style(label, path, False)

            if not is_currently_selected:
                self.selected_image_paths = {file_path}
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
        self.populate_selected_images_gallery()
        
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
        self.populate_selected_images_gallery()

    # --- METHODS FOR BOTTOM "SELECTED" PANEL ---

    def populate_selected_images_gallery(self):
        """
        Clears and repopulates the grid layout in the 'Selected Images' group box.
        """
        # Clear existing widgets and the tracking map
        while self.selected_grid_layout.count():
            item = self.selected_grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.selected_card_map = {}
        
        paths = sorted(list(self.selected_image_paths))
        
        # Use the main thumbnail size for consistency
        thumb_size = self.thumbnail_size 
        padding = 10
        # Calculate approximation based on the main size
        approx_width = thumb_size + padding + 10 
        
        widget_width = self.selected_images_widget.width()
        if widget_width <= 0:
            # Need to get the width from the parent QScrollArea widget inside the QWidget
            widget_width = self.selected_images_area.width()
        
        columns = max(1, widget_width // approx_width)
        
        # Calculate the fixed size for the wrapper to hold the image + path label comfortably
        wrapper_height = self.thumbnail_size + 30 # Image height + room for path label
        wrapper_width = self.thumbnail_size + 10 # Image width + minor padding/margin
        
        if not paths:
            # Add a placeholder when no images are selected
            empty_label = QLabel("Selected images will appear here.")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #b9bbbe; padding: 50px;")
            self.selected_grid_layout.addWidget(empty_label, 0, 0, 1, columns)
            return

        for i, path in enumerate(paths):
            # Use ClickableLabel to wrap the card content for selection/click
            card_clickable_wrapper = ClickableLabel(path)
            
            # Set explicit size constraints on the wrapper to ensure it holds the content
            card_clickable_wrapper.setFixedSize(wrapper_width, wrapper_height) 

            card_clickable_wrapper.path_clicked.connect(self.select_selected_image_card)
            card_clickable_wrapper.path_double_clicked.connect(self.view_selected_image_from_card)
            
            # --- Card Frame Styling ---
            card = QFrame()
            
            # The card should always reflect its true selection status in the master set
            is_master_selected = path in self.selected_image_paths
            
            # ESCAPED NEWLINE FIX: Escaping newlines in multiline QFrame style
            if is_master_selected:
                 card_style = (
                     "QFrame { \n"
                     "    background-color: #2c2f33; \n"
                     "    border-radius: 8px; \n"
                     "    border: 3px solid #5865f2; \n"
                     "}"
                 )
            else:
                card_style = (
                    "QFrame { \n"
                    "    background-color: #2c2f33; \n"
                    "    border-radius: 8px; \n"
                    "    border: 1px solid #4f545c; \n"
                    "}"
                )

            card.setStyleSheet(card_style)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(0, 0, 0, 0) 
            
            img_label = QLabel()
            img_label.setAlignment(Qt.AlignCenter)
            # Explicitly use self.thumbnail_size (200) for fixed size container
            img_label.setFixedSize(self.thumbnail_size, self.thumbnail_size) 
            
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.thumbnail_size, self.thumbnail_size, 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                img_label.setPixmap(scaled)
            else:
                img_label.setText("Failed to Load")
                img_label.setStyleSheet("color: #e74c3c;")

            path_label = QLabel(os.path.basename(path)) 
            path_label.setStyleSheet("color: #b9bbbe; font-size: 10px; border: none; padding: 2px 0;")
            path_label.setAlignment(Qt.AlignCenter)
            path_label.setWordWrap(True)

            card_layout.addWidget(img_label)
            card_layout.addWidget(path_label)
            
            # Set the card frame as the content of the clickable wrapper
            card_clickable_wrapper.setLayout(card_layout)
            
            row = i // columns
            col = i % columns
            
            # Store the wrapper to track the actual selection state of the item within the panel
            self.selected_card_map[path] = card_clickable_wrapper
            
            # Use Qt.AlignLeft on the QGridLayout to center the individual items
            self.selected_grid_layout.addWidget(card_clickable_wrapper, row, col, Qt.AlignTop | Qt.AlignLeft) 

    def select_selected_image_card(self, file_path: str):
        """
        Handles single-click events in the bottom 'Selected Images' panel.
        Toggles selection status in the master set and updates styling.
        """
        card_clickable_wrapper = self.selected_card_map.get(file_path)
        if not card_clickable_wrapper:
            return
            
        # Toggle selection in the master set
        if file_path in self.selected_image_paths:
            self.selected_image_paths.remove(file_path)
            is_selected = False
        else:
            self.selected_image_paths.add(file_path)
            is_selected = True
            
        # Get the QFrame (the visual card) inside the clickable wrapper
        card_frame = card_clickable_wrapper.findChild(QFrame)
        if card_frame:
            # Update the styling of the card itself
            if is_selected:
                card_frame.setStyleSheet("""
                    QFrame {
                        background-color: #2c2f33; \n
                        border-radius: 8px; \n
                        border: 3px solid #5865f2; \n
                    }
                """)
            else:
                card_frame.setStyleSheet("""
                    QFrame {
                        background-color: #2c2f33; \n
                        border-radius: 8px; \n
                        border: 1px solid #4f545c; \n
                    }
                """)
            
        # Also update the styling in the main gallery if the image is loaded there
        main_label = self.path_to_label_map.get(file_path)
        if main_label:
            self._update_label_style(main_label, file_path, is_selected)
        
        self.update_run_button_state()
        
        # NOTE: We skip calling populate_selected_images_gallery() here to keep the deselected card visible.

    def view_selected_image_from_card(self, path: str):
        """Handles double-click event on a card in the selected panel."""
        # Simple implementation: Show a message box with the path
        QMessageBox.information(self, "Image Path", path)

    # --- INPUT/BROWSE METHODS ---
    
    def _browse_files_logic(self):
        """Internal logic for 'Add Files' button."""
        
        # Ensure a fallback to a guaranteed path if last_browsed_dir is somehow unreliable
        start_dir = self.last_browsed_dir if self.last_browsed_dir and os.path.exists(self.last_browsed_dir) else str(Path.home())
        options = QFileDialog.Option.DontResolveSymlinks

        files, _ = QFileDialog.getOpenFileNames(
            self, 
            "Select images to merge", 
            start_dir, 
            "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)",
            options=options # Pass options by keyword
        )
        
        if files:
            # --- MODIFICATION: Update last_browsed_dir ---
            self.last_browsed_dir = os.path.dirname(files[0]) if files else self.last_browsed_dir
            # ---------------------------------------------
            current_paths = set(self.merge_image_list)
            new_paths = [f for f in files if f not in current_paths]
            updated_list = self.merge_image_list + new_paths
            
            # Repopulate the gallery with the combined list
            self.populate_merge_gallery(updated_list, f"Manual: {len(updated_list)} files added")

    def _browse_directories_logic(self):
        """
        Internal logic for 'Scan Directory' button. 
        Prompts for a single directory and scans it.
        """
        # Ensure a fallback to a guaranteed path
        last_dir = self.last_browsed_dir if self.last_browsed_dir and os.path.exists(self.last_browsed_dir) else str(Path.home())
        options = QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks

        directory = QFileDialog.getExistingDirectory(
            self, 
            "Select Directory to Scan", 
            last_dir,
            options # Pass the options flag
        )
        
        if not directory:
            # User clicked Cancel
            self.input_path_info.setPlaceholderText("Use buttons to select images or scan a directory.")
            return

        # --- MODIFICATION: Update last_browsed_dir ---
        self.last_browsed_dir = directory
        # ---------------------------------------------
        
        self.input_path_info.setText("Scanning directory, please wait...")
        
        # 1. Clear any previous scan/load state
        self.clear_merge_gallery() 
        
        worker = ImageScannerWorker([directory]) # Pass the single directory in a list
        thread = QThread()

        # Set class members for tracking and cleanup
        self._scan_worker = worker
        self._scan_thread = thread
        
        worker.moveToThread(thread)
        
        thread.started.connect(worker.run_scan)
        
        # Connect success to populating the gallery (which starts thumbnail loading)
        worker.scan_finished.connect(
            lambda paths: self.populate_merge_gallery(
                paths, 
                f"Scanned: {Path(directory).name}"
            )
        )
        
        # Connect error handling
        worker.scan_error.connect(lambda msg: QMessageBox.critical(self, "Scan Error", msg))
        
        # Robust thread cleanup connections
        worker.scan_finished.connect(thread.quit)
        worker.scan_error.connect(thread.quit)
        thread.finished.connect(self._cleanup_scan_thread_ref) # Call the cleanup method
        
        thread.start()

    def _browse_output_logic(self):
        """Internal logic for 'Browse Output' button."""
        pass
            
    # --- UTILITY METHODS ---

    def update_run_button_state(self):
        """Updates the status label and merge button based on selection count."""
        count = len(self.selected_image_paths)
        self.selection_label.setText(f"{count} images selected.")
        
        # We need to ensure the default button is set correctly here:
        # If enabled, Run Merge should be default. If disabled, 'Add Files' should be default (set in __init__).
        
        # NOTE: QPushButtons in Qt are automatically 'autoDefault' when created, but only
        # one 'default' button can exist per dialog/window. The last one set with setDefault(True) wins.
        # Since 'Add Files' is now set as default, we must explicitly set/unset 'Run Merge' here.
        
        run_button_text = f"Run Merge ({count} images)"

        if count < 2:
            self.run_button.setEnabled(False)
            run_button_text = "Run Merge (Select at least 2 images to merge)"
            self.run_button.setDefault(False) # Unset default property
            
            # Re-enable the Add Files button as the default action when Merge is disabled
            add_files_button = self.findChild(QPushButton)
            if add_files_button and add_files_button.text() == "Add Files":
                add_files_button.setDefault(True)

            self.status_label.setText("") # Clear status label when button is disabled
        else:
            self.run_button.setEnabled(True)
            self.status_label.setText(f"Ready to merge {count} images.")
            self.run_button.setDefault(True) # Set default property
            
            # Unset the Add Files button as the default action
            add_files_button = self.findChild(QPushButton)
            if add_files_button and add_files_button.text() == "Add Files":
                add_files_button.setDefault(False)

        self.run_button.setText(run_button_text)


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
        if not hasattr(self, "_resize_timer"):
             self._resize_timer = QTimer()
             self._resize_timer.setSingleShot(True)
             self._resize_timer.timeout.connect(self._resize_hierarchy) 

        self._resize_timer.stop()
        self._resize_timer.start(100)

    def _resize_hierarchy(self):
        """Helper to resize the parent window slightly if the grid settings appear/disappear."""
        win = self.window()
        if win:
            # Simple placeholder adjustment, usually handled better by container widgets
            pass 

    def toggle_format(self, fmt, checked):
        """Handles format button toggle state."""
        # This logic seems to be from a different version, as self.format_buttons doesn't exist.
        # I will leave the method stub but it won't do anything.
        pass

    def add_all_formats(self):
        """Selects all supported input formats."""
        pass

    def remove_all_formats(self):
        """Deselects all supported input formats."""
        pass

    # --- MERGE EXECUTION METHODS ---

    def is_valid(self):
        """Checks if the minimum requirements for merging are met."""
        if len(self.selected_image_paths) < 2:
            return False
        # Since output_path QLineEdit was removed, we'll ask for it in start_merge
        return True

    def start_merge(self):
        """
        Validates input, collects configuration, and starts the merge worker.
        Includes robust thread handling for the MergeWorker.
        """
        if not self.is_valid():
            QMessageBox.warning(self, "Invalid Input", "Please select at least 2 images.")
            return
            
        # --- MODIFICATION: Ask for output path here ---
        # Use last_browsed_dir as the starting directory for the save dialog
        output_path, _ = QFileDialog.getSaveFileName(
            self, "Save merged image", self.last_browsed_dir, "PNG (*.png)"
        )
        if not output_path:
            self.status_label.setText("Merge cancelled.")
            self.update_run_button_state() # Reset button text if cancelled
            return
        
        # Update last_browsed_dir to the output directory
        self.last_browsed_dir = os.path.dirname(output_path)
        
        # Ensure it has the .png extension
        if not output_path.lower().endswith('.png'):
            output_path += '.png'
        # -----------------------------------------------

        config = self.collect(output_path) # Pass the selected output path
        
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

    def collect(self, output_path: str) -> Dict[str, Any]:
        """Collects all configuration inputs for the MergeWorker."""
        
        # The input paths are the currently selected paths from the gallery
        input_paths = list(self.selected_image_paths)

        # Get formats (dropdown was removed, so use all supported)
        formats = SUPPORTED_IMG_FORMATS

        return {
            "direction": self.direction.currentText(),
            "input_path": input_paths, # List of selected absolute paths
            "output_path": output_path, # Use path from dialog
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
        # This is now handled in start_merge()
        pass
