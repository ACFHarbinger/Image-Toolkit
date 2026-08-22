import contextlib
import os
from typing import Dict, List, Optional

from backend.src.web import ENGINE_GOOGLE, ENGINE_LOCAL_CBIR, ENGINE_TINEYE
from PySide6.QtCore import Property, Qt, QThread, QThreadPool, Signal, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...classes import AbstractClassSingleGallery
from ...components import VirtualGallery
from ...helpers import ImageScannerWorker, ReverseSearchWorker
from ...styles import apply_shadow_effect, set_button_role
from ...utils.sort_utils import natural_sort_key
from ...windows import ImagePreviewWindow

_ENGINE_LABELS = {
    "Google Lens": ENGINE_GOOGLE,
    "TinEye API": ENGINE_TINEYE,
    "Local AI Search": ENGINE_LOCAL_CBIR,
}

# Engines that need the browser-related controls visible
_BROWSER_ENGINES = {ENGINE_GOOGLE}
# Engines that use the resolution filter
_RES_FILTER_ENGINES = {ENGINE_GOOGLE}


class ReverseImageSearchTab(AbstractClassSingleGallery):
    """Tab for browsing a local image gallery and running reverse image searches.

    Supports three search engines selectable via a ComboBox:
    - **Google Lens** — browser-based scrape (existing C++ backend).
    - **TinEye API** — commercial REST API client.
    - **Local AI Search** — CLIP + FAISS against the user's local index.

    The gallery is the virtual-scroll ``VirtualGallery`` composite (GUI/UX
    §2.1 Option A): every scanned image is a model row and thumbnails load
    lazily for the visible viewport, so a multi-thousand-image directory has
    no page cap and no per-card widget rebuild. Pagination is gone; selection
    lives in the model/view selection model.
    """

    def __init__(self):
        super().__init__()

        # --- Data State ---
        self.selected_source_path: Optional[str] = None
        self.search_results: List[Dict[str, str]] = []
        self.open_preview_windows = []
        self._active_worker: Optional[ReverseSearchWorker] = None

        self.scan_thread: Optional[QThread] = None
        self.scan_worker: Optional[ImageScannerWorker] = None

        # QML State
        self._is_searching = False

        # --- UI Setup ---
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(10, 10, 10, 10)

        controls_group = QGroupBox("Configuration")
        controls_layout = QVBoxLayout(controls_group)

        # Row 1: Directory Selection
        scan_layout = QHBoxLayout()
        self.scan_dir_input = QLineEdit()
        self.scan_dir_input.setPlaceholderText("Select directory to scan for images...")
        self.scan_dir_input.setReadOnly(True)

        btn_browse_scan = QPushButton("Browse Folder...")
        btn_browse_scan.clicked.connect(self.browse_scan_directory)
        apply_shadow_effect(btn_browse_scan)

        scan_layout.addWidget(QLabel("Image Source:"))
        scan_layout.addWidget(self.scan_dir_input)
        scan_layout.addWidget(btn_browse_scan)
        controls_layout.addLayout(scan_layout)

        # Row 2: Engine selector + always-visible options
        engine_row = QHBoxLayout()

        self.engine_combo = QComboBox()
        self.engine_combo.addItems(list(_ENGINE_LABELS.keys()))
        self.engine_combo.setToolTip("Select which search engine to use")
        self.engine_combo.currentTextChanged.connect(self._on_engine_changed)

        engine_row.addWidget(QLabel("Engine:"))
        engine_row.addWidget(self.engine_combo)
        engine_row.addSpacing(20)

        # Resolution filter (Google only)
        self.check_filter_res = QCheckBox("Filter Results by Resolution")
        self.check_filter_res.toggled.connect(self.toggle_resolution_inputs)

        self.input_width = QLineEdit("1920")
        self.input_width.setPlaceholderText("W")
        self.input_width.setFixedWidth(60)
        self.input_width.setEnabled(False)

        self.input_height = QLineEdit("1080")
        self.input_height.setPlaceholderText("H")
        self.input_height.setFixedWidth(60)
        self.input_height.setEnabled(False)

        engine_row.addWidget(self.check_filter_res)
        engine_row.addWidget(QLabel("Min:"))
        engine_row.addWidget(self.input_width)
        engine_row.addWidget(QLabel("x"))
        engine_row.addWidget(self.input_height)

        engine_row.addStretch()
        controls_layout.addLayout(engine_row)

        # Row 3: Engine-specific option panels (hidden/shown by engine selection)
        self.engine_options_stack = QStackedWidget()

        # Panel 0 — Google-specific options
        google_panel = QWidget()
        google_layout = QHBoxLayout(google_panel)
        google_layout.setContentsMargins(0, 0, 0, 0)

        self.browser_combo = QComboBox()
        self.browser_combo.addItems(["brave", "chrome", "firefox", "edge"])

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["All", "Visual matches", "Exact matches"])
        self.mode_combo.setToolTip("Select which Google Lens page to scrape")

        self.check_keep_open = QCheckBox("Keep Browser Open")
        self.check_keep_open.setChecked(True)
        self.check_keep_open.setToolTip(
            "If checked, the browser will not close automatically after searching."
        )

        google_layout.addWidget(QLabel("Browser:"))
        google_layout.addWidget(self.browser_combo)
        google_layout.addSpacing(10)
        google_layout.addWidget(QLabel("Mode:"))
        google_layout.addWidget(self.mode_combo)
        google_layout.addSpacing(10)
        google_layout.addWidget(self.check_keep_open)
        google_layout.addStretch()

        # Panel 1 — TinEye-specific options
        tineye_panel = QWidget()
        tineye_layout = QHBoxLayout(tineye_panel)
        tineye_layout.setContentsMargins(0, 0, 0, 0)
        tineye_layout.addWidget(
            QLabel(
                "Credentials via TINEYE_API_KEY / TINEYE_API_SECRET env vars "
                "or backend/config/api_keys.yaml"
            )
        )
        tineye_layout.addStretch()

        # Panel 2 — Local CBIR-specific options
        cbir_panel = QWidget()
        cbir_layout = QHBoxLayout(cbir_panel)
        cbir_layout.setContentsMargins(0, 0, 0, 0)
        self.top_k_input = QLineEdit("20")
        self.top_k_input.setFixedWidth(55)
        self.top_k_input.setToolTip(
            "Maximum number of nearest neighbours to retrieve from the local index"
        )
        cbir_layout.addWidget(QLabel("Results (top-k):"))
        cbir_layout.addWidget(self.top_k_input)
        cbir_layout.addSpacing(20)
        cbir_layout.addWidget(
            QLabel("Index: ~/.image-toolkit/cbir_index/  |  Model: CLIP ViT-B/32")
        )
        cbir_layout.addStretch()

        self.engine_options_stack.addWidget(google_panel)   # index 0
        self.engine_options_stack.addWidget(tineye_panel)   # index 1
        self.engine_options_stack.addWidget(cbir_panel)     # index 2

        controls_layout.addWidget(self.engine_options_stack)

        # Row 4: Search button + selected-image label
        action_row = QHBoxLayout()

        self.lbl_selected_path = QLabel("No image selected")
        self.lbl_selected_path.setStyleSheet("color: #aaa; font-style: italic;")

        self.btn_search = QPushButton("Search Selected Image")
        set_button_role(self.btn_search, "success")
        self.btn_search.clicked.connect(self.start_search)
        self.btn_search.setEnabled(False)

        action_row.addWidget(self.lbl_selected_path)
        action_row.addStretch()
        action_row.addWidget(self.btn_search)
        controls_layout.addLayout(action_row)

        self.root_layout.addWidget(controls_group)

        # Status bar
        self.status_label = QLabel("Ready. Please browse a folder to start.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.root_layout.addWidget(self.status_label)

        # Gallery — virtual-scroll (GUI/UX §2.1 Option A). Replaces the old
        # QGridLayout + ClickableLabel card grid; pagination is dropped.
        self.gallery = VirtualGallery(self)
        self.root_layout.addWidget(self.search_input)
        self.root_layout.addWidget(self.gallery, 1)

        self.gallery.path_clicked.connect(self.handle_image_selection)
        self.gallery.path_activated.connect(self.handle_image_double_click)
        self.gallery.ctrl_wheel.connect(self._on_ctrl_wheel_zoom)

        self.setAcceptDrops(True)
        self._on_engine_changed(self.engine_combo.currentText())

    # ------------------------------------------------------------------
    # Engine selection
    # ------------------------------------------------------------------

    @Slot(str)
    def _on_engine_changed(self, label: str) -> None:
        """Switch the options panel and toggle Google-only controls."""
        engine = _ENGINE_LABELS.get(label, ENGINE_GOOGLE)
        idx = list(_ENGINE_LABELS.values()).index(engine)
        self.engine_options_stack.setCurrentIndex(idx)

        is_google = engine == ENGINE_GOOGLE
        self.check_filter_res.setVisible(is_google)
        self.input_width.setVisible(is_google)
        self.input_height.setVisible(is_google)

    def _current_engine_type(self) -> str:
        return _ENGINE_LABELS.get(self.engine_combo.currentText(), ENGINE_GOOGLE)

    # ------------------------------------------------------------------
    # Directory Scanning
    # ------------------------------------------------------------------

    def browse_scan_directory(self):
        start_dir = self.last_browsed_scan_dir
        d = QFileDialog.getExistingDirectory(
            self,
            "Select Image Directory",
            start_dir,
            QFileDialog.Option.DontUseNativeDialog,
        )
        if d:
            self.last_browsed_scan_dir = d
            self.scan_dir_input.setText(d)
            self.start_scanning(d)

    def start_scanning(self, directory: str):
        if self.scan_thread is not None:
            if self.scan_thread.isRunning():
                if self.scan_worker:
                    with contextlib.suppress(Exception):
                        self.scan_worker.scan_finished.disconnect()
                self.scan_thread.quit()
                self.scan_thread.wait()
            self.scan_thread.deleteLater()
            self.scan_thread = None
            self.scan_worker = None

        self.clear_gallery_widgets()
        self.gallery_image_paths = []
        self._initial_pixmap_cache.clear()
        self.selected_source_path = None
        self.btn_search.setEnabled(False)
        self.lbl_selected_path.setText("No image selected")
        self.status_label.setText(f"Scanning directory: {directory}...")

        self.scan_worker = ImageScannerWorker(directory)
        self.scan_thread = self.scan_worker

        self.scan_worker.scan_finished.connect(self.on_scan_finished)
        self.scan_worker.finished.connect(self.scan_worker.deleteLater)
        self.scan_worker.finished.connect(lambda: setattr(self, "scan_thread", None))

        self.scan_worker.start()

    @Slot(list)
    def on_scan_finished(self, paths: list):
        count = len(paths)
        self.status_label.setText(f"Scan complete. Found {count} images.")
        if count == 0:
            self.gallery.clear()
            return
        paths.sort(key=natural_sort_key)
        self.start_loading_gallery(paths)
        self.qml_gallery_changed.emit()

    # ------------------------------------------------------------------
    # Gallery — virtual-scroll surface (GUI/UX §2.1 Option A)
    # ------------------------------------------------------------------

    def refresh_gallery_view(self):
        """Feed the current filtered path list to the virtual gallery.

        Overrides the base grid/pagination refresh: ``VirtualGallery`` renders
        every row with viewport culling, so there is no page slice or per-card
        widget population step."""
        self.cancel_loading()
        self.clear_gallery_widgets()
        paths = self.gallery_image_paths
        if not paths:
            self.status_label.setText("No images to display.")
            return
        self.gallery.set_paths(paths)

    def clear_gallery_widgets(self):
        """Clear the virtual gallery and cancel its in-flight loads.

        (Base version tears down a QGridLayout that no longer exists.)"""
        self.gallery.clear()
        self.cancel_loading()

    def cancel_loading(self):
        if self.scan_thread is not None:
            if self.scan_thread.isRunning():
                if self.scan_worker:
                    with contextlib.suppress(Exception):
                        self.scan_worker.scan_finished.disconnect()
                self.scan_thread.quit()
                self.scan_thread.wait()
            self.scan_thread = None
            self.scan_worker = None
        if hasattr(self, "gallery"):
            self.gallery.cancel_loading()
        super().cancel_loading()

    def _on_layout_change(self):
        """VirtualGallery re-lays-out itself; nothing to reflow here."""

    def _on_ctrl_wheel_zoom(self, delta: int):
        """Ctrl+wheel thumbnail zoom (§2.2) over the virtual gallery."""
        step = 16 if delta > 0 else -16
        new_size = max(64, min(512, self.thumbnail_size + step))
        if new_size == self.thumbnail_size:
            return
        self.thumbnail_size = new_size
        self.approx_item_width = new_size + self.padding_width + 20
        self._save_thumbnail_size()
        self.gallery.set_thumbnail_size(new_size)

    # ------------------------------------------------------------------
    # Selection (mapped onto the model/view selection model)
    # ------------------------------------------------------------------

    def handle_image_selection(self, path: str):
        self.selected_source_path = path
        self.lbl_selected_path.setText(os.path.basename(path))
        self.btn_search.setEnabled(True)
        self.update_visual_selection()

    def update_visual_selection(self):
        """Single-select model: highlight only ``selected_source_path``."""
        self.gallery.clear_selection()
        if self.selected_source_path:
            row = self.gallery.model.row_for_path(self.selected_source_path)
            if row >= 0:
                sm = self.gallery.view.selectionModel()
                sm.select(self.gallery.model.index(row, 0), sm.SelectionFlag.ClearAndSelect)

    def select_all_items(self):
        self.gallery.select_all()
        self.on_selection_changed()

    def deselect_all_items(self):
        self.gallery.clear_selection()
        self.on_selection_changed()

    def handle_image_double_click(self, path: str):
        window = ImagePreviewWindow(path, parent=self, all_paths=self.gallery_image_paths)
        window.show()
        self.open_preview_windows.append(window)

    # ------------------------------------------------------------------
    # AbstractClassSingleGallery contract (unused by the virtual surface)
    # ------------------------------------------------------------------

    def create_gallery_label(self, path: str, size: int) -> QLabel:
        lbl = QLabel(path)
        lbl.setFixedSize(size, size)
        return lbl

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def start_search(self):
        if not self.selected_source_path:
            return

        engine_type = self._current_engine_type()
        min_w = int(self.input_width.text()) if self.check_filter_res.isChecked() else 0
        min_h = int(self.input_height.text()) if self.check_filter_res.isChecked() else 0
        top_k = int(self.top_k_input.text()) if self.top_k_input.text().isdigit() else 20

        self.btn_search.setEnabled(False)
        self.status_label.setText("Starting search…")

        worker = ReverseSearchWorker(
            image_path=self.selected_source_path,
            engine_type=engine_type,
            min_width=min_w,
            min_height=min_h,
            browser=self.browser_combo.currentText(),
            search_mode=self.mode_combo.currentText(),
            keep_open=self.check_keep_open.isChecked(),
            top_k=top_k,
        )
        self._active_worker = worker
        worker.signals.status.connect(self.status_label.setText)
        worker.signals.finished.connect(self.on_search_finished)
        worker.signals.error.connect(self.on_search_error)
        QThreadPool.globalInstance().start(worker)

    @Slot(list)
    def on_search_finished(self, results: list):
        self._active_worker = None
        self.btn_search.setEnabled(True)
        self.status_label.setText(f"Search complete. Found {len(results)} results.")

        if not results:
            QMessageBox.information(
                self,
                "No Results",
                "No matching images found matching your criteria.",
            )
            return

        engine = results[0].get("engine", "unknown") if results else "unknown"
        result_text = "\n".join(
            [f"{r.get('resolution', '?')} | score={r.get('score','?')} — {r.get('url','')}" for r in results]
        )
        msg = QMessageBox(self)
        msg.setWindowTitle(f"Search Results ({engine})")
        msg.setText(f"Found {len(results)} matches:")
        msg.setDetailedText(result_text)
        msg.exec()

    @Slot(str)
    def on_search_error(self, err: str):
        self._active_worker = None
        self.btn_search.setEnabled(True)
        self.status_label.setText("Error occurred.")
        QMessageBox.critical(self, "Search Failed", err)

    def toggle_resolution_inputs(self):
        enabled = self.check_filter_res.isChecked()
        self.input_width.setEnabled(enabled)
        self.input_height.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Drag and Drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if os.path.isdir(path):
                self.scan_dir_input.setText(path)
                self.start_scanning(path)

    # ------------------------------------------------------------------
    # Config persistence
    # ------------------------------------------------------------------

    def collect(self) -> dict:
        return {
            "scan_dir": self.scan_dir_input.text(),
            "engine": self.engine_combo.currentText(),
            "browser": self.browser_combo.currentText(),
            "filter_res": self.check_filter_res.isChecked(),
            "min_w": self.input_width.text(),
            "min_h": self.input_height.text(),
            "search_mode": self.mode_combo.currentText(),
            "keep_open": self.check_keep_open.isChecked(),
            "top_k": self.top_k_input.text(),
        }

    def set_config(self, config: dict):
        if "scan_dir" in config:
            d = config["scan_dir"]
            self.scan_dir_input.setText(d)
            if os.path.isdir(d):
                self.start_scanning(d)
        if "engine" in config:
            self.engine_combo.setCurrentText(config["engine"])
        if "browser" in config:
            self.browser_combo.setCurrentText(config["browser"])
        if "filter_res" in config:
            self.check_filter_res.setChecked(config["filter_res"])
        if "min_w" in config:
            self.input_width.setText(config["min_w"])
        if "min_h" in config:
            self.input_height.setText(config["min_h"])
        if "search_mode" in config:
            self.mode_combo.setCurrentText(config["search_mode"])
        if "keep_open" in config:
            self.check_keep_open.setChecked(config["keep_open"])
        if "top_k" in config:
            self.top_k_input.setText(config["top_k"])

    def get_default_config(self) -> dict:
        return {
            "scan_dir": "",
            "engine": "Google Lens",
            "browser": "brave",
            "filter_res": False,
            "min_w": "1920",
            "min_h": "1080",
            "search_mode": "All",
            "keep_open": True,
            "top_k": "20",
        }
    # --- QML Integration ---
    qml_searching_changed = Signal()
    qml_selection_changed = Signal()
    qml_gallery_changed = Signal()
    qml_config_changed = Signal()

    @Property(bool, notify=qml_searching_changed)
    def is_searching(self):
        return self._is_searching

    @Property(bool, notify=qml_selection_changed)
    def has_selection(self):
        return self.selected_source_path is not None

    @Property(str, notify=qml_config_changed)
    def scan_dir_path(self):
        return self.scan_dir_input.text()

    @Property(list, notify=qml_gallery_changed)
    def gallery_model(self):
        # QML requires list of objects/dicts.
        # Assuming self.gallery_image_paths is list of strings
        if not hasattr(self, 'gallery_image_paths'):
            return []
        return [{"path": p, "name": os.path.basename(p)} for p in self.gallery_image_paths]

    # ... Configuration properties ...


    @Slot(str)
    def handle_image_selection_qml(self, path):
        self.handle_image_selection(path)
        self.qml_selection_changed.emit()

    @Slot()
    def start_reverse_search(self):
        # Similar logic to start_search but ensuring state updates
        if not self.selected_source_path:
            return
        self._is_searching = True
        self.qml_searching_changed.emit()
        self.start_search()

    @Slot()
    def cancel_search(self):
        if self._active_worker:
            self._active_worker.cancel()
            self.status_label.setText("Cancelling…")
        self._is_searching = False
        self.qml_searching_changed.emit()

    def closeEvent(self, event):
        self.cancel_loading()
        for win in list(self.open_preview_windows):
            with contextlib.suppress(Exception):
                win.close()
        self.open_preview_windows.clear()
        super().closeEvent(event)
