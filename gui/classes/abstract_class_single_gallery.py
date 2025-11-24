import os

from pathlib import Path
from abc import abstractmethod
from typing import List, Tuple, Optional, Dict
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QProgressDialog, 
    QApplication, QLabel, QScrollArea
)
from PySide6.QtCore import Qt, Slot, QThreadPool, QTimer, QEventLoop
from PySide6.QtGui import QPixmap, QResizeEvent
from .meta_abstract_class import MetaAbstractClass
from ..helpers import ImageLoaderWorker


class AbstractClassSingleGallery(QWidget, metaclass=MetaAbstractClass):
    """
    Abstract base class for tabs that contain a single, resizeable image gallery 
    loaded asynchronously (e.g., SearchTab, WallpaperTab).
    
    Handles:
    - Asynchronous Image Loading (QThreadPool)
    - Progress Dialog management
    - Responsive Grid Layout (Reflow on resize)
    - Placeholder management
    """

    def __init__(self):
        super().__init__()
        
        # --- Data State ---
        self.gallery_image_paths: List[str] = [] # Main list of paths in the gallery
        self.path_to_card_widget: Dict[str, QWidget] = {}
        
        # --- UI Configuration ---
        self.thumbnail_size = 150
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width + 20
        self._current_cols = 1

        # --- Threading & Loading State ---
        # Using a local ThreadPool to avoid conflicts with global tasks (e.g., during app init)
        self.thread_pool = QThreadPool()
        self._loaded_results_buffer: List[Tuple[str, QPixmap]] = []
        self._images_loaded_count = 0
        self._total_images_to_load = 0
        self.loading_dialog: Optional[QProgressDialog] = None
        self._loading_cancelled = False

        # --- Resize Debouncing ---
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._on_resize_timeout)

        # --- UI References (Subclasses MUST assign these in their __init__) ---
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
        """
        Create the specific widget to display for an image (e.g., ClickableLabel vs DraggableImageLabel).
        Should handle its own signal connections (clicks, context menus).
        """
        pass

    # --- GEOMETRY & LAYOUT LOGIC ---

    def resizeEvent(self, event: QResizeEvent):
        """Override resizeEvent to trigger debounced reflow."""
        QWidget.resizeEvent(self, event)
        self._resize_timer.start(150)

    def showEvent(self, event):
        """Trigger immediate reflow when tab is shown."""
        super().showEvent(event)
        self._on_resize_timeout()

    @Slot()
    def _on_resize_timeout(self):
        """Reflows the gallery grid based on current width."""
        if self.gallery_scroll_area and self.gallery_layout:
            new_cols = self.calculate_columns()
            if new_cols != self._current_cols:
                self._current_cols = new_cols
                self._reflow_layout(new_cols)

    def calculate_columns(self) -> int:
        if not self.gallery_scroll_area: 
            return 1
            
        # Try viewport width first, fallback to widget width
        width = self.gallery_scroll_area.viewport().width()
        if width <= 0: 
            width = self.gallery_scroll_area.width()
        
        # Default fallback if not yet visible
        if width <= 0: 
            return 4 
            
        return max(1, width // self.approx_item_width)

    def _reflow_layout(self, columns: int):
        """Repacks widgets into the new column configuration."""
        if not self.gallery_layout: return
        
        items = []
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            if item.widget():
                items.append(item.widget())
        
        for i, widget in enumerate(items):
            row = i // columns
            col = i % columns
            
            # Handle centered placeholders
            if isinstance(widget, QLabel) and getattr(widget, "is_placeholder", False):
                 self.gallery_layout.addWidget(widget, 0, 0, 1, columns, Qt.AlignCenter)
                 return
                 
            self.gallery_layout.addWidget(widget, row, col, Qt.AlignLeft | Qt.AlignTop)

    # --- LOADING LOGIC ---

    def start_loading_gallery(self, paths: List[str], show_progress: bool = True):
        """
        Starts the async loading process for the provided paths.
        """
        self.cancel_loading() # Stop any previous loads
        
        self.gallery_image_paths = paths
        self.clear_gallery_widgets()
        
        if not paths:
            self.show_placeholder("No images to display.")
            return

        self._loaded_results_buffer = []
        self._images_loaded_count = 0
        self._total_images_to_load = len(paths)
        self._loading_cancelled = False

        # Setup Progress Dialog
        if show_progress:
            self.loading_dialog = QProgressDialog("Loading gallery...", "Cancel", 0, self._total_images_to_load, self)
            self.loading_dialog.setWindowModality(Qt.WindowModal)
            self.loading_dialog.setMinimumDuration(0)
            self.loading_dialog.canceled.connect(self.cancel_loading)
            self.loading_dialog.show()
            
            # Process events to render dialog immediately
            loop = QEventLoop()
            QTimer.singleShot(1, loop.quit)
            loop.exec()

        # Submit Tasks
        submission_count = 0
        for path in paths:
            if self._loading_cancelled: break
            
            worker = ImageLoaderWorker(path, self.thumbnail_size)
            worker.signals.result.connect(self._on_single_image_loaded)
            self.thread_pool.start(worker)
            dialog = self.loading_dialog
            if dialog:
                submission_count += 1
                dialog.setValue(submission_count)
                dialog.setLabelText(f"Submitting {submission_count}/{self._total_images_to_load}...")
                QApplication.processEvents()
                
        if self.loading_dialog:
            self.loading_dialog.setValue(0)
            self.loading_dialog.setLabelText(f"Processing 0/{self._total_images_to_load}...")

    @Slot(str, QPixmap)
    def _on_single_image_loaded(self, path: str, pixmap: QPixmap):
        """Accumulates loaded images and updates progress."""
        if self._loading_cancelled: return

        self._loaded_results_buffer.append((path, pixmap))
        self._images_loaded_count += 1
        
        if self.loading_dialog:
            self.loading_dialog.setValue(self._images_loaded_count)
            self.loading_dialog.setLabelText(f"Processing {self._images_loaded_count}/{self._total_images_to_load}")
            
        if self._images_loaded_count >= self._total_images_to_load:
            # Sort results to match original list order
            path_index_map = {p: i for i, p in enumerate(self.gallery_image_paths)}
            sorted_results = sorted(self._loaded_results_buffer, key=lambda x: path_index_map.get(x[0], float('inf')))
            self.handle_batch_finished(sorted_results)

    def handle_batch_finished(self, loaded_results: List[Tuple[str, QPixmap]]):
        """Populates the gallery with the final sorted images."""
        if self._loading_cancelled: return
        
        self.clear_gallery_widgets()
        cols = self.calculate_columns()
        
        for i, (path, pixmap) in enumerate(loaded_results):
            card = self.create_card_widget(path, pixmap)
            self.path_to_card_widget[path] = card
            
            row = i // cols
            col = i % cols
            self.gallery_layout.addWidget(card, row, col, Qt.AlignLeft | Qt.AlignTop)
            
        if self.loading_dialog:
            self.loading_dialog.close()
            self.loading_dialog = None

    # --- HELPERS ---

    def cancel_loading(self):
        self._loading_cancelled = True
        self.thread_pool.clear()
        if self.loading_dialog:
            self.loading_dialog.close()
            self.loading_dialog = None

    def clear_gallery_widgets(self):
        self.path_to_card_widget.clear()
        if not self.gallery_layout: return
        
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def show_placeholder(self, text: str):
        self.clear_gallery_widgets()
        if not self.gallery_layout: return
        
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #b9bbbe; padding: 20px; font-style: italic;")
        lbl.is_placeholder = True # Mark for reflow logic
        
        cols = self.calculate_columns()
        self.gallery_layout.addWidget(lbl, 0, 0, 1, cols, Qt.AlignCenter)
