import os
from pathlib import Path
from typing import Dict, Any, Set, List

from PySide6.QtCore import Qt, QTimer, QThread, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QLineEdit, QFileDialog, QWidget, QLabel, QPushButton,
    QComboBox, QSpinBox, QGroupBox, QFormLayout, QHBoxLayout,
    QVBoxLayout, QMessageBox, QApplication, QGridLayout, QScrollArea
)

from .base_tab import BaseTab
from ..components import ClickableLabel, MarqueeScrollArea
from ..helpers import MergeWorker, ImageScannerWorker, BatchThumbnailLoaderWorker
from ..styles.style import apply_shadow_effect
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS


class MergeTab(BaseTab):
    """
    GUI tab for merging images with a file/directory selection gallery.
    Uses safe threading, progressive loading, and dual-panel selection.
    
    Refactored to match the threading and UI patterns of ScanMetadataTab.
    """

    def __init__(self, dropdown=True):
        super().__init__()
        self.dropdown = dropdown

        # --- State ---
        self.selected_image_paths: Set[str] = set()
        self.merge_image_list: List[str] = []
        self.path_to_label_map: Dict[str, ClickableLabel] = {}
        self.selected_card_map: Dict[str, ClickableLabel] = {}
        self.scanned_dir: str | None = None

        # --- Thread tracking (mimicking ScanMetadataTab) ---
        self.current_scan_thread: QThread | None = None
        self.current_scan_worker: ImageScannerWorker | None = None
        self.current_loader_thread: QThread | None = None
        self.current_loader_worker: BatchThumbnailLoaderWorker | None = None
        self.current_merge_thread: QThread | None = None
        self.current_merge_worker: MergeWorker | None = None

        # --- Last browsed dir ---
        try:
            base_dir = Path.cwd()
            while base_dir.name != 'Image-Toolkit' and base_dir.parent != base_dir:
                base_dir = base_dir.parent
            if base_dir.name == 'Image-Toolkit':
                self.last_browsed_dir = str(base_dir / 'data')
            else:
                self.last_browsed_dir = str(Path.cwd() / 'data')
        except Exception:
            self.last_browsed_dir = os.getcwd()

        # --- UI Constants ---
        self.thumbnail_size = 150
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width

        # --- Layout Setup ---
        main_layout = QVBoxLayout(self)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")

        scroll_content = QWidget()
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # === 1. Merge Settings ===
        config_group = QGroupBox("Merge Settings")
        config_layout = QFormLayout(config_group)

        self.direction = QComboBox()
        self.direction.addItems(["horizontal", "vertical", "grid"])
        self.direction.currentTextChanged.connect(self.toggle_grid_visibility)
        config_layout.addRow("Direction:", self.direction)

        self.spacing = QSpinBox()
        self.spacing.setRange(0, 1000)
        self.spacing.setValue(10)
        config_layout.addRow("Spacing (px):", self.spacing)

        self.grid_group = QGroupBox("Grid Size")
        grid_layout = QHBoxLayout()
        self.grid_rows = QSpinBox()
        self.grid_rows.setRange(1, 100)
        self.grid_cols = QSpinBox()
        self.grid_cols.setRange(1, 100)
        grid_layout.addWidget(QLabel("Rows:"))
        grid_layout.addWidget(self.grid_rows)
        grid_layout.addWidget(QLabel("Cols:"))
        grid_layout.addWidget(self.grid_cols)
        self.grid_group.setLayout(grid_layout)
        config_layout.addRow(self.grid_group)
        self.grid_group.hide()

        content_layout.addWidget(config_group)

        # === 2. Input Gallery ===
        gallery_group = QGroupBox("Select Images to Merge")
        gallery_vbox = QVBoxLayout(gallery_group)

        # Buttons (Refactored to match ScanMetadataTab input style)
        input_controls = QHBoxLayout()
        self.input_path_info = QLineEdit()
        self.input_path_info.setPlaceholderText("Scan directory (press Enter) or use buttons.")
        self.input_path_info.setReadOnly(False) # Changed
        self.input_path_info.setStyleSheet("background-color: #333; color: #b9bbbe;")
        self.input_path_info.returnPressed.connect(self.handle_scan_directory_return) # Added

        btn_add_files = QPushButton("Add Files")
        apply_shadow_effect(btn_add_files, "#000000", 8, 0, 3)
        btn_add_files.clicked.connect(self._browse_files_logic)
        btn_add_files.setDefault(True)

        btn_scan_dir = QPushButton("Scan Directory")
        apply_shadow_effect(btn_scan_dir, "#000000", 8, 0, 3)
        btn_scan_dir.clicked.connect(self.browse_scan_directory) # Changed

        input_controls.addWidget(self.input_path_info)
        input_controls.addWidget(btn_add_files)
        input_controls.addWidget(btn_scan_dir)
        gallery_vbox.addLayout(input_controls)

        self.selection_label = QLabel("0 images selected.")
        gallery_vbox.addWidget(self.selection_label)

        # Top Gallery
        self.merge_scroll_area = MarqueeScrollArea()
        self.merge_scroll_area.setWidgetResizable(True)
        self.merge_scroll_area.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.merge_scroll_area.setMinimumHeight(600) # Added
        self.merge_thumbnail_widget = QWidget()
        self.merge_thumbnail_widget.setStyleSheet("background-color: #2c2f33;")
        self.merge_thumbnail_layout = QGridLayout(self.merge_thumbnail_widget)
        self.merge_thumbnail_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.merge_scroll_area.setWidget(self.merge_thumbnail_widget)
        self.merge_scroll_area.selection_changed.connect(self.handle_marquee_selection)
        gallery_vbox.addWidget(self.merge_scroll_area, 1)

        # Bottom Selected Gallery
        self.selected_images_area = MarqueeScrollArea()
        self.selected_images_area.setWidgetResizable(True)
        self.selected_images_area.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.selected_images_area.setMinimumHeight(600) # Added
        self.selected_images_widget = QWidget()
        self.selected_images_widget.setStyleSheet("background-color: #2c2f33;")
        self.selected_grid_layout = QGridLayout(self.selected_images_widget)
        self.selected_grid_layout.setSpacing(10)
        self.selected_grid_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.selected_images_area.setWidget(self.selected_images_widget)
        gallery_vbox.addWidget(self.selected_images_area, 1)

        content_layout.addWidget(gallery_group, 6) # Added stretch
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        # === 3. Action Buttons (Fixed Bottom) ===
        action_vbox = QVBoxLayout()

        self.run_button = QPushButton("Run Merge")
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #5865f2; color: white; font-weight: bold;
                font-size: 16px; padding: 14px; border-radius: 10px; min-height: 44px;
            }
            QPushButton:hover { background-color: #4754c4; }
            QPushButton:disabled { background: #718096; }
            QPushButton:pressed { background: #3f479a; }
        """)
        apply_shadow_effect(self.run_button, "#000000", 8, 0, 3)
        self.run_button.clicked.connect(self.start_merge)
        self.run_button.setDefault(True)
        action_vbox.addWidget(self.run_button)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #b9bbbe; font-style: italic; padding: 10px;")
        action_vbox.addWidget(self.status_label)

        main_layout.addLayout(action_vbox)

        self.update_run_button_state()
        self.toggle_grid_visibility(self.direction.currentText())
        self._show_placeholder("No images loaded. Use buttons above to add files or scan a directory.")

    # === THREAD SAFETY CLEANUP (from ScanMetadataTab) ===
    @Slot()
    def _cleanup_scan_thread_ref(self):
        """Slot to clear the QThread and QObject references after the scan thread finishes."""
        self.current_scan_thread = None
        self.current_scan_worker = None

    @Slot()
    def _cleanup_loader_thread_ref(self):
        """Slot to clear the QThread and QObject references after the loader thread finishes."""
        self.current_loader_thread = None
        self.current_loader_worker = None

    @Slot()
    def _cleanup_merge_thread_ref(self):
        """Slot to clear the QThread and QObject references after the merge thread finishes."""
        self.current_merge_thread = None
        self.current_merge_worker = None

    # === GALLERY MANAGEMENT ===
    def _clear_gallery(self, layout: QGridLayout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _show_placeholder(self, text: str):
        self._clear_gallery(self.merge_thumbnail_layout)
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #b9bbbe; font-style: italic;")
        self.merge_thumbnail_layout.addWidget(lbl, 0, 0, 1, self._columns(), Qt.AlignCenter)

    def _columns(self) -> int:
        w = self.merge_scroll_area.viewport().width()
        return max(1, w // self.approx_item_width)

    @Slot(int, str)
    def _create_thumbnail_placeholder(self, idx: int, path: str):
        label = ClickableLabel(path)
        label.setFixedSize(self.thumbnail_size, self.thumbnail_size)
        label.setScaledContents(True)
        label.setStyleSheet("background:#444; border:1px solid #555;")
        label.setText("Loading...")
        label.setAlignment(Qt.AlignCenter)

        row = idx // self._columns()
        col = idx % self._columns()
        self.merge_thumbnail_layout.addWidget(label, row, col, Qt.AlignCenter)
        self.path_to_label_map[path] = label

        label.path_clicked.connect(self._toggle_selection)
        label.path_double_clicked.connect(lambda p: QMessageBox.information(self, "Path", p))
        
        QApplication.processEvents()


    @Slot(int, QPixmap, str)
    def _update_thumbnail_slot(self, idx: int, pixmap: QPixmap, path: str):
        label = self.path_to_label_map.get(path)
        if label and not pixmap.isNull():
            label.setPixmap(pixmap)
            label.setText("")
            self._update_label_style(label, path, path in self.selected_image_paths)
        elif label:
            label.setText("Load Error")
            self._update_label_style(label, path, path in self.selected_image_paths)


    def _update_label_style(self, label: ClickableLabel, path: str, selected: bool):
        if selected:
            label.setStyleSheet("border: 3px solid #5865f2;")
        else:
            if label.pixmap() and not label.pixmap().isNull():
                label.setStyleSheet("border: 1px solid #4f545c;")
            else:
                label.setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;")

    # === SELECTION HANDLING ===
    def _toggle_selection(self, path: str):
        if path in self.selected_image_paths:
            self.selected_image_paths.remove(path)
            selected = False
        else:
            self.selected_image_paths.add(path)
            selected = True
            
        label = self.path_to_label_map.get(path)
        if label:
            self._update_label_style(label, path, selected)
            
        self._refresh_selected_panel()
        self.update_run_button_state()

    def handle_marquee_selection(self, paths: set, ctrl_pressed: bool):
        if not ctrl_pressed:
            paths_to_deselect = self.selected_image_paths - paths
            self.selected_image_paths.clear()
        else:
            paths_to_deselect = set()

        self.selected_image_paths.update(paths)
        
        # Update styles for all affected labels
        paths_to_update = paths.union(paths_to_deselect)
        for path in paths_to_update:
            label = self.path_to_label_map.get(path)
            if label:
                self._update_label_style(label, path, path in self.selected_image_paths)
                
        self._refresh_selected_panel()
        self.update_run_button_state()

    def _refresh_selected_panel(self):
        self._clear_gallery(self.selected_grid_layout)
        self.selected_card_map.clear()
        
        # MODIFIED: Use the main 'approx_item_width' for column calculation
        cols = max(1, self.selected_images_area.viewport().width() // self.approx_item_width)

        for i, path in enumerate(sorted(list(self.selected_image_paths))):
            src = self.path_to_label_map.get(path)
            
            # MODIFIED: Scale pixmap to the main 'thumbnail_size'
            pix = src.pixmap() if src and src.pixmap() else QPixmap(path).scaled(
                self.thumbnail_size, self.thumbnail_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            card = ClickableLabel(path)
            
            # MODIFIED: Set card size to the main 'thumbnail_size'
            card.setFixedSize(self.thumbnail_size, self.thumbnail_size)
            card.setScaledContents(True)
            
            if not pix.isNull():
                card.setPixmap(pix)
            else:
                card.setText("Error")
                card.setStyleSheet("background: #333; color: red;")
            card.path_clicked.connect(lambda _, p=path: self._toggle_selection(p))

            row = i // cols
            col = i % cols
            self.selected_grid_layout.addWidget(card, row, col, Qt.AlignCenter)
            self.selected_card_map[path] = card

    # === INPUT LOGIC (Refactored) ===
    
    def _browse_files_logic(self):
        """Handles the 'Add Files' button click."""
        start_dir = self.last_browsed_dir or str(Path.home())
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Images", start_dir,
            "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)"
        )
        if files:
            self.last_browsed_dir = os.path.dirname(files[0])
            new_paths = [f for f in files if f not in self.merge_image_list]
            
            # Manually trigger the loader for these files
            self.display_scan_results(self.merge_image_list + new_paths)
            self.input_path_info.setText(f"Added {len(new_paths)} files.")


    def handle_scan_directory_return(self):
        """Custom handler for Enter key press on the scan directory path input."""
        directory = self.input_path_info.text().strip()
        if directory and Path(directory).is_dir():
            self.populate_scan_gallery(directory)
        else:
            # If text is empty or invalid, pop the browse dialog
            self.browse_scan_directory()

    def browse_scan_directory(self):
        """Opens dialog to select scan directory and populates gallery."""
        directory = QFileDialog.getExistingDirectory(
            self, "Scan Directory", self.last_browsed_dir or str(Path.home())
        )
        if directory:
            self.last_browsed_dir = directory
            self.input_path_info.setText(directory)
            self.populate_scan_gallery(directory)
            
    def handle_scan_error(self, message: str):
        self._clear_gallery(self.merge_thumbnail_layout)
        QMessageBox.warning(self, "Error Scanning", message)
        self._show_placeholder("Browse for a directory.")
    
    def _display_load_complete_message(self):
        image_count = len(self.merge_image_list)
        if image_count > 0:
            QMessageBox.information(
                self, 
                "Scan Complete", 
                f"Finished loading **{image_count}** images from the directory. They are now available in the gallery below.",
                QMessageBox.StandardButton.Ok
            )

    def populate_scan_gallery(self, directory: str):
        """
        Initiates scanning. Clears main gallery and aborts active scan/load threads.
        (from ScanMetadataTab)
        """
        self.scanned_dir = directory
        
        # Stop active scan thread
        if self.current_scan_thread and self.current_scan_thread.isRunning():
            self.current_scan_thread.quit()
            self.current_scan_thread.wait(2000)
    
        # Stop active loader thread
        if self.current_loader_thread and self.current_loader_thread.isRunning():
            self.current_loader_thread.quit()
            self.current_loader_thread.wait(2000)

        self._clear_gallery(self.merge_thumbnail_layout)
        self.path_to_label_map.clear()
        self.merge_image_list = []

        loading_label = QLabel("Scanning directory, please wait...")
        loading_label.setAlignment(Qt.AlignCenter)
        loading_label.setStyleSheet("color: #b9bbbe;")
        self.merge_thumbnail_layout.addWidget(loading_label, 0, 0, 1, 10)
        
        worker = ImageScannerWorker(directory)
        thread = QThread()
        
        self.current_scan_worker = worker
        self.current_scan_thread = thread
        worker.moveToThread(thread)

        thread.started.connect(worker.run_scan)
        worker.scan_finished.connect(self.display_scan_results)
        worker.scan_error.connect(self.handle_scan_error)

        worker.scan_finished.connect(thread.quit)
        worker.scan_finished.connect(worker.deleteLater)
        
        worker.scan_error.connect(thread.quit)
        worker.scan_error.connect(worker.deleteLater)

        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._cleanup_scan_thread_ref)

        worker.scan_finished.connect(self._display_load_complete_message)
        
        thread.start()

    def display_scan_results(self, image_paths: list[str]):
        """
        Receives image paths from scan worker, creates placeholders, 
        and starts thumbnail loader. (from ScanMetadataTab)
        """
        
        # --- REMOVED FAULTY THREAD CHECK ---
        # The faulty check that caused the freeze has been removed.

        self.merge_image_list = sorted(image_paths)
        if self.scanned_dir:
             self.input_path_info.setText(f"Source: {Path(self.scanned_dir).name} | {len(image_paths)} images")
        
        self._clear_gallery(self.merge_thumbnail_layout)
        self.path_to_label_map.clear()

        if not image_paths:
            self._show_placeholder("No supported images found.")
            return

        # Stop previous loader thread if any
        if self.current_loader_thread and self.current_loader_thread.isRunning():
            self.current_loader_thread.quit()
            self.current_loader_thread.wait(2000)

        loader = BatchThumbnailLoaderWorker(image_paths, self.thumbnail_size)
        thread = QThread()
        
        self.current_loader_worker = loader
        self.current_loader_thread = thread
        
        loader.moveToThread(thread)
        thread.started.connect(loader.run_load_batch)
        loader.create_placeholder.connect(self._create_thumbnail_placeholder)
        loader.thumbnail_loaded.connect(self._update_thumbnail_slot)
        
        loader.loading_finished.connect(thread.quit)
        loader.loading_finished.connect(loader.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._cleanup_loader_thread_ref)
        
        thread.start()

    # === MERGE EXECUTION (Refactored) ===
    def start_merge(self):
        if len(self.selected_image_paths) < 2:
            QMessageBox.warning(self, "Invalid", "Select at least 2 images.")
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self, "Save Merged Image", self.last_browsed_dir, "PNG (*.png)"
        )
        if not output_path:
            self.status_label.setText("Cancelled.")
            return
        if not output_path.lower().endswith('.png'):
            output_path += '.png'
        self.last_browsed_dir = os.path.dirname(output_path)

        config = self.collect(output_path)
        self.run_button.setEnabled(False)
        self.run_button.setText("Merging...")
        self.status_label.setText("Processing...")

        # --- Refactored Thread Logic ---
        if self.current_merge_thread and self.current_merge_thread.isRunning():
            self.current_merge_thread.quit()
            self.current_merge_thread.wait(2000)

        worker = MergeWorker(config)
        thread = QThread()
        
        self.current_merge_worker = worker
        self.current_merge_thread = thread
        worker.moveToThread(thread)
        
        thread.started.connect(worker.run)
        worker.progress.connect(self.update_progress)
        
        # Assuming MergeWorker emits finished(str) and scan_error(str)
        # based on the original _start_worker's connections
        worker.finished.connect(self.on_merge_done)
        worker.scan_error.connect(self.on_merge_error)
        
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.scan_error.connect(thread.quit)
        worker.scan_error.connect(worker.deleteLater)
        
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._cleanup_merge_thread_ref)
        
        thread.start()

    def update_progress(self, cur, total):
        self.status_label.setText(f"Merging {cur}/{total}...")

    def on_merge_done(self, path):
        self.update_run_button_state()
        self.status_label.setText(f"Saved: {os.path.basename(path)}")
        QMessageBox.information(self, "Success", f"Merge complete!\n{path}")

    def on_merge_error(self, msg):
        self.update_run_button_state()
        self.status_label.setText("Failed.")
        QMessageBox.critical(self, "Error", msg)

    def collect(self, output_path: str) -> Dict[str, Any]:
        return {
            "direction": self.direction.currentText(),
            "input_path": list(self.selected_image_paths),
            "output_path": output_path,
            "input_formats": [f.strip().lstrip('.') for f in SUPPORTED_IMG_FORMATS if f.strip()],
            "spacing": self.spacing.value(),
            "grid_size": (self.grid_rows.value(), self.grid_cols.value())
            if self.direction.currentText() == "grid" else None
        }

    # === UI UTILS ===
    def update_run_button_state(self):
        count = len(self.selected_image_paths)
        self.selection_label.setText(f"{count} images selected.")
        if count < 2:
            self.run_button.setEnabled(False)
            self.run_button.setText("Run Merge (Select 2+ images)")
            self.run_button.setDefault(False)
        else:
            self.run_button.setEnabled(True)
            self.run_button.setText(f"Run Merge ({count} images)")
            self.run_button.setDefault(True)
        self.status_label.setText("" if count < 2 else f"Ready to merge {count} images.")

    def toggle_grid_visibility(self, direction):
        self.grid_group.setVisible(direction == "grid")
        if not hasattr(self, "_resize_timer"):
            self._resize_timer = QTimer()
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(lambda: None)
        self._resize_timer.start(100)

    # === BaseTab Impl ===
    def browse_files(self): self._browse_files_logic()
    def browse_directory(self): self.browse_scan_directory()
    def browse_input(self): self._browse_files_logic()
    def browse_output(self): pass
