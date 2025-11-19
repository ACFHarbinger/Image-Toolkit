import os
import time
from datetime import datetime
from PIL import Image
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from PySide6.QtWidgets import (
    QScrollArea, QGridLayout, QProgressDialog,
    QMessageBox, QLabel, QGroupBox, QWidget,
    QFormLayout, QHBoxLayout, QVBoxLayout,
    QLineEdit, QPushButton, QCheckBox,
    QMenu, QFileDialog, QApplication
)
from PySide6.QtGui import QPixmap, QAction
from PySide6.QtCore import Qt, Slot, QThread, QPoint
from .base_tab import BaseTab
from ..helpers import DeletionWorker, BatchThumbnailLoaderWorker, DuplicateScanWorker
from ..components import (
    OptionalField, MarqueeScrollArea, 
    ClickableLabel, PropertyComparisonDialog
)
from ..styles.style import apply_shadow_effect
from ..windows import ImagePreviewWindow
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS


class DeleteTab(BaseTab):
    def __init__(self, dropdown=True):
        super().__init__()
        self.dropdown = dropdown
        self.worker: Optional[DeletionWorker] = None
        
        # State for duplicate handling
        self.duplicate_results: Dict[str, List[str]] = {}
        self.duplicate_path_list: List[str] = []
        self.selected_duplicates: set = set()
        self.path_to_label_map = {}
        self.thumbnail_size = 150
        self.open_preview_windows: List[ImagePreviewWindow] = [] 
        self.approx_item_width = self.thumbnail_size + 10
        
        # Thread references are initialized to None here
        self.scan_thread = None
        self.scan_worker = None
        self.loader_thread = None
        self.loader_worker = None
        self.loading_dialog = None

        # --- Main Layout ---
        main_layout = QVBoxLayout(self)

        # Create a ScrollArea for the entire tab content to accommodate the new gallery
        page_scroll = QScrollArea()
        page_scroll.setWidgetResizable(True)
        page_scroll.setStyleSheet("QScrollArea { border: none; }")
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # --- Delete Targets Group ---
        target_group = QGroupBox("Delete Targets")
        target_layout = QFormLayout(target_group)

        # Target path
        v_target_group = QVBoxLayout()
        self.target_path = QLineEdit()
        self.target_path.setPlaceholderText("Path to delete OR scan for duplicates...")
        v_target_group.addWidget(self.target_path)

        h_buttons = QHBoxLayout()
        btn_target_file = QPushButton("Choose file...")
        apply_shadow_effect(btn_target_file, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        btn_target_file.clicked.connect(self.browse_file)
        btn_target_dir = QPushButton("Choose directory...")
        apply_shadow_effect(btn_target_dir, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        btn_target_dir.clicked.connect(self.browse_directory)
        h_buttons.addWidget(btn_target_file)
        h_buttons.addWidget(btn_target_dir)
        v_target_group.addLayout(h_buttons)
        target_layout.addRow("Target path:", v_target_group)
        
        content_layout.addWidget(target_group)

        # --- Delete Settings Group ---
        settings_group = QGroupBox("Options")
        settings_layout = QFormLayout(settings_group)

        # Extensions
        if self.dropdown:
            self.selected_extensions = set()
            ext_layout = QVBoxLayout()

            btn_layout = QHBoxLayout()
            self.extension_buttons = {}
            for ext in SUPPORTED_IMG_FORMATS:
                btn = QPushButton(ext)
                btn.setCheckable(True)
                btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")
                apply_shadow_effect(btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
                btn.clicked.connect(lambda checked, e=ext: self.toggle_extension(e, checked))
                btn_layout.addWidget(btn)
                self.extension_buttons[ext] = btn
            ext_layout.addLayout(btn_layout)

            all_btn_layout = QHBoxLayout()
            btn_add_all = QPushButton("Add All")
            btn_add_all.setStyleSheet("background-color: green; color: white;")
            apply_shadow_effect(btn_add_all, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
            btn_add_all.clicked.connect(self.add_all_extensions)
            btn_remove_all = QPushButton("Remove All")
            btn_remove_all.setStyleSheet("background-color: red; color: white;")
            apply_shadow_effect(btn_remove_all, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
            btn_remove_all.clicked.connect(self.remove_all_extensions)
            all_btn_layout.addWidget(btn_add_all)
            all_btn_layout.addWidget(btn_remove_all)
            ext_layout.addLayout(all_btn_layout)

            ext_container = QWidget()
            ext_container.setLayout(ext_layout)
            self.extensions_field = OptionalField("Target extensions", ext_container, start_open=False)
            settings_layout.addRow(self.extensions_field)
        else:
            self.selected_extensions = None
            self.target_extensions = QLineEdit()
            self.target_extensions.setPlaceholderText("e.g. .txt .jpg or txt jpg")
            settings_layout.addRow("Target extensions (optional):", self.target_extensions)

        # Confirmation
        self.confirm_checkbox = QCheckBox("Require confirmation before delete (recommended)")
        self.confirm_checkbox.setChecked(True)
        settings_layout.addRow(self.confirm_checkbox)

        content_layout.addWidget(settings_group)

        # --- Duplicate Scanner Group ---
        self.dup_group = QGroupBox("Duplicate Image Scanner")
        dup_layout = QVBoxLayout(self.dup_group)
        
        self.btn_scan_dups = QPushButton("Scan Directory for Duplicate Images")
        self.btn_scan_dups.setStyleSheet("""
            QPushButton { background-color: #e67e22; color: white; font-weight: bold; padding: 8px; }
            QPushButton:hover { background-color: #d35400; }
        """)
        apply_shadow_effect(self.btn_scan_dups, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_scan_dups.clicked.connect(self.start_duplicate_scan)
        dup_layout.addWidget(self.btn_scan_dups)
        
        # --- Gallery Area for Duplicates ---
        self.gallery_scroll = MarqueeScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")
        self.gallery_scroll.setMinimumHeight(400)
        
        self.gallery_widget = QWidget()
        self.gallery_widget.setStyleSheet("background-color: #2c2f33;")
        self.gallery_layout = QGridLayout(self.gallery_widget)
        self.gallery_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        self.gallery_scroll.setWidget(self.gallery_widget)
        self.gallery_scroll.setVisible(False)
        self.gallery_scroll.selection_changed.connect(self.handle_marquee_selection)
        dup_layout.addWidget(self.gallery_scroll)
        
        # --- NEW: Action Buttons Layout for Duplicates ---
        dup_actions_layout = QHBoxLayout()
        
        # 1. New Compare Button
        self.btn_compare_properties = QPushButton("Compare Properties (0)")
        self.btn_compare_properties.setStyleSheet("""
            QPushButton { background-color: #3498db; color: white; font-weight: bold; padding: 8px; }
            QPushButton:hover { background-color: #2980b9; }
        """)
        apply_shadow_effect(self.btn_compare_properties, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_compare_properties.clicked.connect(self.show_comparison_dialog)
        self.btn_compare_properties.setVisible(False)
        dup_actions_layout.addWidget(self.btn_compare_properties)

        # 2. Existing Delete Button
        self.btn_delete_selected_dups = QPushButton("Delete Selected Duplicates")
        self.btn_delete_selected_dups.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 8px;")
        apply_shadow_effect(self.btn_delete_selected_dups, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_delete_selected_dups.clicked.connect(self.delete_selected_duplicates)
        self.btn_delete_selected_dups.setVisible(False)
        dup_actions_layout.addWidget(self.btn_delete_selected_dups)

        dup_layout.addLayout(dup_actions_layout)

        content_layout.addWidget(self.dup_group)

        # --- Standard Delete Buttons ---
        content_layout.addStretch(1)
        
        run_buttons_layout = QHBoxLayout()
        SHARED_BUTTON_STYLE = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #667eea, stop:1 #764ba2);
                color: white; font-weight: bold; font-size: 14px;
                padding: 14px 8px; border-radius: 10px; min-height: 44px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #764ba2, stop:1 #667eea); }
            QPushButton:disabled { background: #718096; }
            QPushButton:pressed { background: #5a67d8; }
        """

        self.btn_delete_files = QPushButton("Delete Files Only")
        self.btn_delete_files.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(self.btn_delete_files, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_delete_files.clicked.connect(lambda: self.start_deletion(mode='files'))
        run_buttons_layout.addWidget(self.btn_delete_files)

        self.btn_delete_directory = QPushButton("Delete Directory and Contents")
        self.btn_delete_directory.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(self.btn_delete_directory, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_delete_directory.clicked.connect(lambda: self.start_deletion(mode='directory'))
        run_buttons_layout.addWidget(self.btn_delete_directory)

        content_layout.addLayout(run_buttons_layout)

        # --- Status ---
        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(self.status_label)

        # Set scroll widget
        page_scroll.setWidget(content_widget)
        main_layout.addWidget(page_scroll)
        self.setLayout(main_layout)

    # --- HELPER: Get Image Properties (Modified to include 'File Name') ---
    def get_image_properties(self, file_path: str) -> Dict[str, Any]:
        """Reads detailed image properties using PIL."""
        if not Path(file_path).exists():
            return {"Error": "File not found."}

        props = {"Path": file_path, "File Name": os.path.basename(file_path)}
        
        # 1. Get file stats (size, dates)
        try:
            stat = os.stat(file_path)
            props["File Size"] = f"{stat.st_size / (1024 * 1024):.2f} MB ({stat.st_size} bytes)"
            props["Last Modified"] = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            props["Created"] = datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
        except OSError:
            props["File Size"] = "N/A"
            props["Last Modified"] = "N/A"
            props["Created"] = "N/A"

        # 2. Get image dimensions and format
        try:
            # Check for PIL availability before use
            if 'Image' in globals():
                img = Image.open(file_path)
                props["Width"] = f"{img.width} px"
                props["Height"] = f"{img.height} px"
                props["Format"] = img.format
                props["Mode"] = img.mode
                img.close()
            else:
                props["Width"] = "N/A (Pillow Missing)"
                props["Height"] = "N/A (Pillow Missing)"
                props["Format"] = "N/A (Pillow Missing)"
                props["Mode"] = "N/A (Pillow Missing)"
        except Exception:
            props["Width"] = "N/A (Corrupt/Unsupported)"
            props["Height"] = "N/A (Corrupt/Unsupported)"
            props["Format"] = "N/A (Corrupt/Unsupported)"
            props["Mode"] = "N/A (Corrupt/Unsupported)"
            
        return props

    # --- NEW METHOD: Show Comparison Dialog ---
    @Slot()
    def show_comparison_dialog(self):
        if not self.selected_duplicates:
            QMessageBox.warning(self, "No Selection", "Please select at least one image thumbnail to compare its properties.")
            return

        selected_paths = list(self.selected_duplicates)
        
        # Limit comparison to a reasonable number to prevent UI slowdowns
        if len(selected_paths) > 10:
             reply = QMessageBox.question(
                self, "Large Selection",
                f"You have selected {len(selected_paths)} images. Comparing too many may be slow. Continue with the first 10?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
             if reply == QMessageBox.Yes:
                 selected_paths = selected_paths[:10]
             else:
                 return

        property_list = []
        for path in selected_paths:
            # Check for existence just in case the file was deleted outside the app
            if Path(path).exists():
                property_list.append(self.get_image_properties(path))
            else:
                 property_list.append({"File Name": os.path.basename(path), "Path": path, "Error": "File not found on disk."})
        
        # PropertyComparisonDialog must be correctly imported from ../components
        dialog = PropertyComparisonDialog(property_list, self)
        dialog.exec()
        
    # --- Context Menu Handler (UNCHANGED) ---
    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)
        
        # 1. Show Properties
        prop_action = QAction("🖼️ Show Image Properties", self)
        prop_action.triggered.connect(lambda: self.show_image_properties_dialog(path))
        menu.addAction(prop_action)
        
        menu.addSeparator()

        # 2. View Full Size Preview
        view_action = QAction("View Full Size Preview", self)
        view_action.triggered.connect(lambda: self.open_full_preview(path))
        menu.addAction(view_action)
        
        # 3. Select/Deselect
        is_selected = path in self.selected_duplicates
        toggle_text = "Deselect Image" if is_selected else "Select Image for Batch Deletion"
        toggle_action = QAction(toggle_text, self)
        toggle_action.triggered.connect(lambda: self.toggle_duplicate_selection(path))
        menu.addAction(toggle_action)
        
        # 4. Delete File (Individual)
        menu.addSeparator()
        delete_action = QAction("🗑️ Delete This File (Permanent)", self)
        delete_action.triggered.connect(lambda: self.delete_single_file(path))
        menu.addAction(delete_action)
        
        menu.exec(global_pos)
        
    @Slot(str)
    def show_image_properties_dialog(self, path: str):
        """Builds and displays a QMessageBox with detailed image properties."""
        properties = self.get_image_properties(path)
        
        if "Error" in properties:
             QMessageBox.critical(self, "Error Reading File", properties["Error"])
             return

        # Format message content
        prop_text = f"**File:** {os.path.basename(path)}\n"
        prop_text += f"**Path:** {path}\n\n"
        
        prop_text += "**Technical Details**\n"
        
        for key, value in properties.items():
            if key not in ["Path", "File Name"]: # Exclude File Name here as it's at the top
                prop_text += f"  - **{key}:** {value}\n"
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Image Properties")
        msg.setTextFormat(Qt.MarkdownText)
        msg.setText(prop_text)
        msg.setIcon(QMessageBox.Information)
        msg.exec()


    # ... (Keep existing extension helper methods) ...
    def toggle_extension(self, ext, checked):
        btn = self.extension_buttons[ext]
        if checked:
            self.selected_extensions.add(ext)
            btn.setStyleSheet("""
                QPushButton:checked { background-color: #3320b5; color: white; }
                QPushButton:hover { background-color: #00838a; }
            """)
            apply_shadow_effect(btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        else:
            self.selected_extensions.discard(ext)
            btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")
            apply_shadow_effect(btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)

    def add_all_extensions(self):
        for ext, btn in self.extension_buttons.items():
            btn.setChecked(True)
            self.toggle_extension(ext, True)

    def remove_all_extensions(self):
        for ext, btn in self.extension_buttons.items():
            btn.setChecked(False)
            self.toggle_extension(ext, False)

    def _get_starting_dir(self) -> str:
        """Helper to determine a reasonable starting directory."""
        path = Path(os.getcwd())
        parts = path.parts
        try:
            # Attempt to find a 'data' folder inside an 'Image-Toolkit' folder
            start_dir = os.path.join(Path(*parts[:parts.index('Image-Toolkit') + 1]), 'data')
            if not Path(start_dir).is_dir():
                 return os.getcwd()
            return start_dir
        except ValueError:
            return os.getcwd()

    def browse_file(self):
        start_dir = self._get_starting_dir()
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select File", 
            start_dir, 
            f"Image Files ({' '.join(['*' + ext for ext in SUPPORTED_IMG_FORMATS])});;All Files (*)"
        )
        if file_path:
            self.target_path.setText(file_path)

    def browse_directory(self):
        start_dir = self._get_starting_dir()
        directory = QFileDialog.getExistingDirectory(
            self, 
            "Select Directory to Delete", 
            start_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if directory:
            self.target_path.setText(directory)

    def is_valid(self, mode: str):
        path = self.target_path.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Invalid Path", "Please select a valid file or folder.")
            return False
        if mode == 'directory' and not os.path.isdir(path):
            QMessageBox.warning(self, "Invalid Target", "The 'Delete Directory & Contents' action requires a directory path.")
            return False
        return True

    # --- DUPLICATE SCANNING LOGIC (UNCHANGED) ---

    def start_duplicate_scan(self):
        target_dir = self.target_path.text().strip()
        if not target_dir or not os.path.isdir(target_dir):
            QMessageBox.warning(self, "Invalid Path", "Please select a valid directory in the 'Target path' field to scan.")
            return

        extensions = []
        if self.dropdown and self.selected_extensions:
            extensions = list(self.selected_extensions)
        elif not self.dropdown:
            extensions = self.join_list_str(self.target_extensions.text().strip())
        else:
            extensions = SUPPORTED_IMG_FORMATS

        self.btn_scan_dups.setEnabled(False)
        self.status_label.setText("Scanning for duplicates...")
        self.clear_gallery()
        
        # FIX: Instantiate QThread inside the function
        self.scan_thread = QThread()
        self.scan_worker = DuplicateScanWorker(target_dir, extensions)

        self.scan_worker.moveToThread(self.scan_thread)
        
        # This will now correctly connect to the newly created QThread
        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.finished.connect(self.on_scan_finished)
        self.scan_worker.error.connect(self.on_scan_error)
        
        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_worker.finished.connect(self.scan_worker.deleteLater)
        self.scan_thread.finished.connect(self.scan_thread.deleteLater)
        
        self.scan_thread.start()

    @Slot(dict)
    def on_scan_finished(self, results: Dict[str, List[str]]):
        self.btn_scan_dups.setEnabled(True)
        self.duplicate_results = results
        
        self.duplicate_path_list = []
        
        for file_hash, paths in results.items():
            if len(paths) > 1:
                self.duplicate_path_list.extend(paths)

        if not self.duplicate_path_list:
            QMessageBox.information(self, "No Duplicates", "No duplicate images found in the selected directory.")
            self.status_label.setText("Scan complete. No duplicates found.")
            # Ensure new comparison button is hidden
            self.btn_compare_properties.setVisible(False)
            self.btn_delete_selected_dups.setVisible(False)
            return

        self.status_label.setText(f"Found {len(results)} sets of duplicates ({len(self.duplicate_path_list)} total files).")
        
        self.gallery_scroll.setVisible(True)
        self.btn_delete_selected_dups.setVisible(True)
        self.btn_delete_selected_dups.setText(f"Delete Selected ({len(self.selected_duplicates)})")
        # Ensure new comparison button is visible
        self.btn_compare_properties.setVisible(len(self.selected_duplicates) > 0)
        
        self.load_thumbnails(self.duplicate_path_list)

    @Slot(str)
    def on_scan_error(self, error_msg):
        self.btn_scan_dups.setEnabled(True)
        QMessageBox.critical(self, "Scan Error", f"Error during scan: {error_msg}")
        self.status_label.setText("Scan failed.")

    def load_thumbnails(self, paths: list[str]):
        """Uses the batch loader to load images efficiently."""
        self.loading_dialog = QProgressDialog("Loading thumbnails...", None, 0, len(paths), self)
        self.loading_dialog.setWindowModality(Qt.WindowModal)
        self.loading_dialog.setMinimumDuration(0)
        self.loading_dialog.show()

        # FIX: Instantiate QThread inside the function
        self.loader_thread = QThread()
        self.loader_worker = BatchThumbnailLoaderWorker(paths, self.thumbnail_size)
        self.loader_worker.moveToThread(self.loader_thread)

        self.loader_thread.started.connect(self.loader_worker.run_load_batch)
        self.loader_worker.progress_updated.connect(self.update_loading_progress)
        
        self.loader_worker.batch_finished.connect(lambda: self.loader_worker.progress_updated.disconnect(self.update_loading_progress))
        self.loader_worker.batch_finished.connect(self.display_thumbnails)
        
        self.loader_worker.batch_finished.connect(self.loader_thread.quit)
        self.loader_worker.batch_finished.connect(self.loader_worker.deleteLater)
        self.loader_thread.finished.connect(self.loader_thread.deleteLater)

        self.loader_thread.start()

    @Slot(int, int)
    def update_loading_progress(self, current, total):
        # Store a local reference to the dialog object to prevent a race condition.
        # This ensures that even if another slot (like display_thumbnails) sets self.loading_dialog to None
        # immediately after the 'if' check, this function call retains a non-None reference to work with.
        dialog = self.loading_dialog 
        
        # FIX: Check the local reference before attempting to access methods
        if dialog:
            dialog.setValue(current)
            dialog.setLabelText(f"Loading {current} of {total}...")

    @Slot(list)
    def display_thumbnails(self, loaded_results: List[Tuple[str, QPixmap]]):
        self.clear_gallery_widgets()
        
        widget_width = self.gallery_scroll.viewport().width()
        columns = max(1, widget_width // self.approx_item_width)
        
        for idx, (path, pixmap) in enumerate(loaded_results):
            row = idx // columns
            col = idx % columns
            
            label = ClickableLabel(path)
            label.setFixedSize(self.thumbnail_size, self.thumbnail_size)
            label.setAlignment(Qt.AlignCenter)
            
            if not pixmap.isNull():
                label.setPixmap(pixmap)
            else:
                label.setText("Error")
                label.setStyleSheet("border: 1px solid red; color: red;")

            self._update_label_style(label, path in self.selected_duplicates)

            # Context Menu Connection
            label.path_clicked.connect(self.toggle_duplicate_selection)
            label.path_double_clicked.connect(self.open_full_preview)
            label.path_right_clicked.connect(self.show_image_context_menu)
            
            self.gallery_layout.addWidget(label, row, col)
            self.path_to_label_map[path] = label

        # FIX: Disconnection logic moved here for robustness
        if self.loader_worker:
            try:
                self.loader_worker.progress_updated.disconnect(self.update_loading_progress)
            except RuntimeError:
                pass

        if self.loading_dialog:
            self.loading_dialog.close()
            self.loading_dialog = None
        
    @Slot(str)
    def delete_single_file(self, path: str):
        """Handles the deletion of a single image file and updates the UI."""
        filename = os.path.basename(path)
        reply = QMessageBox.question(
            self, 
            "Confirm Single Deletion",
            f"Are you sure you want to PERMANENTLY delete the file:\n\n**{filename}**\n\nThis action cannot be undone!",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
            
        try:
            os.remove(path)
            
            # 1. Remove from all internal tracking lists
            self.selected_duplicates.discard(path)
            if path in self.duplicate_path_list:
                self.duplicate_path_list.remove(path)
                
            # 2. Remove from UI
            if path in self.path_to_label_map:
                lbl = self.path_to_label_map.pop(path)
                lbl.setParent(None)
                lbl.deleteLater()
            
            # 3. Re-render gallery (to fix layout gaps)
            self.load_thumbnails([p for p in self.duplicate_path_list if Path(p).exists()])
            
            # 4. Update status
            self.toggle_duplicate_selection("") # Triggers UI update logic without selecting/deselecting
            self.status_label.setText(f"File deleted: {filename}")
            QMessageBox.information(self, "Success", f"File deleted successfully: {filename}")
            
        except Exception as e:
            QMessageBox.critical(self, "Deletion Failed", f"Could not delete the file: {e}")

    def toggle_duplicate_selection(self, path):
        # The path parameter is ignored if it's the empty string used for general refresh
        if path:
            if path in self.selected_duplicates:
                self.selected_duplicates.remove(path)
                selected = False
            else:
                self.selected_duplicates.add(path)
                selected = True
            
            if path in self.path_to_label_map:
                self._update_label_style(self.path_to_label_map[path], selected)
        
        # Update visibility and text for both action buttons
        count = len(self.selected_duplicates)
        self.btn_delete_selected_dups.setText(f"Delete Selected ({count})")
        self.btn_compare_properties.setText(f"Compare Properties ({count})")
        self.btn_delete_selected_dups.setVisible(count > 0)
        self.btn_compare_properties.setVisible(count > 0)


    def handle_marquee_selection(self, paths_from_marquee: set, is_ctrl_pressed: bool):
        if not is_ctrl_pressed:
            self.selected_duplicates = paths_from_marquee
        else:
            self.selected_duplicates.update(paths_from_marquee)

        for path, label in self.path_to_label_map.items():
            self._update_label_style(label, path in self.selected_duplicates)
            
        # Update visibility and text for both action buttons
        count = len(self.selected_duplicates)
        self.btn_delete_selected_dups.setText(f"Delete Selected ({count})")
        self.btn_compare_properties.setText(f"Compare Properties ({count})")
        self.btn_delete_selected_dups.setVisible(count > 0)
        self.btn_compare_properties.setVisible(count > 0)


    def _update_label_style(self, label, is_selected):
        if is_selected:
            label.setStyleSheet("border: 3px solid #e74c3c;")
        else:
            label.setStyleSheet("border: 1px solid #4f545c;")

    def open_full_preview(self, path):
        try:
            start_index = self.duplicate_path_list.index(path)
        except ValueError:
            start_index = 0

        window = ImagePreviewWindow(
            image_path=path,
            db_tab_ref=None,
            parent=self,
            all_paths=self.duplicate_path_list,
            start_index=start_index
        )
        window.setAttribute(Qt.WA_DeleteOnClose)
        
        def remove_closed_win(event: Any):
            if window in self.open_preview_windows:
                 self.open_preview_windows.remove(window)
            event.accept()

        window.closeEvent = remove_closed_win

        self.open_preview_windows.append(window)
        window.show()

    def delete_selected_duplicates(self):
        if not self.selected_duplicates:
            return
            
        count = len(self.selected_duplicates)
        reply = QMessageBox.question(
            self, "Confirm Batch Delete",
            f"Are you sure you want to permanently delete **{count}** selected duplicate images?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            deleted_count = 0
            errors = []
            
            # Make a copy of the set as we are modifying it inside the loop
            for path in list(self.selected_duplicates):
                try:
                    os.remove(path)
                    deleted_count += 1
                    
                    self.selected_duplicates.discard(path)
                    if path in self.duplicate_path_list:
                        self.duplicate_path_list.remove(path)
                        
                except Exception as e:
                    errors.append(f"{os.path.basename(path)}: {str(e)}")
            
            # Reload thumbnails to reflect deletions
            self.load_thumbnails(self.duplicate_path_list)

            msg = f"Deleted {deleted_count} files."
            if errors:
                msg += f"\nErrors encountered:\n" + "\n".join(errors[:5])
            QMessageBox.information(self, "Deletion Complete", msg)
            
            # Final UI update
            self.toggle_duplicate_selection("") # Triggers UI update logic without selecting/deselecting

    def clear_gallery(self):
        self.selected_duplicates.clear()
        self.duplicate_path_list.clear()
        self.clear_gallery_widgets()
        self.gallery_scroll.setVisible(False)
        self.btn_delete_selected_dups.setVisible(False)
        self.btn_compare_properties.setVisible(False) # Hide compare button

    def clear_gallery_widgets(self):
        self.path_to_label_map.clear()
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # --- EXISTING DELETION LOGIC (Unchanged mainly) ---

    def start_deletion(self, mode: str):
        if not self.is_valid(mode):
            return

        config = self.collect(mode)
        config["require_confirm"] = self.confirm_checkbox.isChecked()

        self.btn_delete_files.setEnabled(False)
        self.btn_delete_directory.setEnabled(False)
        self.status_label.setText(f"Starting {mode} deletion...")
        QApplication.processEvents()

        self.worker = DeletionWorker(config)
        self.worker.confirm_signal.connect(self.handle_confirmation_request)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_deletion_done)
        self.worker.error.connect(self.on_deletion_error)
        self.worker.start()

    @Slot(str, int)
    def handle_confirmation_request(self, message: str, total_items: int):
        title = "Confirm Directory Deletion" if total_items == 1 and "directory" in message else "Confirm File Deletion"
        reply = QMessageBox.question(self, title, message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        self.worker.set_confirmation_response(reply == QMessageBox.Yes)

    def update_progress(self, deleted, total):
        self.status_label.setText(f"Deleted {deleted} of {total}...")

    def on_deletion_done(self, count, msg):
        self.btn_delete_files.setEnabled(True)
        self.btn_delete_directory.setEnabled(True)
        self.status_label.setText(msg)
        QMessageBox.information(self, "Complete", msg)
        self.worker = None

    def on_deletion_error(self, msg):
        self.btn_delete_files.setEnabled(True)
        self.btn_delete_directory.setEnabled(True)
        self.status_label.setText("Failed.")
        QMessageBox.critical(self, "Error", msg)
        self.worker = None

    def collect(self, mode: str) -> Dict[str, Any]:
        extensions = []
        if mode == 'files':
            if self.dropdown and self.selected_extensions:
                extensions = list(self.selected_extensions)
            elif not self.dropdown:
                extensions = self.join_list_str(self.target_extensions.text().strip())
            else:
                extensions = SUPPORTED_IMG_FORMATS
        
        return {
            "target_path": self.target_path.text().strip(),
            "mode": mode, 
            "target_extensions": [e.strip().lstrip('.') for e in extensions if e.strip()],
        }

    def get_default_config(self) -> dict:
        return {
            "target_path": "C:\\Default\\Target\\Path",
            "mode": "files",
            "target_extensions": ["jpg", "png"],
            "require_confirm": True
        }

    def set_config(self, config: dict):
        try:
            self.target_path.setText(config.get("target_path", ""))
            self.confirm_checkbox.setChecked(config.get("require_confirm", True))

            target_extensions = config.get("target_extensions", [])
            if self.dropdown:
                self.remove_all_extensions()
                for ext in target_extensions:
                    if ext in self.extension_buttons:
                        self.extension_buttons[ext].setChecked(True)
                        self.toggle_extension(ext, True)
            else:
                self.target_extensions.setText(", ".join(target_extensions))
        except Exception as e:
            print(f"Error applying DeleteTab config: {e}")
            QMessageBox.warning(self, "Config Error", f"Failed to apply some settings: {e}")

    @staticmethod
    def join_list_str(text: str):
        return [item.strip().lstrip('.') for item in text.replace(',', ' ').split() if item.strip()]
