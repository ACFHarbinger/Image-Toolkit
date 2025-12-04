import os
from typing import Optional, List, Dict

from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent
from PySide6.QtCore import Qt, QThread, Slot, QThreadPool
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QCheckBox,
    QGroupBox,
    QGridLayout,
    QMessageBox,
    QFileDialog,
    QComboBox,
    QScrollArea,
)

from ...components import ClickableLabel, MarqueeScrollArea
from ...windows import ImagePreviewWindow
from ...classes import AbstractClassSingleGallery
from ...helpers import ImageScannerWorker, ReverseSearchWorker, ImageLoaderWorker
from ...styles.style import apply_shadow_effect


class ReverseImageSearchTab(AbstractClassSingleGallery):
    """
    A tab that scans a local directory to show images in a gallery.
    Clicking an image selects it as the source for a Reverse Image Search.
    """

    def __init__(self):
        super().__init__()

        # --- Data State ---
        self.selected_source_path: Optional[str] = None
        self.search_results: List[Dict[str, str]] = []
        self.open_preview_windows = []

        self.scan_thread: Optional[QThread] = None
        self.scan_worker: Optional[ImageScannerWorker] = None

        # --- UI Setup ---
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(10, 10, 10, 10)

        # 2. Configuration Controls
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

        # Row 2: Search Settings
        search_settings_layout = QHBoxLayout()

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

        # Selected Image Label
        self.lbl_selected_path = QLabel("No image selected")
        self.lbl_selected_path.setStyleSheet("color: #aaa; font-style: italic;")

        self.btn_search = QPushButton("Search Selected Image")
        self.btn_search.setStyleSheet(
            "background-color: #007AFF; color: white; font-weight: bold; padding: 6px;"
        )
        self.btn_search.clicked.connect(self.start_search)
        self.btn_search.setEnabled(False)

        search_settings_layout.addWidget(self.check_filter_res)
        search_settings_layout.addWidget(QLabel("Min:"))
        search_settings_layout.addWidget(self.input_width)
        search_settings_layout.addWidget(QLabel("x"))
        search_settings_layout.addWidget(self.input_height)
        search_settings_layout.addSpacing(10)
        search_settings_layout.addWidget(QLabel("Mode:"))
        search_settings_layout.addWidget(self.mode_combo)
        search_settings_layout.addSpacing(10)
        search_settings_layout.addWidget(self.check_keep_open)
        search_settings_layout.addSpacing(10)
        search_settings_layout.addWidget(QLabel("Browser:"))
        search_settings_layout.addWidget(self.browser_combo)

        search_settings_layout.addStretch()
        search_settings_layout.addWidget(self.lbl_selected_path)
        search_settings_layout.addWidget(self.btn_search)

        controls_layout.addLayout(search_settings_layout)

        self.root_layout.addWidget(controls_group)

        # 3. Status Bar
        self.status_label = QLabel("Ready. Please browse a folder to start.")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.root_layout.addWidget(self.status_label)

        # 4. Gallery Area (UPDATED STYLE TO MATCH IMAGE EXTRACTOR)
        self.gallery_scroll_area = MarqueeScrollArea()
        self.gallery_scroll_area.setWidgetResizable(True)
        self.gallery_scroll_area.setStyleSheet(
            """
            QScrollArea { 
                border: 1px solid #4f545c; 
                background-color: #2c2f33; 
                border-radius: 8px; 
            }
            QScrollBar:vertical {
                border: none;
                background: #2c2f33;
                width: 12px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #00BCD4; 
                min-height: 20px;
                border-radius: 6px;
                margin: 0 2px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                subcontrol-position: none;
            }
            QScrollBar:horizontal {
                border: none;
                background: #2c2f33; 
                height: 12px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:horizontal {
                background: #00BCD4; 
                min-width: 20px;
                border-radius: 6px;
                margin: 2px 0;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                subcontrol-position: none;
            }
        """
        )

        self.gallery_container = QWidget()
        self.gallery_container.setStyleSheet("QWidget { background-color: #2c2f33; }")

        self.gallery_layout = QGridLayout(self.gallery_container)
        self.gallery_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.gallery_layout.setSpacing(3)
        self.gallery_scroll_area.setWidget(self.gallery_container)

        self.root_layout.addWidget(self.gallery_scroll_area, 1)
        self.root_layout.addWidget(
            self.pagination_widget, 0, Qt.AlignmentFlag.AlignCenter
        )

        self.setAcceptDrops(True)

    # --- Directory Scanning Logic ---
    def browse_scan_directory(self):
        start_dir = self.last_browsed_scan_dir
        d = QFileDialog.getExistingDirectory(self, "Select Image Directory", start_dir)
        if d:
            self.last_browsed_scan_dir = d
            self.scan_dir_input.setText(d)
            self.start_scanning(d)

    def start_scanning(self, directory: str):
        self.clear_gallery_widgets()
        self.gallery_image_paths = []
        self._initial_pixmap_cache = {}
        self.selected_source_path = None
        self.btn_search.setEnabled(False)
        self.lbl_selected_path.setText("No image selected")

        self.status_label.setText(f"Scanning directory: {directory}...")

        if self.scan_thread is not None:
            if self.scan_thread.isRunning():
                self.scan_thread.quit()
                self.scan_thread.wait()
            self.scan_thread.deleteLater()
            self.scan_thread = None

        self.scan_worker = ImageScannerWorker(directory)
        self.scan_thread = QThread()
        self.scan_worker.moveToThread(self.scan_thread)

        self.scan_thread.started.connect(self.scan_worker.run_scan)
        self.scan_worker.scan_finished.connect(self.on_scan_finished)
        self.scan_worker.scan_finished.connect(self.scan_thread.quit)
        self.scan_thread.finished.connect(self.scan_thread.deleteLater)
        self.scan_thread.finished.connect(lambda: setattr(self, "scan_thread", None))

        self.scan_thread.start()

    @Slot(list)
    def on_scan_finished(self, paths: list):
        count = len(paths)
        self.status_label.setText(f"Scan complete. Found {count} images.")

        if count == 0:
            self.show_placeholder("No images found in directory.")
        else:
            paths.sort()
            self.start_loading_gallery(paths)

    def _trigger_image_load(self, path: str):
        worker = ImageLoaderWorker(path, self.thumbnail_size)
        worker.signals.result.connect(self._on_single_image_loaded)
        QThreadPool.globalInstance().start(worker)

    # --- Card Widget & Styling (Matched to ImageExtractorTab) ---
    def create_card_widget(self, path: str, pixmap: Optional[QPixmap]) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        lbl = ClickableLabel(path, parent=self)
        lbl.setFixedSize(self.thumbnail_size, self.thumbnail_size)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.path = path  # Explicitly set path attribute for helper access

        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                self.thumbnail_size,
                self.thumbnail_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            lbl.setPixmap(scaled)
            lbl.setText("")
        else:
            lbl.setText("Loading...")
            lbl.setStyleSheet(
                "border: 1px solid #4f545c; color: #888; font-size: 10px;"
            )

        # Apply initial selection style
        self._style_label(lbl, selected=(path == self.selected_source_path))

        lbl.path_clicked.connect(self.handle_image_selection)
        lbl.path_double_clicked.connect(self.handle_image_double_click)

        layout.addWidget(lbl)
        self.path_to_card_widget[path] = container
        return container

    def update_card_pixmap(self, widget: QWidget, pixmap: Optional[QPixmap]):
        if not widget:
            return
        lbl = widget.findChild(ClickableLabel)
        if lbl and pixmap:
            scaled = pixmap.scaled(
                self.thumbnail_size,
                self.thumbnail_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            lbl.setPixmap(scaled)
            lbl.setText("")
            self._style_label(lbl, selected=(lbl.path == self.selected_source_path))

    def _style_label(self, label: ClickableLabel, selected: bool):
        if selected:
            label.setStyleSheet("border: 3px solid #5865f2; background-color: #36393f;")
        else:
            if label.text() == "Loading...":
                label.setStyleSheet(
                    "border: 1px solid #4f545c; color: #888; font-size: 10px;"
                )
            else:
                label.setStyleSheet("border: 1px solid #4f545c;")

    def handle_image_selection(self, path: str):
        self.selected_source_path = path
        self.lbl_selected_path.setText(os.path.basename(path))
        self.btn_search.setEnabled(True)
        self.update_visual_selection()

    def update_visual_selection(self):
        for path, widget in self.path_to_card_widget.items():
            lbl = widget.findChild(ClickableLabel)
            if lbl:
                self._style_label(lbl, selected=(path == self.selected_source_path))

    def handle_image_double_click(self, path: str):
        window = ImagePreviewWindow(
            path, parent=self, all_paths=self.gallery_image_paths
        )
        window.show()
        self.open_preview_windows.append(window)

    def start_search(self):
        if not self.selected_source_path:
            return

        min_w = int(self.input_width.text()) if self.check_filter_res.isChecked() else 0
        min_h = (
            int(self.input_height.text()) if self.check_filter_res.isChecked() else 0
        )

        mode = self.mode_combo.currentText()
        keep_open = self.check_keep_open.isChecked()

        self.btn_search.setEnabled(False)
        self.status_label.setText("Starting browser...")

        worker = ReverseSearchWorker(
            image_path=self.selected_source_path,
            min_width=min_w,
            min_height=min_h,
            browser=self.browser_combo.currentText(),
            search_mode=mode,
            keep_open=keep_open,
        )
        worker.signals.status.connect(self.status_label.setText)
        worker.signals.finished.connect(self.on_search_finished)
        worker.signals.error.connect(self.on_search_error)
        QThreadPool.globalInstance().start(worker)

    @Slot(list)
    def on_search_finished(self, results: list):
        self.btn_search.setEnabled(True)
        self.status_label.setText(f"Search complete. Found {len(results)} results.")

        if not results:
            QMessageBox.information(
                self,
                "No Results",
                "No matching images found matching your criteria, or browser was closed.",
            )
            return

        result_text = "\n".join([f"{r['resolution']} - {r['url']}" for r in results])
        msg = QMessageBox(self)
        msg.setWindowTitle("Search Results")
        msg.setText(f"Found {len(results)} matches:")
        msg.setDetailedText(result_text)
        msg.exec()

    @Slot(str)
    def on_search_error(self, err: str):
        self.btn_search.setEnabled(True)
        self.status_label.setText("Error occurred.")
        QMessageBox.critical(self, "Search Failed", err)

    def toggle_resolution_inputs(self):
        enabled = self.check_filter_res.isChecked()
        self.input_width.setEnabled(enabled)
        self.input_height.setEnabled(enabled)

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

    def collect(self) -> dict:
        return {
            "scan_dir": self.scan_dir_input.text(),
            "browser": self.browser_combo.currentText(),
            "filter_res": self.check_filter_res.isChecked(),
            "min_w": self.input_width.text(),
            "min_h": self.input_height.text(),
            "search_mode": self.mode_combo.currentText(),
            "keep_open": self.check_keep_open.isChecked(),
        }

    def set_config(self, config: dict):
        if "scan_dir" in config:
            d = config["scan_dir"]
            self.scan_dir_input.setText(d)
            if os.path.isdir(d):
                self.start_scanning(d)
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

    def get_default_config(self) -> dict:
        return {
            "scan_dir": "",
            "browser": "brave",
            "filter_res": False,
            "min_w": "1920",
            "min_h": "1080",
            "search_mode": "All",
            "keep_open": True,
        }
