import os
import platform
import subprocess
import time

from typing import Dict, Any, List, Optional
from PySide6.QtGui import QPixmap, QAction, QCursor
from PySide6.QtCore import Qt, Signal, QPoint, QThreadPool, Slot
from PySide6.QtWidgets import (
    QLineEdit, QPushButton, QComboBox, QProgressBar,
    QWidget, QLabel, QMessageBox, QMenu, QCheckBox,
    QFormLayout, QHBoxLayout, QVBoxLayout, 
    QGridLayout, QScrollArea, QGroupBox, 
)
from .base_tab import BaseTab
from ..helpers import SearchWorker
from ..windows import ImagePreviewWindow
from ..components import OptionalField, ClickableLabel, MarqueeScrollArea
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS
from ..styles.style import apply_shadow_effect


class SearchTab(BaseTab):
    # Signal to send image to another tab: (target_tab_name, image_path)
    send_to_tab_signal = Signal(str, str)

    def __init__(self, db_tab_ref, dropdown=True):
        super().__init__()
        self.db_tab_ref = db_tab_ref
        self.dropdown = dropdown
        
        self.result_widgets = []
        self.open_preview_windows = [] 
        self.selected_formats = set() 
        self.current_result_paths = [] 
        self._db_was_connected = False 
        
        self.threadpool = QThreadPool.globalInstance()
        self.current_worker: Optional[SearchWorker] = None
        
        self.selected_paths = set()
        self.path_to_widget_map = {} 

        self.thumbnail_size = 150
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width
        
        layout = QVBoxLayout(self)
        
        # --- Search Criteria ---
        search_group = QGroupBox("Search Database")
        form_layout = QFormLayout(search_group)
        form_layout.setContentsMargins(10, 20, 10, 10)
        
        self.group_combo = QComboBox()
        self.group_combo.setEditable(True)
        self.group_combo.setPlaceholderText("e.g., Summer Trip (Optional)")
        form_layout.addRow("Group name:", self.group_combo)
        
        self.subgroup_combo = QComboBox()
        self.subgroup_combo.setEditable(True)
        self.subgroup_combo.setPlaceholderText("e.g., Beach Photos (Optional)")
        form_layout.addRow("Subgroup name:", self.subgroup_combo)
        
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("e.g., *.png, img_001, etc (Optional)")
        self.filename_field = OptionalField("Filename pattern", self.filename_edit, start_open=False)
        form_layout.addRow(self.filename_field)
        
        # --- Input formats ---
        if self.dropdown:
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
            form_layout.addRow(self.formats_field)
        else:
            self.selected_formats = None
            self.input_formats_edit = QLineEdit()
            self.input_formats_edit.setPlaceholderText("e.g. jpg png gif (optional)")
            form_layout.addRow("Input formats:", self.input_formats_edit)

        # --- Tags (Checkbox Grid) ---
        tags_scroll = QScrollArea()
        tags_scroll.setMinimumHeight(200) 
        tags_scroll.setWidgetResizable(True)
        self.tags_widget = QWidget()
        self.tags_layout = QGridLayout(self.tags_widget)
        self.tags_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        tags_scroll.setWidget(self.tags_widget)
        
        self.tag_checkboxes = {}

        # --- Refresh Tags Button ---
        self.btn_refresh_tags = QPushButton("Refresh Tags")
        self.btn_refresh_tags.setFixedWidth(120)
        apply_shadow_effect(self.btn_refresh_tags, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_refresh_tags.clicked.connect(self._setup_tag_checkboxes)
        
        # Add button row before the tags list
        form_layout.addRow("", self.btn_refresh_tags)
        form_layout.addRow("Tags:", tags_scroll)
        
        layout.addWidget(search_group)
        
        # Search button
        self.search_button = QPushButton("Search Database")
        self.search_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white; font-weight: bold; font-size: 16px;
                padding: 14px; border-radius: 10px; min-height: 44px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #764ba2, stop:1 #667eea); }
            QPushButton:disabled { background: #4f545c; color: #a0a0a0; }
            QPushButton:pressed { background: #5a67d8; }
        """)
        apply_shadow_effect(self.search_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.search_button.clicked.connect(self.toggle_search)
        layout.addWidget(self.search_button)
        
        # --- NEW: Progress Bar (Indeterminate) ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0) # Indeterminate mode
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        # Connect Enter key to search
        self.group_combo.lineEdit().returnPressed.connect(self.toggle_search)
        self.subgroup_combo.lineEdit().returnPressed.connect(self.toggle_search)
        self.filename_edit.returnPressed.connect(self.toggle_search)
        if not self.dropdown:
            self.input_formats_edit.returnPressed.connect(self.toggle_search)
        
        # Results area
        results_header_layout = QHBoxLayout()
        results_label = QLabel("Search Results:")
        results_label.setStyleSheet("font-weight: bold; font-size: 12px; margin-top: 10px;")
        results_header_layout.addWidget(results_label)
        
        # --- NEW: Selection Actions ---
        results_header_layout.addStretch()
        
        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.setFixedWidth(120)
        self.btn_select_all.setMinimumHeight(30)
        apply_shadow_effect(self.btn_select_all, color_hex="#000000", radius=4, x_offset=0, y_offset=2)
        self.btn_select_all.clicked.connect(self.select_all_results)
        
        self.btn_deselect_all = QPushButton("Deselect All")
        self.btn_deselect_all.setFixedWidth(120)
        self.btn_deselect_all.setMinimumHeight(30)
        apply_shadow_effect(self.btn_deselect_all, color_hex="#000000", radius=4, x_offset=0, y_offset=2)
        self.btn_deselect_all.clicked.connect(self.deselect_all_results)

        results_header_layout.addWidget(self.btn_select_all)
        results_header_layout.addWidget(self.btn_deselect_all)
        
        layout.addLayout(results_header_layout)
        
        self.results_count_label = QLabel("Not connected to database.")
        self.results_count_label.setStyleSheet("color: #aaa; font-style: italic;")
        layout.addWidget(self.results_count_label)
        
        # --- MODIFIED: Use MarqueeScrollArea ---
        self.results_scroll = MarqueeScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setMinimumHeight(300)
        
        # Matching styles to WallpaperTab
        self.results_scroll.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")
        
        # --- Connect Marquee Selection ---
        self.results_scroll.selection_changed.connect(self.handle_marquee_selection)
        # ---------------------------------

        self.results_widget = QWidget()
        self.results_widget.setStyleSheet("QWidget { background-color: #2c2f33; }")
        
        self.results_layout = QGridLayout(self.results_widget)
        self.results_layout.setSpacing(3)
        self.results_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.results_scroll.setWidget(self.results_widget)
        
        layout.addWidget(self.results_scroll)
        
        self.setLayout(layout)

        # Update enabled state based on DB connection
        self.update_search_button_state()

    # --- Worker and Search Logic ---
    
    @Slot()
    def toggle_search(self):
        """Switches between starting and cancelling the search."""
        if self.current_worker:
            self.cancel_search()
        else:
            self.perform_search()

    def perform_search(self):
        """
        Gathers parameters and starts the asynchronous search worker.
        """
        db = self.db_tab_ref.db
        if not db:
            QMessageBox.warning(self, "Error", "Please connect to the database first.")
            return
            
        # Get search criteria
        query_params = {
            "group_name": self.group_combo.currentText().strip() or None,
            "subgroup_name": self.subgroup_combo.currentText().strip() or None,
            "filename_pattern": self.filename_edit.text().strip() or None,
            "tags": self.get_selected_tags(),
            "input_formats": self.get_selected_formats(),
            "limit": 1000
        }

        # Clear previous UI state and results
        self.clear_results()
        self.search_button.setEnabled(False)
        self.search_button.setText("Searching...")
        self.progress_bar.show()
        
        # Create and start worker
        self.current_worker = SearchWorker(db, query_params)
        self.current_worker.signals.finished.connect(self.on_search_finished)
        self.current_worker.signals.error.connect(self.on_search_error)
        self.current_worker.signals.cancelled.connect(self.on_search_cancelled)
        
        self.threadpool.start(self.current_worker)

    @Slot(list)
    def on_search_finished(self, matching_files: list):
        """Receives results from the worker and updates the UI."""
        self.current_worker = None
        self._reset_search_ui(f"Search Complete. Found {len(matching_files)} images.")
        self.display_results(matching_files)

    @Slot(str)
    def on_search_error(self, error_msg: str):
        """Handles errors from the worker and updates the UI."""
        self.current_worker = None
        self._reset_search_ui("Search Failed.")
        QMessageBox.critical(self, "Search Error", f"An error occurred during search:\n{error_msg}")
        self.results_count_label.setText(f"Error: {error_msg}")

    @Slot()
    def on_search_cancelled(self):
        """Handles manual cancellation."""
        self.current_worker = None
        self._reset_search_ui("Search Cancelled.")
        self.results_count_label.setText("Search cancelled by user.")

    def cancel_search(self):
        """Requests cancellation of the current search worker."""
        if self.current_worker:
            self.current_worker.cancel()
            self.search_button.setText("Stopping...")
            self.search_button.setEnabled(False) 

    def _reset_search_ui(self, message: str):
        """Resets the search button and hides the progress bar."""
        self.search_button.setEnabled(True)
        self.search_button.setText("Search Database")
        self.progress_bar.hide()
        self.results_count_label.setText(message)

    # --- Format Selection Methods ---
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
    
    # --- DB Tags Helper Methods ---

    def _get_tags_from_db(self) -> List[Dict[str, str]]:
        """
        Fetches all tags and their types from the connected database.
        Returns a list of dictionaries [{'name': ..., 'type': ...}].
        """
        db = self.db_tab_ref.db
        if not db: 
            return []
            
        try:
            db_tags = db.get_all_tags_with_types()
            # Sort by name
            return sorted(db_tags, key=lambda x: x['name'])
        except Exception:
            pass 
        return []

    @Slot()
    def _setup_tag_checkboxes(self):
        """
        Clears and repopulates the tags grid layout with checkboxes,
        applying color based on tag type.
        """
        # Clear existing checkboxes
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.tag_checkboxes = {}
        
        tags_data = self._get_tags_from_db()

        # Define color scheme for tag types (using dark mode friendly colors)
        color_map = {
            'Artist': '#5865f2',    # Bright blue/purple
            'Series': '#f1c40f',    # Yellow/Gold
            'Character': '#2ecc71', # Emerald green
            'General': '#e91e63',   # Pink/Magenta
            'Meta': '#9b59b6',      # Amethyst purple
            '': '#c7c7c7',          # Default grey (for untyped tags)
            None: '#c7c7c7'         # Default grey
        }
        
        columns = 8
        
        for i, tag_data in enumerate(tags_data):
            tag_name = tag_data['name']
            # Normalize type: use empty string if None
            tag_type = tag_data['type'] if tag_data['type'] else '' 
            
            checkbox = QCheckBox(tag_name.replace("_", " ").title())
            
            # Determine color and apply styling
            text_color = color_map.get(tag_type, color_map[''])
            
            # Apply styling. Note: QCheckBox text color is set via 'color' property
            checkbox.setStyleSheet(f"QCheckBox {{ color: {text_color}; }}")
            
            self.tag_checkboxes[tag_name] = checkbox
            self.tags_layout.addWidget(checkbox, i // columns, i % columns)
            
    # --- UI and Selection methods ---

    def update_search_button_state(self, connected: bool = None):
        """
        Disables search button if DB is not connected.
        Triggers tag refresh if DB connection is newly established.
        """
        if connected is None:
            db_connected = self.db_tab_ref.db is not None
        else:
            db_connected = connected
            
        self.search_button.setEnabled(db_connected)
        
        if not db_connected:
            self.results_count_label.setText("Not connected to database.")
        else:
            if self.results_count_label.text() == "Not connected to database.":
                self.results_count_label.setText("Ready to search.")
        
        # Refresh tags if we just connected
        if db_connected and not self._db_was_connected:
            self._setup_tag_checkboxes()
        
        self._db_was_connected = db_connected

    def get_selected_tags(self) -> List[str]:
        """Returns a list of tags selected via checkboxes."""
        return [tag for tag, cb in self.tag_checkboxes.items() if cb.isChecked()]

    def get_selected_formats(self) -> Optional[List[str]]:
        """Gets the list of selected formats."""
        if self.dropdown:
            if not self.selected_formats:
                return None
            return list(self.selected_formats)
        else:
            formats_str = self.input_formats_edit.text().strip()
            if not formats_str:
                return None
            return [f.strip().lstrip('.').lower() for f in formats_str.replace(',', ' ').split() if f.strip()]

    @Slot()
    def calculate_columns(self) -> int:
        """
        Calculates the number of columns based on widget width, 
        matching logic from WallpaperTab.
        """
        widget_width = self.results_widget.width()
        if widget_width <= 0:
            try:
                widget_width = self.results_scroll.width()
            except AttributeError:
                 widget_width = 800
        
        if widget_width <= 0:
            return 4 
        
        columns = widget_width // self.approx_item_width
        return max(1, columns)

    # --- Selection Logic Implementations ---

    @Slot()
    def select_all_results(self):
        """Selects all currently displayed results."""
        for path in self.current_result_paths:
            if path not in self.selected_paths:
                self.selected_paths.add(path)
                self._update_widget_style(path)
    
    @Slot()
    def deselect_all_results(self):
        """Deselects all currently displayed results."""
        self.selected_paths.clear()
        for path in self.current_result_paths:
            self._update_widget_style(path)

    def toggle_selection(self, file_path: str):
        """Toggles the selection state of a specific image."""
        if file_path in self.selected_paths:
            self.selected_paths.remove(file_path)
        else:
            self.selected_paths.add(file_path)
        self._update_widget_style(file_path)

    @Slot(set, bool)
    def handle_marquee_selection(self, paths_from_marquee: set, is_ctrl_pressed: bool):
        """Handles selection updates from the marquee tool."""
        # Check for currently visible paths to avoid updating hidden or old items
        visible_paths = set(self.current_result_paths)
        
        # Filter paths_from_marquee to only include currently visible results
        valid_marquee_paths = paths_from_marquee.intersection(visible_paths)
        
        paths_to_update = self.selected_paths.union(valid_marquee_paths)
        
        if not is_ctrl_pressed:
            # Exclusive selection: Start with the valid marquee selection
            self.selected_paths = valid_marquee_paths
        else:
            # Additive selection: Add the valid marquee paths to the existing selection
            self.selected_paths.update(valid_marquee_paths)

        # Update styles for all affected items
        for path in paths_to_update:
            self._update_widget_style(path)
            
    def _update_widget_style(self, file_path: str):
        """Updates the border style of the widget based on selection."""
        widget = self.path_to_widget_map.get(file_path)
        if widget:
            if file_path in self.selected_paths:
                # Selected Style: Blue Border
                widget.setStyleSheet("border: 3px solid #5865f2; background-color: #36393f;")
            else:
                # Default Style: Grey Border
                widget.setStyleSheet("border: 1px solid #4f545c;")

    # --- TAB COMMUNICATION METHODS (remain unchanged) ---

    def _get_target_selection(self, single_path=None):
        """
        Returns the list of paths to process.
        Logic:
        1. If multiple items are selected, return ALL selected paths.
        2. If NO items are selected, but single_path is provided (right-click on non-selected item), return [single_path].
        3. If single_path is provided AND it is inside the current selection, return ALL selected paths (bulk action).
        """
        paths = list(self.selected_paths)
        
        if single_path:
            if single_path in self.selected_paths:
                # Right-clicked on an item that is part of the selection -> Process whole selection
                return sorted(paths)
            else:
                # Right-clicked on an item NOT in selection -> Process only that item
                if not paths:
                    return [single_path]
                else:
                    # Ambiguous case: User has selection but right-clicked outside it.
                    # Here we return ONLY the right-clicked one to be safe/explicit.
                    return [single_path]
        
        return sorted(paths)

    def send_selection_to_scan_tab(self):
        if not self.selected_paths:
            QMessageBox.information(self, "No Selection", "Please select at least one image to open in the Scan Tab.")
            return
        if not self.db_tab_ref or not hasattr(self.db_tab_ref, 'scan_tab_ref') or not self.db_tab_ref.scan_tab_ref:
            QMessageBox.warning(self, "Configuration Error", "Scan Metadata Tab reference not found.")
            return
        scan_tab = self.db_tab_ref.scan_tab_ref
        sorted_selection = sorted(list(self.selected_paths))
        scan_tab.process_scan_results(sorted_selection)
        if hasattr(scan_tab, 'view_db_only_button'):
            scan_tab.view_db_only_button.setChecked(False)
        QMessageBox.information(self, "Images Sent", f"Successfully sent {len(sorted_selection)} images to the Scan Metadata Tab.")

    def send_selection_to_merge_tab(self, single_path=None):
        paths = self._get_target_selection(single_path)
        if not paths:
             QMessageBox.information(self, "No Selection", "No images selected.")
             return
        if not hasattr(self.db_tab_ref, 'merge_tab_ref') or not self.db_tab_ref.merge_tab_ref:
            QMessageBox.warning(self, "Error", "Merge Tab reference not found.")
            return
        self.db_tab_ref.merge_tab_ref.display_scan_results(paths)
        QMessageBox.information(self, "Images Sent", f"Sent {len(paths)} images to the Merge Tab.")

    def send_selection_to_delete_tab(self, single_path=None):
        paths = self._get_target_selection(single_path)
        if not paths:
             QMessageBox.information(self, "No Selection", "No images selected.")
             return
        if not hasattr(self.db_tab_ref, 'delete_tab_ref') or not self.db_tab_ref.delete_tab_ref:
            QMessageBox.warning(self, "Error", "Delete Tab reference not found.")
            return
        delete_tab = self.db_tab_ref.delete_tab_ref
        delete_tab.clear_gallery()
        delete_tab.duplicate_path_list = paths
        delete_tab.status_label.setText(f"Imported {len(paths)} files from Search.")
        delete_tab.gallery_scroll.setVisible(True)
        delete_tab.selected_scroll.setVisible(True)
        delete_tab.load_thumbnails(paths)
        QMessageBox.information(self, "Images Sent", f"Sent {len(paths)} images to the Delete Tab.")

    def send_selection_to_wallpaper_tab(self, single_path=None):
        paths = self._get_target_selection(single_path)
        if not paths:
             QMessageBox.information(self, "No Selection", "No images selected.")
             return
        if not hasattr(self.db_tab_ref, 'wallpaper_tab_ref') or not self.db_tab_ref.wallpaper_tab_ref:
             QMessageBox.warning(self, "Error", "Wallpaper Tab reference not found.")
             return
        self.db_tab_ref.wallpaper_tab_ref.display_scan_results(paths)
        QMessageBox.information(self, "Images Sent", f"Sent {len(paths)} images to the Wallpaper Tab.")

    def display_results(self, results: List[Dict[str, Any]]):
        """Display the search results (dictionaries) as thumbnails"""
        count = len(results)
        self.results_count_label.setText(f"Found {count} matching image(s)")
        self.selected_paths.clear()
        self.path_to_widget_map.clear()
        self.current_result_paths = [res.get('file_path') for res in results if res.get('file_path')]
        if count == 0:
            return
        columns = self.calculate_columns()
        for i, img_data in enumerate(results):
            row = i // columns
            col = i % columns
            file_path = img_data.get('file_path')
            result_container = QWidget()
            result_container.setStyleSheet("background: transparent;") 
            result_layout = QVBoxLayout(result_container)
            result_layout.setContentsMargins(0, 0, 0, 0)
            result_layout.setSpacing(1)
            image_label = ClickableLabel(file_path)
            image_label.setFixedSize(self.thumbnail_size, self.thumbnail_size)
            image_label.setAlignment(Qt.AlignCenter)
            image_label.setStyleSheet("border: 1px solid #4f545c;")
            image_label.path_clicked.connect(lambda checked, p=file_path: self.toggle_selection(p))
            image_label.path_double_clicked.connect(self.open_file_preview)
            image_label.path_right_clicked.connect(
                lambda pos, p=file_path, w=image_label: self.show_context_menu(pos, p, w)
            )
            self.path_to_widget_map[file_path] = image_label
            pixmap = QPixmap(str(file_path))
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    self.thumbnail_size, self.thumbnail_size, 
                    Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                image_label.setPixmap(scaled_pixmap)
            else:
                image_label.setText("Not Found")
                image_label.setStyleSheet("border: 1px solid #e74c3c; background-color: #4f545c; font-size: 8px;")
            result_layout.addWidget(image_label)
            self.results_layout.addWidget(result_container, row, col)
            self.result_widgets.append(result_container)

    def handle_remove_from_db(self, file_path: str):
        db = self.db_tab_ref.db
        if not db:
            QMessageBox.warning(self, "Database Error", "Please connect to the database first.")
            return
        filename = os.path.basename(file_path)
        reply = QMessageBox.question(
            self, 
            "Confirm Database Removal",
            f"Are you sure you want to remove the entry for **{filename}** from the database?\n\nThe physical image file WILL NOT be deleted.",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
        try:
            image_data = db.get_image_by_path(file_path)
            image_id = image_data.get('id') if image_data else None
            if image_id is not None:
                db.delete_image(image_id) 
                if file_path in self.current_result_paths:
                    self.current_result_paths.remove(file_path)
                if file_path in self.selected_paths:
                    self.selected_paths.remove(file_path)
                self.perform_search() 
                QMessageBox.information(self, "Success", f"Database entry for **{filename}** removed successfully.")
            else:
                QMessageBox.warning(self, "Warning", f"No database entry found for file: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Removal Failed", f"Could not remove database entry:\n{e}")

    def handle_delete_image(self, file_path: str):
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Delete Error", "File not found or path is invalid.")
            return
        db = self.db_tab_ref.db
        if not db:
            QMessageBox.warning(self, "Delete Error", "Database connection required for file and DB deletion.")
            return
        filename = os.path.basename(file_path)
        reply = QMessageBox.question(
            self, 
            "Confirm Deletion",
            f"Are you sure you want to PERMANENTLY delete the file:\n\n**{filename}**\n\nThis action cannot be undone!",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
        try:
            image_data = db.get_image_by_path(file_path)
            image_id = image_data.get('id') if image_data else None
            for window in self.open_preview_windows[:]:
                if window.image_path == file_path:
                    window.close()
                    break
            os.remove(file_path)
            if image_id is not None:
                db.delete_image(image_id) 
            else:
                print(f"Warning: Image file deleted, but no entry found in database for path: {file_path}")
            if file_path in self.current_result_paths:
                self.current_result_paths.remove(file_path)
            if file_path in self.selected_paths:
                self.selected_paths.remove(file_path)
            self.perform_search() 
            QMessageBox.information(self, "Success", f"File and associated database entry deleted successfully: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Deletion Failed", f"Could not delete the file:\n{e}")

    def show_image_properties(self, file_path: str):
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Invalid Path", f"File not found at path:\n{file_path}")
            return
        try:
            stats = os.stat(file_path)
            file_size_bytes = stats.st_size
            last_modified = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stats.st_mtime))
            def format_size(size_bytes):
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if size_bytes < 1024.0:
                        return f"{size_bytes:.2f} {unit}"
                    size_bytes /= 1024.0
                return f"{size_bytes:.2f} TB"
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                dimensions = f"{pixmap.width()} x {pixmap.height()} pixels"
            else:
                dimensions = "N/A (Could not load image)"
            properties_text = (
                f"**Filename:** {os.path.basename(file_path)}\n"
                f"**Full Path:** {file_path}\n"
                f"**Dimensions:** {dimensions}\n"
                f"**Size:** {format_size(stats.st_size)} ({file_size_bytes} bytes)\n"
                f"**Last Modified:** {last_modified}\n"
            )
            msg = QMessageBox(self)
            msg.setWindowTitle("Image Properties")
            msg.setText(properties_text)
            msg.setIcon(QMessageBox.Information)
            msg.setStyleSheet("QLabel{min-width: 400px;}") 
            msg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to retrieve properties: {e}")

    def show_context_menu(self, pos: QPoint, file_path: str, widget: QWidget):
        menu = QMenu(self)
        properties_action = QAction("🖼️ Show Image Properties", self)
        properties_action.triggered.connect(lambda: self.show_image_properties(file_path))
        menu.addAction(properties_action)
        preview_action = QAction("👁️ Open Full Preview", self)
        preview_action.triggered.connect(lambda: self.open_file_preview(file_path))
        menu.addAction(preview_action)
        dir_action = QAction("📂 Open File Location", self)
        dir_action.triggered.connect(lambda: self.open_file_directory(file_path))
        menu.addAction(dir_action)
        menu.addSeparator()
        remove_db_action = QAction("❌ Remove from Database Only", self)
        remove_db_action.triggered.connect(lambda: self.handle_remove_from_db(file_path))
        menu.addAction(remove_db_action)
        delete_action = QAction("🗑️ Delete Image File (Permanent)", self)
        delete_action.triggered.connect(lambda: self.handle_delete_image(file_path))
        menu.addAction(delete_action)
        menu.addSeparator()
        send_menu = menu.addMenu("Send To...")
        merge_action = QAction("Merge Tab", self)
        merge_action.triggered.connect(lambda: self.send_selection_to_merge_tab(file_path))
        send_menu.addAction(merge_action)
        wallpaper_action = QAction("Wallpaper Tab", self)
        wallpaper_action.triggered.connect(lambda: self.send_selection_to_wallpaper_tab(file_path))
        send_menu.addAction(wallpaper_action)
        scan_action = QAction("Scan Metadata Tab", self)
        scan_action.triggered.connect(lambda: self.send_selection_to_scan_tab())
        send_menu.addAction(scan_action)
        delete_tab_action = QAction("Delete Tab", self)
        delete_tab_action.triggered.connect(lambda: self.send_selection_to_delete_tab(file_path))
        send_menu.addAction(delete_tab_action)
        menu.addSeparator()
        is_selected = file_path in self.selected_paths
        toggle_text = "Deselect" if is_selected else "Select"
        toggle_action = QAction(toggle_text, self)
        toggle_action.triggered.connect(lambda: self.toggle_selection(file_path))
        menu.addAction(toggle_action)
        menu.exec(QCursor.pos())

    def remove_preview_window(self, window_instance: ImagePreviewWindow):
        try:
            if window_instance in self.open_preview_windows:
                self.open_preview_windows.remove(window_instance)
        except (RuntimeError, ValueError):
            pass

    def open_file_preview(self, file_path: str):
        if not file_path or not os.path.exists(file_path) or not os.path.isfile(file_path):
            QMessageBox.warning(self, "Invalid Path", f"File not found at path:\n{file_path}")
            return
        for window in self.open_preview_windows:
            if window.image_path == file_path:
                window.activateWindow() 
                return
        if self.current_result_paths:
            try:
                start_index = self.current_result_paths.index(file_path)
                all_paths = self.current_result_paths
            except ValueError:
                start_index = 0
                all_paths = [file_path]
        else:
            start_index = 0
            all_paths = [file_path]
        preview = ImagePreviewWindow(
            image_path=file_path, 
            db_tab_ref=self.db_tab_ref, 
            parent=self,
            all_paths=all_paths,
            start_index=start_index
        ) 
        preview.finished.connect(lambda result, p=preview: self.remove_preview_window(p))
        preview.show() 
        self.open_preview_windows.append(preview)

    def open_file_directory(self, file_path: str):
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Invalid Path", f"File not found at path:\n{file_path}")
            return
        directory = os.path.dirname(file_path)
        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(directory)
            elif system == "Darwin":
                subprocess.run(['open', directory])
            else:
                subprocess.run(['xdg-open', directory])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open directory:\n{e}")
    
    def clear_results(self):
        for widget in self.result_widgets:
            widget.deleteLater()
        self.result_widgets.clear()
        self.current_result_paths = []
        self.selected_paths.clear()
        self.path_to_widget_map.clear()
        for window in self.open_preview_windows[:]:
            window.close()
        self.open_preview_windows.clear()
    
    def collect(self) -> Dict[str, Any]:
        return {
            "group_name": self.group_combo.currentText().strip() or None,
            "subgroup_name": self.subgroup_combo.currentText().strip() or None, 
            "filename_pattern": self.filename_edit.text().strip() or None,
            "input_formats": self.get_selected_formats() or None,
            "tags": self.get_selected_tags() or None
        }

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "group_name": "",
            "subgroup_name": "",
            "filename_pattern": "",
            "input_formats": [],
            "tags": []
        }

    def set_config(self, config: Dict[str, Any]):
        try:
            self.group_combo.setCurrentText(config.get("group_name", ""))
            self.subgroup_combo.setCurrentText(config.get("subgroup_name", ""))
            self.filename_edit.setText(config.get("filename_pattern", ""))
            self._setup_tag_checkboxes()
            selected_tags = set(config.get("tags", []))
            for tag, checkbox in self.tag_checkboxes.items():
                checkbox.setChecked(tag in selected_tags)
            formats = config.get("input_formats", [])
            if self.dropdown:
                self.remove_all_formats()
                for fmt in formats:
                    if fmt in self.format_buttons:
                        self.format_buttons[fmt].setChecked(True)
                        self.toggle_format(fmt, True)
            else:
                self.input_formats_edit.setText(" ".join(formats))
            QMessageBox.information(self, "Config Loaded", "Configuration applied successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Config Error", f"Failed to apply configuration:\n{e}")
