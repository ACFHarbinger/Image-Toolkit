import os
import math
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

from abc import abstractmethod
from typing import List, Optional, Dict
from PySide6.QtCore import Qt, Slot, QThreadPool, QTimer
from PySide6.QtGui import QPixmap, QResizeEvent, QAction, QImage, QPainter, QColor
from PySide6.QtWidgets import (
    QWidget,
    QGridLayout,
    QScrollArea,
    QMenu,
    QLabel,
    QVBoxLayout,
)
from backend.src.utils.definitions import LOCAL_SOURCE_PATH, SUPPORTED_VIDEO_FORMATS
from .meta_abstract_class_gallery import MetaAbstractClassGallery
from ..helpers import (
    ImageLoaderWorker,
    BatchImageLoaderWorker,
    VideoLoaderWorker,
)
from ..helpers.video.video_scan_worker import VideoThumbnailer


class AbstractClassSingleGallery(QWidget, metaclass=MetaAbstractClassGallery):
    """
    Abstract base class for a single gallery using MetaAbstractClassGallery.
    Includes built-in support for video thumbnail generation.
    """

    def __init__(self):
        super().__init__()

        # --- Data State ---
        self.gallery_image_paths: List[str] = []
        self.path_to_card_widget: Dict[str, QWidget] = {}
        # Stores pre-generated or cached thumbnails
        self._initial_pixmap_cache: Dict[str, QPixmap] = {}

        # --- Pagination State ---
        self.page_size = 100
        self.current_page = 0

        # --- UI Configuration ---
        self.thumbnail_size = 180
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width + 20
        self._current_cols = 1

        self.thread_pool = QThreadPool.globalInstance()
        self._active_workers = set()

        # --- Resize Debouncing ---
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._on_layout_change)

        # --- Population Timer ---
        self._populate_timer = QTimer()
        self._populate_timer.setSingleShot(True)
        self._populate_timer.timeout.connect(self._populate_step)
        self._paginated_paths: List[str] = []
        self._populating_index = 0

        # --- UI References ---
        self.gallery_scroll_area: Optional[QScrollArea] = None
        self.gallery_layout: Optional[QGridLayout] = None

        # --- Lazy Loading State ---
        self._loading_paths = set()
        self._failed_paths = set()

        # Starting directory
        try:
            self.last_browsed_scan_dir = str(LOCAL_SOURCE_PATH)
        except Exception:
            self.last_browsed_scan_dir = os.getcwd()

        # --- Search State ---
        self.master_image_paths: List[str] = []
        self.search_input = self.common_create_search_input()
        self.search_debounce_timer = QTimer()
        self.search_debounce_timer.setSingleShot(True)
        self.search_debounce_timer.setInterval(300)
        self.search_debounce_timer.timeout.connect(self._perform_search)
        self.search_input.textChanged.connect(self.search_debounce_timer.start)

        # Initialize Pagination Widgets using Shared Logic
        self.pagination_widget = self.create_pagination_controls()

    # --- ABSTRACT METHODS ---

    @abstractmethod
    def create_gallery_label(self, path: str, size: int) -> QLabel:
        """Create the specific interactive label for a gallery item (subclass must implement)."""
        pass

    def create_card_widget(self, path: str, pixmap: Optional[QPixmap]) -> QWidget:
        container = QWidget()
        container.setFixedSize(self.approx_item_width, self.approx_item_width)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setAlignment(Qt.AlignCenter)

        # Factory method
        label = self.create_gallery_label(path, self.thumbnail_size)
        # label.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent) # Removed to fix artifacts

        # Initial State
        is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))

        if (pixmap and not pixmap.isNull()) or (
            hasattr(self, "_failed_paths") and path in self._failed_paths
        ):
            self.update_card_pixmap(container, pixmap, label_ref=label)
        else:
            # Default "Loading..." State
            label.clear()
            label.setText("Loading...")
            if is_video:
                label.setStyleSheet(
                    "border: 2px solid #3498db; color: #3498db; "
                    "font-weight: bold; background-color: #2c2f33;"
                )
            else:
                label.setStyleSheet(
                    "border: 1px dashed #666; color: #888; "
                    "font-size: 10px; background-color: #2c2f33;"
                )

        layout.addWidget(label)
        return container

    def update_card_pixmap(
        self,
        widget: QWidget,
        pixmap: Optional[QPixmap],
        label_ref: Optional[QLabel] = None,
    ):
        if label_ref:
            label = label_ref
        else:
            label = widget.findChild(QLabel)

        if not label:
            return

        # Resolve 'path' vs 'file_path' attribute inconsistency between different Label classes
        path = getattr(label, "file_path", getattr(label, "path", ""))
        is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))

        # 1. Check Failure State
        # 1. Check Failure State
        if hasattr(self, "_failed_paths") and path in self._failed_paths:
            label.clear()
            label.setScaledContents(False)

            if is_video:
                # Match ImageExtractorTab style ("VIDEO" text, Blue border)
                label.setText("VIDEO")
                label.setStyleSheet(
                    "border: 2px solid #3498db; color: #3498db; font-weight: bold; background-color: #2c2f33;"
                )
            else:
                label.setText("No Thumbnail")
                label.setStyleSheet(
                    "border: 2px solid #e74c3c; color: #e74c3c; font-weight: bold; background-color: #2c2f33;"
                )

            label.show()
            return

        # 2. Check Success State
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                self.thumbnail_size,
                self.thumbnail_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            label.setPixmap(scaled)
            label.setText("")

            if is_video:
                label.setStyleSheet(
                    "border: 2px solid #3498db; background-color: transparent;"
                )
            else:
                label.setStyleSheet(
                    "border: 1px solid #4f545c; background-color: transparent;"
                )

        # 3. Loading/Empty State
        else:
            label.setText("Load Failed")
            label.setStyleSheet(
                "border: 1px solid #e74c3c; color: #e74c3c; font-size: 10px; background-color: #2c2f33;"
            )

    def _generate_video_thumbnail(self, path: str) -> Optional[QPixmap]:
        """
        Generates a video thumbnail synchronously on demand.
        Used for fallback or when immediate preview is needed.
        """
        try:
            thumbnailer = VideoThumbnailer()
            image = thumbnailer.generate(path, self.thumbnail_size)
            if image and not image.isNull():
                return QPixmap.fromImage(image)
        except Exception as e:
            print(f"Failed to generate explicit video thumbnail for {path}: {e}")
        return None

    # --- PAGINATION UI HELPERS ---

    def create_pagination_controls(self) -> QWidget:
        """Uses shared logic to create UI, then binds signals."""
        container, controls = self.common_create_pagination_ui()

        # Bind Controls
        self.page_combo = controls["combo"]
        self.prev_btn = controls["btn_prev"]
        self.next_btn = controls["btn_next"]
        self.page_button = controls["btn_page"]

        # Signal Connections
        self.page_combo.currentTextChanged.connect(self._on_page_size_changed)
        self.prev_btn.clicked.connect(lambda: self._change_page(-1))
        self.next_btn.clicked.connect(lambda: self._change_page(1))

        # Initial UI update
        self._update_pagination_ui()

        return container

    def _on_page_size_changed(self, text: str):
        size = 999999 if text == "All" else int(text)
        self.page_size = size
        self.current_page = 0
        self.refresh_gallery_view()

    def _change_page(self, delta: int):
        total_items = len(self.gallery_image_paths)
        if total_items == 0:
            return

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
        if not hasattr(self, "page_button"):
            return

        controls = {
            "btn_page": self.page_button,
            "btn_prev": self.prev_btn,
            "btn_next": self.next_btn,
        }

        # Use shared logic
        corrected_page, total_pages = self.common_update_pagination_state(
            len(self.gallery_image_paths), self.page_size, self.current_page, controls
        )
        self.current_page = corrected_page

        # --- FIX: Prevent memory leak by deleting the old menu and its actions ---
        old_menu = self.page_button.menu()
        if old_menu:
            # Clear actions explicitly although deleteLater should handle it,
            # this is safer in some Qt versions to ensure immediate release of child objects.
            old_menu.clear()
            old_menu.deleteLater()

        # Update Menu
        menu = QMenu(self)
        for i in range(total_pages):
            page_num = i + 1
            action = QAction(f"Page {page_num}", self)
            action.setCheckable(True)
            action.setChecked(i == self.current_page)
            # Use a slightly safer way to connect signals to avoid capturing by reference issues
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
            new_cols = self.common_calculate_columns(
                self.gallery_scroll_area, self.approx_item_width
            )

            if new_cols != self._current_cols:
                self._current_cols = new_cols
                # Shared Reflow
                self.common_reflow_layout(self.gallery_layout, new_cols)

    def _perform_search(self):
        query = self.search_input.text()
        filtered = self.common_filter_string_list(self.master_image_paths, query)
        self.gallery_image_paths = filtered
        self.current_page = 0
        self.refresh_gallery_view()

    # --- LOADING LOGIC ---


    def closeEvent(self, event):
        """Cleanup processes on close."""
        self.cancel_loading()

        # Clear any pending tasks from the shared pool to prevent hanging on exit
        if hasattr(self, "thread_pool"):
            self.thread_pool.clear()

        super().closeEvent(event)

    @Slot(list, list)
    def _on_batch_images_loaded(self, results: List[tuple], requested_paths: List[str]):
        # Cleanup worker reference if called from signals
        sender = self.sender()
        if sender:
            # We need to find the worker that owns this signals object
            for worker in list(self._active_workers):
                if worker.signals == sender:
                    self._active_workers.remove(worker)
                    break

        # 1. Update Results
        for path, q_image in results:
            if path in self._loading_paths:
                self._loading_paths.remove(path)

            pixmap = QPixmap.fromImage(q_image)
            widget = self.path_to_card_widget.get(path)

            if not pixmap.isNull():
                self._initial_pixmap_cache[path] = pixmap
                if widget:
                    self.update_card_pixmap(widget, pixmap)
            else:
                # Mark as failed if the image is Null
                if not hasattr(self, "_failed_paths"):
                    self._failed_paths = set()
                self._failed_paths.add(path)
                if widget:
                    self.update_card_pixmap(widget, QPixmap())

        # 2. Cleanup Missing Results
        processed_paths = set(p for p, _ in results)
        for path in requested_paths:
            if path not in processed_paths:
                if path in self._loading_paths:
                    self._loading_paths.remove(path)

                if not hasattr(self, "_failed_paths"):
                    self._failed_paths = set()
                self._failed_paths.add(path)

                widget = self.path_to_card_widget.get(path)
                if widget:
                    self.update_card_pixmap(widget, QPixmap())

    def _trigger_batch_video_load(self, paths: List[str]):
        # User requested parallel/out-of-order loading.
        # Spawning individual workers allows QThreadPool to manage concurrency.
        for path in paths:
            self._trigger_video_load(path)

    def _trigger_batch_found_load(self, paths: List[str]):
        if not hasattr(self, "found_loading_paths"):
            self.found_loading_paths = set()
        self.found_loading_paths.update(paths)
        worker = BatchImageLoaderWorker(paths, self.thumbnail_size)
        worker.signals.result.connect(self._on_found_image_loaded)
        worker.signals.batch_result.connect(self._on_batch_found_loaded)
        
        self._active_workers.add(worker)
        self.thread_pool.start(worker)

    def _trigger_video_load(self, path: str):
        self._loading_paths.add(path)
        worker = VideoLoaderWorker(path, self.thumbnail_size)
        worker.signals.result.connect(
            self._on_single_image_loaded
        )  # Reuse same handler
        self.thread_pool.start(worker)

    def start_loading_gallery(
        self,
        paths: List[str],
        show_progress: bool = True,
        append: bool = False,
        pixmap_cache: Optional[Dict[str, QPixmap]] = None,
    ):
        """
        Starts the loading process. Accepts an optional pixmap_cache for pre-generated thumbnails.
        """
        if not append:
            self.master_image_paths = paths
            # Reset search when loading new directory (optional, but good UX)
            # self.search_input.clear() # Commented out to persist search if needed, but usually we want reset
            # Ideally we re-apply current search:
            self._perform_search()

            self._initial_pixmap_cache = (
                pixmap_cache if pixmap_cache is not None else {}
            )
            self._loading_paths.clear()
            self._failed_paths.clear()
        else:
            self.master_image_paths.extend(paths)
            if pixmap_cache:
                self._initial_pixmap_cache.update(pixmap_cache)
            # Re-apply search to include new appended items
            self._perform_search()

        # self.refresh_gallery_view() # _perform_search calls this

    def refresh_gallery_view(self):
        self.cancel_loading()
        self.clear_gallery_widgets()
        self._update_pagination_ui()

        if not self.gallery_image_paths:
            self.common_show_placeholder(
                self.gallery_layout, "No images to display.", self.calculate_columns()
            )
            return

        # Prepare for sequential loading
        self._paginated_paths = self.common_get_paginated_slice(
            self.gallery_image_paths, self.current_page, self.page_size
        )
        self._populating_index = 0

        # Start population
        self._populate_step()

    def _populate_step(self):
        """Adds a small batch of widgets to the layout."""
        if not hasattr(self, "_paginated_paths") or self._populating_index >= len(
            self._paginated_paths
        ):
            self._load_all_page_images()
            return

        cols = self.calculate_columns()
        batch_size = 5
        limit = min(self._populating_index + batch_size, len(self._paginated_paths))

        for i in range(self._populating_index, limit):
            path = self._paginated_paths[i]

            # 1. Check Cache
            initial_pixmap = self._initial_pixmap_cache.get(path, None)

            # 2. Check for Video if no cache exists
            is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))

            # 3. Create Widget
            card = self.create_card_widget(path, initial_pixmap)
            self.path_to_card_widget[path] = card

            # 4. Add to Layout
            row = i // cols
            col = i % cols
            if self.gallery_layout:
                self.gallery_layout.addWidget(
                    card, row, col, Qt.AlignLeft | Qt.AlignTop
                )

            # 5. DEFER Async Load (Visibility Check)
            # Both images and videos are now loaded asynchronously via visibility check
            # if initial_pixmap is None:
            #     pass

        self._populating_index = limit

        if self._populating_index < len(self._paginated_paths):
            self._populate_timer.start(0)
        else:
            self._load_all_page_images()

    def _load_all_page_images(self):
        """Triggers loading for all images in the current paginated view."""
        if not self._paginated_paths:
            return

        paths_to_load = []
        for path in self._paginated_paths:
            if path in self._initial_pixmap_cache:
                continue
            if path in self._loading_paths:
                continue
            paths_to_load.append(path)

        if not paths_to_load:
            return

        # Separate images and videos
        image_paths = [
            p
            for p in paths_to_load
            if not p.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
        ]
        video_paths = [
            p
            for p in paths_to_load
            if p.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
        ]

        if video_paths:
            for p in video_paths:
                self._trigger_video_load(p)

        if image_paths:
            for p in image_paths:
                self._trigger_image_load(p)

    def calculate_columns(self):
        return self.common_calculate_columns(
            self.gallery_scroll_area, self.approx_item_width
        )

    def _trigger_image_load(self, path: str):
        self._loading_paths.add(path)
        worker = ImageLoaderWorker(path, self.thumbnail_size)
        worker.signals.result.connect(self._on_single_image_loaded)
        
        self._active_workers.add(worker)
        self.thread_pool.start(worker)

    @Slot(str, QImage)
    def _on_single_image_loaded(self, path: str, q_image: QImage):
        # Cleanup worker ref
        sender = self.sender()
        if sender:
            # We need to find the worker that owns this signals object
            for worker in list(self._active_workers):
                if worker.signals == sender:
                    self._active_workers.remove(worker)
                    break

        if path in self._loading_paths:
            self._loading_paths.remove(path)

        pixmap = QPixmap.fromImage(q_image)

        # If loading failed, mark as failed instead of generating a red placeholder
        if pixmap.isNull():
            if not hasattr(self, "_failed_paths"):
                self._failed_paths = set()
            self._failed_paths.add(path)

            # Cache empty pixmap so _load_visible_images stops asking for it
            self._initial_pixmap_cache[path] = QPixmap()

            widget = self.path_to_card_widget.get(path)
            if widget:
                # This will trigger the "VIDEO" / "No Thumbnail" text style via update_card_pixmap
                self.update_card_pixmap(widget, QPixmap())
            return

        # Cache the result (valid)
        self._initial_pixmap_cache[path] = pixmap

        widget = self.path_to_card_widget.get(path)
        if widget:
            self.update_card_pixmap(widget, pixmap)

    def _generate_error_pixmap(self) -> QPixmap:
        """Generates a visual placeholder for failed loads."""
        size = self.thumbnail_size
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor("#2c2f33"))

        painter = QPainter(pixmap)
        # Red border
        painter.setPen(QColor("#e74c3c"))
        painter.drawRect(0, 0, size - 1, size - 1)

        # Text
        painter.setPen(QColor("#e74c3c"))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "No Thumbnail")
        painter.end()

        return pixmap

    # --- HELPERS ---

    def cancel_loading(self):
        if self._populate_timer.isActive():
            self._populate_timer.stop()

    def clear_gallery_widgets(self):
        self.cancel_loading()
        self.path_to_card_widget.clear()
        self._paginated_paths = []

        if not self.gallery_layout:
            return
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
