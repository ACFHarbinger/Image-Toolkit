import os
import math

from abc import abstractmethod
from typing import List, Optional, Dict
from PySide6.QtWidgets import QWidget, QGridLayout, QScrollArea, QMenu
from PySide6.QtCore import Qt, Slot, QThreadPool, QTimer
from PySide6.QtGui import QPixmap, QResizeEvent, QAction
from backend.src.utils.definitions import LOCAL_SOURCE_PATH
from .meta_abstract_class_gallery import MetaAbstractClassGallery
from ..helpers import ImageLoaderWorker


class AbstractClassSingleGallery(QWidget, metaclass=MetaAbstractClassGallery):
    """
    Abstract base class for a single gallery using MetaAbstractClassGallery.
    Lazy loading removed: Images load immediately upon pagination.
    """

    def __init__(self):
        super().__init__()
        
        # --- Data State ---
        self.gallery_image_paths: List[str] = [] 
        self.path_to_card_widget: Dict[str, QWidget] = {}
        # CORRECT: Initialize the cache. It will be populated by start_loading_gallery.
        self._initial_pixmap_cache: Dict[str, QPixmap] = {}
        
        # --- Pagination State ---
        self.page_size = 100
        self.current_page = 0

        # --- UI Configuration ---
        self.thumbnail_size = 180
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width + 20
        self._current_cols = 1

        # --- Threading ---
        self.thread_pool = QThreadPool.globalInstance()

        # --- Resize Debouncing ---
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._on_layout_change)

        # --- Population Timer (for one-by-one/batched loading) ---
        self._populate_timer = QTimer()
        self._populate_timer.setSingleShot(True)
        self._populate_timer.timeout.connect(self._populate_step)
        self._paginated_paths: List[str] = []
        self._populating_index = 0

        # --- UI References ---
        self.gallery_scroll_area: Optional[QScrollArea] = None
        self.gallery_layout: Optional[QGridLayout] = None
        
        # Starting directory
        try:
            self.last_browsed_scan_dir = str(LOCAL_SOURCE_PATH)
        except Exception:
            self.last_browsed_scan_dir = os.getcwd()

        # Initialize Pagination Widgets using Shared Logic
        self.pagination_widget = self.create_pagination_controls()

    # --- ABSTRACT METHODS ---

    @abstractmethod
    def create_card_widget(self, path: str, pixmap: Optional[QPixmap]) -> QWidget:
        pass
    
    @abstractmethod
    def update_card_pixmap(self, widget: QWidget, pixmap: Optional[QPixmap]):
        pass

    # --- PAGINATION UI HELPERS ---

    def create_pagination_controls(self) -> QWidget:
        """Uses shared logic to create UI, then binds signals."""
        container, controls = self.common_create_pagination_ui()
        
        # Bind Controls
        self.page_combo = controls['combo']
        self.prev_btn = controls['btn_prev']
        self.next_btn = controls['btn_next']
        self.page_button = controls['btn_page']

        # Signal Connections
        self.page_combo.currentTextChanged.connect(self._on_page_size_changed)
        self.prev_btn.clicked.connect(lambda: self._change_page(-1))
        self.next_btn.clicked.connect(lambda: self._change_page(1))
        
        # Initial UI update to ensure correct state (greyed out if empty)
        self._update_pagination_ui()
        
        return container

    def _on_page_size_changed(self, text: str):
        size = 999999 if text == "All" else int(text)
        self.page_size = size
        self.current_page = 0
        self.refresh_gallery_view()

    def _change_page(self, delta: int):
        total_items = len(self.gallery_image_paths)
        if total_items == 0: return
        
        max_page = math.ceil(total_items / self.page_size) - 1
        new_page = max(0, min(self.current_page + delta, max_page))
        
        if new_page != self.current_page:
            self.current_page = new_page
            self.refresh_gallery_view()

    def _jump_to_page(self, page_index: int):
        if page_index != self.current_page:
            self.current_page = page_index
            self.refresh_gallery_view()

    def _update_pagination_ui(self):
        if not hasattr(self, 'page_button'): return

        controls = {
            'btn_page': self.page_button,
            'btn_prev': self.prev_btn,
            'btn_next': self.next_btn
        }

        # Use shared logic to update buttons and validate current page
        corrected_page, total_pages = self.common_update_pagination_state(
            len(self.gallery_image_paths), 
            self.page_size, 
            self.current_page, 
            controls
        )
        self.current_page = corrected_page

        # Update Menu (Specific to this class implementation)
        menu = QMenu(self)
        for i in range(total_pages):
            page_num = i + 1
            action = QAction(f"Page {page_num}", self)
            action.setCheckable(True)
            action.setChecked(i == self.current_page)
            action.triggered.connect(lambda checked=False, p=i: self._jump_to_page(p))
            menu.addAction(action)
        self.page_button.setMenu(menu)

    # --- GEOMETRY & EVENTS ---

    def resizeEvent(self, event: QResizeEvent):
        QWidget.resizeEvent(self, event)
        self._resize_timer.start(100) 

    def showEvent(self, event):
        super().showEvent(event)
        self._on_layout_change()

    @Slot()
    def _on_layout_change(self):
        if self.gallery_scroll_area and self.gallery_layout:
            # Shared Calculation
            new_cols = self.common_calculate_columns(self.gallery_scroll_area, self.approx_item_width)
            
            if new_cols != self._current_cols:
                self._current_cols = new_cols
                # Shared Reflow
                self.common_reflow_layout(self.gallery_layout, new_cols)

    # --- LOADING LOGIC (Immediate & Sequential) ---

    def start_loading_gallery(self, paths: List[str], show_progress: bool = True, append: bool = False, pixmap_cache: Optional[Dict[str, QPixmap]] = None):
        """
        Starts the loading process. Accepts an optional pixmap_cache for pre-generated thumbnails.
        """
        if not append:
            self.gallery_image_paths = paths
            self.current_page = 0
            # Ensure the cache is *replaced*
            self._initial_pixmap_cache = pixmap_cache if pixmap_cache is not None else {}
        else:
            self.gallery_image_paths.extend(paths)
            if pixmap_cache:
                self._initial_pixmap_cache.update(pixmap_cache)

        self.refresh_gallery_view()

    def refresh_gallery_view(self):
        self.cancel_loading()
        self.clear_gallery_widgets() 
        self._update_pagination_ui()

        if not self.gallery_image_paths:
            self.common_show_placeholder(self.gallery_layout, "No images to display.", self.calculate_columns())
            return

        # Prepare for sequential loading of the current page
        self._paginated_paths = self.common_get_paginated_slice(
            self.gallery_image_paths, self.current_page, self.page_size
        )
        self._populating_index = 0
        
        # Start the population loop immediately
        self._populate_step()

    def _populate_step(self):
        """Adds a small batch of widgets to the layout to prevent UI freezing."""
        if not hasattr(self, '_paginated_paths') or self._populating_index >= len(self._paginated_paths):
            return

        cols = self.calculate_columns()

        # Batch size: add 5 images per tick for a smooth "one by one" feel without being too slow
        batch_size = 5
        limit = min(self._populating_index + batch_size, len(self._paginated_paths))

        for i in range(self._populating_index, limit):
            path = self._paginated_paths[i]

            # NEW LOGIC: Check for cached pixmap before creating the card
            initial_pixmap = self._initial_pixmap_cache.get(path, None)

            # 1. Create Placeholder (pass cached pixmap if found)
            card = self.create_card_widget(path, initial_pixmap)
            self.path_to_card_widget[path] = card

            # 2. Add to Layout immediately
            row = i // cols
            col = i % cols
            if self.gallery_layout:
                self.gallery_layout.addWidget(card, row, col, Qt.AlignLeft | Qt.AlignTop)

            # 3. Trigger Load ONLY if pixmap was NOT cached
            # If the thumbnail is already drawn, skip the worker.
            if initial_pixmap is None:
                self._trigger_image_load(path)
            # Delete cache entry after use to save memory
            elif path in self._initial_pixmap_cache:
                del self._initial_pixmap_cache[path]

        self._populating_index = limit

        # Schedule next batch if items remain
        if self._populating_index < len(self._paginated_paths):
            self._populate_timer.start(0) # 0ms delay yields to event loop

    def calculate_columns(self):
        return self.common_calculate_columns(self.gallery_scroll_area, self.approx_item_width)

    def _trigger_image_load(self, path: str):
        worker = ImageLoaderWorker(path, self.thumbnail_size)
        worker.signals.result.connect(self._on_single_image_loaded)
        self.thread_pool.start(worker)

    @Slot(str, QPixmap)
    def _on_single_image_loaded(self, path: str, pixmap: QPixmap):
        widget = self.path_to_card_widget.get(path)
        if widget:
            self.update_card_pixmap(widget, pixmap)

    # --- HELPERS ---

    def cancel_loading(self):
        if self._populate_timer.isActive():
            self._populate_timer.stop()

    def clear_gallery_widgets(self):
        self.cancel_loading()
        self.path_to_card_widget.clear()
        self._paginated_paths = []
        
        if not self.gallery_layout: return
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()