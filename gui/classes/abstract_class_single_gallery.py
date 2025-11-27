import os
import math
from pathlib import Path
from abc import abstractmethod
from typing import List, Tuple, Optional, Dict, Set
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QApplication, QLabel, QScrollArea,
    QHBoxLayout, QPushButton, QComboBox
)
from PySide6.QtCore import Qt, Slot, QThreadPool, QTimer, QPoint, QRect
from PySide6.QtGui import QPixmap, QResizeEvent
from .meta_abstract_class import MetaAbstractClass
from ..helpers import ImageLoaderWorker


class AbstractClassSingleGallery(QWidget, metaclass=MetaAbstractClass):
    """
    Abstract base class for a single gallery with Lazy Loading and Pagination.
    Images are loaded when visible and remain loaded (no unloading).
    """

    def __init__(self):
        super().__init__()
        
        # --- Data State ---
        self.gallery_image_paths: List[str] = [] 
        self.path_to_card_widget: Dict[str, QWidget] = {}
        
        # --- Lazy Loading State ---
        self.pending_paths: Set[str] = set()   # Paths waiting to be checked/loaded
        self.loading_paths: Set[str] = set()   # Paths currently in a thread
        self.loaded_paths: Set[str] = set()    # Paths currently held in memory (visible or previously visible)
        
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
        
        # New flag to track if we are adding to existing or replacing
        self._is_appending = False 

        # --- Resize/Scroll Debouncing ---
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._on_layout_change)

        # --- UI References ---
        self.gallery_scroll_area: Optional[QScrollArea] = None
        self.gallery_layout: Optional[QGridLayout] = None
        self.pagination_layout: Optional[QHBoxLayout] = None # Subclasses should assign this if they want controls

        # Starting directory
        try:
            self.last_browsed_scan_dir = str(Path(os.getcwd()) / 'data')
        except Exception:
            self.last_browsed_scan_dir = Path(os.getcwd())

    # --- ABSTRACT METHODS ---

    @abstractmethod
    def create_card_widget(self, path: str, pixmap: Optional[QPixmap]) -> QWidget:
        """
        Create the widget. 
        IMPORTANT: Subclasses must handle `pixmap` being None by showing a placeholder/loading spinner.
        """
        pass
    
    @abstractmethod
    def update_card_pixmap(self, widget: QWidget, pixmap: Optional[QPixmap]):
        """
        Update an existing card widget.
        If pixmap is None, revert to placeholder/unloaded state.
        """
        pass

    # --- PAGINATION UI HELPERS ---

    def create_pagination_controls(self) -> QWidget:
        """Creates a widget containing pagination controls."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Page Size Combo
        lbl = QLabel(f"Images per page:")
        combo = QComboBox()
        combo.addItems(["20", "50", "100", "All"])
        combo.setCurrentText("100")
        combo.currentTextChanged.connect(self._on_page_size_changed)
        
        # Navigation Buttons
        btn_prev = QPushButton("< Prev")
        btn_prev.clicked.connect(lambda: self._change_page(-1))
        
        lbl_page = QLabel("Page 1 / 1")
        lbl_page.setAlignment(Qt.AlignCenter)
        lbl_page.setFixedWidth(100)
        
        btn_next = QPushButton("Next >")
        btn_next.clicked.connect(lambda: self._change_page(1))

        # Store references
        self.page_combo = combo
        self.prev_btn = btn_prev
        self.next_btn = btn_next
        self.page_label = lbl_page

        layout.addWidget(lbl)
        layout.addWidget(combo)
        layout.addStretch()
        layout.addWidget(btn_prev)
        layout.addWidget(lbl_page)
        layout.addWidget(btn_next)
        
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

    def _update_pagination_ui(self):
        if not hasattr(self, 'page_label'): return # Pagination controls not created

        total = len(self.gallery_image_paths)
        if total == 0:
            self.page_label.setText("Page 0 / 0")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return

        total_pages = math.ceil(total / self.page_size)
        if self.current_page >= total_pages:
            self.current_page = max(0, total_pages - 1)

        self.page_label.setText(f"Page {self.current_page + 1} / {total_pages}")
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(self.current_page < total_pages - 1)

    def _get_paginated_slice(self) -> List[str]:
        start = self.current_page * self.page_size
        end = start + self.page_size
        return self.gallery_image_paths[start:end]

    # --- GEOMETRY & EVENTS ---

    def resizeEvent(self, event: QResizeEvent):
        QWidget.resizeEvent(self, event)
        self._resize_timer.start(100) # Debounce

    def showEvent(self, event):
        super().showEvent(event)
        self._on_layout_change()

    def _setup_scroll_connections(self):
        """Must be called after gallery_scroll_area is instantiated in subclass."""
        if self.gallery_scroll_area:
            # Check visibility whenever the user scrolls
            vbar = self.gallery_scroll_area.verticalScrollBar()
            vbar.valueChanged.connect(lambda val: self._process_visible_items())

    @Slot()
    def _on_layout_change(self):
        """Called on resize or show."""
        if self.gallery_scroll_area and self.gallery_layout:
            new_cols = self.calculate_columns()
            if new_cols != self._current_cols:
                self._current_cols = new_cols
                self._reflow_layout(new_cols)
            
            # After reflow/resize, items might have moved into/out of view
            self._process_visible_items()

    def calculate_columns(self) -> int:
        if not self.gallery_scroll_area: return 1
        width = self.gallery_scroll_area.viewport().width()
        if width <= 0: width = self.gallery_scroll_area.width()
        if width <= 0: return 4 
        return max(1, width // self.approx_item_width)

    def _reflow_layout(self, columns: int):
        if not self.gallery_layout: return
        
        items = []
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            if item.widget():
                items.append(item.widget())
        
        for i, widget in enumerate(items):
            row = i // columns
            col = i % columns
            if isinstance(widget, QLabel) and getattr(widget, "is_placeholder", False):
                 self.gallery_layout.addWidget(widget, 0, 0, 1, columns, Qt.AlignCenter)
                 return
            self.gallery_layout.addWidget(widget, row, col, Qt.AlignLeft | Qt.AlignTop)

    # --- LAZY LOADING LOGIC ---

    def start_loading_gallery(self, paths: List[str], show_progress: bool = True, append: bool = False):
        """
        Initialize loading.
        """
        self._is_appending = append
        
        if not append:
            self.gallery_image_paths = paths
            self.current_page = 0
        else:
            self.gallery_image_paths.extend(paths)
            # Stay on current page unless it was empty/invalid before
        
        self.refresh_gallery_view()

    def refresh_gallery_view(self):
        """Refreshes the view based on current page slice."""
        self.cancel_loading() # Clear queues
        self.clear_gallery_widgets() # Clear widgets from layout
        self._update_pagination_ui()

        if not self.gallery_image_paths:
            self.show_placeholder("No images to display.")
            return

        # Get slice for current page
        paginated_paths = self._get_paginated_slice()
        cols = self.calculate_columns()

        # Add placeholders for this page's items
        for i, path in enumerate(paginated_paths):
            card = self.create_card_widget(path, None)
            self.path_to_card_widget[path] = card
            self.pending_paths.add(path)

            row = i // cols
            col = i % cols
            
            if self.gallery_layout:
                self.gallery_layout.addWidget(card, row, col, Qt.AlignLeft | Qt.AlignTop)

        # Setup scroll listener and check visibility
        self._setup_scroll_connections()
        QTimer.singleShot(50, self._process_visible_items)

    def _process_visible_items(self):
        """
        Determines which widgets are visible to LOAD.
        Once loaded, they are NOT unloaded until the page is changed.
        """
        if not self.gallery_scroll_area:
            return

        viewport = self.gallery_scroll_area.viewport()
        # Add a buffer margin so images don't vanish instantly on the edge
        visible_rect = viewport.rect().adjusted(0, -200, 0, 200)

        # 1. Check Pending (Load if visible)
        for path in list(self.pending_paths):
            widget = self.path_to_card_widget.get(path)
            if not widget: continue

            if self._is_visible(widget, viewport, visible_rect):
                self._trigger_image_load(path)

        # UNLOADING LOGIC REMOVED: Images stay loaded.

    def _is_visible(self, widget, viewport, visible_rect):
        """Check if widget intersects with the visible viewport rect."""
        if not widget.isVisible(): 
            return False
        
        # Map widget position to viewport coordinates
        p = widget.mapTo(viewport, QPoint(0,0))
        widget_rect = QRect(p, widget.size())
        
        return visible_rect.intersects(widget_rect)

    def _trigger_image_load(self, path: str):
        if path in self.loading_paths or path in self.loaded_paths:
            return

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
        """
        Clear queues. 
        """
        self.pending_paths.clear()
        # We don't clear loading_paths or loaded_paths here usually unless we are clearing the gallery.

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

    def _remove_placeholder(self):
        if not self.gallery_layout: return
        if self.gallery_layout.count() > 0:
            item = self.gallery_layout.itemAt(0)
            widget = item.widget()
            if isinstance(widget, QLabel) and getattr(widget, "is_placeholder", False):
                widget.deleteLater()

    def show_placeholder(self, text: str):
        self.clear_gallery_widgets()
        if not self.gallery_layout: return
        
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #b9bbbe; padding: 20px; font-style: italic;")
        lbl.is_placeholder = True 
        
        cols = self.calculate_columns()
        self.gallery_layout.addWidget(lbl, 0, 0, 1, cols, Qt.AlignCenter)