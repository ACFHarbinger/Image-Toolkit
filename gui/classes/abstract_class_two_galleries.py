import os
import math

from abc import abstractmethod
from typing import List, Dict, Optional
from PySide6.QtWidgets import QWidget, QGridLayout, QLabel, QMenu, QApplication
from PySide6.QtCore import Qt, Slot, QThreadPool, QTimer, QEvent
from PySide6.QtGui import QPixmap, QAction
from backend.src.utils.definitions import LOCAL_SOURCE_PATH
from .meta_abstract_class_gallery import MetaAbstractClassGallery
from ..components import MarqueeScrollArea, ClickableLabel
from ..helpers import ImageLoaderWorker


class AbstractClassTwoGalleries(QWidget, metaclass=MetaAbstractClassGallery):
    """
    Abstract base class for tabs with Found/Selected galleries.
    Lazy loading replaced with Sequential Loading: Images appear one by one.
    Includes Select All / Deselect All logic.
    """

    def __init__(self):
        super().__init__()
        
        # --- Data State ---
        self.found_files: List[str] = []       
        self.selected_files: List[str] = []    
        
        self.path_to_label_map: Dict[str, QWidget] = {} 
        self.selected_card_map: Dict[str, QWidget] = {}
        self._selected_pixmap_cache: Dict[str, QPixmap] = {}

        # --- Pagination State ---
        self.found_page_size = 1000
        self.found_current_page = 0
        self.selected_page_size = 1000
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
        self.selected_gallery_scroll: Optional[MarqueeScrollArea] = None
        self.selected_gallery_layout: Optional[QGridLayout] = None
        self.status_label: Optional[QLabel] = None

        # --- Threading ---
        self.thread_pool = QThreadPool.globalInstance()

        # --- Population Timer (Sequential Loading) ---
        self._populate_found_timer = QTimer()
        self._populate_found_timer.setSingleShot(True)
        self._populate_found_timer.timeout.connect(self._populate_found_step)
        self._paginated_found_paths: List[str] = []
        self._populating_found_index = 0

        try:
            self.last_browsed_dir = LOCAL_SOURCE_PATH
        except Exception:
            self.last_browsed_dir = os.getcwd()

        # Initialize Pagination Widgets using Shared Logic
        self.found_pagination_widget = self.create_pagination_controls(is_found_gallery=True)
        self.selected_pagination_widget = self.create_pagination_controls(is_found_gallery=False)

        # Enable keyboard focus for shortcuts
        self.setFocusPolicy(Qt.StrongFocus)

    # --- KEYBOARD SHORTCUTS (Shared) ---
    def keyPressEvent(self, event: QEvent):
        # Check for Ctrl + A (Select All)
        if event.key() == Qt.Key.Key_A and event.modifiers() & Qt.ControlModifier:
            self.select_all_items()
            event.accept()
        # Check for Ctrl + D (Deselect All)
        elif event.key() == Qt.Key.Key_D and event.modifiers() & Qt.ControlModifier:
            self.deselect_all_items()
            event.accept()
        else:
            super().keyPressEvent(event)

    @Slot()
    def select_all_items(self):
        """Selects all items currently in the found_files list."""
        changed = False
        for path in self.found_files:
            if path not in self.selected_files:
                self.selected_files.append(path)
                changed = True
        
        if changed:
            self.refresh_selected_panel()
            self._update_found_card_styles()

    @Slot()
    def deselect_all_items(self):
        """Clears the selection."""
        if self.selected_files:
            self.selected_files.clear()
            self.refresh_selected_panel()
            self._update_found_card_styles()

    def _update_found_card_styles(self):
        """Helper to re-evaluate and apply style to all currently loaded/visible found cards."""
        for path, widget in self.path_to_label_map.items():
            if widget:
                is_selected = path in self.selected_files
                self.update_card_style(widget, is_selected)

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
        """Creates pagination using shared logic, then binds contextual signals."""
        container, controls = self.common_create_pagination_ui()

        # Center the controls horizontally (User request: bottom center)
        if container.layout():
            container.layout().setAlignment(Qt.AlignCenter)
        
        # Bind signals depending on context
        controls['combo'].currentTextChanged.connect(
            lambda text: self._on_page_size_changed(text, is_found_gallery)
        )
        controls['btn_prev'].clicked.connect(
            lambda: self._change_page(-1, is_found_gallery)
        )
        controls['btn_next'].clicked.connect(
            lambda: self._change_page(1, is_found_gallery)
        )

        # Store references
        if is_found_gallery:
            self.found_page_combo = controls['combo']
            self.found_prev_btn = controls['btn_prev']
            self.found_next_btn = controls['btn_next']
            self.found_page_button = controls['btn_page']
        else:
            self.selected_page_combo = controls['combo']
            self.selected_prev_btn = controls['btn_prev']
            self.selected_next_btn = controls['btn_next']
            self.selected_page_button = controls['btn_page']
        
        return container

    def _on_page_size_changed(self, text: str, is_found: bool):
        size = 999999 if text == "All" else int(text)
        if is_found:
            self.found_page_size = size
            self.found_current_page = 0
            self.refresh_found_gallery()
        else:
            self.selected_page_size = size
            self.selected_current_page = 0
            self.refresh_selected_panel()

    def _change_page(self, delta: int, is_found: bool):
        if is_found:
            total = len(self.found_files)
            max_p = math.ceil(total / self.found_page_size) - 1
            new_p = max(0, min(self.found_current_page + delta, max_p))
            if new_p != self.found_current_page:
                self.found_current_page = new_p
                self.refresh_found_gallery()
        else:
            total = len(self.selected_files)
            max_p = math.ceil(total / self.selected_page_size) - 1
            new_p = max(0, min(self.selected_current_page + delta, max_p))
            if new_p != self.selected_current_page:
                self.selected_current_page = new_p
                self.refresh_selected_panel()

    def _jump_to_page(self, page_index: int, is_found: bool):
        if is_found:
            if page_index != self.found_current_page:
                self.found_current_page = page_index
                self.refresh_found_gallery()
        else:
            if page_index != self.selected_current_page:
                self.selected_current_page = page_index
                self.refresh_selected_panel()

    def _update_pagination_ui(self, is_found: bool):
        if is_found:
            if not hasattr(self, 'found_page_button'): return
            controls = {
                'btn_page': self.found_page_button,
                'btn_prev': self.found_prev_btn,
                'btn_next': self.found_next_btn
            }
            total = len(self.found_files)
            size = self.found_page_size
            current = self.found_current_page
        else:
            if not hasattr(self, 'selected_page_button'): return
            controls = {
                'btn_page': self.selected_page_button,
                'btn_prev': self.selected_prev_btn,
                'btn_next': self.selected_next_btn
            }
            total = len(self.selected_files)
            size = self.selected_page_size
            current = self.selected_current_page

        # Shared State Update Logic
        corrected_page, total_pages = self.common_update_pagination_state(
            total, size, current, controls
        )
        
        if is_found: self.found_current_page = corrected_page
        else: self.selected_current_page = corrected_page

        # Update Menu
        menu = QMenu(self)
        for i in range(total_pages):
            action = QAction(f"Page {i + 1}", self)
            action.setCheckable(True)
            action.setChecked(i == corrected_page)
            action.triggered.connect(lambda checked=False, p=i, f=is_found: self._jump_to_page(p, f))
            menu.addAction(action)
        controls['btn_page'].setMenu(menu)

    # --- GEOMETRY & LAYOUT LOGIC ---

    def resizeEvent(self, event):
        super().resizeEvent(event)
        
        # Shared Calculation
        if self.found_gallery_scroll:
            new_cols = self.common_calculate_columns(self.found_gallery_scroll, self.approx_item_width)
            if new_cols != self._current_found_cols:
                self._current_found_cols = new_cols
                self.common_reflow_layout(self.found_gallery_layout, new_cols)

        if self.selected_gallery_scroll:
            new_cols = self.common_calculate_columns(self.selected_gallery_scroll, self.approx_item_width)
            if new_cols != self._current_selected_cols:
                self._current_selected_cols = new_cols
                self.common_reflow_layout(self.selected_gallery_layout, new_cols)

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
        # Check for Shift modifier explicitly
        modifiers = QApplication.keyboardModifiers()
        is_shift_pressed = bool(modifiers & Qt.ShiftModifier)
        
        ordered_current = self.selected_files.copy()
        paths_to_update = set()

        if is_ctrl_pressed:
            # Subtractive selection (CTRL): Remove items in marquee from selection
            for path in paths_from_marquee:
                if path in self.selected_files:
                    self.selected_files.remove(path)
                    paths_to_update.add(path)
        
        elif is_shift_pressed:
            # Additive selection (SHIFT): Keep current selection, add new items from marquee
            newly_added = [p for p in paths_from_marquee if p not in ordered_current]
            self.selected_files = ordered_current + newly_added
            paths_to_update = set(newly_added)
            
        else:
            # Standard selection (No Modifiers): 
            # Replaces selection with what is currently in the marquee.
            paths_to_update = set(self.selected_files).union(paths_from_marquee)
            self.selected_files = list(paths_from_marquee)

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
        if not self.selected_gallery_layout: return

        for path, widget in self.selected_card_map.items():
            if hasattr(widget, "get_pixmap"):
                pixmap = widget.get_pixmap()
                if pixmap and not pixmap.isNull():
                    self._selected_pixmap_cache[path] = pixmap

        self._clear_layout(self.selected_gallery_layout)
        self.selected_card_map = {}
        self._update_pagination_ui(is_found=False)
        
        if not self.selected_files:
            self.common_show_placeholder(self.selected_gallery_layout, "Selected files will appear here.", 1)
            return

        # Shared Slice
        paginated_paths = self.common_get_paginated_slice(
            self.selected_files, self.selected_current_page, self.selected_page_size
        )
        columns = self.common_calculate_columns(self.selected_gallery_scroll, self.approx_item_width)
        
        for i, path in enumerate(paginated_paths):
            pixmap = self._selected_pixmap_cache.get(path)
            if pixmap is None:
                top_widget = self.path_to_label_map.get(path)
                if top_widget and hasattr(top_widget, "get_pixmap"):
                    pixmap = top_widget.get_pixmap()
            
            card = self.create_card_widget(path, pixmap, is_selected=True)
            
            if pixmap is None:
                self._trigger_priority_load(path, card)

            if isinstance(card, ClickableLabel):
                card.path_clicked.connect(lambda checked, p=path: self.toggle_selection(p))
            
            row = i // columns
            col = i % columns
            self.selected_card_map[path] = card
            self.selected_gallery_layout.addWidget(card, row, col, Qt.AlignLeft | Qt.AlignTop)

    def _trigger_priority_load(self, path: str, target_widget: QWidget):
        worker = ImageLoaderWorker(path, self.thumbnail_size)
        worker.signals.result.connect(lambda p, px: self._on_selected_image_loaded(p, px, target_widget))
        self.thread_pool.start(worker)

    def _on_selected_image_loaded(self, path: str, pixmap: QPixmap, widget: QWidget):
        if pixmap and not pixmap.isNull():
            self._selected_pixmap_cache[path] = pixmap
        self.update_card_pixmap(widget, pixmap)

    # --- SEQUENTIAL LOADING (Found Gallery) ---

    def start_loading_thumbnails(self, paths: list[str]):
        self.cancel_loading()
        self.found_files = paths
        self.found_current_page = 0 
        self.refresh_found_gallery()

    def refresh_found_gallery(self):
        self.cancel_loading()
        self.path_to_label_map.clear()
        
        self._clear_layout(self.found_gallery_layout)
        self._update_pagination_ui(is_found=True)

        if not self.found_files:
            self.common_show_placeholder(self.found_gallery_layout, "No images found.", 1)
            if self.status_label: self.status_label.setText("Found 0 files.")
            return

        # Setup batch population
        self._paginated_found_paths = self.common_get_paginated_slice(
            self.found_files, self.found_current_page, self.found_page_size
        )
        self._populating_found_index = 0
        
        if self.status_label:
            self.status_label.setText(f"Found {len(self.found_files)} files. Showing page {self.found_current_page + 1}.")

        # Start population loop
        self._populate_found_step()

    def _populate_found_step(self):
        if not hasattr(self, '_paginated_found_paths') or self._populating_found_index >= len(self._paginated_found_paths):
            return

        cols = self.common_calculate_columns(self.found_gallery_scroll, self.approx_item_width)
        batch_size = 5
        limit = min(self._populating_found_index + batch_size, len(self._paginated_found_paths))

        for i in range(self._populating_found_index, limit):
            path = self._paginated_found_paths[i]
            is_selected = path in self.selected_files
            
            # Create widget (placeholder initially)
            card = self.create_card_widget(path, None, is_selected)
            
            if isinstance(card, ClickableLabel):
                card.path_clicked.connect(self.toggle_selection)

            row = i // cols
            col = i % cols
            if self.found_gallery_layout:
                self.found_gallery_layout.addWidget(card, row, col, Qt.AlignLeft | Qt.AlignTop)
            
            self.path_to_label_map[path] = card
            
            # Trigger load
            self._trigger_found_load(path)

        self._populating_found_index = limit

        # Schedule next batch
        if self._populating_found_index < len(self._paginated_found_paths):
            self._populate_found_timer.start(0)

    def _trigger_found_load(self, path: str):
        worker = ImageLoaderWorker(path, self.thumbnail_size)
        worker.signals.result.connect(self._on_found_image_loaded)
        self.thread_pool.start(worker)

    @Slot(str, QPixmap)
    def _on_found_image_loaded(self, path: str, pixmap: QPixmap):
        widget = self.path_to_label_map.get(path)
        if widget:
            self.update_card_pixmap(widget, pixmap)

    # --- HELPERS ---

    def cancel_loading(self):
        if self._populate_found_timer.isActive():
            self._populate_found_timer.stop()

    def clear_galleries(self, clear_data=True):
        if clear_data:
            self.found_files.clear()
            self.selected_files.clear()
            self.path_to_label_map.clear()
            self.found_current_page = 0
            self.selected_current_page = 0
            self._selected_pixmap_cache.clear()

        self.cancel_loading()
        self._clear_layout(self.found_gallery_layout)
        self.common_show_placeholder(self.found_gallery_layout, "No images found/loaded.", 1)
        self._update_pagination_ui(is_found=True)
        
        self._clear_layout(self.selected_gallery_layout)
        self.common_show_placeholder(self.selected_gallery_layout, "Selected files will appear here.", 1)
        self._update_pagination_ui(is_found=False)
        
        self.on_selection_changed()

    def _clear_layout(self, layout: QGridLayout):
        if not layout: return
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()