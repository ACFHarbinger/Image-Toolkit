import os
import math

from pathlib import Path
from typing import Set, Dict, Any, List, Tuple, Optional
from PySide6.QtGui import QPixmap, QAction, QResizeEvent
from PySide6.QtCore import (
    Qt, QThread, Slot, QPoint, 
    QTimer, QThreadPool, QEventLoop
)
from PySide6.QtWidgets import (
    QWidget, QGroupBox, QCheckBox,
    QMessageBox, QGridLayout, QMenu,
    QPushButton, QLabel, QFormLayout,
    QComboBox, QLineEdit, QFileDialog, 
    QHBoxLayout, QVBoxLayout, QScrollArea, 
    QToolButton,
)
from ...windows import ImagePreviewWindow
from ...classes import AbstractClassTwoGalleries
from ...components import ClickableLabel, MarqueeScrollArea
from ...helpers import ImageScannerWorker, ImageLoaderWorker
from ...styles.style import apply_shadow_effect
from backend.src.utils.definitions import LOCAL_SOURCE_PATH


class ScanMetadataTab(AbstractClassTwoGalleries):
    """
    Manages file and directory metadata scanning, image preview gallery, and batch database operations.
    """
    def __init__(self, db_tab_ref):
        super().__init__()
        self.db_tab_ref = db_tab_ref
        
        self.scan_image_list: list[str] = []
        # Holds the list currently being viewed (filtered by "New Only" if active)
        self.scan_filtered_list: list[str] = [] 
        
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
        self.thumbnail_size = 180
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width + 20
        
        # Pagination State
        self.scan_page_size = 100
        self.scan_current_page = 0
        self.scan_total_pages = 1

        self.selected_page_size = 100
        self.selected_current_page = 0
        self.selected_total_pages = 1

        # Threading references
        self.scan_thread = None
        self.scan_worker = None
        
        # ThreadPool for image loading
        self.thread_pool = QThreadPool()
        # accumulators for threading results
        self._loaded_results_buffer: List[Tuple[str, QPixmap]] = []
        self._images_loaded_count = 0
        self._total_images_to_load = 0
        
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

        # --- Lazy Loading State ---
        self.loaded_paths: Set[str] = set()
        self.loading_paths: Set[str] = set()
        self._lazy_load_timer = QTimer()
        self._lazy_load_timer.setSingleShot(True)
        self._lazy_load_timer.setInterval(150) # Wait 150ms after scroll stops
        self._lazy_load_timer.timeout.connect(self._process_visible_items)
        
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
            self.last_browsed_scan_dir = LOCAL_SOURCE_PATH
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

        # Connect Scroll Bar for Lazy Loading
        self.scan_scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll_event)
        
        # Scan Pagination Controls
        (self.scan_pag_widget, self.scan_pag_combo, 
         self.scan_pag_prev, self.scan_pag_next, 
         self.scan_pag_btn) = self._create_pagination_controls("scan")

        content_layout.addWidget(self.scan_scroll_area, 1)
        # Fix: Add alignment flag to center the widget itself
        content_layout.addWidget(self.scan_pag_widget, 0, Qt.AlignmentFlag.AlignCenter)
        
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
        
        # Selected Pagination Controls
        (self.sel_pag_widget, self.sel_pag_combo, 
         self.sel_pag_prev, self.sel_pag_next, 
         self.sel_pag_btn) = self._create_pagination_controls("selected")

        content_layout.addWidget(self.selected_images_area, 1)
        # Fix: Add alignment flag to center the widget itself
        content_layout.addWidget(self.sel_pag_widget, 0, Qt.AlignmentFlag.AlignCenter)
        
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

        self.setFocusPolicy(Qt.StrongFocus)
        
        self.update_button_states(connected=False) 
        self.populate_selected_images_gallery()

    def _create_pagination_controls(self, prefix: str):
        # Use the common method from AbstractClassTwoGalleries to ensure consistent styling
        container, controls = self.common_create_pagination_ui()
        
        # Center alignment: Explicitly set horizontal center alignment
        if container.layout():
            container.layout().setAlignment(Qt.AlignHCenter)
            
        combo = controls['combo']
        btn_prev = controls['btn_prev']
        btn_next = controls['btn_next']
        btn_page = controls['btn_page']

        # FIX: Force the button to display as a dropdown (InstantPopup style).
        # We also set a dummy menu immediately. This forces the UI to render the 
        # dropdown arrow and reserve the correct spacing/size even before data is loaded.
        try:
            btn_page.setPopupMode(QToolButton.InstantPopup)
        except AttributeError:
            pass # Ignore if it is a QPushButton
        
        # Explicitly attaching a menu ensures the arrow style appears
        btn_page.setMenu(QMenu(self))
        
        # Set default values
        combo.setCurrentText("100")
        
        # Connect signals locally
        if prefix == "scan":
            combo.currentTextChanged.connect(self._on_scan_page_size_changed)
            btn_prev.clicked.connect(self._on_scan_prev)
            btn_next.clicked.connect(self._on_scan_next)
            # The page button uses a menu, managed in _update_pagination_ui
        else:
            combo.currentTextChanged.connect(self._on_sel_page_size_changed)
            btn_prev.clicked.connect(self._on_sel_prev)
            btn_next.clicked.connect(self._on_sel_next)
            
        return container, combo, btn_prev, btn_next, btn_page

    # --- PAGINATION HANDLERS ---
    
    def _on_scan_page_size_changed(self, text):
        if text == "All":
            self.scan_page_size = float('inf')
        else:
            self.scan_page_size = int(text)
        self.scan_current_page = 0
        self._load_current_scan_page()

    def _on_scan_prev(self):
        if self.scan_current_page > 0:
            self.scan_current_page -= 1
            self._load_current_scan_page()

    def _on_scan_next(self):
        if self.scan_current_page < self.scan_total_pages - 1:
            self.scan_current_page += 1
            self._load_current_scan_page()
            
    def _on_scan_page_selected(self, index):
        if index >= 0 and index != self.scan_current_page:
            self.scan_current_page = index
            self._load_current_scan_page()

    def _on_sel_page_size_changed(self, text):
        if text == "All":
            self.selected_page_size = float('inf')
        else:
            self.selected_page_size = int(text)
        self.selected_current_page = 0
        self.populate_selected_images_gallery()

    def _on_sel_prev(self):
        if self.selected_current_page > 0:
            self.selected_current_page -= 1
            self.populate_selected_images_gallery()

    def _on_sel_next(self):
        if self.selected_current_page < self.selected_total_pages - 1:
            self.selected_current_page += 1
            self.populate_selected_images_gallery()
            
    def _on_sel_page_selected(self, index):
        if index >= 0 and index != self.selected_current_page:
            self.selected_current_page = index
            self.populate_selected_images_gallery()

    def _update_pagination_ui(self, mode="scan"):
        if mode == "scan":
            total = len(self.scan_filtered_list)
            size = self.scan_page_size
            current = self.scan_current_page
            btn_page = self.scan_pag_btn
            
            if size == float('inf'):
                self.scan_total_pages = 1
            else:
                self.scan_total_pages = math.ceil(total / size) if total > 0 else 1
            
            # Clamp
            if self.scan_current_page >= self.scan_total_pages:
                self.scan_current_page = max(0, self.scan_total_pages - 1)
                current = self.scan_current_page
            
            # Common State Update logic (reusing base class helper logic manually since state is separate)
            btn_page.setText(f"Page {current + 1} / {self.scan_total_pages}")
            
            self.scan_pag_prev.setEnabled(current > 0)
            self.scan_pag_next.setEnabled(current < self.scan_total_pages - 1)
            
            # Rebuild Menu
            menu = QMenu(self)
            for i in range(self.scan_total_pages):
                action = QAction(f"Page {i + 1}", self)
                action.setCheckable(True)
                action.setChecked(i == current)
                action.triggered.connect(lambda checked=False, idx=i: self._on_scan_page_selected(idx))
                menu.addAction(action)
            btn_page.setMenu(menu)
            
        else:
            total = len(self.selected_image_paths)
            size = self.selected_page_size
            current = self.selected_current_page
            btn_page = self.sel_pag_btn
            
            if size == float('inf'):
                self.selected_total_pages = 1
            else:
                self.selected_total_pages = math.ceil(total / size) if total > 0 else 1
            
            # Clamp
            if self.selected_current_page >= self.selected_total_pages:
                self.selected_current_page = max(0, self.selected_total_pages - 1)
                current = self.selected_current_page

            btn_page.setText(f"Page {current + 1} / {self.selected_total_pages}")

            self.sel_pag_prev.setEnabled(current > 0)
            self.sel_pag_next.setEnabled(current < self.selected_total_pages - 1)
            
            # Rebuild Menu
            menu = QMenu(self)
            for i in range(self.selected_total_pages):
                action = QAction(f"Page {i + 1}", self)
                action.setCheckable(True)
                action.setChecked(i == current)
                action.triggered.connect(lambda checked=False, idx=i: self._on_sel_page_selected(idx))
                menu.addAction(action)
            btn_page.setMenu(menu)

    # --- KEYBOARD SHORTCUTS ---

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts for selection."""
        # CTRL + A: Select All (Visible on Page)
        if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_A:
            self._select_all_images()
            event.accept()
            return

        # CTRL + D: Deselect All
        if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_D:
            self._deselect_all_images()
            event.accept()
            return

        super().keyPressEvent(event)

    def _select_all_images(self):
        """Selects all images currently visible in the scan gallery page."""
        visible_paths = list(self.path_to_wrapper_map.keys())
        
        if not visible_paths:
            return

        self.scan_thumbnail_widget.setUpdatesEnabled(False)
        self.selected_image_paths.update(visible_paths)
        
        for path in visible_paths:
            if path in self.path_to_wrapper_map:
                wrapper = self.path_to_wrapper_map[path]
                inner_label = wrapper.findChild(QLabel)
                is_in_db = wrapper.property("in_db")
                if inner_label:
                    self._update_card_style(inner_label, is_selected=True, is_in_db=is_in_db)

        self.scan_thumbnail_widget.setUpdatesEnabled(True)
        self.populate_selected_images_gallery()
        self.update_button_states(connected=(self.db_tab_ref.db is not None))

    def _deselect_all_images(self):
        """Deselects all currently selected images."""
        if not self.selected_image_paths:
            return

        self.scan_thumbnail_widget.setUpdatesEnabled(False)

        # Update visual style in Top Gallery (Reset to unselected)
        for path in self.selected_image_paths:
            if path in self.path_to_wrapper_map:
                wrapper = self.path_to_wrapper_map[path]
                inner_label = wrapper.findChild(QLabel)
                is_in_db = wrapper.property("in_db")
                if inner_label:
                    self._update_card_style(inner_label, is_selected=False, is_in_db=is_in_db)

        self.selected_image_paths.clear()
        
        self.scan_thumbnail_widget.setUpdatesEnabled(True)
        self.populate_selected_images_gallery()
        self.update_button_states(connected=(self.db_tab_ref.db is not None))

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
            
        # Dialog removed, so no close logic needed here
    
    def cancel_loading(self):
        """Slot for cancelling operation."""
        self._stop_running_threads()
        self._loaded_results_buffer.clear()
        print("Loading cancelled by user.")
    # ------------------------------------

    # --- RESIZE & REFLOW LOGIC ---
    
    def resizeEvent(self, event: QResizeEvent):
        """Trigger grid reflow and lazy load check when window is resized."""
        self._resize_timer.start(150) # existing debounce for layout repack
        self._lazy_load_timer.start(200) # trigger visibility check slightly after layout repack
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
                scaled = pixmap.scaled(thumb_size, thumb_size, Qt.KeepAspectRatio, Qt.FastTransformation)
                img_label.setPixmap(scaled)
            else:
                img_label.setPixmap(pixmap)
        else:
            # Modified to show Loading if passed as None, or Error if null/failed
            if pixmap is None:
                img_label.setText("Loading...")
                img_label.setStyleSheet("color: #b9bbbe; border: 1px dashed #4f545c;")
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
            # If text is loading/error, keep existing style, otherwise apply default
            if not img_label.pixmap() and (img_label.text() == "Loading..." or img_label.text() == "Error"):
                pass 
            else:
                img_label.setStyleSheet("border: 1px solid #4f545c; background-color: #36393f;")
            
    def _get_tags_from_db(self) -> List[Dict[str, str]]:
        db = self.db_tab_ref.db
        if not db: 
            return []
        try:
            return db.get_all_tags_with_types()
        except Exception:
            pass 
        return []

    def _setup_tag_checkboxes(self):
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.tag_checkboxes = {}
        tags_data = self._get_tags_from_db()
        
        color_map = {
            'Artist': '#5865f2', 'Series': '#f1c40f', 'Character': '#2ecc71', 
            'General': '#e91e63', 'Meta': '#9b59b6', '': '#c7c7c7', None: '#c7c7c7'
        }
        
        columns = 4
        for i, tag_data in enumerate(tags_data):
            tag_name = tag_data['name']
            tag_type = tag_data['type'] if tag_data.get('type') else ''
            
            checkbox = QCheckBox(tag_name.replace("_", " ").title())
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
        """Rebuilds the bottom panel using the same card style, now with pagination."""
        self.selected_images_widget.setUpdatesEnabled(False)
        self._clear_gallery(self.selected_grid_layout)
        
        # 1. Sort all selected paths
        all_selected = sorted(list(self.selected_image_paths))
        
        # 2. Update Pagination UI info
        self._update_pagination_ui("selected")
        
        # 3. Calculate Slice
        start_idx = self.selected_current_page * self.selected_page_size
        if self.selected_page_size == float('inf'):
            page_slice = all_selected
        else:
            end_idx = start_idx + self.selected_page_size
            page_slice = all_selected[start_idx:end_idx]

        # Use dynamic columns here
        widget_width = self.selected_images_area.viewport().width()
        if widget_width <= 0: widget_width = self.selected_images_area.width()
        columns = max(1, widget_width // self.approx_item_width)

        if not all_selected:
            empty_label = QLabel("Select images from the scan results above.")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #b9bbbe; padding: 50px;")
            self.selected_grid_layout.addWidget(empty_label, 0, 0, 1, columns)
            self.selected_images_widget.setUpdatesEnabled(True)
            return
        
        if not page_slice and self.selected_current_page > 0:
            # Handle case where last item on page was removed, go back one page
            self.selected_current_page -= 1
            self.populate_selected_images_gallery()
            return

        for i, path in enumerate(page_slice):
            pixmap = None
            is_in_db = False
            
            # If the item is also visible in the top gallery, we can reuse the pixmap for speed
            if path in self.path_to_wrapper_map:
                wrapper = self.path_to_wrapper_map[path]
                is_in_db = wrapper.property("in_db")
                inner_label = wrapper.findChild(QLabel)
                if inner_label and inner_label.pixmap():
                    pixmap = inner_label.pixmap()
            
            # Fallback load
            if pixmap is None:
                pixmap = QPixmap(path)
            
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
            self.scan_filtered_list = [] # Reset filtered list
            self.selected_image_paths = set()
            
            loop = QEventLoop()
            QTimer.singleShot(1, loop.quit)
            loop.exec()
            
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
        
        # If performing a refresh (toggling view_new_only), re-apply filters to existing list
        self.apply_scan_filters()

    @Slot()
    def on_scan_thread_finished(self):
        self.scan_thread = None
        self.scan_worker = None

    @Slot(list)
    def process_scan_results(self, image_paths: list[str]):
        if self._loading_cancelled:
            return
        self.scan_image_list = image_paths
        self.apply_scan_filters()

    def apply_scan_filters(self):
        """Filters the raw scan list based on settings (Show New Only) and resets to Page 1."""
        self.scan_filtered_list = list(self.scan_image_list) # Copy
        
        # FILTERING LOGIC
        if self.db_tab_ref.db is not None and self.view_new_only:
            db = self.db_tab_ref.db
            paths_not_in_db = []
            for path in self.scan_image_list:
                if not db.get_image_by_path(path):
                    paths_not_in_db.append(path)
            self.scan_filtered_list = sorted(paths_not_in_db)
        
        # Reset to page 0 whenever filter changes or new scan happens
        self.scan_current_page = 0
        self._load_current_scan_page()

    def _load_current_scan_page(self):
        """Calculates the slice for the current page and initiates layout (images load lazily)."""
        
        # 1. Update Pagination UI
        self._update_pagination_ui("scan")
        
        self._clear_gallery(self.scan_thumbnail_layout)
        self.path_to_wrapper_map.clear()
        
        # Reset Lazy Load State for new page
        self.loaded_paths.clear()
        self.loading_paths.clear()
        self.thread_pool.clear()
        
        if not self.scan_filtered_list:
            return
        
        # 2. Calculate Slice
        start_idx = self.scan_current_page * self.scan_page_size
        if self.scan_page_size == float('inf'):
            paths_to_load = self.scan_filtered_list
        else:
            end_idx = start_idx + self.scan_page_size
            paths_to_load = self.scan_filtered_list[start_idx:end_idx]
            
        # 3. Create Placeholders immediately
        columns = self._columns()
        
        # Batch DB Check
        db = self.db_tab_ref.db
        paths_in_db_set = set()
        if db:
            try:
                if paths_to_load:
                    with db.conn.cursor() as cur:
                        cur.execute("SELECT file_path FROM images WHERE file_path = ANY(%s)", (paths_to_load,))
                        rows = cur.fetchall()
                        paths_in_db_set = {row[0] for row in rows}
            except Exception as e:
                print(f"Batch DB check error: {e}")

        # Populate Grid with Placeholders
        for index, path in enumerate(paths_to_load):
            row = index // columns
            col = index % columns
            
            is_in_db = path in paths_in_db_set
            is_selected = path in self.selected_image_paths
            
            # Create card with pixmap=None (Loading state)
            card = self._create_gallery_card(path, None, is_selected, is_in_db=is_in_db)
            
            card.path_clicked.connect(lambda checked, p=path: self.toggle_selection(p))
            card.path_double_clicked.connect(self._view_single_image_preview) 
            card.path_right_clicked.connect(self.show_image_context_menu)

            self.scan_thumbnail_layout.addWidget(card, row, col, Qt.AlignLeft | Qt.AlignTop)
            self.path_to_wrapper_map[path] = card 

        self.scan_thumbnail_widget.adjustSize()

        # 4. Trigger Initial Lazy Load (Check what is visible immediately)
        # We give the layout a small moment to stabilize coordinates
        QTimer.singleShot(50, self._process_visible_items)
    
    def _on_scroll_event(self, value):
        """Called whenever the user scrolls. Debounces the heavy calculation."""
        self._lazy_load_timer.start()

    def _process_visible_items(self):
        """Determines which widgets are in the viewport and triggers loading for them."""
        if self._loading_cancelled:
            return

        # 1. Get Viewport Geometry relative to the content widget
        # The visible area starts at the scroll bar value and extends for the viewport height
        scroll_y = self.scan_scroll_area.verticalScrollBar().value()
        viewport_height = self.scan_scroll_area.viewport().height()
        
        # Define a "buffer" so images start loading slightly before they enter the screen
        buffer_y = 200 
        min_y = scroll_y - buffer_y
        max_y = scroll_y + viewport_height + buffer_y

        paths_to_fetch = []

        # 2. Iterate through managed widgets
        # (Using items ensures we don't crash if widgets were deleted)
        for path, widget in self.path_to_wrapper_map.items():
            
            # Skip if already loaded or currently loading
            if path in self.loaded_paths or path in self.loading_paths:
                continue
                
            # Get geometry relative to the parent widget (self.scan_thumbnail_widget)
            # widget.y() and widget.height() are lightweight calls
            y = widget.y()
            height = widget.height()
            
            # Check intersection
            # If the bottom of the widget is below min_y AND the top is above max_y
            if (y + height > min_y) and (y < max_y):
                paths_to_fetch.append(path)
                self.loading_paths.add(path)

        # 3. Batch start threads
        if paths_to_fetch:
            self._start_lazy_batch(paths_to_fetch)

    def _start_lazy_batch(self, paths: list[str]):
        """Starts workers for the identified visible paths."""
        for path in paths:
            if self._loading_cancelled: break
            
            # Re-verify logic to prevent race conditions
            if path in self.loaded_paths: 
                continue

            worker = ImageLoaderWorker(path, self.thumbnail_size)
            worker.signals.result.connect(self.on_single_image_loaded)
            self.thread_pool.start(worker)

    def _start_image_loading_pool(self, paths_to_load: list[str]):
        if self._loading_cancelled:
            return
            
        self.thread_pool.clear()
        
        for path in paths_to_load:
            if self._loading_cancelled: break
            worker = ImageLoaderWorker(path, self.thumbnail_size)
            worker.signals.result.connect(self.on_single_image_loaded)
            self.thread_pool.start(worker)

    @Slot(str, QPixmap)
    def on_single_image_loaded(self, path: str, pixmap: QPixmap):
        if self._loading_cancelled: return
        
        # Mark as fully loaded
        self.loaded_paths.add(path)
        if path in self.loading_paths:
            self.loading_paths.remove(path)
            
        self._loaded_results_buffer.append((path, pixmap))
        
        # --- Update the specific card ---
        if path in self.path_to_wrapper_map:
            wrapper = self.path_to_wrapper_map[path]
            inner_label = wrapper.findChild(QLabel)
            if inner_label:
                # Update Image
                if pixmap and not pixmap.isNull():
                    thumb_size = self.thumbnail_size
                    if pixmap.width() > thumb_size or pixmap.height() > thumb_size:
                        scaled = pixmap.scaled(thumb_size, thumb_size, Qt.KeepAspectRatio, Qt.FastTransformation)
                        inner_label.setPixmap(scaled)
                    else:
                        inner_label.setPixmap(pixmap)
                else:
                    inner_label.setText("Error")
                    inner_label.setStyleSheet("color: #e74c3c; border: 1px solid #e74c3c;")
                
                # Update border style
                is_selected = path in self.selected_image_paths
                is_in_db = wrapper.property("in_db")
                self._update_card_style(inner_label, is_selected, is_in_db)

    def _finalize_batch_loading(self):
        """Called when all threads in the pool have reported back."""
        if self._loading_cancelled: return
        
        # Final UI adjustments or button state updates
        self.populate_selected_images_gallery()
        self.update_button_states(connected=(self.db_tab_ref.db is not None))

    def handle_scan_error(self, message: str):
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
            self.apply_scan_filters()

    def update_button_states(self, connected: bool):
        selection_count = len(self.selected_image_paths)
        
        # Logic: Refresh and Show New Only should be disabled if we haven't scanned a directory yet.
        has_directory = hasattr(self, 'scanned_dir') and bool(self.scanned_dir)
        
        self.refresh_image_button.setEnabled(has_directory)
        self.view_new_only_button.setEnabled(connected and has_directory)
        
        if connected and not self._db_was_connected:
            self._setup_tag_checkboxes()
        self._db_was_connected = connected 

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
                if path in self.scan_filtered_list: self.scan_filtered_list.remove(path)
                if path in self.selected_image_paths: self.selected_image_paths.remove(path)
                
                # Update UI immediately if on current page
                if path in self.path_to_wrapper_map:
                     widget = self.path_to_wrapper_map.pop(path)
                     widget.deleteLater()
                     self._repack_galleries()
                
                # Refresh current pages to fill gaps
                self._load_current_scan_page()
                self.populate_selected_images_gallery()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _view_single_image_preview(self, image_path: str):
        if not os.path.exists(image_path): return
        # Pass the full filtered list so user can navigate next/prev in preview window even if paginated here
        preview = ImagePreviewWindow(
            image_path=image_path, db_tab_ref=self.db_tab_ref, parent=self, 
            all_paths=self.scan_filtered_list, 
            start_index=self.scan_filtered_list.index(image_path) if image_path in self.scan_filtered_list else 0
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
            
            success_count = 0
            
            for path in list(self.selected_image_paths): 
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
                
                if path in self.path_to_wrapper_map:
                    widget = self.path_to_wrapper_map[path]
                    if self.view_new_only:
                        self.scan_thumbnail_layout.removeWidget(widget)
                        widget.deleteLater()
                        del self.path_to_wrapper_map[path]
                        # Remove from underlying lists
                        if path in self.scan_image_list: self.scan_image_list.remove(path)
                        if path in self.scan_filtered_list: self.scan_filtered_list.remove(path)
                    else:
                        widget.setProperty("in_db", True)
                        inner_label = widget.findChild(QLabel)
                        self._update_card_style(inner_label, is_selected=True, is_in_db=True)
            
            if self.view_new_only:
                # Refresh page to fill gaps
                self._load_current_scan_page()

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

    def get_default_config() -> Dict[str, Any]:
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