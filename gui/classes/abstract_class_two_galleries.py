import os
import math

from pathlib import Path
from abc import abstractmethod
from typing import List, Tuple, Dict, Optional, Set
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QApplication, QLabel, QScrollArea,
    QHBoxLayout, QPushButton, QComboBox, QGroupBox, QVBoxLayout
)
from PySide6.QtCore import Qt, Slot, QThreadPool, QPoint, QRect, QTimer
from PySide6.QtGui import QPixmap
from .meta_abstract_class import MetaAbstractClass
from ..components import MarqueeScrollArea, ClickableLabel
from ..helpers import ImageLoaderWorker


class AbstractClassTwoGalleries(QWidget, metaclass=MetaAbstractClass):
    """
    Abstract base class for tabs with:
    1. A 'Found/Scanned' gallery (Lazy Loaded & Paginated).
    2. A 'Selected' gallery (Immediate Load & Paginated).
    """

    def __init__(self):
        super().__init__()
        
        # --- Data State ---
        self.found_files: List[str] = []       
        self.selected_files: List[str] = []    
        
        self.path_to_label_map: Dict[str, QWidget] = {} 
        self.selected_card_map: Dict[str, QWidget] = {}

        # --- Lazy Loading State (For Found Gallery) ---
        self.pending_found_paths: Set[str] = set()
        self.loading_found_paths: Set[str] = set()
        self.loaded_found_paths: Set[str] = set()

        # --- Pagination State ---
        self.found_page_size = 116
        self.found_current_page = 0
        self.selected_page_size = 116
        self.selected_current_page = 0

        # --- UI Configuration ---
        self.thumbnail_size = 180
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width + 20
        self._current_found_cols = 1
        self._current_selected_cols = 1

        # --- UI References ---
        self.found_gallery_scroll: Optional[MarqueeScrollArea] = None
        self.found_gallery_layout: Optional[QGridLayout] = None
        self.found_pagination_layout: Optional[QHBoxLayout] = None
        self.selected_gallery_scroll: Optional[MarqueeScrollArea] = None
        self.selected_gallery_layout: Optional[QGridLayout] = None
        self.selected_pagination_layout: Optional[QHBoxLayout] = None
        self.status_label: Optional[QLabel] = None

        # --- Threading ---
        self.thread_pool = QThreadPool.globalInstance()

        try:
            self.last_browsed_dir = str(Path(os.getcwd()) / 'data')
        except Exception:
            self.last_browsed_dir = Path(os.getcwd())

        # Initialize Pagination Widgets (to be added to layout by subclasses)
        self.found_pagination_widget = self.create_pagination_controls(is_found_gallery=True)
        self.selected_pagination_widget = self.create_pagination_controls(is_found_gallery=False)

    # --- ABSTRACT METHODS ---

    @abstractmethod
    def create_card_widget(self, path: str, pixmap: Optional[QPixmap], is_selected: bool) -> QWidget:
        pass

    @abstractmethod
    def update_card_pixmap(self, widget: QWidget, pixmap: Optional[QPixmap]):
        pass

    @abstractmethod
    def on_selection_changed(self):
        pass

    # --- PAGINATION UI HELPERS ---

    def create_pagination_controls(self, is_found_gallery: bool) -> QWidget:
        """Creates a widget containing pagination controls."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Page Size Combo
        lbl = QLabel(f"Images per page:")
        combo = QComboBox()
        combo.addItems(["20", "50", "100", "All"])
        combo.setCurrentText("100")
        combo.currentTextChanged.connect(lambda text: self._on_page_size_changed(text, is_found_gallery))
        
        # Navigation Buttons
        btn_prev = QPushButton("< Prev")
        btn_prev.clicked.connect(lambda: self._change_page(-1, is_found_gallery))
        
        lbl_page = QLabel("Page 1 / 1")
        lbl_page.setAlignment(Qt.AlignCenter)
        lbl_page.setFixedWidth(100)
        
        btn_next = QPushButton("Next >")
        btn_next.clicked.connect(lambda: self._change_page(1, is_found_gallery))

        # Store references for later updates
        if is_found_gallery:
            self.found_page_combo = combo
            self.found_prev_btn = btn_prev
            self.found_next_btn = btn_next
            self.found_page_label = lbl_page
        else:
            self.selected_page_combo = combo
            self.selected_prev_btn = btn_prev
            self.selected_next_btn = btn_next
            self.selected_page_label = lbl_page

        layout.addWidget(lbl)
        layout.addWidget(combo)
        layout.addStretch()
        layout.addWidget(btn_prev)
        layout.addWidget(lbl_page)
        layout.addWidget(btn_next)
        
        return container

    def _on_page_size_changed(self, text: str, is_found: bool):
        size = 999999 if text == "All" else int(text)
        if is_found:
            self.found_page_size = size
            self.found_current_page = 0
            self.refresh_found_gallery() # Refresh current view
        else:
            self.selected_page_size = size
            self.selected_current_page = 0
            self.refresh_selected_panel()

    def _change_page(self, delta: int, is_found: bool):
        if is_found:
            total_items = len(self.found_files)
            max_page = math.ceil(total_items / self.found_page_size) - 1
            new_page = max(0, min(self.found_current_page + delta, max_page))
            if new_page != self.found_current_page:
                self.found_current_page = new_page
                self.refresh_found_gallery()
        else:
            total_items = len(self.selected_files)
            max_page = math.ceil(total_items / self.selected_page_size) - 1
            new_page = max(0, min(self.selected_current_page + delta, max_page))
            if new_page != self.selected_current_page:
                self.selected_current_page = new_page
                self.refresh_selected_panel()

    def _update_pagination_ui(self, is_found: bool):
        # Check if controls exist before updating to avoid AttributeError
        if is_found:
            if not hasattr(self, 'found_page_label'): return
            total = len(self.found_files)
            size = self.found_page_size
            current = self.found_current_page
            label = self.found_page_label
            btn_prev = self.found_prev_btn
            btn_next = self.found_next_btn
        else:
            if not hasattr(self, 'selected_page_label'): return
            total = len(self.selected_files)
            size = self.selected_page_size
            current = self.selected_current_page
            label = self.selected_page_label
            btn_prev = self.selected_prev_btn
            btn_next = self.selected_next_btn

        if total == 0:
            label.setText("Page 0 / 0")
            btn_prev.setEnabled(False)
            btn_next.setEnabled(False)
            return

        total_pages = math.ceil(total / size)
        # Ensure current page is valid
        if current >= total_pages:
            current = max(0, total_pages - 1)
            if is_found: self.found_current_page = current
            else: self.selected_current_page = current

        label.setText(f"Page {current + 1} / {total_pages}")
        btn_prev.setEnabled(current > 0)
        btn_next.setEnabled(current < total_pages - 1)

    def _get_paginated_slice(self, items: List[str], is_found: bool) -> List[str]:
        if is_found:
            start = self.found_current_page * self.found_page_size
            end = start + self.found_page_size
        else:
            start = self.selected_current_page * self.selected_page_size
            end = start + self.selected_page_size
        return items[start:end]

    # --- GEOMETRY & LAYOUT LOGIC ---

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Recalculate columns and check visibility
        if self.found_gallery_scroll:
            new_cols = self._calculate_columns(self.found_gallery_scroll)
            if new_cols != self._current_found_cols:
                self._current_found_cols = new_cols
                self._reflow_layout(self.found_gallery_layout, new_cols)
            # Check visibility after resize
            QTimer.singleShot(100, self._process_visible_found_items)

        if self.selected_gallery_scroll:
            new_cols = self._calculate_columns(self.selected_gallery_scroll)
            if new_cols != self._current_selected_cols:
                self._current_selected_cols = new_cols
                self._reflow_layout(self.selected_gallery_layout, new_cols)

    def showEvent(self, event):
        super().showEvent(event)
        # Trigger visibility check when tab is shown
        QTimer.singleShot(100, self._process_visible_found_items)

    def _setup_lazy_connections(self):
        """Call this after creating found_gallery_scroll in subclass."""
        if self.found_gallery_scroll:
            vbar = self.found_gallery_scroll.verticalScrollBar()
            vbar.valueChanged.connect(lambda val: self._process_visible_found_items())

    def _calculate_columns(self, scroll_area: QScrollArea) -> int:
        width = scroll_area.viewport().width()
        if width <= 0: width = scroll_area.width()
        if width <= 0: width = 800
        return max(1, width // self.approx_item_width)

    def _reflow_layout(self, layout: QGridLayout, columns: int):
        if not layout: return
        items = []
        placeholder = None
        
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                if isinstance(widget, QLabel) and getattr(widget, "is_placeholder", False):
                    placeholder = widget
                else:
                    items.append(widget)
        
        if placeholder:
             layout.addWidget(placeholder, 0, 0, 1, columns, Qt.AlignCenter)
        else:
            for i, widget in enumerate(items):
                row = i // columns
                col = i % columns
                layout.addWidget(widget, row, col, Qt.AlignLeft | Qt.AlignTop)

    # --- SELECTION LOGIC ---

    @Slot(str)
    def toggle_selection(self, path: str):
        try:
            index = self.selected_files.index(path)
            self.selected_files.pop(index)
            selected = False
        except ValueError:
            self.selected_files.append(path)
            selected = True
            
        label = self.path_to_label_map.get(path)
        if label:
            self.update_card_style(label, selected)
            
        self.refresh_selected_panel()
        self.on_selection_changed()

    def handle_marquee_selection(self, paths_from_marquee: set, is_ctrl_pressed: bool):
        # Note: Marquee only returns paths from currently VISIBLE page in scroll area
        ordered_current = self.selected_files.copy()
        paths_to_update = set()
        
        if not is_ctrl_pressed:
            new_ordered = [p for p in ordered_current if p in paths_from_marquee]
            newly_added = [p for p in paths_from_marquee if p not in ordered_current]
            paths_to_update = paths_from_marquee.union(set(ordered_current))
            self.selected_files = new_ordered + newly_added
        else:
            for path in paths_from_marquee:
                if path in self.selected_files:
                    self.selected_files.remove(path)
                elif path in self.found_files:
                    self.selected_files.append(path)
                paths_to_update.add(path)

        for path in paths_to_update:
             if path in self.path_to_label_map:
                widget = self.path_to_label_map[path]
                self.update_card_style(widget, path in self.selected_files)
                
        self.refresh_selected_panel()
        self.on_selection_changed()

    def update_card_style(self, widget: QWidget, is_selected: bool):
        if hasattr(widget, "set_selected_style"):
            widget.set_selected_style(is_selected)
        else:
            color = "#5865f2" if is_selected else "#4f545c"
            width = "3px" if is_selected else "1px"
            widget.setStyleSheet(f"border: {width} solid {color};")

    def refresh_selected_panel(self):
        """Refreshes the bottom panel with pagination."""
        if not self.selected_gallery_layout: return

        self._clear_layout(self.selected_gallery_layout)
        self.selected_card_map = {}
        self._update_pagination_ui(is_found=False)
        
        all_paths = self.selected_files
        if not all_paths:
            self.show_placeholder(self.selected_gallery_layout, "Selected files will appear here.")
            return

        paginated_paths = self._get_paginated_slice(all_paths, is_found=False)
        columns = self._calculate_columns(self.selected_gallery_scroll) 
        
        for i, path in enumerate(paginated_paths):
            # Try to grab the already loaded pixmap from the top gallery
            pixmap = None
            top_widget = self.path_to_label_map.get(path)
            if top_widget and hasattr(top_widget, "get_pixmap"):
                 pixmap = top_widget.get_pixmap()
            
            card = self.create_card_widget(path, pixmap, is_selected=True)
            if pixmap is None:
                # Force load for selected item if not available
                self._trigger_priority_load(path, card)

            if isinstance(card, ClickableLabel):
                card.path_clicked.connect(lambda checked, p=path: self.toggle_selection(p))
            
            row = i // columns
            col = i % columns
            self.selected_card_map[path] = card
            self.selected_gallery_layout.addWidget(card, row, col, Qt.AlignLeft | Qt.AlignTop)

    def _trigger_priority_load(self, path: str, target_widget: QWidget):
        worker = ImageLoaderWorker(path, self.thumbnail_size)
        worker.signals.result.connect(lambda p, px: self.update_card_pixmap(target_widget, px))
        self.thread_pool.start(worker)

    # --- LAZY LOADING (Found Gallery) ---

    def start_loading_thumbnails(self, paths: list[str]):
        """Initialize loading. Resets to Page 0."""
        self.cancel_loading()
        
        self.found_files = paths
        self.found_current_page = 0 # Reset page
        
        self.refresh_found_gallery()

    def refresh_found_gallery(self):
        """Reloads the found gallery layout based on current page."""
        self.cancel_loading() # Clear lazy load queues for previous page
        self.path_to_label_map.clear()
        self.pending_found_paths.clear()
        self.loaded_found_paths.clear()
        self.loading_found_paths.clear()

        self._clear_layout(self.found_gallery_layout)
        self._update_pagination_ui(is_found=True)

        if not self.found_files:
            self.show_placeholder(self.found_gallery_layout, "No images found.")
            if self.status_label: self.status_label.setText("Found 0 files.")
            return

        # Get slice
        paginated_paths = self._get_paginated_slice(self.found_files, is_found=True)
        columns = self._calculate_columns(self.found_gallery_scroll)
        
        for idx, path in enumerate(paginated_paths):
            is_selected = path in self.selected_files
            
            # Create with None pixmap
            card = self.create_card_widget(path, None, is_selected)
            
            if isinstance(card, ClickableLabel):
                card.path_clicked.connect(self.toggle_selection)

            row = idx // columns
            col = idx % columns
            self.found_gallery_layout.addWidget(card, row, col, Qt.AlignLeft | Qt.AlignTop)
            
            self.path_to_label_map[path] = card
            self.pending_found_paths.add(path)

        if self.status_label:
            self.status_label.setText(f"Found {len(self.found_files)} files. Showing page {self.found_current_page + 1}.")

        self._setup_lazy_connections()
        QTimer.singleShot(50, self._process_visible_found_items)

    def _process_visible_found_items(self):
        if not self.found_gallery_scroll: return

        viewport = self.found_gallery_scroll.viewport()
        visible_rect = viewport.rect().adjusted(0, -200, 0, 200)

        # 1. Load Visible
        for path in list(self.pending_found_paths):
            widget = self.path_to_label_map.get(path)
            if not widget: continue

            if self._is_visible(widget, viewport, visible_rect):
                self._trigger_found_load(path)

        # UNLOADING LOGIC REMOVED

    def _is_visible(self, widget, viewport, visible_rect):
        if not widget.isVisible(): return False
        p = widget.mapTo(viewport, QPoint(0,0))
        return visible_rect.intersects(QRect(p, widget.size()))

    def _trigger_found_load(self, path: str):
        if path in self.loading_found_paths or path in self.loaded_found_paths: return
        
        if path in self.pending_found_paths:
            self.pending_found_paths.remove(path)
        self.loading_found_paths.add(path)

        worker = ImageLoaderWorker(path, self.thumbnail_size)
        worker.signals.result.connect(self._on_found_image_loaded)
        self.thread_pool.start(worker)

    @Slot(str, QPixmap)
    def _on_found_image_loaded(self, path: str, pixmap: QPixmap):
        if path in self.loading_found_paths:
            self.loading_found_paths.remove(path)
        self.loaded_found_paths.add(path)

        # Only update if widget still exists (might have changed page)
        widget = self.path_to_label_map.get(path)
        if widget:
            self.update_card_pixmap(widget, pixmap)

    # --- HELPERS ---

    def cancel_loading(self):
        self.pending_found_paths.clear()

    def clear_galleries(self, clear_data=True):
        if clear_data:
            self.found_files.clear()
            self.selected_files.clear()
            self.path_to_label_map.clear()
            self.found_current_page = 0
            self.selected_current_page = 0
        
        self.pending_found_paths.clear()
        self.loading_found_paths.clear()
        self.loaded_found_paths.clear()

        self._clear_layout(self.found_gallery_layout)
        self.show_placeholder(self.found_gallery_layout, "No images found/loaded.")
        self._update_pagination_ui(is_found=True)
        
        self._clear_layout(self.selected_gallery_layout)
        self.show_placeholder(self.selected_gallery_layout, "Selected files will appear here.")
        self._update_pagination_ui(is_found=False)
        
        self.on_selection_changed()

    def _clear_layout(self, layout: QGridLayout):
        if not layout: return
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def show_placeholder(self, layout: QGridLayout, text: str):
        if not layout: return
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #b9bbbe; padding: 20px; font-style: italic;")
        lbl.is_placeholder = True
        
        cols = 1
        layout.addWidget(lbl, 0, 0, 1, 3, Qt.AlignCenter)