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
    # ... (init remains the same) ...
    def __init__(self):
        super().__init__()
        
        # --- Data State ---
        self.gallery_image_paths: List[str] = [] 
        self.path_to_card_widget: Dict[str, QWidget] = {}
        
        # --- UI Configuration ---
        self.thumbnail_size = 150
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width + 20
        self._current_cols = 1

        # --- Threading & Loading State ---
        self.thread_pool = QThreadPool()
        self._loaded_results_buffer: List[Tuple[str, QPixmap]] = []
        self._images_loaded_count = 0
        self._total_images_to_load = 0
        self.loading_dialog: Optional[QProgressDialog] = None
        self._loading_cancelled = False
        
        # New flag to track if we are adding to existing or replacing
        self._is_appending = False 

        # --- Resize Debouncing ---
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._on_resize_timeout)

        # --- UI References ---
        self.gallery_scroll_area: Optional[QScrollArea] = None
        self.gallery_layout: Optional[QGridLayout] = None

        # Starting directory
        try:
            self.last_browsed_scan_dir = str(Path(os.getcwd()) / 'data')
        except Exception:
            self.last_browsed_scan_dir = Path(os.getcwd())

    # ... (abstract methods and geometry logic remain the same) ...

    @abstractmethod
    def create_card_widget(self, path: str, pixmap: Optional[QPixmap]) -> QWidget:
        pass

    def resizeEvent(self, event: QResizeEvent):
        QWidget.resizeEvent(self, event)
        self._resize_timer.start(150)

    def showEvent(self, event):
        super().showEvent(event)
        self._on_resize_timeout()

    @Slot()
    def _on_resize_timeout(self):
        if self.gallery_scroll_area and self.gallery_layout:
            new_cols = self.calculate_columns()
            if new_cols != self._current_cols:
                self._current_cols = new_cols
                self._reflow_layout(new_cols)

    def calculate_columns(self) -> int:
        if not self.gallery_scroll_area: 
            return 1
        width = self.gallery_scroll_area.viewport().width()
        if width <= 0: 
            width = self.gallery_scroll_area.width()
        if width <= 0: 
            return 4 
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

    # --- UPDATED LOADING LOGIC ---

    def start_loading_gallery(self, paths: List[str], show_progress: bool = True, append: bool = False):
        """
        Starts the async loading process.
        :param paths: List of image paths to load.
        :param show_progress: Whether to show the QProgressDialog.
        :param append: If True, adds to existing gallery. If False, clears it first.
        """
        self.cancel_loading()
        
        self._is_appending = append

        if not append:
            self.gallery_image_paths = paths
            self.clear_gallery_widgets()
        else:
            # Check if we have a placeholder to remove before appending
            self._remove_placeholder()
            self.gallery_image_paths.extend(paths)
        
        if not paths:
            if not append:
                self.show_placeholder("No images to display.")
            return

        self._loaded_results_buffer = []
        self._images_loaded_count = 0
        self._total_images_to_load = len(paths)
        self._loading_cancelled = False

        # Setup Progress Dialog
        if show_progress:
            title = "Adding images..." if append else "Loading gallery..."
            self.loading_dialog = QProgressDialog(title, "Cancel", 0, self._total_images_to_load, self)
            self.loading_dialog.setWindowModality(Qt.WindowModal)
            self.loading_dialog.setMinimumDuration(0)
            self.loading_dialog.canceled.connect(self.cancel_loading)
            self.loading_dialog.show()
            
            loop = QEventLoop()
            QTimer.singleShot(1, loop.quit)
            loop.exec()

        submission_count = 0
        for path in paths:
            if self._loading_cancelled: break
            
            worker = ImageLoaderWorker(path, self.thumbnail_size)
            worker.signals.result.connect(self._on_single_image_loaded)
            self.thread_pool.start(worker)
            
            if self.loading_dialog:
                submission_count += 1
                self.loading_dialog.setValue(submission_count)
                self.loading_dialog.setLabelText(f"Submitting {submission_count}/{self._total_images_to_load}...")
                QApplication.processEvents()

    @Slot(str, QPixmap)
    def _on_single_image_loaded(self, path: str, pixmap: QPixmap):
        if self._loading_cancelled: return

        self._loaded_results_buffer.append((path, pixmap))
        self._images_loaded_count += 1
        
        if self.loading_dialog:
            self.loading_dialog.setValue(self._images_loaded_count)
            self.loading_dialog.setLabelText(f"Processing {self._images_loaded_count}/{self._total_images_to_load}")
            
        if self._images_loaded_count >= self._total_images_to_load:
            # We only sort the *current batch* to match the order they were passed in
            # We do not re-sort the entire gallery here
            input_subset = self.gallery_image_paths[-self._total_images_to_load:] if self._is_appending else self.gallery_image_paths
            
            path_index_map = {p: i for i, p in enumerate(input_subset)}
            sorted_results = sorted(self._loaded_results_buffer, key=lambda x: path_index_map.get(x[0], float('inf')))
            self.handle_batch_finished(sorted_results)

    def handle_batch_finished(self, loaded_results: List[Tuple[str, QPixmap]]):
        """Populates the gallery with the loaded images."""
        if self._loading_cancelled: return
        
        if not self._is_appending:
            self.clear_gallery_widgets()
            start_index = 0
        else:
            # Calculate where to start adding in the grid
            start_index = len(self.path_to_card_widget)

        cols = self.calculate_columns()
        
        for i, (path, pixmap) in enumerate(loaded_results):
            card = self.create_card_widget(path, pixmap)
            self.path_to_card_widget[path] = card
            
            # Calculate absolute index for the grid
            absolute_index = start_index + i
            row = absolute_index // cols
            col = absolute_index % cols
            
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

    def _remove_placeholder(self):
        """Helper to remove only the placeholder widget if it exists."""
        if not self.gallery_layout: return
        
        # Check usually the first item
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
