import os

from PIL import Image
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from PySide6.QtWidgets import (
    QFormLayout, QHBoxLayout, QVBoxLayout,
    QApplication, QComboBox, QMessageBox,
    QLineEdit, QPushButton, QCheckBox,
    QProgressBar, QMenu, QFileDialog, 
    QLabel, QGroupBox, QWidget,
    QScrollArea, QGridLayout,
)
from PySide6.QtCore import Qt, Slot, QThread, QPoint
from PySide6.QtGui import QPixmap, QAction
from ...classes import AbstractClassTwoGalleries
from ...components import (
    OptionalField, MarqueeScrollArea, 
    ClickableLabel, PropertyComparisonDialog
)
from ...helpers import (
    DeletionWorker, 
    DuplicateScanWorker,
)
from ...styles.style import apply_shadow_effect, STYLE_SCAN_CANCEL
from ...windows import ImagePreviewWindow
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS


class DeleteTab(AbstractClassTwoGalleries):
    """
    DeleteTab with identical split-panel galleries for Scan Results and Selected Duplicates.
    Inherits core gallery and selection logic from BaseTwoGalleriesTab.
    """
    def __init__(self, dropdown=True):
        super().__init__()
        self.dropdown = dropdown
        self.worker: Optional[DeletionWorker] = None
        
        # --- State for duplicate handling ---
        self.duplicate_results: Dict[str, List[str]] = {}
        
        self.open_preview_windows: List[ImagePreviewWindow] = [] 
        
        # Thread references
        self.scan_thread = None
        self.scan_worker = None

        # --- Main Layout ---
        main_layout = QVBoxLayout(self)

        # Page Scroll Area
        page_scroll = QScrollArea()
        page_scroll.setWidgetResizable(True)
        page_scroll.setStyleSheet("QScrollArea { border: none; }")
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # --- 1. Delete Targets Group ---
        target_group = QGroupBox("Delete Targets")
        target_layout = QFormLayout(target_group)
        v_target_group = QVBoxLayout()

        browse_layout = QHBoxLayout()
        self.target_path = QLineEdit()
        self.target_path.setPlaceholderText("Path to delete OR scan for duplicates...")
        browse_layout.addWidget(self.target_path)

        btn_browse_scan = QPushButton("Browse...")
        btn_browse_scan.clicked.connect(self.browse_directory)
        apply_shadow_effect(btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        browse_layout.addWidget(btn_browse_scan)

        v_target_group.addLayout(browse_layout)
        target_layout.addRow("Target path:", v_target_group)
        content_layout.addWidget(target_group)

        # --- 2. Options Group ---
        settings_group = QGroupBox("Delete Settings")
        settings_layout = QFormLayout(settings_group)

        self.scan_method_combo = QComboBox()
        self.scan_method_combo.addItems([
            "All Files (List Directory Contents)",
            "Exact Match (Same File - Fastest)",
            "Similar: Perceptual Hash (Resized/Color Edits - Fast)",
            "Similar: ORB Feature Matching (Cropped/Rotated - Medium)",
            "Similar: SIFT Feature Matching (Robust - Slow)",
            "Similar: SSIM (High Quality - Slowest)",
            "Similar: Siamese Network (Semantic Match)"
        ])
        settings_layout.addRow("Scan Method:", self.scan_method_combo)
        content_layout.addWidget(settings_group)

        # --- 3. Galleries ---
        
        # Progress Bar
        self.scan_progress_bar = QProgressBar()
        self.scan_progress_bar.setRange(0, 0) 
        self.scan_progress_bar.setTextVisible(False)
        self.scan_progress_bar.hide()
        content_layout.addWidget(self.scan_progress_bar)
        
        # A. Top Gallery: Found Duplicates
        self.found_gallery_scroll = MarqueeScrollArea()
        self.found_gallery_scroll.setWidgetResizable(True)
        self.found_gallery_scroll.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")
        self.found_gallery_scroll.setMinimumHeight(600)
        
        self.gallery_widget = QWidget()
        self.gallery_widget.setStyleSheet("background-color: #2c2f33;")
        self.found_gallery_layout = QGridLayout(self.gallery_widget)
        self.found_gallery_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.found_gallery_scroll.setWidget(self.gallery_widget)
        self.found_gallery_scroll.selection_changed.connect(self.handle_marquee_selection)
        content_layout.addWidget(self.found_gallery_scroll, 1)

        # Add Pagination Widget (Found) - Moved to Bottom
        if hasattr(self, 'found_pagination_widget'):
            content_layout.addWidget(self.found_pagination_widget, 0, Qt.AlignmentFlag.AlignCenter)
        
        # B. Bottom Gallery: Selected for Deletion
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

        # Add Pagination Widget (Selected) - Moved to Bottom
        if hasattr(self, 'selected_pagination_widget'):
            content_layout.addWidget(self.selected_pagination_widget, 0, Qt.AlignmentFlag.AlignCenter)

        # Actions for Duplicates
        dup_actions_layout = QHBoxLayout()
        self.btn_compare_properties = QPushButton("Compare Properties (0)")
        apply_shadow_effect(self.btn_compare_properties, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_compare_properties.clicked.connect(self.show_comparison_dialog)
        self.btn_compare_properties.setVisible(False)
        dup_actions_layout.addWidget(self.btn_compare_properties)

        self.btn_delete_selected_dups = QPushButton("Delete Selected Duplicates")
        self.btn_delete_selected_dups.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 8px;")
        apply_shadow_effect(self.btn_delete_selected_dups, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_delete_selected_dups.clicked.connect(self.delete_selected_duplicates)
        self.btn_delete_selected_dups.setVisible(False)
        dup_actions_layout.addWidget(self.btn_delete_selected_dups)

        content_layout.addLayout(dup_actions_layout)

        # Other options
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

        self.confirm_checkbox = QCheckBox("Require confirmation before delete (recommended)")
        self.confirm_checkbox.setChecked(True)
        settings_layout.addRow(self.confirm_checkbox)

        # --- 4. Standard Delete Buttons ---
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

        self.btn_delete_files = QPushButton("Scan Directory")
        self.btn_delete_files.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(self.btn_delete_files, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_delete_files.clicked.connect(self.toggle_scan)
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

        page_scroll.setWidget(content_widget)
        main_layout.addWidget(page_scroll)
        self.setLayout(main_layout)
        
        self.clear_galleries()

    # --- IMPLEMENTING ABSTRACT METHODS ---

    def create_card_widget(self, path: str, pixmap: Optional[QPixmap], is_selected: bool) -> QWidget:
        thumb_size = self.thumbnail_size
        card_wrapper = ClickableLabel(path)
        card_wrapper.setFixedSize(thumb_size + 10, thumb_size + 10)
        
        # Base class requirements
        card_wrapper.get_pixmap = lambda: img_label.pixmap()
        card_wrapper.set_selected_style = lambda s: self._update_card_style(img_label, s)

        card_layout = QVBoxLayout(card_wrapper)
        card_layout.setContentsMargins(0, 0, 0, 0)
        
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignCenter)
        img_label.setFixedSize(thumb_size, thumb_size)
        
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(thumb_size, thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            img_label.setPixmap(scaled)
        else:
            img_label.setText("Loading...")
            img_label.setStyleSheet("color: #999; border: 1px dashed #666;")
            
        card_layout.addWidget(img_label)
        card_wrapper.setLayout(card_layout)
        
        # Interaction
        card_wrapper.path_double_clicked.connect(self.open_full_preview)
        card_wrapper.path_right_clicked.connect(self.show_image_context_menu)
        
        self._update_card_style(img_label, is_selected)
        return card_wrapper

    def update_card_pixmap(self, widget: QWidget, pixmap: Optional[QPixmap]):
        """Lazy loading callback."""
        if not isinstance(widget, ClickableLabel): return
        
        img_label = widget.findChild(QLabel)
        if not img_label: return

        if pixmap and not pixmap.isNull():
            thumb_size = self.thumbnail_size
            scaled = pixmap.scaled(thumb_size, thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            img_label.setPixmap(scaled)
            img_label.setText("") # Clear Loading text
        else:
            img_label.clear()
            img_label.setText("Loading...")
            
        # Reapply style (removes dashed border)
        is_selected = widget.path in self.selected_files
        self._update_card_style(img_label, is_selected)

    def _update_card_style(self, img_label: QLabel, is_selected: bool):
        if is_selected:
            img_label.setStyleSheet("border: 3px solid #5865f2; background-color: #36393f;")
        else:
            if img_label.pixmap() and not img_label.pixmap().isNull():
                img_label.setStyleSheet("border: 1px solid #4f545c; background-color: #36393f;")
            else:
                img_label.setStyleSheet("border: 1px dashed #666; color: #999;")

    def on_selection_changed(self):
        count = len(self.selected_files)
        self.btn_delete_selected_dups.setText(f"Delete Selected ({count})")
        self.btn_compare_properties.setText(f"Compare Properties ({count})")
        
        has_dups = len(self.found_files) > 0
        self.btn_delete_selected_dups.setVisible(has_dups)
        self.btn_compare_properties.setVisible(has_dups)
        self.btn_delete_selected_dups.setEnabled(count > 0)
        self.btn_compare_properties.setEnabled(count > 0)

    # --- SCANNING LOGIC ---

    @Slot()
    def toggle_scan(self):
        if self.scan_thread and self.scan_thread.isRunning():
            self.cancel_scan()
        else:
            self.start_duplicate_scan()

    @Slot()
    def cancel_scan(self):
        if self.scan_thread and self.scan_thread.isRunning():
            self.status_label.setText("Stopping...")
            self.scan_thread.requestInterruption()
            self.scan_thread.quit()
            self.scan_thread.wait() 
            self.scan_worker = None
            self.scan_thread = None
            QMessageBox.information(self, "Scan Cancelled", "The image scanning process was manually cancelled.")
            self._reset_scan_ui("Scan cancelled.")
            
    def _reset_scan_ui(self, status_message: str):
        self.btn_delete_files.setText("Scan Directory")
        # Reuse local style definition or import it
        SHARED_BUTTON_STYLE = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #667eea, stop:1 #764ba2);
                color: white; font-weight: bold; font-size: 14px;
                padding: 14px 8px; border-radius: 10px; min-height: 44px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #764ba2, stop:1 #667eea); }
        """
        self.btn_delete_files.setStyleSheet(SHARED_BUTTON_STYLE)
        self.btn_delete_files.setEnabled(True)
        self.scan_progress_bar.hide()
        self.status_label.setText(status_message)

    def start_duplicate_scan(self):
        target_dir = self.target_path.text().strip()
        if not target_dir or not os.path.isdir(target_dir):
            QMessageBox.warning(self, "Invalid Path", "Please select a valid directory in the 'Target path' field to scan.")
            return

        extensions = []
        if self.dropdown and self.selected_extensions: extensions = list(self.selected_extensions)
        elif not self.dropdown: extensions = self.join_list_str(self.target_extensions.text().strip())
        else: extensions = SUPPORTED_IMG_FORMATS
            
        method_text = self.scan_method_combo.currentText()
        if "All Files" in method_text:
            method = "all_files"
            status_msg = "Listing all supported files in directory..."
        elif "Exact Match" in method_text: 
            method = "exact"
            status_msg = "Starting exact scan..."
        elif "Perceptual Hash" in method_text: 
            method = "phash"
            status_msg = "Starting similarity scan..."
        elif "SSIM" in method_text:
            method = "ssim"
            status_msg = "Starting SSIM scan..."
        elif "SIFT" in method_text:
            method = "sift"
            status_msg = "Starting SIFT scan..."
        elif "Siamese" in method_text:
            method = "siamese"
            status_msg = "Initializing Siamese Network..."
        else: 
            method = "orb"
            status_msg = "Starting ORB scan..."

        self.btn_delete_files.setEnabled(False) 
        self.btn_delete_files.setText("Cancel Scan")
        self.btn_delete_files.setStyleSheet(STYLE_SCAN_CANCEL)
        self.btn_delete_files.setEnabled(True)
        self.scan_progress_bar.show()
        
        self.status_label.setText(status_msg)
        self.clear_galleries() 
        
        self.scan_thread = QThread()
        self.scan_worker = DuplicateScanWorker(target_dir, extensions, method=method)
        self.scan_worker.moveToThread(self.scan_thread)
        
        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.status.connect(self.handle_scan_status_update)
        self.scan_worker.finished.connect(self.on_scan_finished)
        self.scan_worker.error.connect(self.on_scan_error)
        
        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_worker.finished.connect(self.scan_worker.deleteLater)
        self.scan_thread.finished.connect(self.on_scan_thread_finished)
        self.scan_thread.finished.connect(self.scan_thread.deleteLater)
        
        self.scan_thread.start()
        
    @Slot()
    def on_scan_thread_finished(self):
        self.scan_thread = None
        self.scan_worker = None

    @Slot(str)
    def handle_scan_status_update(self, message: str):
        self.status_label.setText(message)
        self.scan_progress_bar.setRange(0, 0)

    @Slot(dict)
    def on_scan_finished(self, results: Dict[str, List[str]]):
        self._reset_scan_ui("Scan complete.")
        self.duplicate_results = results
        
        flattened_paths = []

        is_all_files_scan = "All Files" in self.scan_method_combo.currentText()
        for gid, paths in results.items():
            if len(paths) > 1 or is_all_files_scan:
                flattened_paths.extend(paths)
        
        if not flattened_paths:
            QMessageBox.information(self, "No Matches", "No duplicate or similar images found.")
            return
            
        self.status_label.setText(f"Found {len(results)} groups ({len(flattened_paths)} files).")
        
        # Use Base Class method to load thumbnails into top gallery
        self.start_loading_thumbnails(sorted(flattened_paths))

    @Slot(str)
    def on_scan_error(self, error_msg):
        self._reset_scan_ui("Scan failed.")
        QMessageBox.critical(self, "Scan Error", f"Error during scan: {error_msg}")

    # --- ACTION LOGIC ---

    def delete_selected_duplicates(self):
        if not self.selected_files:
            return
        count = len(self.selected_files)
        reply = QMessageBox.question(self, "Confirm Batch Delete", f"Permanently delete **{count}** selected files?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No:
            return
        deleted_count = 0
        errors = []
        for path in list(self.selected_files):
            try:
                os.remove(path)
                deleted_count += 1
                self.selected_files.remove(path)
                if path in self.found_files:
                    self.found_files.remove(path)
                
                # Update visual widgets immediately
                if path in self.path_to_label_map:
                    wrapper = self.path_to_label_map.pop(path)
                    wrapper.deleteLater()
                    
            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {str(e)}")
        
        # Reflow base layouts
        self._reflow_layout(self.found_gallery_layout, self._current_found_cols)
        self.refresh_selected_panel()
        self.on_selection_changed()
        
        msg = f"Deleted {deleted_count} files."
        if errors:
            msg += f"\nErrors:\n" + "\n".join(errors[:5])
        QMessageBox.information(self, "Deletion Complete", msg)

    def delete_single_file(self, path: str):
        filename = os.path.basename(path)
        reply = QMessageBox.question(self, "Confirm Single Deletion", f"Are you sure you want to PERMANENTLY delete:\n**{filename}**?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return
        try:
            os.remove(path)
            if path in self.selected_files: self.selected_files.remove(path)
            if path in self.found_files: self.found_files.remove(path)
            
            if path in self.path_to_label_map:
                wrapper = self.path_to_label_map.pop(path)
                wrapper.deleteLater()

            self._reflow_layout(self.found_gallery_layout, self._current_found_cols)
            self.refresh_selected_panel()
            self.on_selection_changed()
            self.status_label.setText(f"File deleted: {filename}")
            QMessageBox.information(self, "Success", f"Deleted: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Deletion Failed", f"Error: {e}")

    # --- PREVIEWS & PROPERTIES ---

    def get_image_properties(self, file_path: str) -> Dict[str, Any]:
        if not Path(file_path).exists():
            return {"Error": "File not found."}
        props = {"Path": file_path, "File Name": os.path.basename(file_path)}
        try:
            stat = os.stat(file_path)
            props["File Size"] = f"{stat.st_size / (1024 * 1024):.2f} MB ({stat.st_size} bytes)"
            props["Last Modified"] = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except OSError:
            props["File Size"] = "N/A"
        try:
            if 'Image' in globals():
                img = Image.open(file_path)
                props["Width"] = f"{img.width} px"
                props["Height"] = f"{img.height} px"
                props["Format"] = img.format
                img.close()
            else: props["Width"] = "N/A"
        except Exception: props["Width"] = "N/A"
        return props

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)
        prop_action = QAction("🖼️ Show Image Properties", self)
        prop_action.triggered.connect(lambda: self.show_image_properties_dialog(path))
        menu.addAction(prop_action)
        if len(self.selected_files) > 1:
            cmp_action = QAction("📊 Compare Selected Properties", self)
            cmp_action.triggered.connect(self.show_comparison_dialog)
            menu.addAction(cmp_action)
        menu.addSeparator()
        view_action = QAction("🔍 View Full Size Preview", self)
        view_action.triggered.connect(lambda: self.open_full_preview(path))
        menu.addAction(view_action)
        
        is_selected = path in self.selected_files
        toggle_text = "Deselect (Keep)" if is_selected else "Select (Mark for Delete)"
        toggle_action = QAction(toggle_text, self)
        toggle_action.triggered.connect(lambda: self.toggle_selection(path))
        menu.addAction(toggle_action)
        
        menu.addSeparator()
        # send_to_tab_signal needs to be defined if used, removing for now as not in snippet scope
        
        delete_action = QAction("🗑️ Delete This File (Permanent)", self)
        delete_action.triggered.connect(lambda: self.delete_single_file(path))
        menu.addAction(delete_action)
        menu.exec(global_pos)
        
    @Slot(str)
    def show_image_properties_dialog(self, path: str):
        properties = self.get_image_properties(path)
        if "Error" in properties: QMessageBox.critical(self, "Error Reading File", properties["Error"]); return
        prop_text = f"**File:** {os.path.basename(path)}\n**Path:** {path}\n\n**Technical Details**\n"
        for key, value in properties.items():
            if key not in ["Path", "File Name"]: prop_text += f"  - **{key}:** {value}\n"
        msg = QMessageBox(self)
        msg.setWindowTitle("Image Properties")
        msg.setTextFormat(Qt.MarkdownText)
        msg.setText(prop_text)
        msg.setIcon(QMessageBox.Information)
        msg.exec()

    @Slot()
    def show_comparison_dialog(self):
        if not self.selected_files: QMessageBox.warning(self, "No Selection", "Please select at least one image to compare."); return
        selected_paths = list(self.selected_files)
        if len(selected_paths) > 10:
             reply = QMessageBox.question(self, "Large Selection", f"Selected {len(selected_paths)} images. Compare first 10?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
             if reply == QMessageBox.Yes: selected_paths = selected_paths[:10];
             else: return
        property_list = []
        for path in selected_paths:
            if Path(path).exists(): property_list.append(self.get_image_properties(path))
            else: property_list.append({"File Name": os.path.basename(path), "Path": path, "Error": "File not found."})
        dialog = PropertyComparisonDialog(property_list, self)
        dialog.exec()

    def open_full_preview(self, path):
        try:
            start_index = self.found_files.index(path)
        except ValueError:
            start_index = 0
        window = ImagePreviewWindow(image_path=path, db_tab_ref=None, parent=self, all_paths=self.found_files, start_index=start_index)
        window.setAttribute(Qt.WA_DeleteOnClose)
        window.show()
        self.open_preview_windows.append(window)

    # --- STANDARD DELETION LOGIC (Directory/File) ---

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

    def browse_directory(self):
        d = QFileDialog.getExistingDirectory(self, "Select Directory", self.last_browsed_dir)
        if d:
            self.target_path.setText(d)
            self.last_browsed_dir = d
        
    def is_valid(self, mode: str):
        p = self.target_path.text().strip()
        if not p or not os.path.exists(p):
            QMessageBox.warning(self, "Invalid", "Select valid file/folder.")
            return False
        if mode == 'directory' and not os.path.isdir(p):
            QMessageBox.warning(self, "Invalid", "Directory required.")
            return False
        return True

    def toggle_extension(self, ext, checked):
        btn = self.extension_buttons[ext]
        if checked:
            self.selected_extensions.add(ext)
            btn.setStyleSheet("QPushButton:checked { background-color: #3320b5; color: white; }")
            apply_shadow_effect(btn, "#000000", 8, 0, 3)
        else:
            self.selected_extensions.discard(ext)
            btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")
            apply_shadow_effect(btn, "#000000", 8, 0, 3)

    def add_all_extensions(self):
        for ext, btn in self.extension_buttons.items():
            btn.setChecked(True)
            self.toggle_extension(ext, True)

    def remove_all_extensions(self):
        for ext, btn in self.extension_buttons.items():
            btn.setChecked(False)
            self.toggle_extension(ext, False)

    def collect(self, mode: str = "files") -> Dict[str, Any]:
        exts = []
        if self.dropdown and self.selected_extensions is not None:
            exts = list(self.selected_extensions)
        elif not self.dropdown and hasattr(self, 'target_extensions'):
            exts = self.join_list_str(self.target_extensions.text().strip())
            
        return {
            "target_path": self.target_path.text().strip(), 
            "mode": mode,
            "target_extensions": [e.strip().lstrip('.') for e in exts if e.strip()],
            "scan_method": self.scan_method_combo.currentText(),
            "require_confirm": self.confirm_checkbox.isChecked(),
        }

    @staticmethod
    def join_list_str(text: str):
        return [item.strip().lstrip('.') for item in text.replace(',', ' ').split() if item.strip()]

    def get_default_config(self) -> dict:
        """Returns the default configuration dictionary for the DeleteTab."""
        extensions = SUPPORTED_IMG_FORMATS if self.dropdown else "jpg png"
        return {
            "target_path": "",
            "scan_method": "All Files (List Directory Contents)",
            "target_extensions": extensions,
            "require_confirm": True,
        }

    def set_config(self, config: dict):
        """Applies the configuration dictionary to the DeleteTab UI elements."""
        try:
            # 1. Target Path
            target_path = config.get("target_path", "")
            self.target_path.setText(target_path)
            
            # 2. Scan Method
            scan_method = config.get("scan_method", "All Files (List Directory Contents)")
            index = self.scan_method_combo.findText(scan_method)
            if index != -1:
                self.scan_method_combo.setCurrentIndex(index)
            
            # 3. Target Extensions (Handling Dropdown vs. LineEdit)
            extensions = config.get("target_extensions", [])
            if self.dropdown:
                self.remove_all_extensions()
                for ext in extensions:
                    if ext in self.extension_buttons:
                        self.extension_buttons[ext].setChecked(True)
                        self.toggle_extension(ext, True)
                if extensions and len(extensions) < len(SUPPORTED_IMG_FORMATS):
                    self.extensions_field.set_open(True)
            elif hasattr(self, 'target_extensions'):
                self.target_extensions.setText(" ".join(extensions))
                if extensions:
                    self.extensions_field.set_open(True)
            
            # 4. Confirmation Checkbox
            self.confirm_checkbox.setChecked(config.get("require_confirm", True))
            
            print(f"DeleteTab configuration loaded.")

        except Exception as e:
            print(f"Error applying DeleteTab config: {e}")
            QMessageBox.warning(self, "Config Error", f"Failed to apply some settings: {e}")