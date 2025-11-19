import os

from PIL import Image
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from PySide6.QtWidgets import (
    QScrollArea, QGridLayout, QProgressDialog,
    QMessageBox, QLabel, QGroupBox, QWidget,
    QFormLayout, QHBoxLayout, QVBoxLayout,
    QLineEdit, QPushButton, QCheckBox,
    QMenu, QFileDialog, QApplication,
)
from PySide6.QtGui import QPixmap, QAction
from PySide6.QtCore import Qt, Slot, QThread, QPoint

from .base_tab import BaseTab
from ..components import OptionalField, MarqueeScrollArea, ClickableLabel, PropertyComparisonDialog
from ..helpers import DeletionWorker, BatchThumbnailLoaderWorker, DuplicateScanWorker
from ..styles.style import apply_shadow_effect
from ..windows import ImagePreviewWindow
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS


class DeleteTab(BaseTab):
    """
    DeleteTab with identical split-panel galleries for Scan Results and Selected Duplicates.
    """
    def __init__(self, dropdown=True):
        super().__init__()
        self.dropdown = dropdown
        self.worker: Optional[DeletionWorker] = None
        
        # --- State for duplicate handling ---
        self.duplicate_results: Dict[str, List[str]] = {}
        self.duplicate_path_list: List[str] = []
        self.selected_duplicates: List[str] = [] 
        
        # UI Maps
        self.path_to_wrapper_map: Dict[str, ClickableLabel] = {}
        self.selected_card_map: Dict[str, ClickableLabel] = {}
        
        self.thumbnail_size = 150
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width + 20 # +20 for wrapper padding
        
        self.open_preview_windows: List[ImagePreviewWindow] = [] 
        
        # Thread references
        self.scan_thread = None
        self.scan_worker = None
        self.loader_thread = None
        self.loader_worker = None
        self.loading_dialog = None

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

        # --- 2. Options Group ---
        settings_group = QGroupBox("Options")
        settings_layout = QFormLayout(settings_group)

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

        content_layout.addWidget(settings_group)

        # --- 3. Duplicate Scanner & Gallery Group ---
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

        # --- Split Gallery Layout ---
        
        # A. Top Gallery: Found Duplicates (Preview)
        self.gallery_scroll = MarqueeScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")
        self.gallery_scroll.setMinimumHeight(400)
        
        self.gallery_widget = QWidget()
        self.gallery_widget.setStyleSheet("background-color: #2c2f33;")
        self.gallery_layout = QGridLayout(self.gallery_widget)
        self.gallery_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft) # Same alignment as Selected
        self.gallery_layout.setSpacing(10)
        
        self.gallery_scroll.setWidget(self.gallery_widget)
        self.gallery_scroll.setVisible(False)
        self.gallery_scroll.selection_changed.connect(self.handle_marquee_selection)
        dup_layout.addWidget(self.gallery_scroll)
        
        # B. Bottom Gallery: Selected for Deletion
        self.selected_scroll = MarqueeScrollArea()
        self.selected_scroll.setWidgetResizable(True)
        self.selected_scroll.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")
        self.selected_scroll.setMinimumHeight(200)
        self.selected_scroll.setVisible(False)

        self.selected_widget = QWidget()
        self.selected_widget.setStyleSheet("background-color: #2c2f33;")
        self.selected_layout = QGridLayout(self.selected_widget)
        self.selected_layout.setSpacing(10)
        self.selected_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft) 
        
        self.selected_scroll.setWidget(self.selected_widget)
        dup_layout.addWidget(self.selected_scroll)

        # Actions for Duplicates
        dup_actions_layout = QHBoxLayout()
        
        self.btn_compare_properties = QPushButton("Compare Properties (0)")
        self.btn_compare_properties.setStyleSheet("""
            QPushButton { background-color: #3498db; color: white; font-weight: bold; padding: 8px; }
            QPushButton:hover { background-color: #2980b9; }
        """)
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

        dup_layout.addLayout(dup_actions_layout)
        content_layout.addWidget(self.dup_group)

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

        page_scroll.setWidget(content_widget)
        main_layout.addWidget(page_scroll)
        self.setLayout(main_layout)

    # --- HELPER: Create Uniform Gallery Card ---
    def _create_gallery_card(self, path: str, pixmap: Optional[QPixmap], is_selected: bool) -> ClickableLabel:
        """Creates a styled card widget used in both galleries."""
        thumb_size = self.thumbnail_size
        
        # Wrapper (ClickableLabel)
        card_wrapper = ClickableLabel(path)
        card_wrapper.setFixedSize(thumb_size + 10, thumb_size + 10)
        
        # Internal Layout
        card_layout = QVBoxLayout(card_wrapper)
        card_layout.setContentsMargins(0, 0, 0, 0)
        
        # Image Label
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignCenter)
        img_label.setFixedSize(thumb_size, thumb_size)
        
        # Apply Content
        if pixmap and not pixmap.isNull():
            # If pixmap is larger than thumb_size, scale it
            if pixmap.width() > thumb_size or pixmap.height() > thumb_size:
                 scaled = pixmap.scaled(thumb_size, thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                 img_label.setPixmap(scaled)
            else:
                 img_label.setPixmap(pixmap)
        else:
            img_label.setText("Error" if pixmap is not None else "Loading")
            img_label.setStyleSheet("color: #e74c3c; border: 1px solid #e74c3c;")
        
        card_layout.addWidget(img_label)
        card_wrapper.setLayout(card_layout)
        
        # Apply Style
        self._update_card_style(img_label, is_selected)
        
        return card_wrapper

    def _update_card_style(self, img_label: QLabel, is_selected: bool):
        """Updates the border of the inner image label based on selection state."""
        if is_selected:
            img_label.setStyleSheet("border: 3px solid #5865f2; background-color: #36393f;")
        else:
            img_label.setStyleSheet("border: 1px solid #4f545c; background-color: #36393f;")

    # --- HELPER: Get Image Properties ---
    def get_image_properties(self, file_path: str) -> Dict[str, Any]:
        if not Path(file_path).exists():
            return {"Error": "File not found."}

        props = {"Path": file_path, "File Name": os.path.basename(file_path)}
        try:
            stat = os.stat(file_path)
            props["File Size"] = f"{stat.st_size / (1024 * 1024):.2f} MB ({stat.st_size} bytes)"
            props["Last Modified"] = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            props["Created"] = datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
        except OSError:
            props["File Size"] = "N/A"
            props["Last Modified"] = "N/A"
            props["Created"] = "N/A"

        try:
            if 'Image' in globals():
                img = Image.open(file_path)
                props["Width"] = f"{img.width} px"
                props["Height"] = f"{img.height} px"
                props["Format"] = img.format
                props["Mode"] = img.mode
                img.close()
            else:
                props["Width"] = "N/A"
                props["Height"] = "N/A"
                props["Format"] = "N/A"
                props["Mode"] = "N/A"
        except Exception:
            props["Width"] = "N/A"
            props["Height"] = "N/A"
            props["Format"] = "N/A"
            props["Mode"] = "N/A"
            
        return props

    # --- CONTEXT MENU ---
    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)
        
        # 1. Properties
        prop_action = QAction("🖼️ Show Image Properties", self)
        prop_action.triggered.connect(lambda: self.show_image_properties_dialog(path))
        menu.addAction(prop_action)

        # 2. Compare (New)
        if len(self.selected_duplicates) > 1:
             cmp_action = QAction("📊 Compare Selected Properties", self)
             cmp_action.triggered.connect(self.show_comparison_dialog)
             menu.addAction(cmp_action)

        menu.addSeparator()

        # 3. Preview
        view_action = QAction("🔍 View Full Size Preview", self)
        view_action.triggered.connect(lambda: self.open_full_preview(path))
        menu.addAction(view_action)
        
        # 4. Selection
        is_selected = path in self.selected_duplicates
        toggle_text = "Deselect (Keep)" if is_selected else "Select (Mark for Delete)"
        toggle_action = QAction(toggle_text, self)
        toggle_action.triggered.connect(lambda: self.toggle_duplicate_selection(path))
        menu.addAction(toggle_action)
        
        menu.addSeparator()
        
        # 5. Delete
        delete_action = QAction("🗑️ Delete This File (Permanent)", self)
        delete_action.triggered.connect(lambda: self.delete_single_file(path))
        menu.addAction(delete_action)
        
        menu.exec(global_pos)
        
    @Slot(str)
    def show_image_properties_dialog(self, path: str):
        properties = self.get_image_properties(path)
        if "Error" in properties:
             QMessageBox.critical(self, "Error Reading File", properties["Error"])
             return

        prop_text = f"**File:** {os.path.basename(path)}\n**Path:** {path}\n\n**Technical Details**\n"
        for key, value in properties.items():
            if key not in ["Path", "File Name"]:
                prop_text += f"  - **{key}:** {value}\n"
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Image Properties")
        msg.setTextFormat(Qt.MarkdownText)
        msg.setText(prop_text)
        msg.setIcon(QMessageBox.Information)
        msg.exec()

    # --- COMPARISON DIALOG ---
    @Slot()
    def show_comparison_dialog(self):
        if not self.selected_duplicates:
            QMessageBox.warning(self, "No Selection", "Please select at least one image to compare.")
            return

        selected_paths = list(self.selected_duplicates)
        if len(selected_paths) > 10:
             reply = QMessageBox.question(
                self, "Large Selection",
                f"Selected {len(selected_paths)} images. Compare first 10?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
             if reply == QMessageBox.Yes:
                 selected_paths = selected_paths[:10]
             else:
                 return

        property_list = []
        for path in selected_paths:
            if Path(path).exists():
                property_list.append(self.get_image_properties(path))
            else:
                 property_list.append({"File Name": os.path.basename(path), "Path": path, "Error": "File not found."})
        
        dialog = PropertyComparisonDialog(property_list, self)
        dialog.exec()

    # --- GALLERY UTILS ---
    def _columns(self) -> int:
        w = self.gallery_scroll.viewport().width()
        return max(1, w // self.approx_item_width)

    def _clear_gallery(self, layout: QGridLayout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # --- SELECTION HANDLING ---
    def toggle_duplicate_selection(self, path):
        if not path: 
            self._update_action_buttons()
            return

        if path in self.selected_duplicates:
            self.selected_duplicates.remove(path)
            selected = False
        else:
            self.selected_duplicates.append(path)
            selected = True
        
        # Update Style in Top Gallery (Preview)
        if path in self.path_to_wrapper_map:
            wrapper = self.path_to_wrapper_map[path]
            # Find inner label to update border
            inner_label = wrapper.findChild(QLabel)
            if inner_label:
                self._update_card_style(inner_label, selected)
        
        # Refresh Bottom Gallery (Selected)
        self._refresh_selected_panel()
        self._update_action_buttons()

    def handle_marquee_selection(self, paths_from_marquee: set, is_ctrl_pressed: bool):
        ordered_current = self.selected_duplicates.copy()
        
        if not is_ctrl_pressed:
            new_ordered = [p for p in ordered_current if p in paths_from_marquee]
            newly_added = [p for p in paths_from_marquee if p not in ordered_current]
            self.selected_duplicates = new_ordered + newly_added
            paths_to_update = paths_from_marquee.union(set(ordered_current))
        else:
            newly_added = [p for p in paths_from_marquee if p not in ordered_current]
            self.selected_duplicates.extend(newly_added)
            paths_to_update = set(newly_added)

        for path in paths_to_update:
             if path in self.path_to_wrapper_map:
                wrapper = self.path_to_wrapper_map[path]
                inner_label = wrapper.findChild(QLabel)
                if inner_label:
                    self._update_card_style(inner_label, path in self.selected_duplicates)
            
        self._refresh_selected_panel()
        self._update_action_buttons()

    def _update_action_buttons(self):
        count = len(self.selected_duplicates)
        self.btn_delete_selected_dups.setText(f"Delete Selected ({count})")
        self.btn_compare_properties.setText(f"Compare Properties ({count})")
        
        has_dups = len(self.duplicate_path_list) > 0
        self.btn_delete_selected_dups.setVisible(has_dups)
        self.btn_compare_properties.setVisible(has_dups)
        
        self.btn_delete_selected_dups.setEnabled(count > 0)
        self.btn_compare_properties.setEnabled(count > 0)

    def _refresh_selected_panel(self):
        """Rebuilds the bottom panel using the same card style."""
        self.selected_widget.setUpdatesEnabled(False)
        self._clear_gallery(self.selected_layout)
        self.selected_card_map = {}
        
        paths = self.selected_duplicates
        columns = max(1, self.selected_scroll.viewport().width() // self.approx_item_width)
        
        if not paths:
            empty_label = QLabel("Select images from the scan results above to mark them for deletion.")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #b9bbbe; padding: 50px;")
            self.selected_layout.addWidget(empty_label, 0, 0, 1, columns)
            self.selected_widget.setUpdatesEnabled(True)
            return

        for i, path in enumerate(paths):
            # Attempt to retrieve cached pixmap from the top gallery wrapper
            pixmap = None
            if path in self.path_to_wrapper_map:
                wrapper = self.path_to_wrapper_map[path]
                inner_label = wrapper.findChild(QLabel)
                if inner_label and inner_label.pixmap():
                    pixmap = inner_label.pixmap()
            
            # Create Card
            card = self._create_gallery_card(path, pixmap, is_selected=True)
            
            # Connections
            card.path_clicked.connect(lambda checked, p=path: self.toggle_duplicate_selection(p))
            card.path_double_clicked.connect(self.open_full_preview)
            card.path_right_clicked.connect(self.show_image_context_menu)
            
            row = i // columns
            col = i % columns
            self.selected_card_map[path] = card
            self.selected_layout.addWidget(card, row, col, Qt.AlignLeft | Qt.AlignTop)
            
        self.selected_widget.setUpdatesEnabled(True)
        self.selected_widget.adjustSize()

    # --- DUPLICATE SCAN LOGIC ---

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
        
        self.scan_thread = QThread()
        self.scan_worker = DuplicateScanWorker(target_dir, extensions)
        self.scan_worker.moveToThread(self.scan_thread)
        
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
            self._update_action_buttons()
            return

        self.status_label.setText(f"Found {len(results)} sets of duplicates ({len(self.duplicate_path_list)} total files).")
        
        self.gallery_scroll.setVisible(True)
        self.selected_scroll.setVisible(True)
        
        self._update_action_buttons()
        self.load_thumbnails(self.duplicate_path_list)

    @Slot(str)
    def on_scan_error(self, error_msg):
        self.btn_scan_dups.setEnabled(True)
        QMessageBox.critical(self, "Scan Error", f"Error during scan: {error_msg}")
        self.status_label.setText("Scan failed.")

    def load_thumbnails(self, paths: list[str]):
        self.loading_dialog = QProgressDialog("Loading thumbnails...", "Cancel", 0, 0, self)
        self.loading_dialog.setWindowModality(Qt.WindowModal)
        self.loading_dialog.setWindowTitle("Please Wait")
        self.loading_dialog.setMinimumDuration(0)
        self.loading_dialog.setCancelButton(None)
        self.loading_dialog.setMaximum(len(paths))
        self.loading_dialog.show()

        self.loader_thread = QThread()
        self.loader_worker = BatchThumbnailLoaderWorker(paths, self.thumbnail_size)
        self.loader_worker.moveToThread(self.loader_thread)

        self.loader_thread.started.connect(self.loader_worker.run_load_batch)
        self.loader_worker.progress_updated.connect(self.update_loading_progress)
        
        self.loader_worker.batch_finished.connect(self.handle_batch_finished)
        
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
    def handle_batch_finished(self, loaded_results: List[Tuple[str, QPixmap]]):
        """Renders scan results using the unified card style."""
        self._clear_gallery(self.gallery_layout)
        self.path_to_wrapper_map.clear()
        
        columns = self._columns()
        
        for idx, (path, pixmap) in enumerate(loaded_results):
            row = idx // columns
            col = idx % columns
            
            is_selected = path in self.selected_duplicates
            card = self._create_gallery_card(path, pixmap, is_selected)
            
            card.path_clicked.connect(self.toggle_duplicate_selection)
            card.path_double_clicked.connect(self.open_full_preview)
            card.path_right_clicked.connect(self.show_image_context_menu)
            
            self.gallery_layout.addWidget(card, row, col, Qt.AlignLeft | Qt.AlignTop)
            self.path_to_wrapper_map[path] = card

        if self.loader_worker:
            try:
                self.loader_worker.progress_updated.disconnect(self.update_loading_progress)
            except RuntimeError:
                pass

        if self.loading_dialog:
            self.loading_dialog.close()
            self.loading_dialog = None
            
        self._refresh_selected_panel()

    @Slot(str)
    def delete_single_file(self, path: str):
        filename = os.path.basename(path)
        reply = QMessageBox.question(
            self, "Confirm Single Deletion",
            f"Are you sure you want to PERMANENTLY delete:\n**{filename}**?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.No: return
            
        try:
            os.remove(path)
            
            # 1. Remove from internal tracking lists
            if path in self.selected_duplicates:
                self.selected_duplicates.remove(path)
            if path in self.duplicate_path_list:
                self.duplicate_path_list.remove(path)
                
            # 2. Remove from TOP Gallery (Scan Results)
            if path in self.path_to_wrapper_map:
                wrapper = self.path_to_wrapper_map.pop(path)
                
                # Find the widget in the layout and remove it
                for i in range(self.gallery_layout.count()):
                    item = self.gallery_layout.itemAt(i)
                    if item.widget() == wrapper:
                        self.gallery_layout.removeItem(item)
                        break
                
                wrapper.setParent(None)
                wrapper.deleteLater()
            
            # 3. Update UI without rescan
            self._refresh_selected_panel() # Updates bottom panel
            self._update_action_buttons()
            self._repack_gallery() # OPTIONAL: To fix gaps in grid
            
            self.status_label.setText(f"File deleted: {filename}")
            QMessageBox.information(self, "Success", f"Deleted: {filename}")
            
        except Exception as e:
            QMessageBox.critical(self, "Deletion Failed", f"Error: {e}")

    def _repack_gallery(self):
        """Simple helper to repack grid items to close gaps after deletion."""
        columns = self._columns()
        items = []
        
        # Collect all existing items
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            if item.widget():
                items.append(item.widget())
        
        # Re-add them in order
        for idx, widget in enumerate(items):
            row = idx // columns
            col = idx % columns
            self.gallery_layout.addWidget(widget, row, col, Qt.AlignLeft | Qt.AlignTop)

    def open_full_preview(self, path):
        try:
            start_index = self.duplicate_path_list.index(path)
        except ValueError:
            start_index = 0

        window = ImagePreviewWindow(
            image_path=path, db_tab_ref=None, parent=self,
            all_paths=self.duplicate_path_list, start_index=start_index
        )
        window.setAttribute(Qt.WA_DeleteOnClose)
        window.show()
        self.open_preview_windows.append(window)

    def delete_selected_duplicates(self):
        if not self.selected_duplicates: return
            
        count = len(self.selected_duplicates)
        reply = QMessageBox.question(
            self, "Confirm Batch Delete",
            f"Permanently delete **{count}** selected files?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No: return

        deleted_count = 0
        errors = []
        
        # Iterate over a copy to allow modification
        for path in list(self.selected_duplicates):
            try:
                os.remove(path)
                deleted_count += 1
                
                # Update Internal Lists
                self.selected_duplicates.remove(path)
                if path in self.duplicate_path_list:
                    self.duplicate_path_list.remove(path)
                    
                # Remove from Top Gallery UI
                if path in self.path_to_wrapper_map:
                    wrapper = self.path_to_wrapper_map.pop(path)
                    # We remove from layout in bulk later or rely on wrapper.deleteLater()
                    wrapper.setParent(None) 
                    wrapper.deleteLater()

            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {str(e)}")
        
        # Refresh UI without loading thumbnails again
        self._repack_gallery()
        self._refresh_selected_panel()
        self._update_action_buttons()
        
        msg = f"Deleted {deleted_count} files."
        if errors: msg += f"\nErrors:\n" + "\n".join(errors[:5])
        QMessageBox.information(self, "Deletion Complete", msg)

    def clear_gallery(self):
        self.selected_duplicates.clear()
        self.duplicate_path_list.clear()
        self._clear_gallery(self.gallery_layout)
        self._clear_gallery(self.selected_layout)
        self.gallery_scroll.setVisible(False)
        self.selected_scroll.setVisible(False)
        self._update_action_buttons()

    # --- STANDARD DELETION LOGIC ---
    def start_deletion(self, mode: str):
        if not self.is_valid(mode): return
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

    # --- BASE UTILS ---
    def _get_starting_dir(self) -> str:
        try:
            path = Path(os.getcwd())
            parts = path.parts
            idx = parts.index('Image-Toolkit')
            start_dir = os.path.join(Path(*parts[:idx + 1]), 'data')
            return start_dir if Path(start_dir).is_dir() else os.getcwd()
        except ValueError:
            return os.getcwd()

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select File", self._get_starting_dir(), 
            f"Images ({' '.join(['*'+e for e in SUPPORTED_IMG_FORMATS])});;All (*)"
        )
        if file_path: self.target_path.setText(file_path)

    def browse_directory(self):
        d = QFileDialog.getExistingDirectory(self, "Select Directory", self._get_starting_dir())
        if d: self.target_path.setText(d)
        
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

    def collect(self, mode: str) -> Dict[str, Any]:
        exts = []
        if mode == 'files':
            if self.dropdown: exts = list(self.selected_extensions)
            else: exts = self.join_list_str(self.target_extensions.text().strip())
        return {
            "target_path": self.target_path.text().strip(), "mode": mode,
            "target_extensions": [e.strip().lstrip('.') for e in exts if e.strip()]
        }

    @staticmethod
    def join_list_str(text: str):
        return [item.strip().lstrip('.') for item in text.replace(',', ' ').split() if item.strip()]

    def get_default_config(self): return {}
    def set_config(self, config): pass
