import os
import platform
import subprocess
import time

from typing import Dict, Any, List, Optional
from PySide6.QtGui import QPixmap, QAction, QCursor
from PySide6.QtCore import Qt, QTimer, Signal, QPoint
from PySide6.QtWidgets import (
    QFormLayout, QHBoxLayout, QVBoxLayout, QGridLayout,
    QScrollArea, QGroupBox, QApplication, 
    QLineEdit, QPushButton, QComboBox, QCheckBox,
    QWidget, QLabel, QMessageBox, QMenu
)
from .base_tab import BaseTab
from ..windows import ImagePreviewWindow
from ..components import OptionalField, ClickableLabel
from ..styles.style import apply_shadow_effect

# Safe import for supported formats
try:
    from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS
except ImportError:
    SUPPORTED_IMG_FORMATS = [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tiff"]


class SearchTab(BaseTab):
    # Signal to send image to another tab: (target_tab_name, image_path)
    send_to_tab_signal = Signal(str, str)

    def __init__(self, db_tab_ref, dropdown=True):
        super().__init__()
        # Reference to the main DatabaseTab to access the self.db connection object
        self.db_tab_ref = db_tab_ref
        self.dropdown = dropdown
        
        self.result_widgets = []
        self.open_preview_windows = [] # Track open preview windows
        self.selected_formats = set() 
        self.current_result_paths = [] # Store paths for navigation
        self._db_was_connected = False # Track connection state for tag refresh

        # Layout / Thumbnail constants matching WallpaperTab
        self.thumbnail_size = 150
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width
        
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
        self._setup_tag_checkboxes() # Populate with defaults or DB tags

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
        self.search_button.clicked.connect(self.perform_search)
        layout.addWidget(self.search_button)
        
        # Connect Enter key to search
        self.group_combo.lineEdit().returnPressed.connect(self.search_button.click)
        self.subgroup_combo.lineEdit().returnPressed.connect(self.search_button.click)
        self.filename_edit.returnPressed.connect(self.search_button.click)
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
        
        # Matching styles to WallpaperTab
        self.results_scroll.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")
        
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

    # --- Helper methods ---
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

    # --- DB TAGS UTILS ---
    def _get_tags_from_db(self) -> List[str]:
        """Fetches all tags from the connected database."""
        db = self.db_tab_ref.db
        if not db: 
            return []
            
        try:
            # Use get_all_tags_with_types and extract only the names
            db_tags = [item['name'] for item in db.get_all_tags_with_types()]
            if db_tags:
                return sorted(list(set(db_tags)))
        except Exception:
            pass 
        return []

    def _setup_tag_checkboxes(self):
        """Clears and repopulates the tags grid layout with checkboxes."""
        # Clear existing checkboxes
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.tag_checkboxes = {}
        
        tags_list = self._get_tags_from_db()

        columns = 4
        for i, tag in enumerate(tags_list):
            checkbox = QCheckBox(tag.replace("_", " ").title())
            self.tag_checkboxes[tag] = checkbox
            self.tags_layout.addWidget(checkbox, i // columns, i % columns)

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
        formats = self.get_selected_formats()
        
        # Validate inputs
        if not group and not subgroup and not filename and not tags and not formats:
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
                input_formats=formats,
                limit=1000
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

    def display_results(self, results: List[Dict[str, Any]]):
        """Display the search results (dictionaries) as thumbnails"""
        count = len(results)
        self.results_count_label.setText(f"Found {count} matching image(s)")
        
        # Store paths for navigation in the preview window
        self.current_result_paths = [res.get('file_path') for res in results if res.get('file_path')]
        
        if count == 0:
            return
        
        # Use dynamic column calculation
        columns = self.calculate_columns()
        
        for i, img_data in enumerate(results):
            row = i // columns
            col = i % columns
            
            file_path = img_data.get('file_path')
            
            result_container = QWidget()
            result_container.setStyleSheet("background: transparent;") # Ensure transparency
            result_layout = QVBoxLayout(result_container)
            result_layout.setContentsMargins(0, 0, 0, 0)
            result_layout.setSpacing(1)
            
            # Image Label (Thumbnail)
            image_label = ClickableLabel(file_path)
            image_label.setFixedSize(self.thumbnail_size, self.thumbnail_size)
            image_label.setAlignment(Qt.AlignCenter)
            
            # Styling to match WallpaperTab (Dark border, no fill unless error)
            image_label.setStyleSheet("border: 1px solid #4f545c;")
            
            # Connect mouse events for preview and context menu
            image_label.path_double_clicked.connect(self.open_file_preview)
            image_label.path_right_clicked.connect(
                lambda pos, p=file_path, w=image_label: self.show_context_menu(pos, p, w)
            )

            # Load thumbnail
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

    def handle_delete_image(self, file_path: str):
        """
        Handles the permanent deletion of the image file and updates the UI.
        This function implements the actual deletion logic.
        """
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Delete Error", "File not found or path is invalid.")
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
            # 1. Close any open preview windows for this file
            for window in self.open_preview_windows[:]:
                if window.image_path == file_path:
                    window.close()
                    break
            
            # 2. Delete the file from the filesystem
            os.remove(file_path)
            
            # 3. If connected, attempt to remove it from the database
            db = self.db_tab_ref.db
            if db:
                try:
                    # Assuming db has a method to delete by path/filename
                    # Note: Actual DB implementation depends on external 'backend' code.
                    db.delete_image_by_path(file_path) 
                except Exception as db_e:
                    # Log DB failure but continue, file is already gone
                    print(f"Warning: Failed to remove image from database: {db_e}")

            # 4. Remove the image from current search results lists/widgets
            if file_path in self.current_result_paths:
                self.current_result_paths.remove(file_path)

            # Re-run search to update the grid cleanly
            self.perform_search() 

            QMessageBox.information(self, "Success", f"File and associated database entry (if applicable) deleted successfully: {filename}")
            
        except Exception as e:
            QMessageBox.critical(self, "Deletion Failed", f"Could not delete the file:\n{e}")

    def show_image_properties(self, file_path: str):
        """Gathers and displays the image file's properties in a QMessageBox."""
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Invalid Path", f"File not found at path:\n{file_path}")
            return
            
        try:
            # 1. File System Properties
            stats = os.stat(file_path)
            file_size_bytes = stats.st_size
            last_modified = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stats.st_mtime))
            
            # Helper for size formatting
            def format_size(size_bytes):
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if size_bytes < 1024.0:
                        return f"{size_bytes:.2f} {unit}"
                    size_bytes /= 1024.0
                return f"{size_bytes:.2f} TB"

            # 2. Image Dimensions (Attempt to load QPixmap to get size)
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
            msg.setStyleSheet("QLabel{min-width: 400px;}") # Adjust size for readability
            msg.exec()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to retrieve properties: {e}")


    def show_context_menu(self, pos: QPoint, file_path: str, widget: QWidget):
        """Displays a context menu with Send To options."""
        menu = QMenu(self)

        # 1. Show Image Properties (New Separate Action)
        properties_action = QAction("🖼️ Show Image Properties", self)
        properties_action.triggered.connect(lambda: self.show_image_properties(file_path))
        menu.addAction(properties_action)

        # 2. Open Full Preview (Existing functionality)
        preview_action = QAction("👁️ Open Full Preview", self)
        preview_action.triggered.connect(lambda: self.open_file_preview(file_path))
        menu.addAction(preview_action)
        
        dir_action = QAction("📂 Open File Location", self)
        dir_action.triggered.connect(lambda: self.open_file_directory(file_path))
        menu.addAction(dir_action)
        
        menu.addSeparator()

        # 3. Delete Image File (Direct action, now calling local deletion handler)
        delete_action = QAction("🗑️ Delete Image File (Permanent)", self)
        delete_action.triggered.connect(lambda: self.handle_delete_image(file_path))
        menu.addAction(delete_action)

        menu.addSeparator()
        
        # Send To Actions (Removed redundant "Delete Tab" entry)
        send_menu = menu.addMenu("Send To...")
        
        actions_data = [
            ("Merge Tab", "merge"),
            ("Wallpaper Tab", "wallpaper"),
            ("Scan Metadata Tab", "scan")
        ]
        
        for name, code in actions_data:
            action = QAction(name, self)
            # emit signal with (tab_code, file_path)
            action.triggered.connect(lambda chk, c=code, p=file_path: self.send_to_tab_signal.emit(c, p))
            send_menu.addAction(action)

        # Display menu at global position (next to cursor)
        menu.exec(QCursor.pos())

    def remove_preview_window(self, window_instance: ImagePreviewWindow):
        """Removes a preview window from the tracking list when it's closed."""
        try:
            if window_instance in self.open_preview_windows:
                self.open_preview_windows.remove(window_instance)
        except (RuntimeError, ValueError):
            pass

    def open_file_preview(self, file_path: str):
        """Opens the full-size image preview window with navigation support."""
        if not file_path or not os.path.exists(file_path) or not os.path.isfile(file_path):
            QMessageBox.warning(self, "Invalid Path", f"File not found at path:\n{file_path}")
            return

        # Focus existing window if open
        for window in self.open_preview_windows:
            if window.image_path == file_path:
                window.activateWindow() 
                return
        
        # Determine index for navigation
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
            else:  # Linux/Unix
                subprocess.run(['xdg-open', directory])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open directory:\n{e}")
    
    def clear_results(self):
        """Clear all previous search results"""
        for widget in self.result_widgets:
            widget.deleteLater()
        self.result_widgets.clear()
        self.current_result_paths = []
        
        # Close previously opened previews
        for window in self.open_preview_windows[:]:
            window.close()
        self.open_preview_windows.clear()
    
    def collect(self) -> Dict[str, Any]:
        """Collect search parameters"""
        return {
            "group_name": self.group_combo.currentText().strip() or None,
            "subgroup_name": self.subgroup_combo.currentText().strip() or None, 
            "filename_pattern": self.filename_edit.text().strip() or None,
            "input_formats": self.get_selected_formats() or None,
            "tags": self.get_selected_tags() or None
        }

    def get_default_config(self) -> Dict[str, Any]:
        """Returns the default configuration dictionary for this tab."""
        return {
            "group_name": "",
            "subgroup_name": "",
            "filename_pattern": "",
            "input_formats": [],
            "tags": []
        }

    def set_config(self, config: Dict[str, Any]):
        """Applies a loaded configuration to the tab's UI elements."""
        try:
            self.group_combo.setCurrentText(config.get("group_name", ""))
            self.subgroup_combo.setCurrentText(config.get("subgroup_name", ""))
            self.filename_edit.setText(config.get("filename_pattern", ""))
            
            # Populate checkbox tags from config
            self._setup_tag_checkboxes() # Ensure populated first
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