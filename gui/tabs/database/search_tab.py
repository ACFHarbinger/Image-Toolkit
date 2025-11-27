import os
import time
import platform
import subprocess

from typing import Dict, Any, List, Optional
from PySide6.QtGui import QPixmap, QAction, QCursor
from PySide6.QtCore import Qt, Signal, QPoint, Slot, QThreadPool, QEvent
from PySide6.QtWidgets import (
    QLineEdit, QPushButton, QComboBox, QProgressBar,
    QWidget, QLabel, QMessageBox, QMenu, QCheckBox,
    QFormLayout, QHBoxLayout, QVBoxLayout, 
    QGridLayout, QScrollArea, QGroupBox, 
)
from ...helpers import SearchWorker
from ...windows import ImagePreviewWindow
from ...classes import AbstractClassTwoGalleries
from ...components import OptionalField, ClickableLabel, MarqueeScrollArea
from ...styles.style import apply_shadow_effect
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS


class SearchTab(AbstractClassTwoGalleries):
    # Signal to send image to another tab: (target_tab_name, image_path)
    send_to_tab_signal = Signal(str, str)

    def __init__(self, db_tab_ref, dropdown=True):
        # Initialize Base Class (Two Galleries)
        super().__init__()
        
        self.db_tab_ref = db_tab_ref
        self.dropdown = dropdown
        
        self.open_preview_windows = [] 
        self.selected_formats = set() 
        self._db_was_connected = False 
        
        # Search specific worker
        self.current_search_worker: Optional[SearchWorker] = None
        
        # --- UI SETUP ---
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
        
        # Progress Bar (for search query, not image loading)
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
        
        # --- GALLERY AREA ---
        
        # 1. Search Results (Found Gallery)
        found_group = QGroupBox("Search Results (Ctrl+A: Select All | Ctrl+D: Deselect All)")
        found_layout = QVBoxLayout(found_group)
        
        results_header_layout = QHBoxLayout()
        self.results_count_label = QLabel("Not connected to database.")
        self.results_count_label.setStyleSheet("color: #aaa; font-style: italic;")
        results_header_layout.addWidget(self.results_count_label)
        results_header_layout.addStretch()
        
        # --- REMOVED SELECT/DESELECT BUTTONS ---
        
        found_layout.addLayout(results_header_layout)
        
        # Pagination Widget (Found)
        if hasattr(self, 'found_pagination_widget'):
            found_layout.addWidget(self.found_pagination_widget)
        
        self.results_scroll = MarqueeScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setMinimumHeight(300)
        self.results_scroll.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")
        # Connect Marquee Selection
        self.results_scroll.selection_changed.connect(self.handle_marquee_selection)

        self.results_widget = QWidget()
        self.results_widget.setStyleSheet("QWidget { background-color: #2c2f33; }")
        
        self.results_layout = QGridLayout(self.results_widget)
        self.results_layout.setSpacing(3)
        self.results_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.results_scroll.setWidget(self.results_widget)
        
        found_layout.addWidget(self.results_scroll)
        layout.addWidget(found_group, stretch=1) # Results take more space
        
        # 2. Selected Images Gallery
        selected_group = QGroupBox("Selected Images")
        selected_layout = QVBoxLayout(selected_group)
        
        # Pagination Widget (Selected)
        if hasattr(self, 'selected_pagination_widget'):
            selected_layout.addWidget(self.selected_pagination_widget)
            
        self.selected_scroll = MarqueeScrollArea()
        self.selected_scroll.setWidgetResizable(True)
        self.selected_scroll.setMinimumHeight(200)
        self.selected_scroll.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")
        
        self.selected_widget_container = QWidget()
        self.selected_widget_container.setStyleSheet("QWidget { background-color: #2c2f33; }")
        self.selected_layout_grid = QGridLayout(self.selected_widget_container)
        self.selected_layout_grid.setSpacing(3)
        self.selected_layout_grid.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.selected_scroll.setWidget(self.selected_widget_container)
        
        selected_layout.addWidget(self.selected_scroll)
        layout.addWidget(selected_group, stretch=1)
        
        # **Assign Base Class References**
        self.found_gallery_scroll = self.results_scroll
        self.found_gallery_layout = self.results_layout
        
        self.selected_gallery_scroll = self.selected_scroll
        self.selected_gallery_layout = self.selected_layout_grid
        
        self.setLayout(layout)

        # Enable widget to receive keyboard events for shortcuts
        self.setFocusPolicy(Qt.StrongFocus)

        # Update enabled state based on DB connection
        self.update_search_button_state()
        
        # Initial cleanup
        self.clear_galleries()

    # --- KEYBOARD SHORTCUTS ---
    def keyPressEvent(self, event: QEvent):
        # Check for Ctrl + A (Select All)
        if event.key() == Qt.Key.Key_A and event.modifiers() & Qt.ControlModifier:
            self.select_all_items() # Calls inherited method
            event.accept()
        # Check for Ctrl + D (Deselect All)
        elif event.key() == Qt.Key.Key_D and event.modifiers() & Qt.ControlModifier:
            self.deselect_all_items() # Calls inherited method
            event.accept()
        else:
            super().keyPressEvent(event)

    # --- IMPLEMENT ABSTRACT METHODS ---

    def create_card_widget(self, path: str, pixmap: Optional[QPixmap], is_selected: bool) -> QWidget:
        """
        Creates a ClickableLabel for the Search Tab gallery.
        """
        container = QWidget()
        container.setStyleSheet("background: transparent;") 
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0) # FIX: Corrected method name
        layout.setSpacing(1)
        
        # Use Base Class thumbnail size
        image_label = ClickableLabel(path)
        image_label.setFixedSize(self.thumbnail_size, self.thumbnail_size)
        image_label.setAlignment(Qt.AlignCenter)
        
        # Helper to get pixmap for base class caching
        container.get_pixmap = lambda: image_label.pixmap()
        # Helper to set style for base class updates
        container.set_selected_style = lambda s: self._update_card_style(image_label, s)
        
        # Connect signals
        image_label.path_clicked.connect(lambda checked, p=path: self.toggle_selection(p))
        image_label.path_double_clicked.connect(self.open_file_preview)
        image_label.path_right_clicked.connect(
            lambda pos, p=path, w=image_label: self.show_context_menu(pos, p, w)
        )
        
        if pixmap and not pixmap.isNull():
            # Scale if needed (though ImageLoaderWorker usually handles this)
            if pixmap.width() > self.thumbnail_size or pixmap.height() > self.thumbnail_size:
                pixmap = pixmap.scaled(self.thumbnail_size, self.thumbnail_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            image_label.setPixmap(pixmap)
        else:
            # Placeholder
            image_label.setText("Loading...")
            image_label.setStyleSheet("color: #888; font-size: 10px;")
        
        layout.addWidget(image_label)
        
        # Apply Initial Style
        self._update_card_style(image_label, is_selected)
        
        return container

    def update_card_pixmap(self, widget: QWidget, pixmap: Optional[QPixmap]):
        """
        Called by lazy loader when pixmap is ready or unloaded.
        'widget' here is the container returned by create_card_widget.
        """
        image_label = widget.findChild(ClickableLabel)
        if image_label:
            if pixmap and not pixmap.isNull():
                if pixmap.width() > self.thumbnail_size or pixmap.height() > self.thumbnail_size:
                    pixmap = pixmap.scaled(self.thumbnail_size, self.thumbnail_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                image_label.setPixmap(pixmap)
                image_label.setText("")
            else:
                image_label.clear()
                image_label.setText("Loading...")
            
            # Re-apply selection style logic
            # Check if this widget represents a selected path
            is_selected = image_label.path in self.selected_files
            self._update_card_style(image_label, is_selected)

    def on_selection_changed(self):
        # The base class method is sufficient here.
        pass

    def _update_card_style(self, label: QLabel, is_selected: bool):
        if is_selected:
            label.setStyleSheet("border: 3px solid #5865f2; background-color: #36393f;")
        else:
            if label.text() == "Loading...":
                label.setStyleSheet("border: 1px dashed #666; color: #888;")
            else:
                label.setStyleSheet("border: 1px solid #4f545c;")

    # --- Worker and Search Logic ---
    
    @Slot()
    def toggle_search(self):
        if self.current_search_worker:
            self.cancel_search()
        else:
            self.perform_search()

    def perform_search(self):
        db = self.db_tab_ref.db
        if not db:
            QMessageBox.warning(self, "Error", "Please connect to the database first.")
            return
            
        query_params = {
            "group_name": self.group_combo.currentText().strip() or None,
            "subgroup_name": self.subgroup_combo.currentText().strip() or None,
            "filename_pattern": self.filename_edit.text().strip() or None,
            "tags": self.get_selected_tags(),
            "input_formats": self.get_selected_formats(),
            "limit": 10000 # Increased limit since we have pagination now
        }

        self.clear_search_data()
        self.search_button.setEnabled(False)
        self.search_button.setText("Searching...")
        self.progress_bar.show()
        
        self.current_search_worker = SearchWorker(db, query_params)
        self.current_search_worker.signals.finished.connect(self.on_search_finished)
        self.current_search_worker.signals.error.connect(self.on_search_error)
        self.current_search_worker.signals.cancelled.connect(self.on_search_cancelled)
        
        # Use global threadpool for search worker
        QThreadPool.globalInstance().start(self.current_search_worker)

    @Slot(list)
    def on_search_finished(self, matching_files: list):
        self.current_search_worker = None
        self._reset_search_ui(f"Search Complete. Found {len(matching_files)} images.")
        self.display_results(matching_files)

    @Slot(str)
    def on_search_error(self, error_msg: str):
        self.current_search_worker = None
        self._reset_search_ui("Search Failed.")
        QMessageBox.critical(self, "Search Error", f"An error occurred during search:\n{error_msg}")
        self.results_count_label.setText(f"Error: {error_msg}")

    @Slot()
    def on_search_cancelled(self):
        self.current_search_worker = None
        self._reset_search_ui("Search Cancelled.")
        self.results_count_label.setText("Search cancelled by user.")

    def cancel_search(self):
        if self.current_search_worker:
            self.current_search_worker.cancel()
            self.search_button.setText("Stopping...")
            self.search_button.setEnabled(False) 

    def _reset_search_ui(self, message: str):
        self.search_button.setEnabled(True)
        self.search_button.setText("Search Database")
        self.progress_bar.hide()
        self.results_count_label.setText(message)

    def display_results(self, results: List[Dict[str, Any]]):
        """
        Extracts paths and delegates loading to AbstractClassTwoGalleries logic.
        """
        paths = [res.get('file_path') for res in results if res.get('file_path')]
        
        count = len(paths)
        self.results_count_label.setText(f"Found {count} matching image(s)")
        
        # Call Base Class method to populate the Found Gallery
        self.start_loading_thumbnails(sorted(paths))

    def clear_search_data(self):
        """Clears local selection data and widgets."""
        for window in self.open_preview_windows[:]:
            window.close()
        self.open_preview_windows.clear()
        
        # Call base class to clear galleries
        self.clear_galleries(clear_data=True)

    # --- Format & Tag Logic (Unchanged) ---
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
    
    def _get_tags_from_db(self) -> List[Dict[str, str]]:
        db = self.db_tab_ref.db
        if not db: return []
        try:
            db_tags = db.get_all_tags_with_types()
            return sorted(db_tags, key=lambda x: x['name'])
        except Exception:
            pass 
        return []

    @Slot()
    def _setup_tag_checkboxes(self):
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.tag_checkboxes = {}
        tags_data = self._get_tags_from_db()
        color_map = {
            'Artist': '#5865f2', 'Series': '#f1c40f', 
            'Character': '#2ecc71', 'General': '#e91e63', 
            'Meta': '#9b59b6', '': '#c7c7c7', None: '#c7c7c7'
        }
        columns = 8
        for i, tag_data in enumerate(tags_data):
            tag_name = tag_data['name']
            tag_type = tag_data['type'] if tag_data['type'] else '' 
            checkbox = QCheckBox(tag_name.replace("_", " ").title())
            text_color = color_map.get(tag_type, color_map[''])
            checkbox.setStyleSheet(f"QCheckBox {{ color: {text_color}; }}")
            self.tag_checkboxes[tag_name] = checkbox
            self.tags_layout.addWidget(checkbox, i // columns, i % columns)

    def update_search_button_state(self, connected: bool = None):
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
        
        if db_connected and not self._db_was_connected:
            self._setup_tag_checkboxes()
        self._db_was_connected = db_connected

    def get_selected_tags(self) -> List[str]:
        return [tag for tag, cb in self.tag_checkboxes.items() if cb.isChecked()]

    def get_selected_formats(self) -> Optional[List[str]]:
        if self.dropdown:
            if not self.selected_formats:
                return None
            return list(self.selected_formats)
        else:
            formats_str = self.input_formats_edit.text().strip()
            if not formats_str:
                return None
            return [f.strip().lstrip('.').lower() for f in formats_str.replace(',', ' ').split() if f.strip()]

    # --- Selection Logic Overrides/Helpers ---

    @Slot()
    def select_all_results(self):
        # Calls the inherited select_all_items which handles state update and UI refresh
        self.select_all_items()
    
    @Slot()
    def deselect_all_results(self):
        # Calls the inherited deselect_all_items which handles state update and UI refresh
        self.deselect_all_items()

    def _update_found_card_styles(self):
        """Helper to re-evaluate and apply style to all currently loaded/visible found cards."""
        for path, widget in self.path_to_label_map.items():
            if widget:
                # Find the ClickableLabel to extract the path and the internal QLabel for styling
                image_label = widget.findChild(QLabel)
                if image_label:
                    is_selected = path in self.selected_files
                    self._update_card_style(image_label, is_selected)
    
    # --- TAB COMMUNICATION & FILE ACTIONS ---

    def _get_target_selection(self, single_path=None):
        # Use self.selected_files instead of self.selected_paths
        paths = list(self.selected_files)
        if single_path:
            if single_path in paths:
                return sorted(paths)
            else:
                return [single_path]
        return sorted(paths)

    def send_selection_to_scan_tab(self):
        if not self.selected_files:
            QMessageBox.information(self, "No Selection", "Please select at least one image to open in the Scan Tab.")
            return
        if not self.db_tab_ref or not hasattr(self.db_tab_ref, 'scan_tab_ref') or not self.db_tab_ref.scan_tab_ref:
            QMessageBox.warning(self, "Configuration Error", "Scan Metadata Tab reference not found.")
            return
        scan_tab = self.db_tab_ref.scan_tab_ref
        sorted_selection = sorted(list(self.selected_files))
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
        delete_tab.clear_galleries()
        delete_tab.duplicate_results = {"imported": paths} # Adapt data structure for delete tab
        delete_tab.status_label.setText(f"Imported {len(paths)} files from Search.")
        delete_tab.start_loading_thumbnails(paths)
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

    def handle_remove_from_db(self, file_path: str):
        db = self.db_tab_ref.db
        if not db:
            QMessageBox.warning(self, "Database Error", "Please connect to the database first.")
            return
        filename = os.path.basename(file_path)
        reply = QMessageBox.question(
            self, "Confirm Database Removal",
            f"Are you sure you want to remove the entry for **{filename}** from the database?\n\nThe physical image file WILL NOT be deleted.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.No: return
        try:
            image_data = db.get_image_by_path(file_path)
            image_id = image_data.get('id') if image_data else None
            if image_id is not None:
                db.delete_image(image_id) 
                if file_path in self.found_files:
                    self.found_files.remove(file_path)
                if file_path in self.selected_files:
                    self.selected_files.remove(file_path)
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
            self, "Confirm Deletion",
            f"Are you sure you want to PERMANENTLY delete the file:\n\n**{filename}**\n\nThis action cannot be undone!",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.No: return
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
            
            if file_path in self.found_files:
                self.found_files.remove(file_path)
            if file_path in self.selected_files:
                self.selected_files.remove(file_path)
            
            self.perform_search() 
            QMessageBox.information(self, "Success", f"File deleted: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Deletion Failed", f"Could not delete the file:\n{e}")

    def show_image_properties(self, file_path: str):
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Invalid Path", f"File not found at path:\n{file_path}")
            return
        try:
            stats = os.stat(file_path)
            last_modified = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stats.st_mtime))
            def format_size(size_bytes):
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if size_bytes < 1024.0: return f"{size_bytes:.2f} {unit}"
                    size_bytes /= 1024.0
                return f"{size_bytes:.2f} TB"
            pixmap = QPixmap(file_path)
            dimensions = f"{pixmap.width()} x {pixmap.height()} pixels" if not pixmap.isNull() else "N/A"
            properties_text = (
                f"**Filename:** {os.path.basename(file_path)}\n"
                f"**Full Path:** {file_path}\n"
                f"**Dimensions:** {dimensions}\n"
                f"**Size:** {format_size(stats.st_size)}\n"
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
        
        is_selected = file_path in self.selected_files
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
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Invalid Path", f"File not found at path:\n{file_path}")
            return
        for window in self.open_preview_windows:
            if window.image_path == file_path:
                window.activateWindow() 
                return
        
        # Use self.found_files from Base class
        if self.found_files:
            try:
                start_index = self.found_files.index(file_path)
                all_paths = self.found_files
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
            if system == "Windows": os.startfile(directory)
            elif system == "Darwin": subprocess.run(['open', directory])
            else: subprocess.run(['xdg-open', directory])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open directory:\n{e}")
    
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