import os

from pathlib import Path
from typing import Dict, Any, List, Tuple
from PySide6.QtGui import QPixmap, QAction
from PySide6.QtCore import Qt, QTimer, QThread, Slot, QPoint, QThreadPool, QEventLoop
from PySide6.QtWidgets import (
    QFrame, QMenu, QProgressDialog, QFormLayout,
    QComboBox, QSpinBox, QGroupBox, QHBoxLayout,
    QVBoxLayout, QMessageBox, QGridLayout, QScrollArea,
    QLineEdit, QFileDialog, QWidget, QLabel, QPushButton,
)
from .base_tab import BaseTab
from ..windows import ImagePreviewWindow
from ..components import ClickableLabel, MarqueeScrollArea
from ..helpers import MergeWorker, ImageScannerWorker, ImageLoaderWorker 
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS
from ..styles.style import apply_shadow_effect


class MergeTab(BaseTab):
    """
    GUI tab for merging images with a file/directory selection gallery.
    Uses safe threading, concurrent loading via QThreadPool, and dual-panel selection.
    """

    def __init__(self, dropdown=True):
        super().__init__()
        self.dropdown = dropdown

        # --- State ---
        self.selected_image_paths: List[str] = [] 
        self.merge_image_list: List[str] = []
        self.path_to_label_map: Dict[str, ClickableLabel] = {}
        self.selected_card_map: Dict[str, ClickableLabel] = {}
        self.scanned_dir: str | None = None
        self.open_preview_windows: list[ImagePreviewWindow] = [] 
        self.loading_dialog = None 
        self._loading_cancelled = False # Added flag
        
        # Column tracking
        self._current_gallery_cols = 1
        self._current_selected_cols = 1
        
        # --- Concurrent Loading State (QThreadPool) ---
        self.thread_pool = QThreadPool.globalInstance()
        self._loaded_results_buffer: List[Tuple[str, QPixmap]] = []
        self._images_loaded_count = 0
        self._total_images_to_load = 0
        # ----------------------------------------------
        
        # --- Thread tracking ---
        self.current_scan_thread: QThread | None = None
        self.current_scan_worker: ImageScannerWorker | None = None
        # Removed current_loader_thread/worker as QThreadPool manages them.
        self.current_merge_thread: QThread | None = None
        self.current_merge_worker: MergeWorker | None = None

        # --- Last browsed dir ---
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

        # --- UI Constants ---
        self.thumbnail_size = 150
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width

        # --- Layout Setup ---
        main_layout = QVBoxLayout(self)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")

        scroll_content = QWidget()
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # === 1. Merge Settings ===
        config_group = QGroupBox("Merge Settings")
        config_layout = QFormLayout(config_group)

        self.direction = QComboBox()
        self.direction.addItems(["horizontal", "vertical", "grid"])
        self.direction.currentTextChanged.connect(self.toggle_grid_visibility)
        config_layout.addRow("Direction:", self.direction)

        self.spacing = QSpinBox()
        self.spacing.setRange(0, 1000)
        self.spacing.setValue(10)
        config_layout.addRow("Spacing (px):", self.spacing)

        self.align_mode = QComboBox()
        self.align_mode.addItems([
            "Default (Top/Center)", 
            "Align Top/Left", 
            "Align Bottom/Right", 
            "Center", 
            "Scaled (Grow Smallest)", 
            "Squish (Shrink Largest)"
        ])
        config_layout.addRow("Alignment/Resize:", self.align_mode)

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

        content_layout.addWidget(config_group)

        # === 2. Input Gallery ===
        gallery_group = QGroupBox("Select Images to Merge")
        gallery_vbox = QVBoxLayout(gallery_group)

        # --- Scan Directory Group ---
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
        
        self.scan_directory_path.returnPressed.connect(self.handle_scan_directory_return)

        apply_shadow_effect(btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3)

        scan_dir_layout.addWidget(self.scan_directory_path)
        scan_dir_layout.addWidget(btn_browse_scan)

        scan_layout.addLayout(scan_dir_layout)
        
        scan_group.setLayout(scan_layout)
        
        gallery_vbox.addWidget(scan_group) 

        self.selection_label = QLabel("0 images selected.")
        gallery_vbox.addWidget(self.selection_label)

        # Top Gallery (Preview Section)
        self.merge_scroll_area = MarqueeScrollArea()
        self.merge_scroll_area.setWidgetResizable(True)
        self.merge_scroll_area.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.merge_scroll_area.setMinimumHeight(600)
        self.merge_thumbnail_widget = QWidget()
        self.merge_thumbnail_widget.setStyleSheet("background-color: #2c2f33;")
        self.merge_thumbnail_layout = QGridLayout(self.merge_thumbnail_widget)
        self.merge_thumbnail_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.merge_scroll_area.setWidget(self.merge_thumbnail_widget)
        self.merge_scroll_area.selection_changed.connect(self.handle_marquee_selection)
        gallery_vbox.addWidget(self.merge_scroll_area, 1)

        # Bottom Selected Gallery 
        self.selected_images_area = MarqueeScrollArea()
        self.selected_images_area.setWidgetResizable(True)
        self.selected_images_area.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.selected_images_area.setMinimumHeight(400)
        self.selected_images_widget = QWidget()
        self.selected_images_widget.setStyleSheet("background-color: #2c2f33;")
        self.selected_grid_layout = QGridLayout(self.selected_images_widget)
        self.selected_grid_layout.setSpacing(10)
        
        # Align selected grid layout to the left
        self.selected_grid_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        
        self.selected_images_area.setWidget(self.selected_images_widget)
        gallery_vbox.addWidget(self.selected_images_area, 1)

        content_layout.addWidget(gallery_group, 6)
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        # === 3. Action Buttons (Fixed Bottom) ===
        action_vbox = QVBoxLayout()

        self.run_button = QPushButton("Run Merge")
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #5865f2; color: white; font-weight: bold;
                font-size: 16px; padding: 14px; border-radius: 10px; min-height: 44px;
            }
            QPushButton:hover { background-color: #4754c4; }
            QPushButton:disabled { background: #718096; }
            QPushButton:pressed { background: #3f479a; }
        """)
        apply_shadow_effect(self.run_button, "#000000", 8, 0, 3)
        self.run_button.clicked.connect(self.start_merge)
        self.run_button.setDefault(True)
        action_vbox.addWidget(self.run_button)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #b9bbbe; font-style: italic; padding: 10px;")
        action_vbox.addWidget(self.status_label)

        main_layout.addLayout(action_vbox)

        self.update_run_button_state()
        self.toggle_grid_visibility(self.direction.currentText())
        self._show_placeholder("No images loaded. Use buttons above to add files or scan a directory.")

    # --- MERGE SETTINGS HELPER ---
    @Slot(str)
    def toggle_grid_visibility(self, direction):
        """Toggles the visibility of the grid size input based on the merge direction."""
        self.grid_group.setVisible(direction == "grid")
        
        # Force a quick recalculation after visibility change
        if not hasattr(self, "_resize_timer"):
            self._resize_timer = QTimer()
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(lambda: None)
        self._resize_timer.start(100)

    # === NEW: RESIZE REFLOW LOGIC ===
    def resizeEvent(self, event):
        """Handle resize events to reflow the gallery grid."""
        super().resizeEvent(event)
        
        # Use the shared robust calculation
        new_gallery_cols = self._calculate_columns(self.merge_scroll_area)
        if new_gallery_cols != self._current_gallery_cols:
            self._current_gallery_cols = new_gallery_cols
            self._reflow_layout(self.merge_thumbnail_layout, new_gallery_cols)

        new_selected_cols = self._calculate_columns(self.selected_images_area)
        if new_selected_cols != self._current_selected_cols:
            self._current_selected_cols = new_selected_cols
            self._reflow_layout(self.selected_grid_layout, new_selected_cols)
            
    def showEvent(self, event):
        """Trigger reflow when tab is shown."""
        super().showEvent(event)
        # Force update columns
        self._current_gallery_cols = self._calculate_columns(self.merge_scroll_area)
        self._reflow_layout(self.merge_thumbnail_layout, self._current_gallery_cols)
        
        self._current_selected_cols = self._calculate_columns(self.selected_images_area)
        self._reflow_layout(self.selected_grid_layout, self._current_selected_cols)

    def _calculate_columns(self, scroll_area) -> int:
        """Calculates columns based on the actual viewport width."""
        width = scroll_area.viewport().width()
        if width <= 0: width = scroll_area.width()
        
        # Important: If width is still 0 (e.g. unshown tab), assume a reasonable default width
        if width <= 0: width = 800 
            
        columns = width // self.approx_item_width
        return max(1, columns)

    def _reflow_layout(self, layout: QGridLayout, columns: int):
        """Removes all items from layout and re-adds them with new column count."""
        if not layout: return
        items = []
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                items.append(item.widget())
        
        for i, widget in enumerate(items):
            row = i // columns
            col = i % columns
            align = Qt.AlignLeft | Qt.AlignTop
            # Special check for placeholder label which should be centered
            if isinstance(widget, QLabel) and "No images loaded" in widget.text():
                 align = Qt.AlignCenter
                 # If placeholder, span all columns
                 layout.addWidget(widget, 0, 0, 1, columns, align)
                 return
                 
            layout.addWidget(widget, row, col, align)
    # --------------------------------

    # === NEW HANDLER: Double-Click Preview ===
    @Slot(str)
    def handle_full_image_preview(self, image_path: str):
        selected_paths_list = self.selected_image_paths.copy() 
        
        try:
            start_index = selected_paths_list.index(image_path)
        except ValueError:
            selected_paths_list = [image_path]
            start_index = 0

        for win in list(self.open_preview_windows):
            if isinstance(win, ImagePreviewWindow) and win.image_path == image_path:
                win.activateWindow()
                return

        window = ImagePreviewWindow(
            image_path=image_path, 
            db_tab_ref=None, 
            parent=self,
            all_paths=selected_paths_list,
            start_index=start_index
        )
        window.setAttribute(Qt.WA_DeleteOnClose)
        
        def remove_closed_win(event: Any):
            if window in self.open_preview_windows:
                 self.open_preview_windows.remove(window)
            event.accept()

        window.closeEvent = remove_closed_win
        
        window.show()
        self.open_preview_windows.append(window)

    @Slot(str)
    def handle_delete_image(self, path: str):
        if not path or not Path(path).exists():
            QMessageBox.warning(self, "Delete Error", "File not found or path is invalid.")
            return

        filename = os.path.basename(path)
        
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
            
            if path in self.merge_image_list:
                self.merge_image_list.remove(path)
            
            try:
                self.selected_image_paths.remove(path)
            except ValueError:
                pass 
            
            if path in self.path_to_label_map:
                widget = self.path_to_label_map.pop(path)
                
                for i in range(self.merge_thumbnail_layout.count()):
                    item = self.merge_thumbnail_layout.itemAt(i)
                    if item and item.widget() is widget:
                        self.merge_thumbnail_layout.removeItem(item)
                        widget.deleteLater()
                        break
            
            self._reflow_layout(self.merge_thumbnail_layout, self._current_gallery_cols) # Reflow gallery after delete
            self._refresh_selected_panel()
            self.update_run_button_state()
            
            QMessageBox.information(self, "Success", f"File deleted successfully: {filename}")
            
        except Exception as e:
            QMessageBox.critical(self, "Deletion Failed", f"Could not delete the file: {e}")
            
    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)
        
        view_action = QAction("View Full Size Preview", self)
        view_action.triggered.connect(lambda: self.handle_full_image_preview(path))
        menu.addAction(view_action)
        
        menu.addSeparator()

        is_selected = path in self.selected_image_paths
        toggle_text = "Deselect Image (Remove from Merge List)" if is_selected else "Select Image (Add to Merge List)"
        toggle_action = QAction(toggle_text, self)
        toggle_action.triggered.connect(lambda: self._toggle_selection(path))
        menu.addAction(toggle_action)
        
        menu.addSeparator()
        delete_action = QAction("🗑️ Delete Image File (Permanent)", self)
        delete_action.triggered.connect(lambda: self.handle_delete_image(path))
        menu.addAction(delete_action)
        
        menu.exec(global_pos)

    # === THREAD SAFETY CLEANUP ===
    @Slot()
    def _cleanup_scan_thread_ref(self):
        self.current_scan_thread = None
        self.current_scan_worker = None

    @Slot()
    def _cleanup_merge_thread_ref(self):
        self.current_merge_thread = None
        self.current_merge_worker = None
        
    def _stop_running_threads(self):
        """Safely interrupts and cleans up any active scanner or loader threads."""
        self._loading_cancelled = True
        
        # Clear the ThreadPool
        self.thread_pool.clear()
            
        if self.loading_dialog and self.loading_dialog.isVisible():
            self.loading_dialog.close()
            self.loading_dialog = None
            
    def cancel_loading(self):
        """Slot for cancelling operation via ProgressDialog."""
        self._stop_running_threads()
        self._loaded_results_buffer.clear()
        print("Loading cancelled by user.")

    # === GALLERY MANAGEMENT ===
    def _clear_gallery(self, layout: QGridLayout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def _show_placeholder(self, text: str):
        self._clear_gallery(self.merge_thumbnail_layout)
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #b9bbbe; font-style: italic;")
        columns = max(1, self._calculate_columns(self.merge_scroll_area))
        self.merge_thumbnail_layout.addWidget(lbl, 0, 0, 1, columns, Qt.AlignCenter)

    def _columns(self) -> int:
        return self._calculate_columns(self.merge_scroll_area)

    def _update_label_style(self, label: ClickableLabel, path: str, selected: bool):
        is_error = "Error" in label.text()

        if selected:
            if is_error:
                label.setStyleSheet("border: 3px solid #5865f2; background-color: #4f545c; font-size: 8px;")
            else:
                label.setStyleSheet("border: 3px solid #5865f2;")
        else:
            if is_error:
                label.setStyleSheet("border: 1px solid #e74c3c; background-color: #4f545c; font-size: 8px;")
            elif label.pixmap() and not label.pixmap().isNull():
                label.setStyleSheet("border: 1px solid #4f545c;")
            else:
                label.setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;")

    # === SELECTION HANDLING ===
    def _toggle_selection(self, path: str):
        try:
            index = self.selected_image_paths.index(path)
            self.selected_image_paths.pop(index)
            selected = False
        except ValueError:
            self.selected_image_paths.append(path)
            selected = True
            
        label = self.path_to_label_map.get(path)
        if label:
            self._update_label_style(label, path, selected)
            
        self._refresh_selected_panel()
        self.update_run_button_state()

    def handle_marquee_selection(self, paths: set, ctrl_pressed: bool):
        ordered_paths = self.selected_image_paths.copy()
        
        if not ctrl_pressed:
            new_ordered_paths = [p for p in ordered_paths if p in paths]
            newly_selected = [p for p in paths if p not in ordered_paths]
            self.selected_image_paths = new_ordered_paths + newly_selected
            paths_to_update = paths.union(set(ordered_paths))
        else:
            paths_to_add = [p for p in paths if p not in ordered_paths]
            self.selected_image_paths.extend(paths_to_add)
            paths_to_update = set(paths_to_add)

        for path in paths_to_update:
            label = self.path_to_label_map.get(path)
            if label:
                self._update_label_style(label, path, path in self.selected_image_paths)
                
        self._refresh_selected_panel()
        self.update_run_button_state()

    def _refresh_selected_panel(self):
        self.selected_images_widget.setUpdatesEnabled(False)

        while self.selected_grid_layout.count():
            item = self.selected_grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.selected_card_map = {}
        
        paths = self.selected_image_paths 
        
        thumb_size = self.thumbnail_size 
        padding = 10
        approx_width = thumb_size + padding + 10 
        
        columns = self._calculate_columns(self.selected_images_area)
        
        wrapper_height = self.thumbnail_size + 10 
        wrapper_width = self.thumbnail_size + 10 
        
        if not paths:
            empty_label = QLabel("Select images from the gallery above to view them here.")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #b9bbbe; padding: 50px;")
            self.selected_grid_layout.addWidget(empty_label, 0, 0, 1, columns)
            
            self.selected_images_widget.setUpdatesEnabled(True)
            return

        for i, path in enumerate(paths): 
            card_clickable_wrapper = ClickableLabel(path)
            card_clickable_wrapper.setFixedSize(wrapper_width, wrapper_height) 

            card_clickable_wrapper.path_clicked.connect(lambda checked, p=path: self._toggle_selection(p))
            
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

            src_label = self.path_to_label_map.get(path)
            pixmap = src_label.pixmap() if src_label and src_label.pixmap() and not src_label.pixmap().isNull() else QPixmap(path)
            
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.thumbnail_size, self.thumbnail_size, 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                img_label.setPixmap(scaled)
            else:
                img_label.setText("Load Error")
                img_label.setStyleSheet("color: #e74c3c; border: 1px solid #e74c3c;")

            card_layout.addWidget(img_label)
            
            card_clickable_wrapper.setLayout(card_layout)
            
            row = i // columns
            col = i % columns
            
            self.selected_card_map[path] = card_clickable_wrapper
            
            self.selected_grid_layout.addWidget(card_clickable_wrapper, row, col, Qt.AlignLeft | Qt.AlignTop) 

        self.selected_images_widget.setUpdatesEnabled(True)
        self.selected_images_widget.adjustSize()

    # === INPUT LOGIC ===
    
    def _browse_files_logic(self):
        start_dir = self.last_browsed_dir or str(Path.home())
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Images", start_dir,
            "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)"
        )
        if files:
            self.last_browsed_dir = os.path.dirname(files[0])
            new_paths = [f for f in files if f not in self.merge_image_list]
            
            self.display_scan_results(self.merge_image_list + new_paths)
            self.scan_directory_path.setText(f"Added {len(new_paths)} files.")


    def handle_scan_directory_return(self):
        directory = self.scan_directory_path.text().strip()
        if directory and Path(directory).is_dir():
            self.populate_scan_gallery(directory)
        else:
            self.browse_scan_directory()

    def browse_scan_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Scan Directory", self.last_browsed_dir or str(Path.home())
        )
        if directory:
            self.last_browsed_dir = directory
            self.scan_directory_path.setText(directory)
            self.populate_scan_gallery(directory)
            
    def handle_scan_error(self, message: str):
        if self.loading_dialog: self.loading_dialog.close()
        self._clear_gallery(self.merge_thumbnail_layout)
        QMessageBox.warning(self, "Error Scanning", message)
        self._show_placeholder("Browse for a directory.")
    
    def _display_load_complete_message(self):
        image_count = len(self.merge_image_list)
        if image_count > 0:
            pass

    def populate_scan_gallery(self, directory: str):
        self.scanned_dir = directory
        
        if self.current_scan_thread and self.current_scan_thread.isRunning():
            self.current_scan_thread.quit()
            self.current_scan_thread.wait(2000)
        
        self._stop_running_threads()
        self._loading_cancelled = False
    
        # No need to stop the loader thread, as QThreadPool manages its workers, 
        # and we clear the pool before starting new submissions in display_scan_results.

        self._clear_gallery(self.merge_thumbnail_layout)
        self.path_to_label_map.clear()
        self.merge_image_list = []

        self.loading_dialog = QProgressDialog("Scanning directory...", "Cancel", 0, 0, self)
        self.loading_dialog.setWindowModality(Qt.WindowModal)
        self.loading_dialog.setWindowTitle("Please Wait")
        self.loading_dialog.setMinimumDuration(0)
        # Enable cancellation for the scanner phase too
        self.loading_dialog.canceled.connect(self.cancel_loading) 
        self.loading_dialog.show()
        
        # Block to ensure scanner dialog visibility
        loop = QEventLoop()
        QTimer.singleShot(1, loop.quit)
        loop.exec()
        
        worker = ImageScannerWorker(directory)
        thread = QThread()
        
        self.current_scan_worker = worker
        self.current_scan_thread = thread
        worker.moveToThread(thread)

        thread.started.connect(worker.run_scan)
        worker.scan_finished.connect(self.display_scan_results)
        worker.scan_error.connect(self.handle_scan_error)

        worker.scan_finished.connect(thread.quit)
        worker.scan_finished.connect(worker.deleteLater)
        
        worker.scan_error.connect(thread.quit)
        worker.scan_error.connect(worker.deleteLater)

        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._cleanup_scan_thread_ref)
        
        thread.start()
    
    @Slot(str, QPixmap)
    def _on_single_image_loaded(self, path: str, pixmap: QPixmap):
        """Aggregates results and checks for batch completion."""
        if self._loading_cancelled:
            return
            
        self._loaded_results_buffer.append((path, pixmap))
        self._images_loaded_count += 1
            
        if self._images_loaded_count >= self._total_images_to_load:
            # Sort results before handing them to the finalization method
            sorted_results = sorted(self._loaded_results_buffer, key=lambda x: x[0])
            self.handle_batch_finished(sorted_results)

    def display_scan_results(self, image_paths: list[str]):
        if self._loading_cancelled:
            return
            
        self.merge_image_list = sorted(image_paths)
        if self.scanned_dir:
             self.scan_directory_path.setText(f"Source: {Path(self.scanned_dir).name} | {len(image_paths)} images")
        
        self._clear_gallery(self.merge_thumbnail_layout)
        self.path_to_label_map.clear()

        if not image_paths:
            if self.loading_dialog: self.loading_dialog.close()
            self._show_placeholder("No supported images found.")
            return

        # --- Thread Pool Setup ---
        self.thread_pool.clear()
        self._loaded_results_buffer = []
        self._images_loaded_count = 0
        self._total_images_to_load = len(image_paths)

        if self.loading_dialog:
            self.loading_dialog.setMaximum(self._total_images_to_load)
            self.loading_dialog.setValue(0)
            self.loading_dialog.setLabelText(f"Loading image 0 of {self._total_images_to_load}...")
            # Reconnect cancel just in case
            self.loading_dialog.canceled.disconnect()
            self.loading_dialog.canceled.connect(self.cancel_loading)

        loop = QEventLoop()
        QTimer.singleShot(1, loop.quit)
        loop.exec()
        
        # Submit tasks
        for path in image_paths:
            if self._loading_cancelled:
                break
                
            worker = ImageLoaderWorker(path, self.thumbnail_size)
            worker.signals.result.connect(self._on_single_image_loaded)
            self.thread_pool.start(worker)
            
            # --- PROGRESS BAR UPDATE ON SUBMISSION (Instant Feedback) ---
            dialog_box = self.loading_dialog
            if dialog_box:
                dialog_box.setValue(dialog_box.value() + 1)
                dialog_box.setLabelText(f"Loading image {dialog_box.value()} of {self._total_images_to_load}...")

    @Slot(list)
    def handle_batch_finished(self, loaded_results: List[Tuple[str, QPixmap]]):
        if self._loading_cancelled:
            return
            
        # Use robust column calculation
        columns = self._calculate_columns(self.merge_scroll_area)
        
        for idx, (path, pixmap) in enumerate(loaded_results):
            row = idx // columns
            col = idx % columns
            
            clickable_label = ClickableLabel(path) 
            clickable_label.setText("Loading...")
            clickable_label.setAlignment(Qt.AlignCenter)
            clickable_label.setFixedSize(self.thumbnail_size, self.thumbnail_size)
            
            clickable_label.path_clicked.connect(self._toggle_selection)
            clickable_label.path_double_clicked.connect(self.handle_full_image_preview)
            clickable_label.path_right_clicked.connect(self.show_image_context_menu)

            self.merge_thumbnail_layout.addWidget(clickable_label, row, col, Qt.AlignCenter)
            self.path_to_label_map[path] = clickable_label
            
            is_selected = path in self.selected_image_paths 
            if not pixmap.isNull():
                clickable_label.setPixmap(pixmap) 
                clickable_label.setText("") 
                self._update_label_style(clickable_label, path, is_selected)
            else:
                clickable_label.setText("Load Error")
                if is_selected:
                    clickable_label.setStyleSheet("border: 3px solid #5865f2; background-color: #4f545c; font-size: 8px;") 
                else:
                    clickable_label.setStyleSheet("border: 1px solid #e74c3c; background-color: #4f545c; font-size: 8px;")

        self.merge_thumbnail_widget.update()
        
        if self.loading_dialog:
            self.loading_dialog.close()
            self.loading_dialog = None
            
        self._display_load_complete_message()
        self._refresh_selected_panel()

    def start_merge(self):
        if len(self.selected_image_paths) < 2:
            QMessageBox.warning(self, "Invalid", "Select at least 2 images.")
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self, "Save Merged Image", self.last_browsed_dir, "PNG (*.png)"
        )
        if not output_path:
            self.status_label.setText("Cancelled.")
            return
        if not output_path.lower().endswith('.png'):
            output_path += '.png'
        self.last_browsed_dir = os.path.dirname(output_path)

        config = self.collect(output_path)
        self.run_button.setEnabled(False)
        self.run_button.setText("Merging...")
        self.status_label.setText("Processing...")

        if self.current_merge_thread and self.current_merge_thread.isRunning():
            self.current_merge_thread.quit()
            self.current_merge_thread.wait(2000)

        worker = MergeWorker(config)
        thread = QThread()
        
        self.current_merge_worker = worker
        self.current_merge_thread = thread
        worker.moveToThread(thread)
        
        thread.started.connect(worker.run)
        worker.progress.connect(self.update_progress)
        
        worker.finished.connect(self.on_merge_done)
        worker.error.connect(self.on_merge_error)
        
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(thread.quit)
        worker.error.connect(worker.deleteLater)
        
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._cleanup_merge_thread_ref)
        
        thread.start()

    def update_progress(self, cur, total):
        self.status_label.setText(f"Merging {cur}/{total}...")

    def on_merge_done(self, path):
        self.update_run_button_state()
        self.status_label.setText(f"Saved: {os.path.basename(path)}")
        QMessageBox.information(self, "Success", f"Merge complete!\n{path}")

    def on_merge_error(self, msg):
        self.update_run_button_state()
        self.status_label.setText("Failed.")
        QMessageBox.critical(self, "Error", msg)

    def collect(self, output_path: str) -> Dict[str, Any]:
        return {
            "direction": self.direction.currentText(),
            "input_path": self.selected_image_paths,
            "output_path": output_path,
            "input_formats": [f.strip().lstrip('.') for f in SUPPORTED_IMG_FORMATS if f.strip()],
            "spacing": self.spacing.value(),
            "align_mode": self.align_mode.currentText(),
            "grid_size": (self.grid_rows.value(), self.grid_cols.value())
            if self.direction.currentText() == "grid" else None
        }

    # === UI UTILS ===
    def update_run_button_state(self):
        count = len(self.selected_image_paths)
        self.selection_label.setText(f"{count} images selected.")
        if count < 2:
            self.run_button.setEnabled(False)
            self.run_button.setText("Run Merge (Select 2+ images)")
            self.run_button.setDefault(False)
        else:
            self.run_button.setEnabled(True)
            self.run_button.setText(f"Run Merge ({count} images)")
            self.run_button.setDefault(True)
        self.status_label.setText("" if count < 2 else f"Ready to merge {count} images.")

    def toggle_grid_visibility(self, direction):
        self.grid_group.setVisible(direction == "grid")
        if not hasattr(self, "_resize_timer"):
            self._resize_timer = QTimer()
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(lambda: None)
        self._resize_timer.start(100)

    # === BaseTab Impl ===
    def browse_files(self): self._browse_files_logic()
    def browse_directory(self): self.browse_scan_directory()
    def browse_input(self): self._browse_files_logic()
    def browse_output(self): pass

    def get_default_config(self) -> dict:
        return {
            "direction": "horizontal",
            "spacing": 10,
            "grid_size": [2, 2], 
            "scan_directory": "C:/path/to/images",
            "align_mode": "Default (Top/Center)"
        }

    def set_config(self, config: dict):
        try:
            direction = config.get("direction", "horizontal")
            if self.direction.findText(direction) != -1:
                self.direction.setCurrentText(direction)
            
            self.spacing.setValue(config.get("spacing", 10))

            align_mode = config.get("align_mode", "Default (Top/Center)")
            if self.align_mode.findText(align_mode) != -1:
                self.align_mode.setCurrentText(align_mode)
            
            grid_size = config.get("grid_size", [2, 2])
            if isinstance(grid_size, list) and len(grid_size) == 2:
                self.grid_rows.setValue(grid_size[0])
                self.grid_cols.setValue(grid_size[1])

            scan_dir = config.get("scan_directory")
            if scan_dir:
                self.scan_directory_path.setText(scan_dir)
                if os.path.isdir(scan_dir):
                    self.populate_scan_gallery(scan_dir)
            
            print(f"MergeTab configuration loaded.")
            
        except Exception as e:
            print(f"Error applying MergeTab config: {e}")
            QMessageBox.warning(self, "Config Error", f"Failed to apply some settings: {e}")
