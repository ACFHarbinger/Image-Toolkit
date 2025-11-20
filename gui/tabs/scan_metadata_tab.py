import os

from pathlib import Path
from typing import Set, Dict, Any, List, Tuple
from PySide6.QtGui import QPixmap, QAction
from PySide6.QtCore import (
    Qt, QThreadPool, QThread, Slot, QPoint
)
from PySide6.QtWidgets import (
    QComboBox, QLineEdit, QFileDialog, 
    QHBoxLayout, QVBoxLayout, QScrollArea, 
    QWidget, QGroupBox, QCheckBox, QFrame,
    QApplication, QMessageBox, QGridLayout,
    QPushButton, QLabel, QFormLayout, QMenu,
    QProgressDialog # --- ADDED IMPORT ---
)
from .base_tab import BaseTab
from ..windows import ImagePreviewWindow
from ..components import ClickableLabel, MarqueeScrollArea
from ..helpers import ImageScannerWorker, BatchThumbnailLoaderWorker
from ..styles.style import apply_shadow_effect


class ScanMetadataTab(BaseTab):
    """
    Manages file and directory metadata scanning, image preview gallery, and batch database operations.
    Requires a reference to the main DatabaseTab for database connection access.
    """
    def __init__(self, db_tab_ref, dropdown=True):
        super().__init__()
        self.db_tab_ref = db_tab_ref
        self.dropdown = dropdown
        
        self.scan_image_list: list[str] = []
        self.selected_image_paths: Set[str] = set()
        self.selected_scan_image_path: str = None
        self.open_preview_windows: list[ImagePreviewWindow] = [] 
        self.loading_dialog = None # --- ADDED STATE ---

        # Current thumbnail size (150x150)
        self.thumbnail_size = 150
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width
        
        # New dictionary to track selection in the bottom panel for styling
        self.selected_card_map = {} 
        
        main_layout = QVBoxLayout(self)

        # ------------------------------------------------------------------
        # --- Scrollable Content Setup ---
        # ------------------------------------------------------------------
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        
        scroll_content = QWidget()
        scroll_content_layout = QVBoxLayout(scroll_content)
        scroll_content_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- Scan Directory Section ---
        scan_group = QGroupBox("Scan Directory")
        scan_group.setStyleSheet("""
            QGroupBox {  
                border: 1px solid #4f545c; \n
                border-radius: 8px; \n
                margin-top: 10px; \n
            }
            QGroupBox::title { 
                subcontrol-origin: margin; \n
                subcontrol-position: top left; \n
                padding: 4px 10px; \n
                color: white; \n
                border-radius: 4px; \n
            }
        """)
        
        scan_layout = QVBoxLayout()
        scan_layout.setContentsMargins(10, 20, 10, 10) 
        
        scan_dir_layout = QHBoxLayout()
        self.scan_directory_path = QLineEdit()
        self.scan_directory_path.setPlaceholderText("Select directory to scan...")
        btn_browse_scan = QPushButton("Browse...")
        btn_browse_scan.clicked.connect(self.browse_scan_directory)
        
        # Connect Enter key on Linedit to custom handler
        self.scan_directory_path.returnPressed.connect(self.handle_scan_directory_return)

        apply_shadow_effect(btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3)

        scan_dir_layout.addWidget(self.scan_directory_path)
        scan_dir_layout.addWidget(btn_browse_scan)
        scan_layout.addLayout(scan_dir_layout)
        
        scan_group.setLayout(scan_layout)
        scroll_content_layout.addWidget(scan_group)

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
            self.last_browsed_scan_dir = os.getcwd() 
        
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None
        self.path_to_label_map = {}

        # View Image button
        self.scan_view_image_btn = QPushButton("View Full Size Selected Image(s)")
        self.scan_view_image_btn.clicked.connect(self.view_selected_scan_image)
        self.scan_view_image_btn.setEnabled(False) 
        self.scan_view_image_btn.setStyleSheet("""
            QPushButton { 
                background-color: #5865f2; \n
                color: white; \n
                padding: 10px; \n
                border-radius: 8px; \n
            } 
            QPushButton:hover { 
                background-color: #4754c4; \n
            }
            QPushButton:disabled {
                background-color: #4f545c; \n
                color: #a0a0a0; \n
            }
        """)
        apply_shadow_effect(self.scan_view_image_btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        scroll_content_layout.addWidget(self.scan_view_image_btn)

        # Scroll Area for image thumbnails (Main Gallery)
        self.scan_scroll_area = MarqueeScrollArea() 
        self.scan_scroll_area.setWidgetResizable(True)
        self.scan_scroll_area.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")

        # Set minimum height for the main gallery scroll area
        self.scan_scroll_area.setMinimumHeight(600) 

        self.scan_thumbnail_widget = QWidget()
        self.scan_thumbnail_widget.setStyleSheet("QWidget { background-color: #2c2f33; }")

        self.scan_thumbnail_layout = QGridLayout(self.scan_thumbnail_widget)
        
        self.scan_scroll_area.selection_changed.connect(self.handle_marquee_selection)
        
        self.scan_thumbnail_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        
        self.scan_scroll_area.setWidget(self.scan_thumbnail_widget)
        
        scroll_content_layout.addWidget(self.scan_scroll_area, 1)
        
        # --- Selected Images Area --- (Bottom Gallery)
        self.selected_images_area = MarqueeScrollArea() 
        self.selected_images_area.setWidgetResizable(True)
        self.selected_images_area.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")
        self.selected_images_area.selection_changed.connect(self.handle_marquee_selection) 
        
        # Set minimum height for the selected images scroll area
        self.selected_images_area.setMinimumHeight(600)

        self.selected_images_widget = QWidget()
        self.selected_images_widget.setStyleSheet("QWidget { background-color: #2c2f33; }")
        self.selected_grid_layout = QGridLayout(self.selected_images_widget)
        self.selected_grid_layout.setSpacing(10)
        
        # Align selected grid layout to the left
        self.selected_grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft) 
        
        self.selected_images_area.setWidget(self.selected_images_widget)
        
        self.selected_images_area.setVisible(True) 
        scroll_content_layout.addWidget(self.selected_images_area, 1)
        
        # --- Metadata Group Box ---
        self.metadata_group = QGroupBox("Batch Metadata (Applies to ALL Selected Images)")
        self.metadata_group.setVisible(False) 
        metadata_vbox = QVBoxLayout(self.metadata_group)
        
        form_layout = QFormLayout()
        
        series_layout = QHBoxLayout()
        self.series_combo = QComboBox()
        self.series_combo.setEditable(True)
        self.series_combo.setPlaceholderText("Enter or select series name...")
        # Connect Enter key on combo box line edit to upsert button
        self.series_combo.lineEdit().returnPressed.connect(lambda: self.upsert_button.click())
        series_layout.addWidget(self.series_combo)
        form_layout.addRow("Series Name:", series_layout)
        
        char_layout = QVBoxLayout()
        self.characters_edit = QLineEdit()
        self.characters_edit.setPlaceholderText("Enter character names (comma-separated)...")
        # Connect Enter key
        self.characters_edit.returnPressed.connect(lambda: self.upsert_button.click())
        char_layout.addWidget(self.characters_edit)
        self.char_suggestions = QLabel()
        self.char_suggestions.setStyleSheet("font-size: 9px; color: #b9bbbe;")
        char_layout.addWidget(self.char_suggestions)
        form_layout.addRow("Characters:", char_layout)
        
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
                    width: 16px; height: 16px; border: 1px solid #555; \n
                    border-radius: 3px; background-color: #333; \n
                }
                QCheckBox::indicator:checked {
                    background-color: #4CAF50; border: 1px solid #4CAF50; \n
                    image: url(./src/gui/assets/check.png); \n
                }
            """)
            self.tag_checkboxes[tag] = checkbox
            row = i // columns
            col = i % columns
            self.tags_layout.addWidget(checkbox, row, col)

        form_layout.addRow("Tags:", tags_scroll)
        
        metadata_vbox.addLayout(form_layout)
        
        scroll_content_layout.addWidget(self.metadata_group)

        # Add scroll content to scroll area
        scroll_area.setWidget(scroll_content)
        # Add scroll area to the main layout
        main_layout.addWidget(scroll_area, 1)

        # --- Action buttons (Fixed at the bottom) ---
        
        self.view_batch_button = QPushButton("View Selected")
        self.view_batch_button.setStyleSheet("""
            QPushButton { 
                background-color: #3498db; \n
                color: white; \n
                padding: 10px 8px; \n
                border-radius: 8px; \n
                font-weight: bold; \n
            } 
            QPushButton:hover { 
                background-color: #2980b9; \n
            }
            QPushButton:disabled {
                background-color: #4f545c; \n
                color: #a0a0a0; \n
            }
        """)
        apply_shadow_effect(self.view_batch_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.view_batch_button.clicked.connect(self.toggle_selected_images_view) 

        self.upsert_button = QPushButton("Add/Update Database Data")
        self.upsert_button.setStyleSheet("""
            QPushButton { 
                background-color: #2ecc71; \n
                color: white; \n
                padding: 10px 8px; \n
                border-radius: 8px; \n
                font-weight: bold; \n
            } 
            QPushButton:hover { 
                background-color: #1e8449; \n
            }
            QPushButton:disabled {
                background-color: #4f545c; \n
                color: #a0a0a0; \n
            }
        """)
        apply_shadow_effect(self.upsert_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.upsert_button.clicked.connect(self.perform_upsert_operation)

        self.refresh_image_button = QPushButton("Refresh Image Directory")
        self.refresh_image_button.setStyleSheet("""
            QPushButton { 
                background-color: #f1c40f; \n
                color: white; \n
                padding: 10px 8px; \n
                border-radius: 8px; \n
                font-weight: bold; \n
            } 
            QPushButton:hover { 
                background-color: #d4ac0d; \n
            }
            QPushButton:disabled {
                background-color: #4f545c; \n
                color: #a0a0a0; \n
            }
        """)
        apply_shadow_effect(self.refresh_image_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.refresh_image_button.clicked.connect(self.refresh_image_directory) 

        self.delete_selected_button = QPushButton("Delete Images Data from Database")
        self.delete_selected_button.setStyleSheet("""
            QPushButton { 
                background-color: #e74c3c; \n
                color: white; \n
                padding: 10px 8px; \n
                border-radius: 8px; \n
                font-weight: bold; \n
            } 
            QPushButton:hover { 
                background-color: #c0392b; \n
            }
            QPushButton:disabled {
                background-color: #4f545c; \n
                color: #a0a0a0; \n
            }
        """)
        apply_shadow_effect(self.delete_selected_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.delete_selected_button.clicked.connect(self.delete_selected_images)
        
        scan_action_layout = QHBoxLayout()
        scan_action_layout.addWidget(self.view_batch_button)
        scan_action_layout.addWidget(self.upsert_button)
        scan_action_layout.addWidget(self.refresh_image_button)
        scan_action_layout.addWidget(self.delete_selected_button)
        
        main_layout.addLayout(scan_action_layout) 
        
        self.setLayout(main_layout)
        
        self.update_button_states(connected=False) 
        # Initial population of the selected gallery to show a placeholder
        self.populate_selected_images_gallery()
    
    # --- Context Menu Handler ---
    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        """
        Displays a context menu for the clicked image thumbnail, offering 
        View, Select, and DELETE options.
        """
        menu = QMenu(self)
        
        # 1. View Full Size (ONLY THE CLICKED IMAGE)
        view_action = QAction("View Full Size Preview", self)
        view_action.triggered.connect(lambda: self._view_single_image_preview(path))
        menu.addAction(view_action)
        
        menu.addSeparator()

        # 2. Select/Deselect
        is_selected = path in self.selected_image_paths
        toggle_text = "Deselect Image (Remove from Batch)" if is_selected else "Select Image (Add to Batch)"
        toggle_action = QAction(toggle_text, self)
        
        # Connect to the single-click selection handler
        toggle_action.triggered.connect(lambda: self.select_scan_image(path))
        menu.addAction(toggle_action)
        
        # 3. DELETE IMAGE FILE ACTION (NEW)
        menu.addSeparator()
        delete_action = QAction("🗑️ Delete Image File (Permanent)", self)
        delete_action.triggered.connect(lambda: self.handle_delete_image(path))
        menu.addAction(delete_action)
        
        menu.exec(global_pos)

    @Slot(str)
    def handle_delete_image(self, path: str):
        if not path or not Path(path).exists():
            QMessageBox.warning(self, "Delete Error", "File not found or path is invalid.")
            return

        filename = os.path.basename(path)
        
        # Confirmation Dialog
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
            os.remove(path)
            
            if path in self.scan_image_list:
                self.scan_image_list.remove(path)
            
            if path in self.selected_image_paths:
                self.selected_image_paths.remove(path)
            
            if path in self.path_to_label_map:
                widget = self.path_to_label_map.pop(path)
                
                for i in range(self.scan_thumbnail_layout.count()):
                    item = self.scan_thumbnail_layout.itemAt(i)
                    if item and item.widget() is widget:
                        self.scan_thumbnail_layout.removeItem(item)
                        widget.deleteLater()
                        break
            
            if self.scanned_dir:
                 self.display_scan_results(self.scan_image_list)
            
            if self.selected_images_area.isVisible():
                self.populate_selected_images_gallery()

            self.update_button_states(connected=(self.db_tab_ref.db is not None))
            
            QMessageBox.information(self, "Success", f"File deleted successfully: {filename}")
            
        except Exception as e:
            QMessageBox.critical(self, "Deletion Failed", f"Could not delete the file: {e}")

    @Slot(str)
    def _view_single_image_preview(self, image_path: str):
        """Opens a full-size preview window for the single image path provided (DOUBLE/RIGHT CLICK)."""
        selected_paths_list = sorted(list(self.selected_image_paths))
        
        try:
            start_index = selected_paths_list.index(image_path)
        except ValueError:
            selected_paths_list = [image_path]
            start_index = 0

        for win in list(self.open_preview_windows):
            if isinstance(win, ImagePreviewWindow) and win.image_path == image_path:
                win.activateWindow() 
                return
        
        preview = ImagePreviewWindow(
            image_path=image_path, 
            db_tab_ref=self.db_tab_ref, 
            parent=self,
            all_paths=selected_paths_list,
            start_index=start_index
        )
        
        preview.finished.connect(lambda result, p=preview: self.remove_preview_window(p))
        preview.show() 
        self.open_preview_windows.append(preview)


    @Slot()
    def _cleanup_thumbnail_thread_ref(self):
        """Slot to clear the QThread and QObject references after the thread finishes its work."""
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None

    def _display_load_complete_message(self):
        image_count = len(self.scan_image_list)
        if image_count > 0:
            # Optional
            pass
    
    @Slot(int, int)
    def update_loading_progress(self, current: int, total: int):
        """Updates the progress dialog with the current loading count."""
        dialog = self.loading_dialog 
        if dialog:
            dialog.setValue(current)
            dialog.setLabelText(f"Loading {current} of {total}...")

    def display_scan_results(self, image_paths: list[str]):
        """Receives image paths from the worker thread, starts BatchThumbnailLoaderWorker using batch signals."""
        
        if self.current_thumbnail_loader_thread and self.current_thumbnail_loader_thread.isRunning():
            self.current_thumbnail_loader_thread.quit()
        
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None
        self.path_to_label_map = {} 

        while self.scan_thumbnail_layout.count():
            item = self.scan_thumbnail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.scan_image_list = []
        
        self.scan_image_list = image_paths
        
        columns = self.calculate_columns()
        
        if not self.scan_image_list:
            if self.loading_dialog: self.loading_dialog.close()
            no_images_label = QLabel("No supported images found.")
            no_images_label.setAlignment(Qt.AlignCenter)
            no_images_label.setStyleSheet("color: #b9bbbe;")
            self.scan_thumbnail_layout.addWidget(no_images_label, 0, 0, 1, columns)
            return
        
        # --- MODIFIED: Setup QProgressDialog range and initial text ---
        total_images = len(image_paths)
        if self.loading_dialog:
            self.loading_dialog.setMaximum(total_images) # Set maximum value
            self.loading_dialog.setValue(0) # Set initial value
            self.loading_dialog.setLabelText(f"Loading images 0 of {total_images}...")
        # ----------------------------------------------------------------------
        
        worker = BatchThumbnailLoaderWorker(self.scan_image_list, self.thumbnail_size)
        thread = QThread()

        # --- CHANGE: Removed the premature disconnection line here ---

        self.current_thumbnail_loader_worker = worker
        self.current_thumbnail_loader_thread = thread
        
        worker.moveToThread(thread)
        thread.started.connect(worker.run_load_batch)
        
        # --- NEW CONNECTION FOR PROGRESS UPDATE ---
        worker.progress_updated.connect(self.update_loading_progress)
        # ------------------------------------------
        
        # --- MODIFIED: Connect to batch signal ---
        worker.batch_finished.connect(self.handle_batch_finished)
        
        worker.batch_finished.connect(thread.quit)
        worker.batch_finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._cleanup_thumbnail_thread_ref) 

        worker.batch_finished.connect(self._display_load_complete_message)
        
        thread.start()
        
    @Slot(list)
    def handle_batch_finished(self, loaded_results: List[Tuple[str, QPixmap]]):
        """
        Renders all loaded thumbnails at once and applies current selection styling.
        """
        columns = self.calculate_columns()
        
        for index, (path, pixmap) in enumerate(loaded_results):
            row = index // columns
            col = index % columns

            clickable_label = ClickableLabel(path) 
            clickable_label.setAlignment(Qt.AlignCenter)
            clickable_label.setFixedSize(self.thumbnail_size, self.thumbnail_size)
            
            clickable_label.path_right_clicked.connect(self.show_image_context_menu)
            clickable_label.path_clicked.connect(self.select_scan_image)
            clickable_label.path_double_clicked.connect(self._view_single_image_preview) 

            is_selected = path in self.selected_image_paths
            
            if not pixmap.isNull():
                clickable_label.setPixmap(pixmap) 
                clickable_label.setText("") 
                if is_selected:
                    clickable_label.setStyleSheet("border: 3px solid #5865f2;")
                else:
                    clickable_label.setStyleSheet("border: 1px solid #4f545c;")
            else:
                clickable_label.setText("Load Error")
                if is_selected:
                    clickable_label.setStyleSheet("border: 3px solid #5865f2; background-color: #4f545c; font-size: 8px;") 
                else:
                    clickable_label.setStyleSheet("border: 1px solid #e74c3c; background-color: #4f545c; font-size: 8px;")

            self.scan_thumbnail_layout.addWidget(clickable_label, row, col)
            self.path_to_label_map[path] = clickable_label 
        
        self.scan_thumbnail_widget.update()
        
        # --- FIX: DISCONNECT PROGRESS SIGNAL BEFORE CLOSING DIALOG ---
        if self.current_thumbnail_loader_worker:
            try:
                # Disconnect the progress signal using the worker reference
                self.current_thumbnail_loader_worker.progress_updated.disconnect(self.update_loading_progress)
            except RuntimeError:
                # Signal may already be disconnected if the thread quit, ignore error
                pass
        # -------------------------------------------------------------
        
        if self.loading_dialog:
            self.loading_dialog.close()
            self.loading_dialog = None

    def clear_scan_image_gallery(self):
        """Performs a FULL clear of the gallery AND the selection state (used by DB ops)."""
        if self.current_thumbnail_loader_thread and self.current_thumbnail_loader_thread.isRunning():
            self.current_thumbnail_loader_thread.quit()
        
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None
        self.path_to_label_map = {} 

        while self.scan_thumbnail_layout.count():
            item = self.scan_thumbnail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        
        while self.selected_grid_layout.count():
            item = self.selected_grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        
        self.selected_card_map = {} 
        
        self.scan_image_list = []
        self.selected_image_paths = set()
        self.selected_scan_image_path = None
        self.update_button_states(connected=(self.db_tab_ref.db is not None))
        self.metadata_group.setVisible(False) 
        self.populate_selected_images_gallery() 

    def handle_scan_error(self, message: str):
        if self.loading_dialog: self.loading_dialog.close()
        self.clear_scan_image_gallery() 
        QMessageBox.warning(self, "Error Scanning", message)
        ready_label = QLabel("Browse for a directory.")
        ready_label.setAlignment(Qt.AlignCenter)
        ready_label.setStyleSheet("color: #b9bbbe;")
        self.scan_thumbnail_layout.addWidget(ready_label, 0, 0, 1, 1)

    def handle_scan_directory_return(self):
        directory = self.scan_directory_path.text().strip()
        if directory and Path(directory).is_dir():
            self.populate_scan_image_gallery(directory)
        else:
            self.browse_scan_directory()

    def browse_scan_directory(self):
        start_dir = self.last_browsed_scan_dir
        options = QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        directory = QFileDialog.getExistingDirectory(self, "Select directory to scan", start_dir, options)
        
        if directory:
            self.last_browsed_scan_dir = directory
            self.scan_directory_path.setText(directory)
            self.populate_scan_image_gallery(directory)

    def calculate_columns(self) -> int:
        widget_width = self.scan_thumbnail_widget.width()
        if widget_width <= 0:
            widget_width = self.scan_thumbnail_widget.parentWidget().width()
        
        if widget_width <= 0:
            return 4 
        
        columns = widget_width // self.approx_item_width
        return max(1, columns)

    def populate_scan_image_gallery(self, directory: str):
        """
        Initiates scanning. Only clears the top gallery to preserve current selection state.
        """
        self.scanned_dir = directory
        
        # --- Clear Top Gallery ---
        if self.current_thumbnail_loader_thread and self.current_thumbnail_loader_thread.isRunning():
            self.current_thumbnail_loader_thread.quit()
        
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None
        self.path_to_label_map = {} 

        while self.scan_thumbnail_layout.count():
            item = self.scan_thumbnail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.scan_image_list = []
        
        self.scan_view_image_btn.setEnabled(False)
        
        # --- MODIFIED: Start Modal Progress Dialog ---
        self.loading_dialog = QProgressDialog("Scanning directory...", "Cancel", 0, 0, self)
        self.loading_dialog.setWindowModality(Qt.WindowModal)
        self.loading_dialog.setWindowTitle("Please Wait")
        self.loading_dialog.setMinimumDuration(0) 
        self.loading_dialog.setCancelButton(None) 
        self.loading_dialog.show()
        # -------------------------------------------
        
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
        Toggles selection state of an image in the main gallery. 
        Defaults to additive selection.
        """
        clicked_widget = self.path_to_label_map.get(file_path)
        if not clicked_widget:
            return

        # Toggle the selection state
        if file_path in self.selected_image_paths:
            self.selected_image_paths.remove(file_path)
        else:
            self.selected_image_paths.add(file_path)

        is_selected = file_path in self.selected_image_paths

        # Update styling for the clicked item in the main gallery
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
        
        # Auto-refresh selected section if visible
        if self.selected_images_area.isVisible():
            self.populate_selected_images_gallery()
            
    def select_selected_image_card(self, file_path: str):
        """
        Handles single-click events in the bottom 'Selected Images' panel.
        """
        card_clickable_wrapper = self.selected_card_map.get(file_path)
        if not card_clickable_wrapper:
            return
            
        if file_path in self.selected_image_paths:
            self.selected_image_paths.remove(file_path)
            is_selected = False
        else:
            self.selected_image_paths.add(file_path)
            is_selected = True
            
        main_label = self.path_to_label_map.get(file_path)
        if main_label:
            if is_selected:
                main_label.setStyleSheet("border: 3px solid #5865f2;")
            else:
                if not main_label.pixmap().isNull():
                    main_label.setStyleSheet("border: 1px solid #4f545c;")
                else:
                    main_label.setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;")
        
        self.update_button_states(connected=(self.db_tab_ref.db is not None))
        self.populate_selected_images_gallery()

    def view_selected_image_from_card(self, path: str):
        if path not in self.selected_image_paths:
            self.selected_image_paths.add(path)
            self.select_selected_image_card(path)
            
        self.selected_scan_image_path = path
        self.view_selected_scan_image()


    def handle_marquee_selection(self, paths_from_marquee: set, is_ctrl_pressed: bool):
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

        if self.selected_images_area.isVisible():
            self.populate_selected_images_gallery()

    def view_selected_scan_image_from_double_click(self, path: str):
        self._view_single_image_preview(path)

    def remove_preview_window(self, window_instance: ImagePreviewWindow):
        try:
            if window_instance in self.open_preview_windows:
                self.open_preview_windows.remove(window_instance)
        except (RuntimeError, ValueError):
            pass

    def view_selected_scan_image(self):
        selected_paths_list = sorted(list(self.selected_image_paths))
        
        if not selected_paths_list:
            QMessageBox.warning(self, "No Images Selected", "Please select one or more image thumbnails from the gallery first.")
            return

        start_path = selected_paths_list[0]
        
        for window in self.open_preview_windows:
            if isinstance(window, ImagePreviewWindow) and window.image_path == start_path:
                window.activateWindow() 
                return

        preview = ImagePreviewWindow(
            image_path=start_path, 
            db_tab_ref=self.db_tab_ref, 
            parent=self, 
            all_paths=selected_paths_list, 
            start_index=0
        )
        
        preview.finished.connect(lambda result, p=preview: self.remove_preview_window(p))
        preview.show() 
        self.open_preview_windows.append(preview)

    def toggle_selected_images_view(self):
        selection_count = len(self.selected_image_paths)
        if selection_count == 0:
            self.update_button_states(connected=(self.db_tab_ref.db is not None))
            return

        if self.selected_images_area.isVisible():
            self.selected_images_area.setVisible(False)
            self.view_batch_button.setText(f"View {selection_count} Selected")
        else:
            self.populate_selected_images_gallery()
            self.selected_images_area.setVisible(True)
            self.view_batch_button.setText(f"Hide {selection_count} Selected")
            
    def populate_selected_images_gallery(self):
        self.selected_images_widget.setUpdatesEnabled(False)
        
        while self.selected_grid_layout.count():
            item = self.selected_grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.selected_card_map = {}
        
        paths = sorted(list(self.selected_image_paths))
        
        thumb_size = self.thumbnail_size 
        padding = 10
        approx_width = thumb_size + padding + 10 
        
        widget_width = self.selected_images_widget.width()
        if widget_width <= 0:
            widget_width = self.parentWidget().width()
        
        columns = max(1, widget_width // approx_width)
        
        wrapper_height = self.thumbnail_size + 10 
        wrapper_width = self.thumbnail_size + 10 
        
        if not paths:
            empty_label = QLabel("Select images from the scan directory above to view them here.")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #b9bbbe; padding: 50px;")
            self.selected_grid_layout.addWidget(empty_label, 0, 0, 1, columns)
            
            self.selected_images_widget.setUpdatesEnabled(True)
            return

        for i, path in enumerate(paths):
            card_clickable_wrapper = ClickableLabel(path)
            card_clickable_wrapper.setFixedSize(wrapper_width, wrapper_height) 

            card_clickable_wrapper.path_clicked.connect(self.select_selected_image_card)
            card_clickable_wrapper.path_double_clicked.connect(self.view_selected_image_from_card)
            
            card = QFrame()
            card.setStyleSheet("background-color: transparent; border: none;")

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(0, 0, 0, 0) 
            
            img_label = QLabel()
            img_label.setAlignment(Qt.AlignCenter)
            img_label.setFixedSize(self.thumbnail_size, self.thumbnail_size) 
            
            is_master_selected = path in self.selected_image_paths
            if is_master_selected:
                img_label.setStyleSheet("border: 3px solid #5865f2;")
            else:
                img_label.setStyleSheet("border: 1px solid #4f545c;")

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

            card_layout.addWidget(img_label)
            
            card_clickable_wrapper.setLayout(card_layout)
            
            row = i // columns
            col = i % columns
            
            self.selected_card_map[path] = card_clickable_wrapper
            
            self.selected_grid_layout.addWidget(card_clickable_wrapper, row, col, Qt.AlignLeft | Qt.AlignTop) 

        self.selected_images_widget.setUpdatesEnabled(True)
        self.selected_images_widget.adjustSize()

    def perform_upsert_operation(self):
        db = self.db_tab_ref.db
        if not db:
            QMessageBox.warning(self, "Error", "Please connect to a database first (in Database tab)")
            return
        
        selected_paths = list(self.selected_image_paths)
        if not selected_paths:
            QMessageBox.warning(self, "Error", "No images selected.")
            return

        if not self.metadata_group.isVisible():
            self.metadata_group.setVisible(True)
            self.upsert_button.setText(f"Confirm & Upsert {len(selected_paths)} Images")
            return
            
        self.upsert_button.setText(f"Processing {len(selected_paths)}...")
        self.upsert_button.setEnabled(False)
        QApplication.processEvents() 
        
        try:
            added_count = 0
            updated_count = 0
            
            series = self.series_combo.currentText().strip() or None
            characters = [c.strip() for c in self.characters_edit.text().split(',') if c.strip()] or None
            tags = [tag for tag, cb in self.tag_checkboxes.items() if cb.isChecked()] or None

            for path in selected_paths:
                existing_data = db.get_image_by_path(path)
                
                if existing_data:
                    db.update_image(
                        image_id=existing_data['id'],
                        series_name=series,
                        characters=characters,
                        tags=tags
                    )
                    updated_count += 1
                else:
                    db.add_image(
                        file_path=path,
                        embedding=None, 
                        series_name=series,
                        characters=characters,
                        tags=tags
                    )
                    added_count += 1
            
            self.clear_scan_image_gallery()
            if self.scanned_dir:
                self.populate_scan_image_gallery(self.scanned_dir) 
            
            self.db_tab_ref.update_statistics()
            self.db_tab_ref.refresh_autocomplete_data()
            
            QMessageBox.information(self, "Success", f"Operation Complete:\nAdded: {added_count}\nUpdated: {updated_count}")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process images:\n{str(e)}")
        
        finally:
            self.metadata_group.setVisible(False) 
            self.update_button_states(connected=True)

    def refresh_image_directory(self):
        self.scan_directory_path.clear()
        self.scanned_dir = None
        
        if self.current_thumbnail_loader_thread and self.current_thumbnail_loader_thread.isRunning():
            self.current_thumbnail_loader_thread.quit()
        
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None
        self.path_to_label_map = {} 

        while self.scan_thumbnail_layout.count():
            item = self.scan_thumbnail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        
        self.scan_image_list = []
        
        ready_label = QLabel("Image preview cleared. Browse for a new directory.")
        ready_label.setAlignment(Qt.AlignCenter)
        ready_label.setStyleSheet("color: #b9bbbe;")
        columns = self.calculate_columns()
        self.scan_thumbnail_layout.addWidget(ready_label, 0, 0, 1, columns)

        self.update_button_states(connected=(self.db_tab_ref.db is not None))

    def delete_selected_images(self):
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
        selection_count = len(self.selected_image_paths)
        
        self.scan_view_image_btn.setEnabled(selection_count > 0)
        self.scan_view_image_btn.setText(f"View Full Size {selection_count} Selected Image(s)")
        
        self.refresh_image_button.setEnabled(True) 

        if self.selected_images_area.isVisible():
            self.view_batch_button.setText(f"Hide {selection_count} Selected")
        else:
            self.view_batch_button.setText(f"View {selection_count} Selected")
            
        self.view_batch_button.setEnabled(selection_count > 0 or self.selected_images_area.isVisible())

        if self.metadata_group.isVisible() and self.upsert_button.text().startswith("Confirm & Upsert"):
             self.upsert_button.setText(f"Confirm & Upsert {selection_count} Images")
        else:
            self.upsert_button.setText(f"Add/Update {selection_count} Selected Images")
        
        self.upsert_button.setEnabled(connected and selection_count > 0)

        self.delete_selected_button.setText(f"Delete {selection_count} Images from DB")
        self.delete_selected_button.setEnabled(connected and selection_count > 0)

    def collect(self) -> dict:
        out = {
            "scan_directory": self.scan_directory_path.text().strip() or None,
            "selected_images": list(self.selected_image_paths) 
        }
        return out

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "scan_directory": "",
            "batch_metadata": {
                "series_name": "",
                "characters": [],
                "tags": []
            }
        }
    
    def set_config(self, config: Dict[str, Any]):
        try:
            if "scan_directory" in config:
                self.scan_directory_path.setText(config.get("scan_directory", ""))
                if os.path.isdir(config["scan_directory"]):
                    self.populate_scan_image_gallery(config["scan_directory"])

            if "batch_metadata" in config:
                metadata = config.get("batch_metadata", {})
                self.series_combo.setCurrentText(metadata.get("series_name", ""))
                self.characters_edit.setText(", ".join(metadata.get("characters", [])))
                
                selected_tags = set(metadata.get("tags", []))
                for tag, checkbox in self.tag_checkboxes.items():
                    checkbox.setChecked(tag in selected_tags)
                    
            QMessageBox.information(self, "Config Loaded", "Configuration applied successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Config Error", f"Failed to apply configuration:\n{e}")
