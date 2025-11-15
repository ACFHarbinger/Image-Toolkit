import os
import platform
import subprocess

from typing import Dict, Any, List, Optional
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFormLayout, QHBoxLayout, QVBoxLayout, QGridLayout,
    QScrollArea, QGroupBox, QApplication, 
    QLineEdit, QPushButton, QComboBox,
    QWidget, QLabel, QMessageBox
)
from .base_tab import BaseTab
from ..components import OptionalField
from ..components import ImagePreviewWindow
from ..styles.style import apply_shadow_effect
from ...utils.definitions import SUPPORTED_IMG_FORMATS


class SearchTab(BaseTab):
    def __init__(self, db_tab_ref, dropdown=True):
        super().__init__()
        # Reference to the main DatabaseTab to access the self.db connection object
        self.db_tab_ref = db_tab_ref
        self.dropdown = dropdown
        self.result_widgets = []
        self.open_preview_windows = [] # Track open preview windows
        self.selected_formats = set() # NEW
        
        layout = QVBoxLayout(self)
        
        # --- Search Criteria ---
        search_group = QGroupBox("Search Database")
        
        form_layout = QFormLayout(search_group)
        form_layout.setContentsMargins(10, 20, 10, 10)
        
        # Group name
        self.group_combo = QComboBox()
        self.group_combo.setEditable(True)
        self.group_combo.setPlaceholderText("e.g., Summer Trip (Optional)")
        form_layout.addRow("Group name:", self.group_combo)
        
        # Subgroup Name
        self.subgroup_combo = QComboBox()
        self.subgroup_combo.setEditable(True)
        self.subgroup_combo.setPlaceholderText("e.g., Beach Photos (Optional)")
        form_layout.addRow("Subgroup name:", self.subgroup_combo)
        
        # Filename
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("e.g., *.png, img_001, etc (Optional)")
        self.filename_field = OptionalField("Filename pattern", self.filename_edit, start_open=False)
        form_layout.addRow(self.filename_field)
        
        # --- NEW: Input formats (copied from Convert.py) ---
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
        # --- END NEW ---

        # Tags
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("tag1, tag2, tag3... (comma-separated, optional)")
        form_layout.addRow("Tags:", self.tags_edit)
        
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
        self.search_button.clicked.connect(self.perform_search)
        layout.addWidget(self.search_button)
        
        # Connect Enter key to search
        self.group_combo.lineEdit().returnPressed.connect(self.search_button.click)
        self.subgroup_combo.lineEdit().returnPressed.connect(self.search_button.click)
        self.filename_edit.returnPressed.connect(self.search_button.click)
        self.tags_edit.returnPressed.connect(self.search_button.click)
        if not self.dropdown:
            self.input_formats_edit.returnPressed.connect(self.search_button.click)
        
        # Results area
        results_label = QLabel("Search Results:")
        results_label.setStyleSheet("font-weight: bold; font-size: 12px; margin-top: 10px;")
        layout.addWidget(results_label)
        
        self.results_count_label = QLabel("Not connected to database.")
        self.results_count_label.setStyleSheet("color: #aaa; font-style: italic;")
        layout.addWidget(self.results_count_label)
        
        # Scrollable area for image results
        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setMinimumHeight(300)
        
        self.results_widget = QWidget()
        self.results_layout = QGridLayout(self.results_widget)
        self.results_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.results_scroll.setWidget(self.results_widget)
        
        layout.addWidget(self.results_scroll)
        
        self.setLayout(layout)

        # Update enabled state based on DB connection
        self.update_search_button_state()

    # --- NEW: Helper methods copied from Convert.py ---
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
    # --- END NEW ---

    def update_search_button_state(self):
        """Disables search button if DB is not connected."""
        db_connected = self.db_tab_ref.db is not None
        self.search_button.setEnabled(db_connected)
        if not db_connected:
            self.results_count_label.setText("Not connected to database.")
        else:
            self.results_count_label.setText("Ready to search.")

    def get_selected_tags(self) -> List[str]:
        """Parses comma-separated tags from the QLineEdit."""
        tags_str = self.tags_edit.text().strip()
        if not tags_str:
            return None
        return [tag.strip().lower() for tag in tags_str.split(',') if tag.strip()]

    # --- NEW: Helper to get selected formats ---
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
    
    def perform_search(self):
        """Perform the image search using the database."""
        db = self.db_tab_ref.db
        if not db:
            QMessageBox.warning(self, "Error", "Please connect to the database first.")
            return

        self.search_button.setEnabled(False)
        self.search_button.setText("Searching...")
        QApplication.processEvents()
    
        self.clear_results()
        
        # Get search criteria
        group = self.group_combo.currentText().strip() or None
        subgroup = self.subgroup_combo.currentText().strip() or None
        filename = self.filename_edit.text().strip() or None
        tags = self.get_selected_tags()
        formats = self.get_selected_formats() # NEW
        
        if not group and not subgroup and not filename and not tags and not formats: # MODIFIED
            self.results_count_label.setText("Please enter at least one search criterion.")
            self._reset_search_button()
            return
        
        try:
            # Perform database search
            matching_files = db.search_images(
                group_name=group,
                subgroup_name=subgroup,
                tags=tags,
                filename_pattern=filename,
                input_formats=formats, # NEW
                limit=100 
            )
            
            self.display_results(matching_files)

        except Exception as e:
            QMessageBox.critical(self, "Search Error", f"An error occurred during search:\n{str(e)}")
            self.results_count_label.setText(f"Error: {str(e)}")
        
        QTimer.singleShot(200, self._reset_search_button)
    
    def _reset_search_button(self):
        """Reset search button to original style"""
        self.search_button.setEnabled(True)
        self.search_button.setText("Search Database")
    
    def display_results(self, results: List[Dict[str, Any]]):
        """Display the search results (dictionaries) as thumbnails"""
        count = len(results)
        self.results_count_label.setText(f"Found {count} matching image(s)")
        
        if count == 0:
            return
        
        columns = 4 
        for i, img_data in enumerate(results):
            row = i // columns
            col = i % columns
            
            file_path = img_data.get('file_path')
            
            result_container = QWidget()
            result_layout = QVBoxLayout(result_container)
            result_layout.setContentsMargins(5, 5, 5, 5)
            
            image_label = QLabel()
            image_label.setFixedSize(150, 150)
            image_label.setAlignment(Qt.AlignCenter)
            image_label.setStyleSheet("border: 1px solid #4f545c; background: #36393f;")

            pixmap = QPixmap(str(file_path))
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                image_label.setPixmap(scaled_pixmap)
            else:
                image_label.setText("Not Found")
            
            result_layout.addWidget(image_label)
            
            filename_label = QLabel(img_data.get('filename', 'N/A'))
            filename_label.setWordWrap(True)
            filename_label.setAlignment(Qt.AlignCenter)
            filename_label.setStyleSheet("font-size: 10px;")
            result_layout.addWidget(filename_label)
            
            btn_layout = QHBoxLayout()
            
            view_button = QPushButton("View")
            apply_shadow_effect(view_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
            view_button.clicked.connect(lambda chk, p=file_path: self.open_file_preview(p))
            btn_layout.addWidget(view_button)
            
            folder_button = QPushButton("Folder")
            apply_shadow_effect(folder_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
            folder_button.clicked.connect(lambda chk, p=file_path: self.open_file_directory(p))
            btn_layout.addWidget(folder_button)
            
            result_layout.addLayout(btn_layout)
            
            self.results_layout.addWidget(result_container, row, col)
            self.result_widgets.append(result_container)

    def remove_preview_window(self, window_instance: ImagePreviewWindow):
        """Removes a preview window from the tracking list when it's closed."""
        try:
            if window_instance in self.open_preview_windows:
                self.open_preview_windows.remove(window_instance)
        except (RuntimeError, ValueError):
            pass

    def open_file_preview(self, file_path: str):
        """Opens the full-size image preview window."""
        if not file_path or not os.path.exists(file_path) or not os.path.isfile(file_path):
            QMessageBox.warning(self, "Invalid Path", f"File not found at path:\n{file_path}")
            return

        for window in self.open_preview_windows:
            if window.image_path == file_path:
                window.activateWindow() 
                return
        
        preview = ImagePreviewWindow(file_path, self.db_tab_ref, parent=self) 
        preview.finished.connect(lambda result, p=preview: self.remove_preview_window(p))
        preview.show() 
        self.open_preview_windows.append(preview)

    def open_file_directory(self, file_path: str):
        """Open the file's parent directory with the default system application"""
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Invalid Path", f"File not found at path:\n{file_path}")
            return
            
        directory = os.path.dirname(file_path)
        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(directory)
            elif system == "Darwin":  # macOS
                subprocess.run(['open', directory])
            else:  # Linux
                subprocess.run(['xdg-open', directory])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open directory:\n{e}")
    
    def clear_results(self):
        """Clear all previous search results"""
        for widget in self.result_widgets:
            widget.deleteLater()
        self.result_widgets.clear()
        
        for window in self.open_preview_windows[:]:
            window.close()
        self.open_preview_windows.clear()
    
    def collect(self) -> Dict[str, Any]:
        """Collect search parameters"""
        return {
            "group_name": self.group_combo.currentText().strip() or None,
            "subgroup_name": self.subgroup_combo.currentText().strip() or None, 
            "filename_pattern": self.filename_edit.text().strip() or None,
            "input_formats": self.get_selected_formats() or None, # NEW
            "tags": self.get_selected_tags() or None
        }
