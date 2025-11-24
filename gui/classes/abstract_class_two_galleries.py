import os

from pathlib import Path
from abc import abstractmethod
from typing import List, Tuple, Dict, Optional
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QProgressDialog, QApplication, QLabel, QScrollArea
)
from PySide6.QtCore import Qt, Slot, QThreadPool
from PySide6.QtGui import QPixmap
from .meta_abstract_class import MetaAbstractClass
from ..components import MarqueeScrollArea, ClickableLabel
from ..helpers import ImageLoaderWorker


class AbstractClassTwoGalleries(QWidget, metaclass=MetaAbstractClass):
    """
    Abstract base class for tabs that require two image galleries:
    1. A 'Found/Scanned' gallery (top).
    2. A 'Selected' gallery (bottom).
    
    Handles:
    - Threading (Image Loading)
    - Selection Logic (Marquee & Click)
    - Layout Reflow/Resizing
    - Progress Dialogs
    """

    def __init__(self):
        super().__init__()
        
        # --- Data State ---
        self.found_files: List[str] = []       # All files found in scan
        self.selected_files: List[str] = []    # Files explicitly selected
        
        # Maps file path -> Widget (Card)
        self.path_to_label_map: Dict[str, QWidget] = {} 
        self.selected_card_map: Dict[str, QWidget] = {}

        # --- UI Configuration ---
        self.thumbnail_size = 150
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width + 20
        self._current_found_cols = 1
        self._current_selected_cols = 1

        # --- UI References (Subclasses MUST assign these in their __init__) ---
        self.found_gallery_scroll: Optional[MarqueeScrollArea] = None
        self.found_gallery_layout: Optional[QGridLayout] = None
        self.selected_gallery_scroll: Optional[MarqueeScrollArea] = None
        self.selected_gallery_layout: Optional[QGridLayout] = None
        self.status_label: Optional[QLabel] = None

        # --- Threading & Loading ---
        self.thread_pool = QThreadPool.globalInstance()
        self._loaded_results_buffer: List[Tuple[str, QPixmap]] = []
        self._images_loaded_count = 0
        self._total_images_to_load = 0
        self.loading_dialog: Optional[QProgressDialog] = None
        self._loading_cancelled = False

        # Starting directory
        try:
            self.last_browsed_dir = str(Path(os.getcwd()) / 'data')
        except Exception:
            self.last_browsed_dir = Path(os.getcwd())

    # --- ABSTRACT METHODS ---

    @abstractmethod
    def create_card_widget(self, path: str, pixmap: Optional[QPixmap], is_selected: bool) -> QWidget:
        """Create the widget to display in the galleries."""
        pass

    @abstractmethod
    def on_selection_changed(self):
        """Hook called when selection changes (for button updates, etc)."""
        pass

    # --- GEOMETRY & LAYOUT LOGIC ---

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.found_gallery_scroll:
            new_cols = self._calculate_columns(self.found_gallery_scroll)
            if new_cols != self._current_found_cols:
                self._current_found_cols = new_cols
                self._reflow_layout(self.found_gallery_layout, new_cols)

        if self.selected_gallery_scroll:
            new_cols = self._calculate_columns(self.selected_gallery_scroll)
            if new_cols != self._current_selected_cols:
                self._current_selected_cols = new_cols
                self._reflow_layout(self.selected_gallery_layout, new_cols)

    def showEvent(self, event):
        super().showEvent(event)
        if self.found_gallery_scroll:
            self._current_found_cols = self._calculate_columns(self.found_gallery_scroll)
            self._reflow_layout(self.found_gallery_layout, self._current_found_cols)
        
        if self.selected_gallery_scroll:
            self._current_selected_cols = self._calculate_columns(self.selected_gallery_scroll)
            self._reflow_layout(self.selected_gallery_layout, self._current_selected_cols)

    def _calculate_columns(self, scroll_area: QScrollArea) -> int:
        width = scroll_area.viewport().width()
        if width <= 0: width = scroll_area.width()
        if width <= 0: width = 800
        return max(1, width // self.approx_item_width)

    def _reflow_layout(self, layout: QGridLayout, columns: int):
        if not layout: return
        items = []
        placeholder = None
        
        # Extract items
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                # Check for placeholders (labels that span full width)
                if isinstance(widget, QLabel) and getattr(widget, "is_placeholder", False):
                    placeholder = widget
                else:
                    items.append(widget)
        
        # Re-add items
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
            
        # Update visual state in found gallery
        label = self.path_to_label_map.get(path)
        if label:
            self.update_card_style(label, selected)
            
        self.refresh_selected_panel()
        self.on_selection_changed()

    def handle_marquee_selection(self, paths_from_marquee: set, is_ctrl_pressed: bool):
        ordered_current = self.selected_files.copy()
        paths_to_update = set()
        
        if not is_ctrl_pressed:
            # Replace selection
            new_ordered = [p for p in ordered_current if p in paths_from_marquee]
            newly_added = [p for p in paths_from_marquee if p not in ordered_current]
            paths_to_update = paths_from_marquee.union(set(ordered_current))
            self.selected_files = new_ordered + newly_added
        else:
            # Toggle selection
            for path in paths_from_marquee:
                if path in self.selected_files:
                    self.selected_files.remove(path)
                elif path in self.found_files: # Only allow selecting known files
                    self.selected_files.append(path)
                paths_to_update.add(path)

        for path in paths_to_update:
             if path in self.path_to_label_map:
                widget = self.path_to_label_map[path]
                self.update_card_style(widget, path in self.selected_files)
                
        self.refresh_selected_panel()
        self.on_selection_changed()

    def update_card_style(self, widget: QWidget, is_selected: bool):
        """
        Updates the visual style of a card based on selection.
        Subclasses can override if complex hierarchy exists.
        """
        # Default implementation assumes widget is the styling target or has a standard method
        if hasattr(widget, "set_selected_style"):
            widget.set_selected_style(is_selected)
        else:
            # Fallback/Generic styling
            color = "#5865f2" if is_selected else "#4f545c"
            width = "3px" if is_selected else "1px"
            widget.setStyleSheet(f"border: {width} solid {color};")

    def refresh_selected_panel(self):
        if not self.selected_gallery_layout: return

        # Clear layout
        self._clear_layout(self.selected_gallery_layout)
        self.selected_card_map = {}
        
        paths = self.selected_files
        columns = self._calculate_columns(self.selected_gallery_scroll) 
        
        if not paths:
            self.show_placeholder(self.selected_gallery_layout, "Selected files will appear here.")
            return

        for i, path in enumerate(paths):
            # Try to get pixmap from existing map to avoid reload
            pixmap = None 
            if path in self.path_to_label_map:
                # This depends on specific widget structure, subclasses might need more robust way
                # For now, we rely on the subclass implementation of create_card_widget to handle pixmap reuse if needed
                # or we just pass None and let it handle placeholders.
                pass 
                
            # We get the source widget to extract pixmap if possible
            src_widget = self.path_to_label_map.get(path)
            if src_widget and hasattr(src_widget, "get_pixmap"):
                pixmap = src_widget.get_pixmap()
            elif src_widget and isinstance(src_widget, QLabel) and src_widget.pixmap():
                pixmap = src_widget.pixmap()
            
            # Create new card for bottom panel
            card = self.create_card_widget(path, pixmap, is_selected=True)
            
            # Connect click for toggling (removing)
            if isinstance(card, ClickableLabel):
                card.path_clicked.connect(lambda checked, p=path: self.toggle_selection(p))
            
            row = i // columns
            col = i % columns
            self.selected_card_map[path] = card
            self.selected_gallery_layout.addWidget(card, row, col, Qt.AlignLeft | Qt.AlignTop)

    # --- LOADING & THREADING ---

    def start_loading_thumbnails(self, paths: list[str]):
        """Starts concurrent loading using QThreadPool."""
        self.cancel_loading() # Clear previous
        
        self.found_files = paths
        self.path_to_label_map.clear()
        self._loaded_results_buffer = []
        self._images_loaded_count = 0
        self._total_images_to_load = len(paths)
        self._loading_cancelled = False
        
        if not paths:
            self.clear_galleries()
            return

        # Setup Progress Dialog
        self.loading_dialog = QProgressDialog("Loading images...", "Cancel", 0, self._total_images_to_load, self)
        self.loading_dialog.setWindowModality(Qt.WindowModal)
        self.loading_dialog.setMinimumDuration(0)
        self.loading_dialog.canceled.connect(self.cancel_loading)
        self.loading_dialog.show()
        
        QApplication.processEvents()

        submitted_count = 0
        for path in paths:
            if self._loading_cancelled: break
            
            worker = ImageLoaderWorker(path, self.thumbnail_size)
            worker.signals.result.connect(self._on_single_image_loaded)
            self.thread_pool.start(worker)
            
            submitted_count += 1
            if submitted_count % 10 == 0:
                self.loading_dialog.setLabelText(f"Submitting {submitted_count}/{self._total_images_to_load}")
                QApplication.processEvents()

    @Slot(str, QPixmap)
    def _on_single_image_loaded(self, path: str, pixmap: QPixmap):
        if self._loading_cancelled: return

        self._loaded_results_buffer.append((path, pixmap))
        self._images_loaded_count += 1
        
        if self.loading_dialog:
            self.loading_dialog.setValue(self._images_loaded_count)
            
        if self._images_loaded_count >= self._total_images_to_load:
            # Sort by path to maintain order
            sorted_results = sorted(self._loaded_results_buffer, key=lambda x: x[0])
            self.handle_batch_finished(sorted_results)

    def handle_batch_finished(self, loaded_results: List[Tuple[str, QPixmap]]):
        if self._loading_cancelled: return

        self._clear_layout(self.found_gallery_layout)
        columns = self._calculate_columns(self.found_gallery_scroll)
        
        for idx, (path, pixmap) in enumerate(loaded_results):
            row = idx // columns
            col = idx % columns
            
            is_selected = path in self.selected_files
            card = self.create_card_widget(path, pixmap, is_selected)
            
            # Common connections
            if isinstance(card, ClickableLabel):
                card.path_clicked.connect(self.toggle_selection)

            self.found_gallery_layout.addWidget(card, row, col, Qt.AlignLeft | Qt.AlignTop)
            self.path_to_label_map[path] = card

        if self.loading_dialog:
            self.loading_dialog.close()
            self.loading_dialog = None
            
        if self.status_label:
            self.status_label.setText(f"Loaded {len(loaded_results)} files.")
        
        self.refresh_selected_panel()

    def cancel_loading(self):
        self._loading_cancelled = True
        self.thread_pool.clear()
        if self.loading_dialog:
            self.loading_dialog.close()
            self.loading_dialog = None

    # --- HELPERS ---

    def clear_galleries(self, clear_data=True):
        if clear_data:
            self.found_files.clear()
            self.selected_files.clear()
            self.path_to_label_map.clear()
        
        self._clear_layout(self.found_gallery_layout)
        self.show_placeholder(self.found_gallery_layout, "No images found/loaded.")
        
        self._clear_layout(self.selected_gallery_layout)
        self.show_placeholder(self.selected_gallery_layout, "Selected files will appear here.")
        
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
        lbl.is_placeholder = True # Tag for reflow logic
        
        # Span all columns
        cols = 1
        parent_widget = layout.parentWidget()
        if parent_widget:
            # Try to find scroll area parent to calc columns, or default
            cols = 3 # Safe default
             
        layout.addWidget(lbl, 0, 0, 1, cols, Qt.AlignCenter)
