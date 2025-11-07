import os

from typing import Set
from pathlib import Path
from PySide6.QtGui import QPixmap
from PySide6.QtCore import (
    Qt, QThreadPool, QThread,
)
from PySide6.QtWidgets import (
    QApplication, QMessageBox, QGridLayout,
    QHBoxLayout, QVBoxLayout, QScrollArea, 
    QComboBox, QLineEdit, QFileDialog, 
    QPushButton, QLabel, QFormLayout,
    QWidget, QGroupBox, QCheckBox,
)
from .BaseTab import BaseTab
from ..components import ImagePreviewWindow, ClickableLabel, MarqueeScrollArea
from ..helpers import ImageScannerWorker, BatchThumbnailLoaderWorker
from ..styles import apply_shadow_effect


class ScanFSETab(BaseTab):
    """
    Manages file and directory scanning, image preview gallery, and batch database operations.
    Requires a reference to the main DatabaseTab for database connection access.
    """
    def __init__(self, db_tab_ref, dropdown=True):
        super().__init__()
        # Reference to the main DatabaseTab to access the self.db connection object
        self.db_tab_ref = db_tab_ref
        self.dropdown = dropdown
        
        self.scan_image_list: list[str] = []
        self.selected_image_paths: Set[str] = set()
        self.selected_scan_image_path: str = None
        self.open_preview_windows: list[ImagePreviewWindow] = []

        self.thumbnail_size = 150
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width
        
        # --- MODIFIED: Set main layout directly on the tab ---
        main_layout = QVBoxLayout(self)
        
        # --- Scan Directory Section (Settings Box) ---
        scan_group = QGroupBox("Scan Directory")
        # --- NEW: Apply styling from ImageCrawlerTab ---
        scan_group.setStyleSheet("""
            QGroupBox {  
                border: 1px solid #4f545c; 
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title { 
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 10px;
                color: white;
                border-radius: 4px;
            }
        """)
        
        scan_layout = QVBoxLayout()
        scan_layout.setContentsMargins(10, 20, 10, 10) 
        
        # Directory path selection
        scan_dir_layout = QHBoxLayout()
        self.scan_directory_path = QLineEdit()
        self.scan_directory_path.setPlaceholderText("Select directory to scan...")
        btn_browse_scan = QPushButton("Browse...")
        btn_browse_scan.clicked.connect(self.browse_scan_directory)
        
        btn_browse_scan.setStyleSheet("QPushButton { background-color: #4f545c; padding: 6px 12px; } QPushButton:hover { background-color: #5865f2; }")
        apply_shadow_effect(btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3)

        scan_dir_layout.addWidget(self.scan_directory_path)
        scan_dir_layout.addWidget(btn_browse_scan)
        scan_layout.addLayout(scan_dir_layout)
        
        # --- MODIFIED: Set layout for group and add to main layout ---
        scan_group.setLayout(scan_layout)
        main_layout.addWidget(scan_group)

        self.threadpool = QThreadPool.globalInstance()
        self.scanned_dir = None
        try:
            base_dir = Path.cwd()
            while base_dir.name != 'Image-Toolkit' and base_dir.parent != base_dir:
                base_dir = base_dir.parent
            if base_dir.name == 'Image-Toolkit':
                self.last_browsed_scan_dir = str(base_dir / 'data')
            else:
                self.last_browsed_scan_dir = str(Path.cwd() / 'data')
        except Exception:
             self.last_browsed_scan_dir = os.getcwd() # Fallback
        
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None
        self.path_to_label_map = {}

        # --- MODIFIED: Add widgets directly to main_layout ---

        # View Image button
        self.scan_view_image_btn = QPushButton("View Full Size Selected Image(s)")
        self.scan_view_image_btn.clicked.connect(self.view_selected_scan_image)
        self.scan_view_image_btn.setEnabled(False) 
        self.scan_view_image_btn.setStyleSheet("""
            QPushButton { 
                background-color: #5865f2; /* Violet */
                color: white; 
                padding: 10px;
                border-radius: 8px;
            } 
            QPushButton:hover { 
                background-color: #4754c4;
            }
            QPushButton:disabled {
                background-color: #4f545c;
                color: #a0a0a0;
            }
        """)
        apply_shadow_effect(self.scan_view_image_btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        main_layout.addWidget(self.scan_view_image_btn)

        # Scroll Area for image thumbnails
        self.scan_scroll_area = MarqueeScrollArea() 
        self.scan_scroll_area.setWidgetResizable(True)
        self.scan_scroll_area.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")

        self.scan_thumbnail_widget = QWidget()
        self.scan_thumbnail_widget.setStyleSheet("QWidget { background-color: #2c2f33; }")

        self.scan_thumbnail_layout = QGridLayout(self.scan_thumbnail_widget)
        
        self.scan_scroll_area.selection_changed.connect(self.handle_marquee_selection)
        
        self.scan_thumbnail_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        
        self.scan_scroll_area.setWidget(self.scan_thumbnail_widget)
        
        main_layout.addWidget(self.scan_scroll_area, 1) # Add scroll area to main layout
        
        
        # --- Metadata Group Box (Initially hidden) ---
        self.metadata_group = QGroupBox("Batch Metadata (Applies to ALL Selected Images)")
        self.metadata_group.setVisible(False) 
        metadata_vbox = QVBoxLayout(self.metadata_group)
        
        # Metadata form layout
        form_layout = QFormLayout()
        
        # Series name with autocomplete
        series_layout = QHBoxLayout()
        self.series_combo = QComboBox()
        self.series_combo.setEditable(True)
        self.series_combo.setPlaceholderText("Enter or select series name...")
        series_layout.addWidget(self.series_combo)
        form_layout.addRow("Series Name:", series_layout)
        
        # Characters (comma-separated with autocomplete)
        char_layout = QVBoxLayout()
        self.characters_edit = QLineEdit()
        self.characters_edit.setPlaceholderText("Enter character names (comma-separated)...")
        char_layout.addWidget(self.characters_edit)
        self.char_suggestions = QLabel()
        self.char_suggestions.setStyleSheet("font-size: 9px; color: #b9bbbe;") # Light gray text
        char_layout.addWidget(self.char_suggestions)
        form_layout.addRow("Characters:", char_layout)
        
        # Tags with checkboxes
        tags_scroll = QScrollArea()
        tags_scroll.setMaximumHeight(150)
        tags_scroll.setWidgetResizable(True)
        self.tags_widget = QWidget()
        self.tags_layout = QGridLayout(self.tags_widget)
        tags_scroll.setWidget(self.tags_widget)
        
        self.common_tags = sorted([
            "landscape", "night", "day", "indoor", "outdoor",
            "solo", "multiple", "fanart", "official", "cosplay",
            "portrait", "full_body", "action", "close_up", "nsfw",
            "color", "monochrome", "sketch", "digital", "traditional"
        ])
        self.tag_checkboxes = {}
        columns = 4
        for i, tag in enumerate(self.common_tags):
            checkbox = QCheckBox(tag.replace("_", " ").title())
            checkbox.setStyleSheet("""
                QCheckBox::indicator {
                    width: 16px; height: 16px; border: 1px solid #555;
                    border-radius: 3px; background-color: #333;
                }
                QCheckBox::indicator:checked {
                    background-color: #4CAF50; border: 1px solid #4CAF50;
                    image: url(./src/gui/assets/check.png);
                }
            """)
            self.tag_checkboxes[tag] = checkbox
            row = i // columns
            col = i % columns
            self.tags_layout.addWidget(checkbox, row, col)

        form_layout.addRow("Tags:", tags_scroll)
        
        metadata_vbox.addLayout(form_layout)
        
        main_layout.addWidget(self.metadata_group) # Add to main layout

        # Action buttons (Batch Operations)
        
        self.scan_button = QPushButton("Add Images Data to Database")
        self.scan_button.setStyleSheet("""
            QPushButton { 
                background-color: #2ecc71; /* Green */
                color: white; 
                padding: 10px 8px; 
                border-radius: 8px;
                font-weight: bold;
            } 
            QPushButton:hover { 
                background-color: #1e8449; /* Darker Green */
            }
            QPushButton:disabled {
                background-color: #4f545c;
                color: #a0a0a0;
            }
        """)
        apply_shadow_effect(self.scan_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.scan_button.clicked.connect(self.scan_directory) 

        self.update_selected_button = QPushButton("Update Images Data in Database")
        self.update_selected_button.setStyleSheet("""
            QPushButton { 
                background-color: #3498db; /* Blue */
                color: white; 
                padding: 10px 8px; 
                border-radius: 8px;
                font-weight: bold;
            } 
            QPushButton:hover { 
                background-color: #2980b9; /* Darker Blue */
            }
            QPushButton:disabled {
                background-color: #4f545c;
                color: #a0a0a0;
            }
        """)
        apply_shadow_effect(self.update_selected_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.update_selected_button.clicked.connect(self.update_selected_metadata)

        self.refresh_image_button = QPushButton("Refresh Image Directory")
        self.refresh_image_button.setStyleSheet("""
            QPushButton { 
                background-color: #f1c40f; /* Yellow */
                color: white; 
                padding: 10px 8px; 
                border-radius: 8px;
                font-weight: bold;
            } 
            QPushButton:hover { 
                background-color: #d4ac0d; /* Darker Yellow */
            }
            QPushButton:disabled {
                background-color: #4f545c;
                color: #a0a0a0;
            }
        """)
        apply_shadow_effect(self.refresh_image_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.refresh_image_button.clicked.connect(self.refresh_image_directory) 

        self.delete_selected_button = QPushButton("Delete Images Data from Database")
        self.delete_selected_button.setStyleSheet("""
            QPushButton { 
                background-color: #e74c3c; /* Red */
                color: white; 
                padding: 10px 8px; 
                border-radius: 8px;
                font-weight: bold;
            } 
            QPushButton:hover { 
                background-color: #c0392b; /* Darker Red */
            }
            QPushButton:disabled {
                background-color: #4f545c;
                color: #a0a0a0;
            }
        """)
        apply_shadow_effect(self.delete_selected_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.delete_selected_button.clicked.connect(self.delete_selected_images)
        
        scan_action_layout = QHBoxLayout()
        scan_action_layout.addWidget(self.scan_button)
        scan_action_layout.addWidget(self.update_selected_button)
        scan_action_layout.addWidget(self.refresh_image_button)
        scan_action_layout.addWidget(self.delete_selected_button)
        
        main_layout.addLayout(scan_action_layout) # Add to main layout

        # --- REMOVED: Extra scroll area and top_layout wrappers ---
        
        self.setLayout(main_layout)
        
        self.update_button_states(connected=False) 
    
    def _cleanup_thumbnail_thread_ref(self):
        """Slot to clear the QThread and QObject references after the thread finishes its work."""
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None

    def display_scan_results(self, image_paths: list[str]):
        """
        Receives image paths from the worker thread, creates placeholders, and starts 
        a single BatchThumbnailLoaderWorker to progressively load and display images.
        """
        
        self.clear_scan_image_gallery() 
        self.scan_image_list = image_paths
        
        columns = self.calculate_columns()
        
        if not self.scan_image_list:
            no_images_label = QLabel("No supported images found.")
            no_images_label.setAlignment(Qt.AlignCenter)
            no_images_label.setStyleSheet("color: #b9bbbe;")
            self.scan_thumbnail_layout.addWidget(no_images_label, 0, 0, 1, columns)
            return

        # 1. Create ALL Placeholders immediately on the main thread
        for i, path in enumerate(self.scan_image_list):
            row = i // columns
            col = i % columns

            clickable_label = ClickableLabel(path) 
            clickable_label.setText("Loading...")
            clickable_label.setAlignment(Qt.AlignCenter)
            clickable_label.setFixedSize(self.thumbnail_size, self.thumbnail_size)
            clickable_label.setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;") # Dark mode style
            clickable_label.path_clicked.connect(self.select_scan_image)
            clickable_label.path_double_clicked.connect(self.view_selected_scan_image_from_double_click) 

            self.scan_thumbnail_layout.addWidget(clickable_label, row, col)
            self.path_to_label_map[path] = clickable_label 

        # 2. Kick off the SINGLE asynchronous worker for batch loading
        worker = BatchThumbnailLoaderWorker(self.scan_image_list, self.thumbnail_size)
        thread = QThread()

        self.current_thumbnail_loader_worker = worker
        self.current_thumbnail_loader_thread = thread
        
        worker.moveToThread(thread)
        
        thread.started.connect(worker.run_load_batch)
        worker.thumbnail_loaded.connect(self._update_thumbnail_slot)
        
        worker.loading_finished.connect(thread.quit)
        worker.loading_finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._cleanup_thumbnail_thread_ref)
        
        thread.start()
        
    def _update_thumbnail_slot(self, index: int, pixmap: QPixmap, path: str):
        """
        Slot executed on the main thread to update a specific thumbnail widget
        after the single batch worker has finished loading one image.
        """
        label = self.path_to_label_map.get(path)
        
        if label is None:
            return

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
            
    def clear_scan_image_gallery(self):
        """Removes all widgets from the scan gallery layout and cleans up the single active thread."""
        
        if self.current_thumbnail_loader_thread and self.current_thumbnail_loader_thread.isRunning():
            self.current_thumbnail_loader_thread.quit()
        
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None
        self.path_to_label_map = {} 

        while self.scan_thumbnail_layout.count():
            item = self.scan_thumbnail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        
        self.scan_image_list = []
        self.selected_image_paths = set()
        self.selected_scan_image_path = None
        self.update_button_states(connected=(self.db_tab_ref.db is not None))
        self.metadata_group.setVisible(False) 

    def handle_scan_error(self, message: str):
        """Handles and displays errors that occurred during the background scan."""
        self.clear_scan_image_gallery() 
        QMessageBox.warning(self, "Error Scanning", message)
        ready_label = QLabel("Browse for a directory.")
        ready_label.setAlignment(Qt.AlignCenter)
        ready_label.setStyleSheet("color: #b9bbbe;")
        self.scan_thumbnail_layout.addWidget(ready_label, 0, 0, 1, 1)

    def browse_scan_directory(self):
        """Select directory to scan and display image thumbnails."""
        start_dir = self.last_browsed_scan_dir
        directory = QFileDialog.getExistingDirectory(self, "Select directory to scan", start_dir)
        if directory:
            self.last_browsed_scan_dir = directory
            self.scan_directory_path.setText(directory)
            self.populate_scan_image_gallery(directory)

    def calculate_columns(self) -> int:
        """Calculates the maximum number of thumbnail columns that fit in the widget."""
        widget_width = self.scan_thumbnail_widget.width()
        if widget_width <= 0:
            widget_width = self.scan_thumbnail_widget.parentWidget().width()
        
        if widget_width <= 0:
            return 4 
        
        columns = widget_width // self.approx_item_width
        return max(1, columns)

    def populate_scan_image_gallery(self, directory: str):
        """Initiates scanning on a separate thread and sets up the gallery structure."""
        self.scanned_dir = directory
        self.clear_scan_image_gallery()
        self.scan_view_image_btn.setEnabled(False)
        
        loading_label = QLabel("Scanning directory, please wait...")
        loading_label.setAlignment(Qt.AlignCenter)
        loading_label.setStyleSheet("color: #b9bbbe;")
        self.scan_thumbnail_layout.addWidget(loading_label, 0, 0, 1, 10) 
        
        self.worker = ImageScannerWorker(directory)
        self.thread = QThread() 
        self.worker.moveToThread(self.thread) 
        
        self.thread.started.connect(self.worker.run_scan)
        self.worker.scan_finished.connect(self.display_scan_results)
        self.worker.scan_error.connect(self.handle_scan_error)
        
        self.worker.scan_finished.connect(self.thread.quit)
        self.worker.scan_finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.thread.start()

    def select_scan_image(self, file_path: str):
        """
        Handles the click on a thumbnail in the scan directory gallery,
        toggling selection for batch operations and updating the single-view path.
        
        Respects Ctrl modifier for multi-selection.
        """
        clicked_widget = self.path_to_label_map.get(file_path)
        if not clicked_widget:
            return

        mods = QApplication.keyboardModifiers()
        is_ctrl_pressed = bool(mods & Qt.ControlModifier)

        if not is_ctrl_pressed:
            paths_to_deselect = self.selected_image_paths - {file_path}
            self.selected_image_paths = {file_path}
            
            for path in paths_to_deselect:
                label = self.path_to_label_map.get(path)
                if label:
                    if not label.pixmap().isNull():
                        label.setStyleSheet("border: 1px solid #4f545c;")
                    else:
                        if "Error" in label.text():
                             label.setStyleSheet("border: 1px solid #e74c3c; background-color: #4f545c; font-size: 8px;")
                        else:
                             label.setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;")

        else:
            if file_path in self.selected_image_paths:
                self.selected_image_paths.remove(file_path)
            else:
                self.selected_image_paths.add(file_path)

        is_selected = file_path in self.selected_image_paths
        if is_selected:
            if "Error" in clicked_widget.text():
                clicked_widget.setStyleSheet("border: 3px solid #5865f2; background-color: #4f545c; font-size: 8px;")
            else:
                clicked_widget.setStyleSheet("border: 3px solid #5865f2;")
        else:
            if not clicked_widget.pixmap().isNull():
                clicked_widget.setStyleSheet("border: 1px solid #4f545c;")
            else:
                if "Error" in clicked_widget.text():
                     clicked_widget.setStyleSheet("border: 1px solid #e74c3c; background-color: #4f545c; font-size: 8px;")
                else:
                     clicked_widget.setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;") 

        self.selected_scan_image_path = file_path
        self.update_button_states(connected=(self.db_tab_ref.db is not None))

    def handle_marquee_selection(self, paths_from_marquee: set, is_ctrl_pressed: bool):
        """
        Handles the selection update from the MarqueeSelectionWidget.
        """
        if not is_ctrl_pressed:
            paths_to_deselect = self.selected_image_paths - paths_from_marquee
            paths_to_select = paths_from_marquee - self.selected_image_paths
            
            self.selected_image_paths = paths_from_marquee
            
            paths_to_update = paths_to_deselect.union(paths_to_select)

        else:
            paths_to_update = paths_from_marquee - self.selected_image_paths
            self.selected_image_paths.update(paths_from_marquee)

        for path in paths_to_update:
            label = self.path_to_label_map.get(path)
            if not label:
                continue
            
            is_selected = path in self.selected_image_paths
            
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

        self.update_button_states(connected=(self.db_tab_ref.db is not None))

    def view_selected_scan_image_from_double_click(self, path: str):
        """
        Special slot for double-click.
        Ensures the double-clicked item is selected, then opens previews.
        """
        if path not in self.selected_image_paths:
            self.select_scan_image(path)
        
        self.selected_scan_image_path = path
        self.view_selected_scan_image()

    def remove_preview_window(self, window_instance: ImagePreviewWindow):
        """Removes a preview window from the tracking list when it's closed."""
        try:
            if window_instance in self.open_preview_windows:
                self.open_preview_windows.remove(window_instance)
        except (RuntimeError, ValueError):
            pass

    def view_selected_scan_image(self):
        """
        Opens non-modal, full-size image preview windows for ALL
        currently selected scan images.
        """
        if not self.selected_image_paths:
            if self.selected_scan_image_path:
                self.selected_image_paths.add(self.selected_scan_image_path)
                self.update_button_states(connected=(self.db_tab_ref.db is not None))
            else:
                QMessageBox.warning(self, "No Images Selected", "Please select one or more image thumbnails from the gallery first.")
                return

        for path in self.selected_image_paths:
            if not (path and os.path.exists(path) and os.path.isfile(path)):
                QMessageBox.warning(self, "Invalid Path", f"The path '{path}' is invalid or not a file. Skipping.")
                continue

            already_open = False
            for window in self.open_preview_windows:
                if window.image_path == path:
                    window.activateWindow() 
                    already_open = True
                    break
            
            if not already_open:
                preview = ImagePreviewWindow(path, self.db_tab_ref, parent=self) 
                
                preview.finished.connect(lambda result, p=preview: self.remove_preview_window(p))
                
                preview.show() 
                self.open_preview_windows.append(preview)


    # --- Database Interaction Methods (ADD Operation) ---
    def scan_directory(self):
        """
        Toggles the metadata form visibility, or performs the actual database 
        addition if the form is already visible. (ADD Operation)
        """
        db = self.db_tab_ref.db
        if not db:
            QMessageBox.warning(self, "Error", "Please connect to a database first (in Database tab)")
            return
        
        selected_paths = list(self.selected_image_paths)
        if not selected_paths:
            QMessageBox.warning(self, "Error", "No images selected to add to the database.")
            return

        if not self.metadata_group.isVisible():
            self.metadata_group.setVisible(True)
            self.scan_button.setText(f"Confirm & Add {len(selected_paths)} Images with Metadata")
            return
            
        self.scan_button.setText(f"Adding {len(selected_paths)}...")
        self.scan_button.setEnabled(False)
        QApplication.processEvents() 
        
        try:
            count = 0
            series = self.series_combo.currentText().strip() or None
            characters = [c.strip() for c in self.characters_edit.text().split(',') if c.strip()] or None
            tags = [tag for tag, cb in self.tag_checkboxes.items() if cb.isChecked()] or None

            for path in selected_paths:
                db.add_image(
                    file_path=path,
                    embedding=None, 
                    series_name=series,
                    characters=characters,
                    tags=tags
                )
                count += 1
            
            self.clear_scan_image_gallery()
            if self.scanned_dir:
                self.populate_scan_image_gallery(self.scanned_dir)
            
            self.db_tab_ref.update_statistics()
            self.db_tab_ref.refresh_autocomplete_data()
            QMessageBox.information(self, "Success", f"Added/Updated {count} selected image paths in database")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add selected images:\n{str(e)}")
        
        finally:
            self.metadata_group.setVisible(False) 
            self.update_button_states(connected=True)

    def refresh_image_directory(self):
        """
        Clears the directory path line edit and removes all images from the 
        scan preview gallery.
        """
        if self.scanned_dir is not None:
            self.scan_directory_path.clear()
            self.clear_scan_image_gallery()
            self.scan_view_image_btn.setEnabled(False)
            self.scanned_dir = None
            
            ready_label = QLabel("Image preview cleared. Browse for a new directory.")
            ready_label.setAlignment(Qt.AlignCenter)
            ready_label.setStyleSheet("color: #b9bbbe;")

            columns = self.calculate_columns()
            self.scan_thumbnail_layout.addWidget(ready_label, 0, 0, 1, columns)
            
            QMessageBox.information(self, "Refreshed", "Image directory path and preview cleared.")
        else:
            self.scan_directory_path.clear()
            self.clear_scan_image_gallery()
            ready_label = QLabel("Image preview cleared. Browse for a new directory.")
            ready_label.setAlignment(Qt.AlignCenter)
            ready_label.setStyleSheet("color: #b9bbbe;")

            columns = self.calculate_columns()
            self.scan_thumbnail_layout.addWidget(ready_label, 0, 0, 1, columns)

    # --- Database Interaction Methods (UPDATE Operation) ---
    def update_selected_metadata(self):
        """Performs the UPDATE operation on selected image paths."""
        db = self.db_tab_ref.db
        if not db:
            QMessageBox.warning(self, "Error", "Please connect to a database first (in Database tab)")
            return
            
        selected_paths = list(self.selected_image_paths)
        if not selected_paths:
            QMessageBox.warning(self, "Error", "No images selected for update operation.")
            return

        if not self.metadata_group.isVisible():
            self.metadata_group.setVisible(True)
            self.update_selected_button.setText(f"Confirm & Update {len(selected_paths)} Images")
            return

        self.update_selected_button.setText(f"Updating {len(selected_paths)}...")
        self.update_selected_button.setEnabled(False)
        QApplication.processEvents() 
        
        try:
            count = 0
            series = self.series_combo.currentText().strip() or None
            characters = [c.strip() for c in self.characters_edit.text().split(',') if c.strip()] or None
            tags = [tag for tag, cb in self.tag_checkboxes.items() if cb.isChecked()] or None
            
            image_ids = []
            for path in selected_paths:
                img_data = db.get_image_by_path(path)
                if img_data:
                    image_ids.append(img_data['id'])

            for image_id in image_ids:
                db.update_image(
                    image_id=image_id,
                    series_name=series,
                    characters=characters,
                    tags=tags
                )
                count += 1
            
            self.clear_scan_image_gallery()
            if self.scanned_dir:
                self.populate_scan_image_gallery(self.scanned_dir)
            
            self.db_tab_ref.update_statistics()
            QMessageBox.information(self, "Success", f"Updated metadata for {count} selected image paths in database.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update selected images:\n{str(e)}")
        finally:
            self.metadata_group.setVisible(False)
            self.update_button_states(connected=True)

    # --- Database Interaction Methods (DELETE Operation) ---
    def delete_selected_images(self):
        """Confirms and performs the DELETE operation on selected image paths."""
        db = self.db_tab_ref.db
        if not db:
            QMessageBox.warning(self, "Error", "Please connect to a database first (in Database tab)")
            return
            
        selected_paths = list(self.selected_image_paths)
        if not selected_paths:
            QMessageBox.warning(self, "Error", "No images selected for deletion.")
            return

        confirm = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete **{len(selected_paths)}** selected image entries from the database?\nThis action is irreversible.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.delete_selected_button.setText(f"Deleting {len(selected_paths)}...")
            self.delete_selected_button.setEnabled(False)
            QApplication.processEvents() 
            
            try:
                image_ids = []
                for path in selected_paths:
                    img_data = db.get_image_by_path(path)
                    if img_data:
                        image_ids.append(img_data['id'])
                        
                count = 0
                for img_id in image_ids:
                    db.delete_image(img_id)
                    count += 1
                
                self.clear_scan_image_gallery()
                if self.scanned_dir:
                    self.populate_scan_image_gallery(self.scanned_dir)

                self.db_tab_ref.update_statistics()
                QMessageBox.information(self, "Deleted", f"Deleted {count} image entries from database.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete images:\n{str(e)}")
            finally:
                self.update_button_states(connected=True)
        else:
            QMessageBox.information(self, "Aborted", "Delete operation aborted by user.")

    def update_button_states(self, connected: bool):
        """Enable or disable buttons based on database connection status."""
        selection_count = len(self.selected_image_paths)
        
        self.scan_view_image_btn.setEnabled(selection_count > 0)
        self.scan_view_image_btn.setText(f"View Full Size {selection_count} Selected Image(s)")
        
        self.refresh_image_button.setEnabled(True) 

        if self.metadata_group.isVisible() and self.scan_button.text().startswith("Confirm & Add"):
            self.scan_button.setText(f"Confirm & Add {selection_count} Images with Metadata")
        else:
            self.scan_button.setText(f"Add {selection_count} Selected Images to Database")
        self.scan_button.setEnabled(connected and selection_count > 0)

        if self.metadata_group.isVisible() and self.update_selected_button.text().startswith("Confirm & Update"):
            self.update_selected_button.setText(f"Confirm & Update {selection_count} Images")
        else:
            self.update_selected_button.setText(f"Update {selection_count} Selected Images")
        self.update_selected_button.setEnabled(connected and selection_count > 0)

        self.delete_selected_button.setText(f"Delete {selection_count} Images from DB")
        self.delete_selected_button.setEnabled(connected and selection_count > 0)

    def collect(self) -> dict:
        """Collect current inputs from the Scan Directory tab as a dict."""
        out = {
            "scan_directory": self.scan_directory_path.text().strip() or None,
            "selected_images": list(self.selected_image_paths) 
        }
        return out
