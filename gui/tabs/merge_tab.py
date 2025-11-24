import os

from pathlib import Path
from typing import Dict, Any, Optional
from PySide6.QtGui import QPixmap, QAction
from PySide6.QtCore import Qt, QTimer, QThread, Slot, QPoint, QEventLoop
from PySide6.QtWidgets import (
    QMenu, QProgressDialog, QFormLayout,
    QComboBox, QSpinBox, QGroupBox, QHBoxLayout,
    QVBoxLayout, QMessageBox, QGridLayout, QScrollArea,
    QLineEdit, QFileDialog, QWidget, QLabel, QPushButton,
)
from ..classes import AbstractClassTwoGalleries
from ..windows import ImagePreviewWindow
from ..components import ClickableLabel, MarqueeScrollArea
from ..helpers import MergeWorker, ImageScannerWorker
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS
from ..styles.style import apply_shadow_effect, SHARED_BUTTON_STYLE


class MergeTab(AbstractClassTwoGalleries):
    """
    GUI tab for merging images, now structured with a clear 'Merge Targets' section.
    Inherits core gallery and threading logic from BaseTwoGalleriesTab.
    """
    def __init__(self, dropdown=True):
        super().__init__()
        self.dropdown = dropdown
        self.thumbnail_size = 150 

        # --- State ---
        self.scanned_dir: str | None = None
        self.open_preview_windows: list[ImagePreviewWindow] = [] 
        
        self.current_scan_thread: QThread | None = None
        self.current_scan_worker: ImageScannerWorker | None = None
        self.current_merge_thread: QThread | None = None
        self.current_merge_worker: MergeWorker | None = None

        # --- UI Setup ---
        main_layout = QVBoxLayout(self)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")

        scroll_content = QWidget()
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # === 1. Merge Targets Group ===
        target_group = QGroupBox("Merge Targets")
        target_layout = QFormLayout(target_group)
        v_input_group = QVBoxLayout()

        scan_dir_layout = QHBoxLayout()
        self.scan_directory_path = QLineEdit() 
        self.scan_directory_path.setPlaceholderText("Path to directory containing images for merging...")
        self.scan_directory_path.returnPressed.connect(self.handle_scan_directory_return)
        
        btn_browse_scan = QPushButton("Browse...")
        btn_browse_scan.clicked.connect(self.browse_and_scan_directory)
        apply_shadow_effect(btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3)

        scan_dir_layout.addWidget(self.scan_directory_path)
        scan_dir_layout.addWidget(btn_browse_scan)
        
        v_input_group.addLayout(scan_dir_layout)
        
        target_layout.addRow("Input path:", v_input_group)
        content_layout.addWidget(target_group)
        
        # === 2. Merge Settings ===
        config_group = QGroupBox("Merge Settings")
        config_layout = QFormLayout(config_group)

        self.direction = QComboBox()
        # ADDED "panorama" option here
        self.direction.addItems(["horizontal", "vertical", "grid", "panorama", "stitch"])
        self.direction.currentTextChanged.connect(self.handle_direction_change)
        config_layout.addRow("Direction:", self.direction)

        # Spacing and Align are grouped so they can be hidden for panorama
        self.lbl_spacing = QLabel("Spacing (px):")
        self.spacing = QSpinBox()
        self.spacing.setRange(0, 1000)
        self.spacing.setValue(10)
        config_layout.addRow(self.lbl_spacing, self.spacing)

        self.lbl_align = QLabel("Alignment/Resize:")
        self.align_mode = QComboBox()
        self.align_mode.addItems([
            "Default (Top/Center)", "Align Top/Left", "Align Bottom/Right", 
            "Center", "Scaled (Grow Smallest)", "Squish (Shrink Largest)"
        ])
        config_layout.addRow(self.lbl_align, self.align_mode)

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

        # === 3. Galleries ===
        
        self.selection_label = QLabel("0 images selected.")
        self.selection_label.setStyleSheet("padding: 5px 0; font-weight: bold;")
        content_layout.addWidget(self.selection_label)

        self.found_gallery_scroll = MarqueeScrollArea()
        self.found_gallery_scroll.setWidgetResizable(True)
        self.found_gallery_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.found_gallery_scroll.setMinimumHeight(600)
        
        self.found_thumbnail_widget = QWidget()
        self.found_thumbnail_widget.setStyleSheet("background-color: #2c2f33;")
        self.found_gallery_layout = QGridLayout(self.found_thumbnail_widget)
        self.found_gallery_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.found_gallery_scroll.setWidget(self.found_thumbnail_widget)
        self.found_gallery_scroll.selection_changed.connect(self.handle_marquee_selection)
        content_layout.addWidget(self.found_gallery_scroll, 1)

        self.selected_gallery_scroll = MarqueeScrollArea()
        self.selected_gallery_scroll.setWidgetResizable(True)
        self.selected_gallery_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.selected_gallery_scroll.setMinimumHeight(400)
        
        self.selected_images_widget = QWidget()
        self.selected_images_widget.setStyleSheet("background-color: #2c2f33;")
        self.selected_gallery_layout = QGridLayout(self.selected_images_widget)
        self.selected_gallery_layout.setSpacing(10)
        self.selected_gallery_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        
        self.selected_gallery_scroll.setWidget(self.selected_images_widget)
        content_layout.addWidget(self.selected_gallery_scroll, 1)

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        # === 4. Action Buttons ===
        action_vbox = QVBoxLayout()
        self.run_button = QPushButton("Run Merge")
        self.run_button.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(self.run_button, "#000000", 8, 0, 3)
        self.run_button.clicked.connect(self.start_merge)
        action_vbox.addWidget(self.run_button)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #b9bbbe; font-style: italic; padding: 10px;")
        action_vbox.addWidget(self.status_label)
        main_layout.addLayout(action_vbox)

        self.on_selection_changed()
        self.handle_direction_change(self.direction.currentText())
        self.clear_galleries()

    # --- IMPLEMENTING ABSTRACT METHODS ---
    def create_card_widget(self, path: str, pixmap: Optional[QPixmap], is_selected: bool) -> QWidget:
        thumb_size = self.thumbnail_size
        clickable_label = ClickableLabel(path) 
        clickable_label.setFixedSize(thumb_size + 10, thumb_size + 10)
        
        clickable_label.get_pixmap = lambda: img_label.pixmap()
        clickable_label.set_selected_style = lambda s: self._update_label_style(img_label, path, s)

        layout = QVBoxLayout(clickable_label)
        layout.setContentsMargins(0, 0, 0, 0)
        
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignCenter)
        img_label.setFixedSize(thumb_size, thumb_size)
        layout.addWidget(img_label)

        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(thumb_size, thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            img_label.setPixmap(scaled)
        else:
            img_label.setText("Error")
            img_label.setStyleSheet("color: #e74c3c; border: 1px solid #e74c3c;")

        self._update_label_style(img_label, path, is_selected)

        clickable_label.path_double_clicked.connect(self.handle_full_image_preview)
        clickable_label.path_right_clicked.connect(self.show_image_context_menu)
        
        return clickable_label

    def _update_label_style(self, label: QLabel, path: str, selected: bool):
        is_error = label.text() == "Error"
        if selected:
            if is_error:
                label.setStyleSheet("border: 3px solid #5865f2; background-color: #4f545c;")
            else:
                label.setStyleSheet("border: 3px solid #5865f2;")
        else:
            if is_error:
                label.setStyleSheet("border: 1px solid #e74c3c; background-color: #4f545c;")
            else:
                label.setStyleSheet("border: 1px solid #4f545c;")

    def on_selection_changed(self):
        count = len(self.selected_files)
        self.selection_label.setText(f"{count} images selected.")
        if count < 2:
            self.run_button.setEnabled(False)
            self.run_button.setText("Run Merge (Select 2+ images)")
        else:
            self.run_button.setEnabled(True)
            self.run_button.setText(f"Run Merge ({count} images)")
        self.status_label.setText("" if count < 2 else f"Ready to merge {count} images.")

    # --- INPUT LOGIC ---
    @Slot()
    def handle_scan_directory_return(self):
        d = self.scan_directory_path.text().strip()
        if d and os.path.isdir(d):
            self.populate_scan_gallery(d)
        else:
            QMessageBox.warning(self, "Invalid Path", "The entered path is not a valid directory.")

    @Slot()
    def browse_and_scan_directory(self):
        d = QFileDialog.getExistingDirectory(self, "Select Directory to Scan", self.last_browsed_dir)
        if d:
            self.scan_directory_path.setText(d)
            self.last_browsed_dir = d
            self.populate_scan_gallery(d)
            
    def populate_scan_gallery(self, directory: str):
        self.scanned_dir = directory
        if self.current_scan_thread and self.current_scan_thread.isRunning():
            self.current_scan_thread.quit()
            self.current_scan_thread.wait(2000)
            
        self.cancel_loading()
        
        self.loading_dialog = QProgressDialog("Scanning directory...", "Cancel", 0, 0, self)
        self.loading_dialog.setWindowModality(Qt.WindowModal)
        self.loading_dialog.setWindowTitle("Please Wait")
        self.loading_dialog.setMinimumDuration(0)
        self.loading_dialog.canceled.connect(self.cancel_loading) 
        self.loading_dialog.show()
        
        loop = QEventLoop()
        QTimer.singleShot(1, loop.quit)
        loop.exec()
        
        worker = ImageScannerWorker(directory)
        thread = QThread()
        
        self.current_scan_worker = worker
        self.current_scan_thread = thread
        worker.moveToThread(thread)

        thread.started.connect(worker.run_scan)
        worker.scan_finished.connect(self.on_scan_finished)
        worker.scan_finished.connect(thread.quit)
        thread.finished.connect(self.cleanup_scan_thread_ref)
        thread.start()

    @Slot()
    def cleanup_scan_thread_ref(self):
        self.current_scan_thread = None
        self.current_scan_worker = None
        
    @Slot(list)
    def on_scan_finished(self, paths):
        if self.loading_dialog: self.loading_dialog.close()
        
        if not paths:
            QMessageBox.information(self, "No Files", f"No supported images found in {self.scanned_dir}")
            self.clear_galleries()
            return
            
        self.selected_files.clear()
        self.start_loading_thumbnails(sorted(paths))
        self.status_label.setText(f"Scan complete. Loaded {len(paths)} files.")

    # --- MERGING ---
    @Slot(str)
    def handle_full_image_preview(self, image_path: str):
        selected_paths_list = self.selected_files.copy() 
        try:
            start_index = selected_paths_list.index(image_path)
        except ValueError:
            selected_paths_list = [image_path]
            start_index = 0
            
        window = ImagePreviewWindow(
            image_path=image_path, 
            db_tab_ref=None, 
            parent=self,
            all_paths=selected_paths_list,
            start_index=start_index
        )
        window.setAttribute(Qt.WA_DeleteOnClose)
        
        def remove_closed_win(event: Any):
            if window in self.open_preview_windows:
                 self.open_preview_windows.remove(window)
            event.accept()

        window.closeEvent = remove_closed_win
        window.show()
        self.open_preview_windows.append(window)

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)
        view_action = QAction("View Full Size Preview", self)
        view_action.triggered.connect(lambda: self.handle_full_image_preview(path))
        menu.addAction(view_action)
        menu.addSeparator()

        is_selected = path in self.selected_files
        toggle_text = "Deselect Image (Remove from Merge List)" if is_selected else "Select Image (Add to Merge List)"
        toggle_action = QAction(toggle_text, self)
        toggle_action.triggered.connect(lambda: self.toggle_selection(path))
        menu.addAction(toggle_action)
        menu.exec(global_pos)
        
    def start_merge(self):
        if len(self.selected_files) < 2: 
            QMessageBox.warning(self, "Invalid", "Select at least 2 images.")
            return
        
        out, _ = QFileDialog.getSaveFileName(self, "Save Merged Image", self.last_browsed_dir, "PNG (*.png)")
        if not out: 
            self.status_label.setText("Cancelled.")
            return
        if not out.lower().endswith('.png'): out += '.png'
        
        self.last_browsed_dir = os.path.dirname(out)
        self.run_button.setEnabled(False)
        self.run_button.setText("Merging...")
        
        worker = MergeWorker(self.collect(out))
        thread = QThread()
        self.current_merge_worker = worker
        self.current_merge_thread = thread
        worker.moveToThread(thread)
        
        thread.started.connect(worker.run)
        worker.progress.connect(lambda c, t: self.status_label.setText(f"Merging {c}/{t}"))
        worker.finished.connect(self.on_merge_done)
        worker.error.connect(self.on_merge_error)
        
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def on_merge_done(self, path):
        self.on_selection_changed()
        self.status_label.setText("Done.")
        QMessageBox.information(self, "Success", f"Saved to {path}")

    def on_merge_error(self, msg):
        self.on_selection_changed()
        self.status_label.setText("Failed.")
        QMessageBox.critical(self, "Error", msg)

    def collect(self, output_path: str) -> Dict[str, Any]:
        return {
            "direction": self.direction.currentText(),
            "input_path": self.selected_files,
            "output_path": output_path,
            "input_formats": [f.strip().lstrip('.') for f in SUPPORTED_IMG_FORMATS if f.strip()],
            "spacing": self.spacing.value(),
            "align_mode": self.align_mode.currentText(),
            "grid_size": (self.grid_rows.value(), self.grid_cols.value())
            if self.direction.currentText() == "grid" else None
        }

    def handle_direction_change(self, direction):
        # Update visibility of settings based on direction
        is_grid = direction == "grid"
        is_complex_stitch = direction in ["panorama", "stitch"]
        
        self.grid_group.setVisible(is_grid)
        
        self.lbl_spacing.setVisible(not is_complex_stitch)
        self.spacing.setVisible(not is_complex_stitch)
        self.lbl_align.setVisible(not is_complex_stitch)
        self.align_mode.setVisible(not is_complex_stitch)
    
    def get_default_config(self) -> dict:
        return {
            "direction": "horizontal",
            "spacing": 10,
            "grid_size": [2, 2], 
            "scan_directory": "C:/path/to/images",
            "align_mode": "Default (Top/Center)"
        }

    def set_config(self, config: dict):
        try:
            direction = config.get("direction", "horizontal")
            if self.direction.findText(direction) != -1:
                self.direction.setCurrentText(direction)
            
            self.spacing.setValue(config.get("spacing", 10))

            align_mode = config.get("align_mode", "Default (Top/Center)")
            if self.align_mode.findText(align_mode) != -1:
                self.align_mode.setCurrentText(align_mode)
            
            grid_size = config.get("grid_size", [2, 2])
            if isinstance(grid_size, list) and len(grid_size) == 2:
                self.grid_rows.setValue(grid_size[0])
                self.grid_cols.setValue(grid_size[1])

            scan_dir = config.get("scan_directory")
            if scan_dir:
                self.scan_directory_path.setText(scan_dir)
                if os.path.isdir(scan_dir):
                    self.populate_scan_gallery(scan_dir)
            
            print(f"MergeTab configuration loaded.")
            
        except Exception as e:
            print(f"Error applying MergeTab config: {e}")
            QMessageBox.warning(self, "Config Error", f"Failed to apply some settings: {e}")
