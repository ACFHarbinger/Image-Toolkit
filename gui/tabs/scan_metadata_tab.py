import os

from pathlib import Path
from typing import Set, Dict, Any, List, Tuple, Optional
from PySide6.QtGui import QPixmap, QAction, QResizeEvent
from PySide6.QtCore import (
    Qt, QThread, Slot, QPoint, QTimer
)
from PySide6.QtWidgets import (
    QWidget, QGroupBox, QCheckBox,
    QComboBox, QLineEdit, QFileDialog, 
    QHBoxLayout, QVBoxLayout, QScrollArea, 
    QProgressDialog, QMessageBox, QGridLayout,
    QPushButton, QLabel, QFormLayout, QMenu,
)
from .base_tab import BaseTab
from ..windows import ImagePreviewWindow
from ..components import ClickableLabel, MarqueeScrollArea
from ..helpers import ImageScannerWorker, BatchThumbnailLoaderWorker
from ..styles.style import apply_shadow_effect


class ScanMetadataTab(BaseTab):
    """
    Manages file and directory metadata scanning, image preview gallery, and batch database operations.
    """
    def __init__(self, db_tab_ref, dropdown=True):
        super().__init__()
        self.db_tab_ref = db_tab_ref
        self.dropdown = dropdown
        
        self.scan_image_list: list[str] = []
        self.selected_image_paths: Set[str] = set()
        self.selected_scan_image_path: str = None
        self.open_preview_windows: list[ImagePreviewWindow] = [] 

        # Database view filter state
        self.view_db_only: bool = False
        self._db_was_connected: bool = False 

        # UI Maps
        self.path_to_wrapper_map: Dict[str, ClickableLabel] = {}
        self.selected_card_map: Dict[str, ClickableLabel] = {}

        # Gallery Constants
        self.thumbnail_size = 150
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width + 20
        
        # Thread references
        self.scan_thread = None
        self.scan_worker = None
        self.loader_thread = None
        self.loader_worker = None
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
        self.view_db_only_button = QPushButton("View Database Only (Off)")
        self.view_db_only_button.setCheckable(True)
        apply_shadow_effect(self.view_db_only_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.view_db_only_button.toggled.connect(self.toggle_db_only_view) 

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
        scan_action_layout.addWidget(self.view_db_only_button)
        scan_action_layout.addWidget(self.upsert_button)
        scan_action_layout.addWidget(self.refresh_image_button)
        scan_action_layout.addWidget(self.delete_selected_button)
        
        main_layout.addLayout(scan_action_layout) 
        self.setLayout(main_layout)
        
        self.update_button_states(connected=False) 
        self.populate_selected_images_gallery()

    # --- RESIZE & REFLOW LOGIC ---
    
    def resizeEvent(self, event: QResizeEvent):
        """Trigger grid reflow when window is resized."""
        self._resize_timer.start(150) # Debounce resize
        super().resizeEvent(event)

    def showEvent(self, event):
        """Ensure grid is correct when tab is shown."""
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
            layout.addWidget(widget, row, col, Qt.AlignLeft | Qt.AlignTop)
            
    # ---------------------------------------------------------

    def _create_gallery_card(self, path: str, pixmap: Optional[QPixmap], is_selected: bool) -> ClickableLabel:
        thumb_size = self.thumbnail_size
        card_wrapper = ClickableLabel(path)
        card_wrapper.setFixedSize(thumb_size + 10, thumb_size + 10)
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
        self._update_card_style(img_label, is_selected)
        return card_wrapper

    def _update_card_style(self, img_label: QLabel, is_selected: bool):
        if is_selected:
            img_label.setStyleSheet("border: 3px solid #5865f2; background-color: #36393f;")
        else:
            img_label.setStyleSheet("border: 1px solid #4f545c; background-color: #36393f;")
            
    def _get_tags_from_db(self) -> List[str]:
        db = self.db_tab_ref.db
        if not db: 
            return []
        try:
            db_tags = [item['name'] for item in db.get_all_tags_with_types()]
            if db_tags:
                return sorted(list(set(db_tags))) 
        except Exception:
            pass 
        return []

    def _setup_tag_checkboxes(self):
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
            if inner_label:
                self._update_card_style(inner_label, selected)
        
        self.populate_selected_images_gallery()
        self.update_button_states(connected=(self.db_tab_ref.db is not None))

    def handle_marquee_selection(self, paths_from_marquee: set, is_ctrl_pressed: bool):
        if not is_ctrl_pressed:
            self.selected_image_paths = paths_from_marquee
        else:
            self.selected_image_paths.update(paths_from_marquee)

        for path, wrapper in self.path_to_wrapper_map.items():
            inner_label = wrapper.findChild(QLabel)
            if inner_label:
                self._update_card_style(inner_label, path in self.selected_image_paths)
            
        self.populate_selected_images_gallery()
        self.update_button_states(connected=(self.db_tab_ref.db is not None))

    def populate_selected_images_gallery(self):
        """Rebuilds the bottom panel using the same card style."""
        self.selected_images_widget.setUpdatesEnabled(False)
        self._clear_gallery(self.selected_grid_layout)
        self.selected_card_map = {}
        
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
            if path in self.path_to_wrapper_map:
                wrapper = self.path_to_wrapper_map[path]
                inner_label = wrapper.findChild(QLabel)
                if inner_label and inner_label.pixmap():
                    pixmap = inner_label.pixmap()
            
            card = self._create_gallery_card(path, pixmap, is_selected=True)
            card.path_clicked.connect(lambda checked, p=path: self.toggle_selection(p))
            card.path_double_clicked.connect(self._view_single_image_preview)
            card.path_right_clicked.connect(self.show_image_context_menu)
            
            row = i // columns
            col = i % columns
            self.selected_card_map[path] = card
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
        
        if not is_refresh or not self.scan_image_list:
            if self.loader_thread and self.loader_thread.isRunning():
                self.loader_thread.quit()
                self.loader_thread.wait()
            
            self.loader_thread = None
            self.loader_worker = None
            self.path_to_wrapper_map = {} 
            self._clear_gallery(self.scan_thumbnail_layout)
            self._clear_gallery(self.selected_grid_layout) 
            self.scan_image_list = []
            self.selected_image_paths = set()
            self.selected_card_map = {}

            self.loading_dialog = QProgressDialog("Scanning directory...", "Cancel", 0, 0, self)
            self.loading_dialog.setWindowModality(Qt.WindowModal)
            self.loading_dialog.setWindowTitle("Please Wait")
            self.loading_dialog.setMinimumDuration(0)
            self.loading_dialog.setCancelButton(None) 
            self.loading_dialog.show()
            
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
        
        self.display_scan_results(self.scan_image_list)

    @Slot()
    def on_scan_thread_finished(self):
        self.scan_thread = None
        self.scan_worker = None

    @Slot(list)
    def process_scan_results(self, image_paths: list[str]):
        self.scan_image_list = image_paths
        self.display_scan_results(image_paths)

    def display_scan_results(self, image_paths: list[str]):
        final_paths_to_load = image_paths
        if self.view_db_only and self.db_tab_ref.db is not None:
            db = self.db_tab_ref.db
            paths_in_db = set()
            for path in image_paths:
                if db.get_image_by_path(path):
                    paths_in_db.add(path)
            final_paths_to_load = sorted(list(paths_in_db))

        if not final_paths_to_load:
            if self.loading_dialog: self.loading_dialog.close()
            no_images_label = QLabel("No supported images found.")
            if self.view_db_only:
                 no_images_label.setText("No scanned images found in the database.")
            no_images_label.setAlignment(Qt.AlignCenter)
            no_images_label.setStyleSheet("color: #b9bbbe;")
            self._clear_gallery(self.scan_thumbnail_layout)
            self.scan_thumbnail_layout.addWidget(no_images_label, 0, 0, 1, 1)
            return
        
        if self.loading_dialog:
            self.loading_dialog.setMaximum(len(final_paths_to_load))
            self.loading_dialog.setValue(0)
            self.loading_dialog.setLabelText(f"Loading images 0 of {len(final_paths_to_load)}...")
        
        self.loader_worker = BatchThumbnailLoaderWorker(final_paths_to_load, self.thumbnail_size)
        self.loader_thread = QThread()
        self.loader_worker.moveToThread(self.loader_thread)
        
        self.loader_thread.started.connect(self.loader_worker.run_load_batch)
        self.loader_worker.progress_updated.connect(self.update_loading_progress)
        self.loader_worker.batch_finished.connect(self.handle_batch_finished)
        
        self.loader_worker.batch_finished.connect(self.loader_thread.quit)
        self.loader_worker.batch_finished.connect(self.loader_worker.deleteLater)
        self.loader_thread.finished.connect(self.loader_thread.deleteLater)
        self.loader_thread.finished.connect(self.on_loader_thread_finished)
        
        self.loader_thread.start()

    @Slot()
    def on_loader_thread_finished(self):
        self.loader_thread = None
        self.loader_worker = None

    @Slot(int, int)
    def update_loading_progress(self, current: int, total: int):
        dialog = self.loading_dialog 
        if dialog:
            dialog.setValue(current)
            dialog.setLabelText(f"Loading {current} of {total}...")

    @Slot(list)
    def handle_batch_finished(self, loaded_results: List[Tuple[str, QPixmap]]):
        self._clear_gallery(self.scan_thumbnail_layout)
        self.path_to_wrapper_map.clear()
        
        # Calculate columns dynamically
        columns = self._columns()
        
        for index, (path, pixmap) in enumerate(loaded_results):
            row = index // columns
            col = index % columns

            is_selected = path in self.selected_image_paths
            card = self._create_gallery_card(path, pixmap, is_selected)
            
            card.path_clicked.connect(lambda checked, p=path: self.toggle_selection(p))
            card.path_double_clicked.connect(self._view_single_image_preview) 
            card.path_right_clicked.connect(self.show_image_context_menu)

            self.scan_thumbnail_layout.addWidget(card, row, col, Qt.AlignLeft | Qt.AlignTop)
            self.path_to_wrapper_map[path] = card 
        
        if self.loading_dialog:
            self.loading_dialog.close()
            self.loading_dialog = None
            
        self.populate_selected_images_gallery()
        self.update_button_states(connected=(self.db_tab_ref.db is not None))

    def handle_scan_error(self, message: str):
        if self.loading_dialog: self.loading_dialog.close()
        QMessageBox.warning(self, "Error Scanning", message)

    @Slot(bool)
    def toggle_db_only_view(self, checked: bool):
        db_connected = (self.db_tab_ref.db is not None)
        if not db_connected and checked:
            QMessageBox.warning(self, "Database Required", "Please connect to the database to filter by database content.")
            self.view_db_only_button.setChecked(False) 
            return

        self.view_db_only = checked
        self.view_db_only_button.setText(f"View Database Only ({'On' if checked else 'Off'})")
        if self.view_db_only:
            self.view_db_only_button.setStyleSheet("background-color: #7289da; color: white;")
        else:
            self.view_db_only_button.setStyleSheet("") 
            
        if hasattr(self, 'scanned_dir') and self.scanned_dir:
            self.populate_scan_image_gallery(self.scanned_dir, is_refresh=True)

    def update_button_states(self, connected: bool):
        selection_count = len(self.selected_image_paths)
        self.refresh_image_button.setEnabled(True) 
        
        if connected and not self._db_was_connected:
            self._setup_tag_checkboxes()
        self._db_was_connected = connected 

        self.view_db_only_button.setEnabled(connected)
        
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
                self.display_scan_results(self.scan_image_list) 
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
            for path in self.selected_image_paths:
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
            QMessageBox.information(self, "Success", "Upsert complete.")
            self.metadata_group.setVisible(False)
            self.refresh_image_directory()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def delete_selected_images(self):
        db = self.db_tab_ref.db
        if not db: return
        if QMessageBox.question(self, "Confirm", f"Delete {len(self.selected_image_paths)} entries from DB?") == QMessageBox.Yes:
            for path in self.selected_image_paths:
                img = db.get_image_by_path(path)
                if img: db.delete_image(img['id'])
            QMessageBox.information(self, "Success", "Deleted entries.")
            self.refresh_image_directory()

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
