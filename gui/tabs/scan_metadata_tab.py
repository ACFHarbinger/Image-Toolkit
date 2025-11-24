import os

from pathlib import Path
from typing import Set, Dict, Any, List, Tuple, Optional
from PySide6.QtGui import QPixmap, QAction, QResizeEvent
from PySide6.QtCore import (
    Qt, QThread, Slot, QPoint, QTimer, QThreadPool, QEventLoop
)
from PySide6.QtWidgets import (
    QWidget, QGroupBox, QCheckBox,
    QComboBox, QLineEdit, QFileDialog, 
    QHBoxLayout, QVBoxLayout, QScrollArea, 
    QPushButton, QLabel, QFormLayout, QMenu,
    QProgressDialog, QMessageBox, QGridLayout,
)
from ..windows import ImagePreviewWindow
from ..components import ClickableLabel, MarqueeScrollArea
from ..helpers import ImageScannerWorker, ImageLoaderWorker
from ..styles.style import apply_shadow_effect


class ScanMetadataTab(QWidget):
    """
    Manages file and directory metadata scanning, image preview gallery, and batch database operations.
    """
    def __init__(self, db_tab_ref, dropdown=True):
        super().__init__()
        self.db_tab_ref = db_tab_ref
        self.dropdown = dropdown
        
        self.scan_image_list: list[str] = []
        self.selected_image_paths: Set[str] = set()
        self.open_preview_windows: list[ImagePreviewWindow] = [] 

        # Database view filter state
        self.view_new_only: bool = False
        self._db_was_connected: bool = False 
        
        # Cancellation flag
        self._loading_cancelled = False

        # UI Maps
        # Maps file_path -> ClickableLabel widget
        self.path_to_wrapper_map: Dict[str, ClickableLabel] = {}
        
        # Gallery Constants
        self.thumbnail_size = 150
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width + 20
        
        # Threading references
        self.scan_thread = None
        self.scan_worker = None
        
        # ThreadPool for image loading
        self.thread_pool = QThreadPool()
        # accumulators for threading results
        self._loaded_results_buffer: List[Tuple[str, QPixmap]] = []
        self._images_loaded_count = 0
        self._total_images_to_load = 0
        
        self.loading_dialog = None
        
        # --- Resize Handling ---
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._repack_galleries)
        
        main_layout = QVBoxLayout(self)

        # --- Scrollable Content Setup ---
        page_scroll = QScrollArea()
        page_scroll.setWidgetResizable(True)
        page_scroll.setStyleSheet("QScrollArea { border: none; }")
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- Scan Directory Section ---
        scan_group = QGroupBox("Scan Directory")
        scan_layout = QVBoxLayout()
        scan_layout.setContentsMargins(10, 20, 10, 10) 
        
        scan_dir_layout = QHBoxLayout()
        self.scan_directory_path = QLineEdit()
        self.scan_directory_path.setPlaceholderText("Select directory to scan...")
        self.scan_directory_path.returnPressed.connect(self.handle_scan_directory_return)
        
        btn_browse_scan = QPushButton("Browse...")
        btn_browse_scan.clicked.connect(self.browse_scan_directory)
        apply_shadow_effect(btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3)

        scan_dir_layout.addWidget(self.scan_directory_path)
        scan_dir_layout.addWidget(btn_browse_scan)
        scan_layout.addLayout(scan_dir_layout)
        scan_group.setLayout(scan_layout)
        content_layout.addWidget(scan_group)
        try:
            base_dir = Path.cwd()
            while base_dir.name != 'Image-Toolkit' and base_dir.parent != base_dir:
                base_dir = base_dir.parent
            if base_dir.name == 'Image-Toolkit':
                self.last_browsed_scan_dir = str(base_dir / 'data')
            else:
                self.last_browsed_scan_dir = os.getcwd() 
        except Exception:
            self.last_browsed_scan_dir = os.getcwd() 

        # --- Galleries ---
        
        # A. Top Gallery: Scan Results
        self.scan_scroll_area = MarqueeScrollArea() 
        self.scan_scroll_area.setWidgetResizable(True)
        self.scan_scroll_area.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")
        self.scan_scroll_area.setMinimumHeight(600) 

        self.scan_thumbnail_widget = QWidget()
        self.scan_thumbnail_widget.setStyleSheet("background-color: #2c2f33;")
        self.scan_thumbnail_layout = QGridLayout(self.scan_thumbnail_widget)
        self.scan_thumbnail_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        
        self.scan_scroll_area.setWidget(self.scan_thumbnail_widget)
        self.scan_scroll_area.selection_changed.connect(self.handle_marquee_selection)
        content_layout.addWidget(self.scan_scroll_area, 1)
        
        # B. Bottom Gallery: Selected Images
        self.selected_images_area = MarqueeScrollArea() 
        self.selected_images_area.setWidgetResizable(True)
        self.selected_images_area.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")
        self.selected_images_area.setMinimumHeight(400)
        self.selected_images_area.setVisible(True) 
        self.selected_images_area.selection_changed.connect(self.handle_marquee_selection) 

        self.selected_images_widget = QWidget()
        self.selected_images_widget.setStyleSheet("background-color: #2c2f33;")
        self.selected_grid_layout = QGridLayout(self.selected_images_widget)
        self.selected_grid_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter) 
        
        self.selected_images_area.setWidget(self.selected_images_widget)
        content_layout.addWidget(self.selected_images_area, 1)
        
        # --- Metadata Group Box ---
        self.metadata_group = QGroupBox("Batch Metadata (Applies to ALL Selected Images)")
        self.metadata_group.setVisible(False) 
        metadata_vbox = QVBoxLayout(self.metadata_group)
        
        form_layout = QFormLayout()
        
        group_layout = QHBoxLayout()
        self.group_combo = QComboBox()
        self.group_combo.setEditable(True)
        self.group_combo.setPlaceholderText("Enter or select Group/Series name...")
        self.group_combo.lineEdit().returnPressed.connect(lambda: self.upsert_button.click())
        group_layout.addWidget(self.group_combo)
        form_layout.addRow("Group Name:", group_layout)
        
        subgroup_layout = QHBoxLayout()
        self.subgroup_combo = QComboBox()
        self.subgroup_combo.setEditable(True)
        self.subgroup_combo.setPlaceholderText("Enter or select Subgroup name...")
        self.subgroup_combo.lineEdit().returnPressed.connect(lambda: self.upsert_button.click())
        subgroup_layout.addWidget(self.subgroup_combo)
        form_layout.addRow("Subgroup Name:", subgroup_layout)
        
        tags_scroll = QScrollArea()
        tags_scroll.setMinimumHeight(400) 
        tags_scroll.setWidgetResizable(True)
        self.tags_widget = QWidget()
        self.tags_layout = QGridLayout(self.tags_widget)
        tags_scroll.setWidget(self.tags_widget)
        
        self.tag_checkboxes = {}
        self._setup_tag_checkboxes() 

        form_layout.addRow("Tags:", tags_scroll)
        metadata_vbox.addLayout(form_layout)
        content_layout.addWidget(self.metadata_group)

        page_scroll.setWidget(content_widget)
        main_layout.addWidget(page_scroll, 1)

        # --- Action buttons ---
        
        self.view_new_only_button = QPushButton("👁️ Show Only New (Not in DB)")
        self.view_new_only_button.setCheckable(True)
        self.view_new_only_button.setChecked(False)
        apply_shadow_effect(self.view_new_only_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.view_new_only_button.toggled.connect(self.toggle_new_only_view) 

        self.upsert_button = QPushButton("Add/Update Database Data")
        self.upsert_button.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 10px;")
        apply_shadow_effect(self.upsert_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.upsert_button.clicked.connect(self.perform_upsert_operation)

        self.refresh_image_button = QPushButton("Refresh Image Directory")
        self.refresh_image_button.setStyleSheet("background-color: #f1c40f; color: white; font-weight: bold; padding: 10px;")
        apply_shadow_effect(self.refresh_image_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.refresh_image_button.clicked.connect(self.refresh_image_directory) 

        self.delete_selected_button = QPushButton("Delete Images Data from Database")
        self.delete_selected_button.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; padding: 10px;")
        apply_shadow_effect(self.delete_selected_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.delete_selected_button.clicked.connect(self.delete_selected_images)
        
        scan_action_layout = QHBoxLayout()
        scan_action_layout.addWidget(self.view_new_only_button)
        scan_action_layout.addWidget(self.upsert_button)
        scan_action_layout.addWidget(self.refresh_image_button)
        scan_action_layout.addWidget(self.delete_selected_button)
        
        main_layout.addLayout(scan_action_layout) 
        self.setLayout(main_layout)
        
        self.update_button_states(connected=False) 
        self.populate_selected_images_gallery()

    # --- THREAD SAFETY CLEANUP METHOD ---
    def _stop_running_threads(self):
        """Safely interrupts and cleans up any active scanner or loader threads."""
        self._loading_cancelled = True
        
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.requestInterruption()
            self.scan_thread.quit()
            self.scan_thread.wait(1000)
            self.scan_worker = None
            self.scan_thread = None
            
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
    # ------------------------------------

    # --- RESIZE & REFLOW LOGIC ---
    
    def resizeEvent(self, event: QResizeEvent):
        """Trigger grid reflow when window is resized."""
        self._resize_timer.start(150) # Debounce resize
        super().resizeEvent(event)

    def showEvent(self, event):
        """Trigger grid reflow when tab is shown."""
        self._repack_galleries()
        super().showEvent(event)

    def _repack_galleries(self):
        """Re-calculates columns and moves widgets for all galleries."""
        self._repack_specific_layout(self.scan_thumbnail_layout, self.scan_scroll_area)
        self._repack_specific_layout(self.selected_grid_layout, self.selected_images_area)

    def _repack_specific_layout(self, layout: QGridLayout, scroll_area: QScrollArea):
        """Extracts all items and re-adds them based on new width."""
        width = scroll_area.viewport().width()
        if width <= 0:
            width = scroll_area.width()
        if width <= 0: 
            return
            
        columns = max(1, width // self.approx_item_width)
        
        # 1. Extract all widgets from layout
        items = []
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                items.append(item.widget())
        
        # 2. Re-add them in the new grid configuration
        for idx, widget in enumerate(items):
            row = idx // columns
            col = idx % columns
            
            align = Qt.AlignLeft | Qt.AlignTop
            # Handle placeholder alignment for the main gallery
            if isinstance(widget, QLabel) and ("No supported images" in widget.text() or "No scanned images" in widget.text()):
                 align = Qt.AlignCenter
                 layout.addWidget(widget, 0, 0, 1, columns, align)
                 return
                 
            layout.addWidget(widget, row, col, align)
            
    # ---------------------------------------------------------

    def _create_gallery_card(self, path: str, pixmap: Optional[QPixmap], is_selected: bool, is_in_db: bool = False) -> ClickableLabel:
        thumb_size = self.thumbnail_size
        card_wrapper = ClickableLabel(path)
        card_wrapper.setFixedSize(thumb_size + 10, thumb_size + 10)
        
        # Attach custom property to store DB status on the widget
        card_wrapper.setProperty("in_db", is_in_db)
        
        card_layout = QVBoxLayout(card_wrapper)
        card_layout.setContentsMargins(0, 0, 0, 0)
        
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignCenter)
        img_label.setFixedSize(thumb_size, thumb_size)
        
        if pixmap and not pixmap.isNull():
            if pixmap.width() > thumb_size or pixmap.height() > thumb_size:
                 scaled = pixmap.scaled(thumb_size, thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                 img_label.setPixmap(scaled)
            else:
                 img_label.setPixmap(pixmap)
        else:
            img_label.setText("Error")
            img_label.setStyleSheet("color: #e74c3c; border: 1px solid #e74c3c;")
        
        card_layout.addWidget(img_label)
        card_wrapper.setLayout(card_layout)
        self._update_card_style(img_label, is_selected, is_in_db)
        return card_wrapper

    def _update_card_style(self, img_label: QLabel, is_selected: bool, is_in_db: bool):
        """
        Updates card border style.
        Blue = Selected (Highest priority)
        Green = In Database (Medium priority)
        Grey = Default
        """
        if is_selected:
            # Blue Border
            img_label.setStyleSheet("border: 3px solid #5865f2; background-color: #36393f;")
        elif is_in_db:
            # Green Border
            img_label.setStyleSheet("border: 3px solid #2ecc71; background-color: #36393f;")
        else:
            # Default Grey Border
            img_label.setStyleSheet("border: 1px solid #4f545c; background-color: #36393f;")
            
    def _get_tags_from_db(self) -> List[Dict[str, str]]:
        """
        Fetches tags with their types. Returns [{'name': 'x', 'type': 'y'}]
        """
        db = self.db_tab_ref.db
        if not db: 
            return []
        try:
            # Expecting get_all_tags_with_types() from the DB class
            return db.get_all_tags_with_types()
        except Exception:
            pass 
        return []

    def _setup_tag_checkboxes(self):
        """
        Creates checkboxes with color coding based on tag type.
        """
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.tag_checkboxes = {}
        tags_data = self._get_tags_from_db()
        
        # --- Color Map (Matches Search Tab) ---
        color_map = {
            'Artist': '#5865f2',    # Blue/Purple
            'Series': '#f1c40f',    # Yellow
            'Character': '#2ecc71', # Green
            'General': '#e91e63',   # Pink
            'Meta': '#9b59b6',      # Purple
            '': '#c7c7c7',          # Grey
            None: '#c7c7c7'
        }
        
        columns = 4
        for i, tag_data in enumerate(tags_data):
            tag_name = tag_data['name']
            tag_type = tag_data['type'] if tag_data.get('type') else ''
            
            checkbox = QCheckBox(tag_name.replace("_", " ").title())
            
            # Apply Color
            text_color = color_map.get(tag_type, color_map[''])
            checkbox.setStyleSheet(f"QCheckBox {{ color: {text_color}; }}")
            
            self.tag_checkboxes[tag_name] = checkbox
            self.tags_layout.addWidget(checkbox, i // columns, i % columns)

    def _columns(self) -> int:
        width = self.scan_scroll_area.viewport().width()
        if width <= 0:
            width = self.scan_scroll_area.width()
        if width <= 0:
            return 4 
        columns = width // self.approx_item_width
        return max(1, columns)

    def _clear_gallery(self, layout: QGridLayout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def toggle_selection(self, path):
        if not path: 
            self.update_button_states(connected=(self.db_tab_ref.db is not None))
            return

        if path in self.selected_image_paths:
            self.selected_image_paths.remove(path)
            selected = False
        else:
            self.selected_image_paths.add(path)
            selected = True
        
        if path in self.path_to_wrapper_map:
            wrapper = self.path_to_wrapper_map[path]
            inner_label = wrapper.findChild(QLabel)
            is_in_db = wrapper.property("in_db")
            if inner_label:
                self._update_card_style(inner_label, selected, is_in_db)
        
        self.populate_selected_images_gallery()
        self.update_button_states(connected=(self.db_tab_ref.db is not None))

    def handle_marquee_selection(self, paths_from_marquee: set, is_ctrl_pressed: bool):
        if not is_ctrl_pressed:
            self.selected_image_paths = paths_from_marquee
        else:
            self.selected_image_paths.update(paths_from_marquee)

        for path, wrapper in self.path_to_wrapper_map.items():
            inner_label = wrapper.findChild(QLabel)
            is_in_db = wrapper.property("in_db")
            if inner_label:
                self._update_card_style(inner_label, path in self.selected_image_paths, is_in_db)
            
        self.populate_selected_images_gallery()
        self.update_button_states(connected=(self.db_tab_ref.db is not None))

    def populate_selected_images_gallery(self):
        """Rebuilds the bottom panel using the same card style."""
        self.selected_images_widget.setUpdatesEnabled(False)
        self._clear_gallery(self.selected_grid_layout)
        
        paths = sorted(list(self.selected_image_paths))
        
        # Use dynamic columns here
        widget_width = self.selected_images_area.viewport().width()
        if widget_width <= 0: widget_width = self.selected_images_area.width()
        columns = max(1, widget_width // self.approx_item_width)

        if not paths:
            empty_label = QLabel("Select images from the scan results above.")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #b9bbbe; padding: 50px;")
            self.selected_grid_layout.addWidget(empty_label, 0, 0, 1, columns)
            self.selected_images_widget.setUpdatesEnabled(True)
            return

        for i, path in enumerate(paths):
            pixmap = None
            is_in_db = False
            
            if path in self.path_to_wrapper_map:
                wrapper = self.path_to_wrapper_map[path]
                is_in_db = wrapper.property("in_db")
                inner_label = wrapper.findChild(QLabel)
                if inner_label and inner_label.pixmap():
                    pixmap = inner_label.pixmap()
            
            card = self._create_gallery_card(path, pixmap, is_selected=True, is_in_db=is_in_db)
            card.path_clicked.connect(lambda checked, p=path: self.toggle_selection(p))
            card.path_double_clicked.connect(self._view_single_image_preview)
            card.path_right_clicked.connect(self.show_image_context_menu)
            
            row = i // columns
            col = i % columns
            self.selected_grid_layout.addWidget(card, row, col, Qt.AlignLeft | Qt.AlignTop)
            
        self.selected_images_widget.setUpdatesEnabled(True)
        self.selected_images_widget.adjustSize()

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

    def populate_scan_image_gallery(self, directory: str, is_refresh: bool = False):
        self.scanned_dir = directory
        
        # Stop all running threads before starting a new scan/load
        self._stop_running_threads()
        self._loading_cancelled = False
        
        if not is_refresh or not self.scan_image_list:
            self.path_to_wrapper_map = {} 
            self._clear_gallery(self.scan_thumbnail_layout)
            self._clear_gallery(self.selected_grid_layout) 
            self.scan_image_list = []
            self.selected_image_paths = set()

            self.loading_dialog = QProgressDialog("Scanning directory...", "Cancel", 0, 0, self)
            self.loading_dialog.setWindowModality(Qt.WindowModal)
            self.loading_dialog.setWindowTitle("Please Wait")
            self.loading_dialog.setMinimumDuration(0)
            self.loading_dialog.canceled.connect(self.cancel_loading)
            
            # --- FIX: Blocking Wait to ensure Scanner Dialog Visibility ---
            self.loading_dialog.show()
            
            # Block the main thread but allow GUI events (like painting) to process.
            loop = QEventLoop()
            # A single shot timer of 1ms is used to exit the blocking loop, 
            # ensuring the dialog gets painted before control returns.
            QTimer.singleShot(1, loop.quit)
            loop.exec()
            # -------------------------------------------------------------
            
            self.scan_worker = ImageScannerWorker(directory)
            self.scan_thread = QThread() 
            self.scan_worker.moveToThread(self.scan_thread) 
            
            self.scan_thread.started.connect(self.scan_worker.run_scan)
            self.scan_worker.scan_finished.connect(self.process_scan_results) 
            self.scan_worker.scan_error.connect(self.handle_scan_error)
            
            self.scan_worker.scan_finished.connect(self.scan_thread.quit)
            self.scan_worker.scan_finished.connect(self.scan_worker.deleteLater)
            self.scan_thread.finished.connect(self.on_scan_thread_finished)
            self.scan_thread.finished.connect(self.scan_thread.deleteLater)
            
            self.scan_thread.start()
            return
        
        # If performing a refresh (toggling view_new_only)
        self.display_scan_results(self.scan_image_list)

    @Slot()
    def on_scan_thread_finished(self):
        self.scan_thread = None
        self.scan_worker = None

    @Slot(list)
    def process_scan_results(self, image_paths: list[str]):
        if self._loading_cancelled:
            return
        self.scan_image_list = image_paths
        self.display_scan_results(image_paths)

    def display_scan_results(self, image_paths: list[str]):
        final_paths_to_load = image_paths
        
        # FILTERING LOGIC: Check DB status (omitted for brevity)
        if self.db_tab_ref.db is not None:
            db = self.db_tab_ref.db
            
            if self.view_new_only:
                paths_not_in_db = []
                for path in image_paths:
                    if not db.get_image_by_path(path):
                        paths_not_in_db.append(path)
                final_paths_to_load = sorted(list(paths_not_in_db))
        # --------------------------------------------------------

        if not final_paths_to_load:
            if self.loading_dialog: self.loading_dialog.close()
            # ... (Existing no-images label setup) ...
            return
        
        # Setup Loading Progress Dialog
        self._loaded_results_buffer = []
        self._images_loaded_count = 0
        self._total_images_to_load = len(final_paths_to_load)
        
        # Check if dialog needs to be created or just reused
        if not self.loading_dialog:
            self.loading_dialog = QProgressDialog("Loading thumbnails...", "Cancel", 0, self._total_images_to_load, self)
            self.loading_dialog.setWindowModality(Qt.WindowModal)
            self.loading_dialog.setWindowTitle("Please Wait")
            self.loading_dialog.setMinimumDuration(0) 
            self.loading_dialog.canceled.connect(self.cancel_loading)
        
        self.loading_dialog.setMaximum(self._total_images_to_load)
        self.loading_dialog.setValue(0)
        self.loading_dialog.setLabelText(f"Loading image 0 of {self._total_images_to_load}...")
        
        # --- FIX: Ensure visibility using QEventLoop and defer work submission ---
        self.loading_dialog.show()

        # 1. Block the main thread execution for 1ms using QEventLoop.
        loop = QEventLoop()
        QTimer.singleShot(1, loop.quit)
        loop.exec()

        # 2. Schedule the actual work submission using a separate QTimer.singleShot(0).
        # Work submission will update the progress bar instantly.
        QTimer.singleShot(0, lambda: self._start_image_loading_pool(final_paths_to_load))

    def _start_image_loading_pool(self, final_paths_to_load: list[str]):
        """
        Method that submits the tasks to the QThreadPool and updates the progress bar
        immediately upon submission.
        """
        if self._loading_cancelled:
            return
            
        # Clear existing thread pool tasks if any
        self.thread_pool.clear()
        
        # FIX: Use a separate counter for tracking task submission (instant feedback)
        submission_count = 0
        
        # Submit tasks to ThreadPool
        for path in final_paths_to_load:
            if self._loading_cancelled: break
            worker = ImageLoaderWorker(path, self.thumbnail_size)
            # Connect the result signal. Signals are processed by the main thread.
            worker.signals.result.connect(self.on_single_image_loaded)
            self.thread_pool.start(worker)
            
            # --- PROGRESS BAR UPDATE ON SUBMISSION (Instant Feedback) ---
            submission_count += 1
            dialog_box = self.loading_dialog
            if dialog_box:
                dialog_box.setValue(submission_count)
                # Update text to reflect that this is submission, not completion.
                dialog_box.setLabelText(f"Loading image {submission_count} of {self._total_images_to_load}...")
            # -------------------------------------------------------------

    @Slot(str, QPixmap)
    def on_single_image_loaded(self, path: str, pixmap: QPixmap):
        """
        Called when a single ImageLoaderWorker finishes via signal.
        Runs on the main GUI thread.
        """
        if self._loading_cancelled: return
        
        self._loaded_results_buffer.append((path, pixmap))
        # We still increment the internal count to check for finalization
        self._images_loaded_count += 1 
        
        # Check for completion
        if self._images_loaded_count >= self._total_images_to_load:
            self._finalize_batch_loading()

    def _finalize_batch_loading(self):
        """
        Called when all threads in the pool have reported back.
        Populates the gallery and cleans up.
        """
        if self._loading_cancelled: return
        
        self._clear_gallery(self.scan_thumbnail_layout)
        self.path_to_wrapper_map.clear()
        
        # Threads finish in random order, so we sort by path to keep the gallery tidy
        sorted_results = sorted(self._loaded_results_buffer, key=lambda x: x[0])
        
        # --- OPTIMIZATION: BATCH DB CHECK ---
        db = self.db_tab_ref.db
        paths_in_db_set = set()
        
        if db:
            try:
                paths_to_check = [p for p, _ in sorted_results]
                if paths_to_check:
                    with db.conn.cursor() as cur:
                        cur.execute("SELECT file_path FROM images WHERE file_path = ANY(%s)", (paths_to_check,))
                        rows = cur.fetchall()
                        paths_in_db_set = {row[0] for row in rows}
            except Exception as e:
                print(f"Batch DB check error: {e}")
        # ------------------------------------

        columns = self._columns()
        
        for index, (path, pixmap) in enumerate(sorted_results):
            row = index // columns
            col = index % columns
            
            is_in_db = path in paths_in_db_set
            is_selected = path in self.selected_image_paths
            
            card = self._create_gallery_card(path, pixmap, is_selected, is_in_db=is_in_db)
            
            card.path_clicked.connect(lambda checked, p=path: self.toggle_selection(p))
            card.path_double_clicked.connect(self._view_single_image_preview) 
            card.path_right_clicked.connect(self.show_image_context_menu)

            self.scan_thumbnail_layout.addWidget(card, row, col, Qt.AlignLeft | Qt.AlignTop)
            self.path_to_wrapper_map[path] = card 
        
        self.scan_thumbnail_widget.adjustSize()
        
        if self.loading_dialog:
            self.loading_dialog.close()
            self.loading_dialog = None
            
        self.populate_selected_images_gallery()
        self.update_button_states(connected=(self.db_tab_ref.db is not None))

    def handle_scan_error(self, message: str):
        if self.loading_dialog: self.loading_dialog.close()
        QMessageBox.warning(self, "Error Scanning", message)

    @Slot(bool)
    def toggle_new_only_view(self, checked: bool):
        db_connected = (self.db_tab_ref.db is not None)
        if not db_connected and checked:
            QMessageBox.warning(self, "Database Required", "Please connect to the database to filter by database content.")
            self.view_new_only_button.setChecked(False) 
            return

        self.view_new_only = checked
        if self.view_new_only:
            self.view_new_only_button.setText("👁️ Show Only New (On)")
            self.view_new_only_button.setStyleSheet("background-color: #e67e22; color: white; border: 2px solid #d35400;")
        else:
            self.view_new_only_button.setText("👁️ Show Only New (Off)")
            self.view_new_only_button.setStyleSheet("") 
            
        if hasattr(self, 'scanned_dir') and self.scanned_dir:
            # This triggers a new load/filter process
            self.populate_scan_image_gallery(self.scanned_dir, is_refresh=True)

    def update_button_states(self, connected: bool):
        selection_count = len(self.selected_image_paths)
        self.refresh_image_button.setEnabled(True) 
        
        if connected and not self._db_was_connected:
            self._setup_tag_checkboxes()
        self._db_was_connected = connected 

        self.view_new_only_button.setEnabled(connected)
        
        if self.metadata_group.isVisible():
             self.upsert_button.setText(f"Confirm and Upsert {selection_count} Images")
        else:
            self.upsert_button.setText(f"Add/Update {selection_count} Selected Images")
        
        self.upsert_button.setEnabled(connected and selection_count > 0)
        self.delete_selected_button.setText(f"Delete {selection_count} Images from DB")
        self.delete_selected_button.setEnabled(connected and selection_count > 0)

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)
        view_props_action = QAction("🖼️ View Properties (File/DB)", self)
        view_props_action.triggered.connect(lambda: self._view_image_properties(path))
        menu.addAction(view_props_action)
        menu.addSeparator()
        view_action = QAction("View Full Size Preview", self)
        view_action.triggered.connect(lambda: self._view_single_image_preview(path))
        menu.addAction(view_action)
        menu.addSeparator()
        is_selected = path in self.selected_image_paths
        toggle_text = "Deselect" if is_selected else "Select"
        toggle_action = QAction(toggle_text, self)
        toggle_action.triggered.connect(lambda: self.toggle_selection(path))
        menu.addAction(toggle_action)
        menu.addSeparator()
        delete_action = QAction("🗑️ Delete Image File (Permanent)", self)
        delete_action.triggered.connect(lambda: self.handle_delete_image(path))
        menu.addAction(delete_action)
        menu.exec(global_pos)

    def _view_image_properties(self, file_path: str):
        db = self.db_tab_ref.db
        path = Path(file_path)
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        file_mtime = os.path.getmtime(file_path) if os.path.exists(file_path) else 'N/A'
        width, height = 'N/A', 'N/A'
        try:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                width = pixmap.width()
                height = pixmap.height()
        except Exception:
            pass
        file_info = f"""
        --- **FILE SYSTEM PROPERTIES** ---
        **Filename:** {path.name}
        **Directory:** {path.parent}
        **Size:** {file_size / (1024 * 1024):.2f} MB ({file_size} bytes)
        **Dimensions:** {width} x {height} pixels
        **Modified:** {file_mtime}
        """
        db_info = "\n--- **DATABASE METADATA** ---"
        if db:
            try:
                db_record = db.get_image_by_path(file_path)
                if db_record:
                    db_info += f"""
        **DB ID:** {db_record.get('id')}
        **Group:** {db_record.get('group_name') or 'N/A'}
        **Subgroup:** {db_record.get('subgroup_name') or 'N/A'}
        **Tags:** {', '.join(db_record.get('tags', [])) or 'None'}
        **DB Width:** {db_record.get('width') or 'N/A'}
        **DB Height:** {db_record.get('height') or 'N/A'}
        **Added:** {db_record.get('date_added')}
        """
                else:
                    db_info += "\nImage not found in database."
            except Exception as e:
                db_info += f"\nError querying database: {e}"
        else:
            db_info += "\nDatabase is not connected."
        QMessageBox.information(self, f"Image Properties: {path.name}", file_info + db_info)

    def handle_delete_image(self, path: str):
        if QMessageBox.question(self, "Delete", f"Permanently delete {os.path.basename(path)}?") == QMessageBox.Yes:
            try:
                os.remove(path)
                if path in self.scan_image_list: self.scan_image_list.remove(path)
                if path in self.selected_image_paths: self.selected_image_paths.remove(path)
                
                # Update UI immediately
                if path in self.path_to_wrapper_map:
                     widget = self.path_to_wrapper_map.pop(path)
                     widget.deleteLater()
                     self._repack_galleries()
                
                self.populate_selected_images_gallery()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _view_single_image_preview(self, image_path: str):
        if not os.path.exists(image_path): return
        preview = ImagePreviewWindow(
            image_path=image_path, db_tab_ref=self.db_tab_ref, parent=self, 
            all_paths=self.scan_image_list, start_index=self.scan_image_list.index(image_path) if image_path in self.scan_image_list else 0
        )
        preview.setAttribute(Qt.WA_DeleteOnClose)
        preview.show() 
        self.open_preview_windows.append(preview)

    def perform_upsert_operation(self):
        """
        Adds/Updates selected images in the database.
        DOES NOT trigger a full re-scan. Updates UI locally.
        """
        db = self.db_tab_ref.db
        if not db:
            QMessageBox.warning(self, "Error", "Connect to database first.")
            return
        if not self.metadata_group.isVisible():
            self.metadata_group.setVisible(True)
            self.update_button_states(True)
            return
        try:
            group_name = self.group_combo.currentText().strip() or None
            subgroup_name = self.subgroup_combo.currentText().strip() or None
            tags = [t for t, cb in self.tag_checkboxes.items() if cb.isChecked()] or None
            
            success_count = 0
            
            for path in list(self.selected_image_paths): # Iterate copy for safety
                width, height = None, None
                try:
                    pixmap = QPixmap(path)
                    if not pixmap.isNull():
                        width = pixmap.width()
                        height = pixmap.height()
                except Exception:
                    pass 
                
                existing = db.get_image_by_path(path)
                if existing:
                    db.update_image(
                        existing['id'], group_name=group_name, subgroup_name=subgroup_name, tags=tags
                    )
                else:
                    db.add_image(
                        path, embedding=None, group_name=group_name, subgroup_name=subgroup_name, tags=tags,
                        width=width, height=height
                    )
                success_count += 1
                
                # --- UI LOCAL UPDATE ---
                if path in self.path_to_wrapper_map:
                    widget = self.path_to_wrapper_map[path]
                    
                    if self.view_new_only:
                        # If viewing only new, remove the now-processed image
                        self.scan_thumbnail_layout.removeWidget(widget)
                        widget.deleteLater()
                        del self.path_to_wrapper_map[path]
                        if path in self.scan_image_list:
                            self.scan_image_list.remove(path)
                    else:
                        # Just update the style to indicate it's in DB
                        widget.setProperty("in_db", True)
                        inner_label = widget.findChild(QLabel)
                        # Re-apply style (Selected=True because it is currently selected)
                        self._update_card_style(inner_label, is_selected=True, is_in_db=True)
            
            # Clean up gaps if we removed widgets
            if self.view_new_only:
                self._repack_galleries()

            QMessageBox.information(self, "Success", f"Upserted {success_count} images.")
            self.metadata_group.setVisible(False)
            
            self.update_button_states(True)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def delete_selected_images(self):
        db = self.db_tab_ref.db
        if not db: return
        if QMessageBox.question(self, "Confirm", f"Delete {len(self.selected_image_paths)} entries from DB?") == QMessageBox.Yes:
            for path in self.selected_image_paths:
                img = db.get_image_by_path(path)
                if img: db.delete_image(img['id'])
                
                # Update UI locally
                if path in self.path_to_wrapper_map:
                    wrapper = self.path_to_wrapper_map[path]
                    wrapper.setProperty("in_db", False)
                    inner_label = wrapper.findChild(QLabel)
                    self._update_card_style(inner_label, is_selected=True, is_in_db=False)
            
            QMessageBox.information(self, "Success", "Deleted entries.")

    def refresh_image_directory(self):
        if hasattr(self, 'scanned_dir') and self.scanned_dir:
            self.populate_scan_image_gallery(self.scanned_dir, is_refresh=False)
        else:
             self.handle_scan_directory_return()

    def collect(self) -> dict:
        out = {
            "scan_directory": self.scan_directory_path.text().strip() or None,
            "selected_images": list(self.selected_image_paths),
            "batch_metadata": { 
                "group_name": self.group_combo.currentText().strip() or "",
                "subgroup_name": self.subgroup_combo.currentText().strip() or "",
                "tags": [t for t, cb in self.tag_checkboxes.items() if cb.isChecked()]
            }
        }
        return out

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "scan_directory": "",
            "batch_metadata": {
                "group_name": "",
                "subgroup_name": "",
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
                self.group_combo.setCurrentText(metadata.get("group_name", ""))
                self.subgroup_combo.setCurrentText(metadata.get("subgroup_name", ""))
                self._setup_tag_checkboxes()
                selected_tags = set(metadata.get("tags", []))
                for tag, checkbox in self.tag_checkboxes.items():
                    checkbox.setChecked(tag in selected_tags)
            QMessageBox.information(self, "Config Loaded", "Configuration applied successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Config Error", f"Failed to apply configuration:\n{e}")
