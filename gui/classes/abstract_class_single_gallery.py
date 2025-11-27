import os
import math

from pathlib import Path
from abc import abstractmethod
from typing import List, Optional, Dict, Set
from PySide6.QtWidgets import QWidget, QGridLayout, QScrollArea, QMenu
from PySide6.QtCore import Qt, Slot, QThreadPool, QTimer
from PySide6.QtGui import QPixmap, QResizeEvent, QAction

from ..helpers import ImageLoaderWorker
from .meta_abstract_class_gallery import MetaAbstractClassGallery


class AbstractClassSingleGallery(QWidget, metaclass=MetaAbstractClassGallery):
    """
    Abstract base class for a single gallery using MetaAbstractClassGallery.
    Uses injected common methods for layout and pagination.
    """

    def __init__(self):
        super().__init__()
        
        # --- Data State ---
        self.gallery_image_paths: List[str] = [] 
        self.path_to_card_widget: Dict[str, QWidget] = {}
        
        # --- Lazy Loading State ---
        self.pending_paths: Set[str] = set()
        self.loading_paths: Set[str] = set()
        self.loaded_paths: Set[str] = set()
        
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
        self._is_appending = False 

        # --- Resize Debouncing ---
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._on_layout_change)

        # --- UI References ---
        self.gallery_scroll_area: Optional[QScrollArea] = None
        self.gallery_layout: Optional[QGridLayout] = None
        
        # Starting directory
        try:
            self.last_browsed_scan_dir = str(Path(os.getcwd()) / 'data')
        except Exception:
            self.last_browsed_scan_dir = Path(os.getcwd())

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

    def _setup_scroll_connections(self):
        if self.gallery_scroll_area:
            vbar = self.gallery_scroll_area.verticalScrollBar()
            vbar.valueChanged.connect(lambda val: self._process_visible_items())

    @Slot()
    def _on_layout_change(self):
        if self.gallery_scroll_area and self.gallery_layout:
            # Shared Calculation
            new_cols = self.common_calculate_columns(self.gallery_scroll_area, self.approx_item_width)
            
            if new_cols != self._current_cols:
                self._current_cols = new_cols
                # Shared Reflow
                self.common_reflow_layout(self.gallery_layout, new_cols)
            
            self._process_visible_items()

    # --- LAZY LOADING LOGIC ---

    def start_loading_gallery(self, paths: List[str], show_progress: bool = True, append: bool = False):
        self._is_appending = append
        if not append:
            self.gallery_image_paths = paths
            self.current_page = 0
        else:
            self.gallery_image_paths.extend(paths)
        
        self.refresh_gallery_view()

    def refresh_gallery_view(self):
        self.cancel_loading()
        self.clear_gallery_widgets() 
        self._update_pagination_ui()

        if not self.gallery_image_paths:
            self.common_show_placeholder(self.gallery_layout, "No images to display.", self.calculate_columns())
            return

        # Shared Slice Logic
        paginated_paths = self.common_get_paginated_slice(
            self.gallery_image_paths, self.current_page, self.page_size
        )
        
        cols = self.calculate_columns() # Helper wrapper

        for i, path in enumerate(paginated_paths):
            card = self.create_card_widget(path, None)
            self.path_to_card_widget[path] = card
            self.pending_paths.add(path)

            row = i // cols
            col = i % cols
            
            if self.gallery_layout:
                self.gallery_layout.addWidget(card, row, col, Qt.AlignLeft | Qt.AlignTop)

        self._setup_scroll_connections()
        QTimer.singleShot(50, self._process_visible_items)

    def calculate_columns(self):
        return self.common_calculate_columns(self.gallery_scroll_area, self.approx_item_width)

    def _process_visible_items(self):
        if not self.gallery_scroll_area: return

        viewport = self.gallery_scroll_area.viewport()
        visible_rect = viewport.rect().adjusted(0, -200, 0, 200)

        for path in list(self.pending_paths):
            widget = self.path_to_card_widget.get(path)
            if not widget: continue

            # Shared Visibility Check
            if self.common_is_visible(widget, viewport, visible_rect):
                self._trigger_image_load(path)

    def _trigger_image_load(self, path: str):
        if path in self.loading_paths or path in self.loaded_paths: return

        if path in self.pending_paths:
            self.pending_paths.remove(path)
        self.loading_paths.add(path)

        worker = ImageLoaderWorker(path, self.thumbnail_size)
        worker.signals.result.connect(self._on_single_image_loaded)
        self.thread_pool.start(worker)

    @Slot(str, QPixmap)
    def _on_single_image_loaded(self, path: str, pixmap: QPixmap):
        if path in self.loading_paths:
            self.loading_paths.remove(path)
        self.loaded_paths.add(path)

        widget = self.path_to_card_widget.get(path)
        if widget:
            self.update_card_pixmap(widget, pixmap)

    # --- HELPERS ---

    def cancel_loading(self):
        self.pending_paths.clear()

    def clear_gallery_widgets(self):
        self.path_to_card_widget.clear()
        self.pending_paths.clear()
        self.loaded_paths.clear()
        self.loading_paths.clear()
        
        if not self.gallery_layout: return
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()