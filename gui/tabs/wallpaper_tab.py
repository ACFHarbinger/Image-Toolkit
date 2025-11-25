import os
import platform
import subprocess

from pathlib import Path
from screeninfo import get_monitors, Monitor
from typing import Dict, List, Optional, Tuple, Any
from PySide6.QtGui import QPixmap, QAction, QColor
from PySide6.QtCore import (
    Qt, QThreadPool, QThread,
    QTimer, Slot, QPoint, QEventLoop,
) 
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, 
    QGroupBox, QComboBox, QMenu,
    QWidget, QLabel, QPushButton, 
    QGridLayout, QSpinBox, QCheckBox,
    QLineEdit, QFileDialog, QScrollArea, 
    QMessageBox, QApplication, QColorDialog,
    QProgressDialog
)
from ..classes import AbstractClassSingleGallery
from ..windows import SlideshowQueueWindow, ImagePreviewWindow
from ..helpers import ImageScannerWorker, WallpaperWorker
from ..components import MonitorDropWidget, DraggableImageLabel, MarqueeScrollArea
from ..styles.style import apply_shadow_effect, STYLE_START_ACTION, STYLE_STOP_ACTION
from backend.src.utils.definitions import WALLPAPER_STYLES
from backend.src.core import WallpaperManager


class WallpaperTab(AbstractClassSingleGallery):
    
    @Slot()
    def _is_slideshow_validation_ready(self) -> Tuple[bool, int]:
        monitor_ids = list(self.monitor_widgets.keys())
        if not monitor_ids: return False, 0
        total_images = 0
        all_queues_empty = True
        for mid in monitor_ids:
            queue_len = len(self.monitor_slideshow_queues.get(mid, []))
            if queue_len > 0: all_queues_empty = False
            total_images += queue_len 
        return not all_queues_empty, total_images

    @Slot()
    def check_all_monitors_set(self):
        if self.slideshow_timer and self.slideshow_timer.isActive(): return
        if self.current_wallpaper_worker: return
        self.set_wallpaper_btn.setStyleSheet(STYLE_START_ACTION)
        target_monitor_ids = list(self.monitor_widgets.keys())
        num_monitors = len(target_monitor_ids)
        set_count = sum(1 for mid in target_monitor_ids if mid in self.monitor_image_paths and self.monitor_image_paths[mid])
        is_ready, total_images = self._is_slideshow_validation_ready()

        if self.background_type == "Solid Color":
            self.set_wallpaper_btn.setText(f"Set Solid Color ({self.solid_color_hex})")
            self.set_wallpaper_btn.setEnabled(num_monitors > 0)
            return

        if self.slideshow_enabled_checkbox.isChecked():
            if is_ready:
                self.set_wallpaper_btn.setEnabled(True)
                self.set_wallpaper_btn.setText(f"Start Slideshow ({total_images} total images)")
            else:
                self.set_wallpaper_btn.setEnabled(False)
                self.set_wallpaper_btn.setText("Slideshow (Drop images)")
        elif set_count > 0: 
            self.set_wallpaper_btn.setText("Set Wallpaper")
            self.set_wallpaper_btn.setEnabled(True)
        else:
            self.set_wallpaper_btn.setText("Set Wallpaper (0 images)")
            self.set_wallpaper_btn.setEnabled(False)

    def __init__(self, db_tab_ref, dropdown=True):
        # Initialize Base Class
        super().__init__()    
        self.db_tab_ref = db_tab_ref
        if os.environ.get("DESKTOP_SESSION").lower() in ["plasma", "kde"]:
            try:
                subprocess.run(["which", "qdbus6"], check=True, capture_output=True)
                self.qdbus = "qdbus6"
            except (FileNotFoundError, subprocess.CalledProcessError):
                try:
                    subprocess.run(["which", "qdbus"], check=True, capture_output=True)
                    self.qdbus = "qdbus"
                except (FileNotFoundError, subprocess.CalledProcessError):
                    QMessageBox.warning(self, "System Error", "You need qdbus configured on KDE Plasma to access wallpaper functionality.")
        else:
            self.qdbus = None

        self.monitors: List[Monitor] = []
        self.monitor_widgets: Dict[str, MonitorDropWidget] = {}
        
        self.monitor_image_paths: Dict[str, str] = {}
        self.monitor_slideshow_queues: Dict[str, List[str]] = {} 
        self.monitor_current_index: Dict[str, int] = {}
        
        self.current_wallpaper_worker: Optional[WallpaperWorker] = None
        
        self.slideshow_timer: Optional[QTimer] = None
        self.countdown_timer: Optional[QTimer] = None
        self.time_remaining_sec: int = 0
        self.interval_sec: int = 0
        self.open_queue_windows: List[QWidget] = [] 
        self.open_image_preview_windows: List[QWidget] = [] 
        
        self.wallpaper_style: str = "Fill" 
        self.background_type: str = "Image" 
        self.solid_color_hex: str = "#000000" 

        # --- Scanner References ---
        self.scanner_worker: Optional[Any] = None
        self.scanner_thread: Optional[QThread] = None
        self.scan_dialog: Optional[QProgressDialog] = None
        # --------------------------
        
        # --- UI SETUP ---
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        main_scroll_area = QScrollArea()
        main_scroll_area.setWidgetResizable(True)
        main_scroll_area.setWidget(content_widget)
        
        main_tab_layout = QVBoxLayout(self)
        main_tab_layout.setContentsMargins(0, 0, 0, 0) 
        main_tab_layout.addWidget(main_scroll_area)
        self.setLayout(main_tab_layout) 
        
        group_box_style = """
            QGroupBox {  
                border: 1px solid #4f545c; 
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title { 
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 10px;
                color: white;
                border-radius: 4px;
            }
        """
        
        # Monitor Layout Group
        layout_group = QGroupBox("Monitor Layout (Drop images here, double-click to see queue)")
        layout_group.setStyleSheet(group_box_style)
        
        self.monitor_layout_container = QWidget()
        self.monitor_layout = QHBoxLayout(self.monitor_layout_container)
        self.monitor_layout.setSpacing(15)
        self.monitor_layout.setAlignment(Qt.AlignCenter)
        
        layout_group.setLayout(self.monitor_layout)
        content_layout.addWidget(layout_group) 

        # Slideshow Controls Group
        self.slideshow_group = QGroupBox("Slideshow Settings (Per-Monitor Cycle)")
        self.slideshow_group.setStyleSheet(group_box_style)
        slideshow_layout = QHBoxLayout(self.slideshow_group)
        slideshow_layout.setContentsMargins(10, 20, 10, 10)

        self.slideshow_enabled_checkbox = QCheckBox("Enable Slideshow")
        self.slideshow_enabled_checkbox.setToolTip("Cycles through dropped images on each monitor.")
        slideshow_layout.addWidget(self.slideshow_enabled_checkbox)

        slideshow_layout.addWidget(QLabel("Interval:"))
        
        self.interval_min_spinbox = QSpinBox()
        self.interval_min_spinbox.setRange(0, 60)
        self.interval_min_spinbox.setValue(5)
        self.interval_min_spinbox.setFixedWidth(50)
        slideshow_layout.addWidget(self.interval_min_spinbox)
        slideshow_layout.addWidget(QLabel("min"))

        self.interval_sec_spinbox = QSpinBox()
        self.interval_sec_spinbox.setRange(0, 59)
        self.interval_sec_spinbox.setValue(0) 
        self.interval_sec_spinbox.setFixedWidth(50)
        slideshow_layout.addWidget(self.interval_sec_spinbox)
        slideshow_layout.addWidget(QLabel("sec"))

        slideshow_layout.addStretch(1)
        
        self.countdown_label = QLabel("Timer: --:--")
        self.countdown_label.setStyleSheet("color: #2ecc71; font-weight: bold; font-size: 14px;")
        self.countdown_label.setFixedWidth(100)
        slideshow_layout.addWidget(self.countdown_label)

        content_layout.addWidget(self.slideshow_group) 

        # Combined Settings Group
        settings_group = QGroupBox("Wallpaper Settings")
        settings_group.setStyleSheet(group_box_style)
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setContentsMargins(10, 20, 10, 10)
        
        background_type_layout = QHBoxLayout()
        self.background_type_combo = QComboBox()
        self.background_type_combo.addItems(["Image", "Solid Color"])
        self.background_type_combo.setCurrentText(self.background_type)
        self.background_type_combo.currentTextChanged.connect(self._update_background_type)

        background_type_layout.addWidget(QLabel("Background Type:"))
        background_type_layout.addWidget(self.background_type_combo)
        background_type_layout.addStretch(1)
        settings_layout.addLayout(background_type_layout)

        self.solid_color_widget = QWidget()
        self.solid_color_layout = QHBoxLayout(self.solid_color_widget)
        self.solid_color_layout.setContentsMargins(0, 0, 0, 0)
        
        self.solid_color_preview = QLabel(" ")
        self.solid_color_preview.setFixedSize(20, 20)
        self.solid_color_preview.setStyleSheet(f"background-color: {self.solid_color_hex}; border: 1px solid #4f545c;")
        
        btn_select_color = QPushButton("Select Color...")
        btn_select_color.clicked.connect(self.select_solid_color)
        
        self.solid_color_layout.addWidget(QLabel("Color:"))
        self.solid_color_layout.addWidget(self.solid_color_preview)
        self.solid_color_layout.addWidget(btn_select_color)
        self.solid_color_layout.addStretch(1)
        
        settings_layout.addWidget(self.solid_color_widget)
        self.solid_color_widget.setVisible(False) 

        style_layout = QHBoxLayout()
        self.style_combo = QComboBox()
        self.style_combo.setStyleSheet("QComboBox { padding: 5px; border-radius: 4px; }")
        
        initial_styles = self._get_relevant_styles()
        self.style_combo.addItems(initial_styles.keys())
        self.style_combo.setCurrentText(list(initial_styles.keys())[0])
        self.wallpaper_style = list(initial_styles.keys())[0]
        
        self.style_combo.currentTextChanged.connect(self._update_wallpaper_style)

        style_layout.addWidget(QLabel("Image Style:"))
        style_layout.addWidget(self.style_combo)
        style_layout.addStretch(1)
        settings_layout.addLayout(style_layout)
        
        settings_layout.addWidget(QLabel("<hr>")) 

        settings_layout.addWidget(QLabel("Scan Directory (Image Source):"))
        scan_dir_layout = QHBoxLayout()
        self.scan_directory_path = QLineEdit()
        self.scan_directory_path.setPlaceholderText("Select directory to scan...")
        btn_browse_scan = QPushButton("Browse...")
        btn_browse_scan.clicked.connect(self.browse_scan_directory)
        apply_shadow_effect(btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3)

        scan_dir_layout.addWidget(self.scan_directory_path)
        scan_dir_layout.addWidget(btn_browse_scan)
        settings_layout.addLayout(scan_dir_layout)
        
        content_layout.addWidget(settings_group) 

        # --- Gallery Setup for Base Class ---
        self.scan_scroll_area = MarqueeScrollArea() 
        self.scan_scroll_area.setWidgetResizable(True)
        self.scan_scroll_area.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")
        self.scan_scroll_area.setMinimumHeight(600) 

        self.scan_thumbnail_widget = QWidget()
        self.scan_thumbnail_widget.setStyleSheet("QWidget { background-color: #2c2f33; }")

        self.scan_thumbnail_layout = QGridLayout(self.scan_thumbnail_widget)
        self.scan_thumbnail_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.scan_scroll_area.setWidget(self.scan_thumbnail_widget)
        
        content_layout.addWidget(self.scan_scroll_area, 1) 
        
        # **Assign Base Class References**
        self.gallery_scroll_area = self.scan_scroll_area
        self.gallery_layout = self.scan_thumbnail_layout

        # Action Buttons
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)
        
        self.set_wallpaper_btn = QPushButton("Set Wallpaper")
        self.set_wallpaper_btn.setStyleSheet(STYLE_START_ACTION)
        apply_shadow_effect(self.set_wallpaper_btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.set_wallpaper_btn.clicked.connect(self.handle_set_wallpaper_click)
        action_layout.addWidget(self.set_wallpaper_btn, 1) 
        
        content_layout.addLayout(action_layout) 

        # State for scanner
        self.scanned_dir = None
        self.path_to_label_map = {}
        
        # NOTE: self.loading_dialog is provided by BaseSingleGalleryTab. 
        # We need a separate reference for the *Scanning* dialog or reuse it carefully.
        
        # Initial setup
        self.populate_monitor_layout()
        self.check_all_monitors_set()
        self.stop_slideshow()
        
    # --- IMPLEMENT ABSTRACT METHOD ---

    def create_card_widget(self, path: str, pixmap: Optional[QPixmap]) -> QWidget:
        """
        Creates a DraggableImageLabel for the Wallpaper Tab gallery.
        """
        draggable_label = DraggableImageLabel(path, self.thumbnail_size)
        
        # Connect signals
        draggable_label.path_double_clicked.connect(self.handle_thumbnail_double_click)
        draggable_label.path_right_clicked.connect(self.show_image_context_menu)
        
        if pixmap and not pixmap.isNull():
            draggable_label.setPixmap(pixmap) 
            draggable_label.setText("") 
            draggable_label.setStyleSheet("border: 1px solid #4f545c;")
        else:
            draggable_label.setText("Load Error")
            draggable_label.setStyleSheet("border: 1px solid #e74c3c; background-color: #4f545c; font-size: 8px;")
            
        self.path_to_label_map[path] = draggable_label
        return draggable_label

    # --- Logic ---

    def _get_relevant_styles(self) -> Dict[str, str]:
        system = platform.system()
        if system == "Windows":
            return WALLPAPER_STYLES["Windows"]
        elif system == "Linux":
            try:
                subprocess.run(["which", self.qdbus], check=True, capture_output=True)
                return WALLPAPER_STYLES["KDE"]
            except (FileNotFoundError, subprocess.CalledProcessError):
                return WALLPAPER_STYLES["GNOME"]
            except:
                return {"Default (System)": None}
        else:
            return {"Default (System)": None}

    @Slot(str)
    def _update_wallpaper_style(self, style_name: str):
        self.wallpaper_style = style_name

    @Slot(str)
    def _update_background_type(self, type_name: str):
        self.background_type = type_name
        is_solid_color = (type_name == "Solid Color")
        self.solid_color_widget.setVisible(is_solid_color)
        style_enabled = not is_solid_color
        self.style_combo.setEnabled(style_enabled)
        self.scan_directory_path.setEnabled(style_enabled)
        self.scan_scroll_area.setEnabled(style_enabled)
        self.slideshow_group.setEnabled(style_enabled)
        if is_solid_color and self.slideshow_timer and self.slideshow_timer.isActive():
            self.stop_slideshow()
        self.check_all_monitors_set()

    @Slot()
    def select_solid_color(self):
        initial_color = QColor(self.solid_color_hex)
        color = QColorDialog.getColor(initial_color, self, "Select Solid Background Color")
        if color.isValid():
            self.solid_color_hex = color.name().upper()
            self.solid_color_preview.setStyleSheet(f"background-color: {self.solid_color_hex}; border: 1px solid #4f545c;")
            self.check_all_monitors_set()

    @Slot()
    def handle_set_wallpaper_click(self):
        if self.background_type == "Solid Color":
             if self.current_wallpaper_worker:
                self.stop_wallpaper_worker()
             else:
                self.run_wallpaper_worker()
             return

        if self.slideshow_timer and self.slideshow_timer.isActive():
            self.stop_slideshow()
        elif self.slideshow_enabled_checkbox.isChecked():
            self.start_slideshow()
        else:
            if self.current_wallpaper_worker:
                self.stop_wallpaper_worker()
            else:
                self.run_wallpaper_worker()

    @Slot()
    def start_slideshow(self):
        num_monitors = len(self.monitor_widgets)
        if self.background_type == "Solid Color":
            QMessageBox.warning(self, "Slideshow Error", "Slideshow is disabled when Solid Color mode is selected.")
            self.slideshow_enabled_checkbox.setChecked(False)
            return
        is_ready, total_images = self._is_slideshow_validation_ready()
        if num_monitors == 0:
            QMessageBox.warning(self, "Slideshow Error", "No monitors detected or configured.")
            self.slideshow_enabled_checkbox.setChecked(False)
            return
        if not is_ready:
            QMessageBox.critical(self, "Slideshow Error", "To start the slideshow, at least one monitor must have images dropped on it.")
            self.slideshow_enabled_checkbox.setChecked(False)
            return
        self.stop_slideshow() 
        for mid in self.monitor_widgets.keys(): self.monitor_current_index[mid] = -1 
        interval_minutes = self.interval_min_spinbox.value()
        interval_seconds = self.interval_sec_spinbox.value()
        self.interval_sec = (interval_minutes * 60) + interval_seconds
        if self.interval_sec <= 0:
            QMessageBox.critical(self, "Slideshow Error", "Slideshow interval must be greater than 0 seconds.")
            self.slideshow_enabled_checkbox.setChecked(False)
            return
        interval_ms = self.interval_sec * 1000
        self.time_remaining_sec = self.interval_sec
        self.slideshow_timer = QTimer(self)
        self.slideshow_timer.timeout.connect(self._cycle_slideshow_wallpaper)
        self.slideshow_timer.start(interval_ms)
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)
        QMessageBox.information(self, "Slideshow Started", 
                                f"Per-monitor slideshow started with {total_images} total images, cycling every {interval_minutes} minutes and {interval_seconds} seconds.")
        self._cycle_slideshow_wallpaper()
        self.set_wallpaper_btn.setText(f"Slideshow Running (Stop)")
        self.set_wallpaper_btn.setStyleSheet(STYLE_STOP_ACTION)
        self.set_wallpaper_btn.setEnabled(True)

    def update_countdown(self):
        if self.time_remaining_sec > 0:
            self.time_remaining_sec -= 1
            m, s = divmod(self.time_remaining_sec, 60)
            self.countdown_label.setText(f"Timer: {m:02}:{s:02}")
        else:
            self.time_remaining_sec = self.interval_sec 

    @Slot()
    def stop_slideshow(self):
        if self.slideshow_timer and self.slideshow_timer.isActive():
            self.slideshow_timer.stop()
            self.slideshow_timer.deleteLater()
            self.slideshow_timer = None
            QMessageBox.information(self, "Slideshow Stopped", "Wallpaper slideshow stopped.")
        
        if self.countdown_timer and self.countdown_timer.isActive():
            self.countdown_timer.stop()
            self.countdown_timer.deleteLater()
            self.countdown_timer = None

        self.stop_wallpaper_worker()

        for win in list(self.open_queue_windows):
            if win.isVisible(): win.close()
        self.open_queue_windows.clear()
        
        for win in list(self.open_image_preview_windows):
            if win.isVisible(): win.close()
        self.open_image_preview_windows.clear()
        
        self.monitor_current_index.clear()
        self.time_remaining_sec = 0
        self.countdown_label.setText("Timer: --:--")

        self.slideshow_enabled_checkbox.setChecked(False)
        self.unlock_ui_for_wallpaper()

    @Slot()
    def _cycle_slideshow_wallpaper(self):
        monitor_ids = list(self.monitor_widgets.keys())
        if not monitor_ids: return 
        if self.background_type == "Solid Color":
             self.stop_slideshow()
             return
        try:
            new_monitor_paths = {}
            has_valid_path_to_set = False
            for monitor_id in monitor_ids:
                current_index = self.monitor_current_index.get(monitor_id, -1)
                queue = self.monitor_slideshow_queues.get(monitor_id, [])
                current_queue_length = len(queue)
                if current_queue_length > 0:
                    next_index = (current_index + 1) % current_queue_length
                    path = queue[next_index]
                    new_monitor_paths[monitor_id] = path
                    self.monitor_current_index[monitor_id] = next_index
                    has_valid_path_to_set = True
                else:
                    new_monitor_paths[monitor_id] = self.monitor_image_paths.get(monitor_id)
                    self.monitor_current_index[monitor_id] = -1 
            if not has_valid_path_to_set:
                self.stop_slideshow()
                return
            self.monitor_image_paths = new_monitor_paths
            self.run_wallpaper_worker(slideshow_mode=True)
            for monitor_id, path in new_monitor_paths.items():
                if monitor_id in self.monitor_widgets and path:
                    self.monitor_widgets[monitor_id].set_image(path)
            self.time_remaining_sec = self.interval_sec
        except Exception as e:
            QMessageBox.critical(self, "Slideshow Cycle Error", f"Failed to cycle wallpaper: {str(e)}")
            self.stop_slideshow()
    
    @Slot(str)
    def handle_monitor_double_click(self, monitor_id: str):
        if self.background_type == "Solid Color": return
        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        monitor_name = self.monitor_widgets[monitor_id].monitor.name
        for win in self.open_queue_windows:
            if isinstance(win, SlideshowQueueWindow) and win.monitor_id == monitor_id:
                win.activateWindow()
                return
        window = SlideshowQueueWindow(monitor_name, monitor_id, queue)
        window.setAttribute(Qt.WA_DeleteOnClose)
        window.queue_reordered.connect(self.on_queue_reordered)
        window.image_preview_requested.connect(self.handle_full_image_preview)
        def remove_closed_win(event: Any):
            if window in self.open_queue_windows: self.open_queue_windows.remove(window)
            event.accept()
        window.closeEvent = remove_closed_win
        window.show()
        self.open_queue_windows.append(window)

    @Slot(str)
    def handle_full_image_preview(self, image_path: str):
        # Use gallery_image_paths from Base Class
        all_paths_list = sorted(self.gallery_image_paths) if self.gallery_image_paths else [image_path]
        try:
            start_index = all_paths_list.index(image_path)
        except ValueError:
            all_paths_list = [image_path]
            start_index = 0
            
        for win in list(self.open_image_preview_windows):
            if isinstance(win, ImagePreviewWindow) and win.image_path == image_path:
                win.activateWindow()
                return
        window = ImagePreviewWindow(
            image_path=image_path, db_tab_ref=None, parent=self, 
            all_paths=all_paths_list, start_index=start_index
        )
        window.setAttribute(Qt.WA_DeleteOnClose)
        def remove_closed_win(event: Any):
            if window in self.open_image_preview_windows: self.open_image_preview_windows.remove(window)
            event.accept()
        window.closeEvent = remove_closed_win
        window.show()
        self.open_image_preview_windows.append(window)

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        if self.background_type == "Solid Color": return
        menu = QMenu(self)
        view_action = QAction("View Full Size Preview", self)
        view_action.triggered.connect(lambda: self.handle_full_image_preview(path))
        menu.addAction(view_action)
        if self.monitor_widgets:
            menu.addSeparator()
            add_menu = menu.addMenu("Add to Monitor Queue")
            for monitor_id, widget in self.monitor_widgets.items():
                monitor_name = widget.monitor.name
                action = QAction(f"{monitor_name} (ID: {monitor_id})", self)
                action.triggered.connect(lambda checked, mid=monitor_id, img_path=path: self.on_image_dropped(mid, img_path))
                add_menu.addAction(action)
        menu.addSeparator()
        delete_action = QAction("🗑️ Delete Image File (Permanent)", self)
        delete_action.triggered.connect(lambda: self.handle_delete_image(path))
        menu.addAction(delete_action)
        menu.exec(global_pos)

    @Slot(str)
    def handle_delete_image(self, path: str):
        if not path or not Path(path).exists():
            QMessageBox.warning(self, "Delete Error", "File not found or path is invalid.")
            return
        filename = os.path.basename(path)
        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to PERMANENTLY delete the file:\n\n**{filename}**\n\nThis action cannot be undone!",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.No: return
        try:
            os.remove(path)
            
            # Remove from base list
            if path in self.gallery_image_paths:
                self.gallery_image_paths.remove(path)
            
            # Remove widget manually
            if path in self.path_to_label_map:
                widget = self.path_to_label_map.pop(path)
                widget.deleteLater()
            
            for mid in self.monitor_slideshow_queues:
                self.monitor_slideshow_queues[mid] = [p for p in self.monitor_slideshow_queues[mid] if p != path]
            for mid, current_path in self.monitor_image_paths.items():
                if current_path == path:
                    self.monitor_image_paths[mid] = None
                    self.monitor_widgets[mid].clear()
            
            self._reflow_layout(self._current_cols) # Base class method
            self.check_all_monitors_set()
            QMessageBox.information(self, "Success", f"File deleted successfully: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Deletion Failed", f"Could not delete the file: {e}")

    @Slot(str, list)
    def on_queue_reordered(self, monitor_id: str, new_queue: List[str]):
        self.monitor_slideshow_queues[monitor_id] = new_queue
        self.monitor_current_index[monitor_id] = -1 
        new_first_image = new_queue[0] if new_queue else None
        self.monitor_image_paths[monitor_id] = new_first_image
        if new_first_image and self.monitor_widgets[monitor_id].image_path != new_first_image:
            self.monitor_widgets[monitor_id].set_image(new_first_image)
        elif not new_first_image:
            self.monitor_widgets[monitor_id].clear() 
        self.check_all_monitors_set()
        
    @Slot(str)
    def handle_clear_monitor_queue(self, monitor_id: str):
        if monitor_id not in self.monitor_widgets: return
        monitor_name = self.monitor_widgets[monitor_id].monitor.name
        if monitor_id in self.monitor_slideshow_queues: self.monitor_slideshow_queues[monitor_id].clear()
        if monitor_id in self.monitor_image_paths: self.monitor_image_paths[monitor_id] = None
        if monitor_id in self.monitor_current_index: self.monitor_current_index[monitor_id] = -1
        
        system = platform.system()
        num_monitors_detected = len(self.monitors)
        current_system_wallpaper_paths = {}
        if system == "Linux" and num_monitors_detected > 0:
            try:
                subprocess.run(["which", self.qdbus], check=True, capture_output=True) 
                raw_paths = WallpaperManager.get_current_system_wallpaper_path_kde(num_monitors_detected, self.qdbus)
                current_system_wallpaper_paths = self._get_rotated_map_for_ui(raw_paths)
            except (FileNotFoundError, subprocess.CalledProcessError): pass 
            except Exception as e: print(f"KDE retrieval failed unexpectedly: {e}")
        
        system_wallpaper_path = current_system_wallpaper_paths.get(monitor_id)
        if system_wallpaper_path and Path(system_wallpaper_path).exists():
            self.monitor_widgets[monitor_id].set_image(system_wallpaper_path)
        else:
            self.monitor_widgets[monitor_id].clear() 
        self.check_all_monitors_set()
        QMessageBox.information(self, "Monitor Cleared", 
                                f"All pending images and the slideshow queue for **{monitor_name}** have been cleared.\n\nThe system's current background remains unchanged.")

    def _get_rotated_map_for_ui(self, source_paths: Dict[str, str]) -> Dict[str, str]:
        n = len(self.monitors)
        if n == 0: return {}
        rotated_map = {}
        for current_monitor_id_str in [str(i) for i in range(n)]:
            current_monitor_id = int(current_monitor_id_str)
            source_monitor_index = (current_monitor_id + 1) % n
            source_monitor_id_str = str(source_monitor_index)
            path_from_source = source_paths.get(source_monitor_id_str)
            rotated_map[current_monitor_id_str] = path_from_source
        return rotated_map
    
    def populate_monitor_layout(self):
        for i in reversed(range(self.monitor_layout.count())): 
            widget = self.monitor_layout.takeAt(i).widget()
            if widget is not None: widget.deleteLater()
        self.monitor_widgets.clear()
        try:
            system_monitors = get_monitors()
            physical_monitors = sorted(system_monitors, key=lambda m: m.x)
            self.monitors = system_monitors
        except Exception as e:
             QMessageBox.critical(self, "Error", f"Could not get monitor info: {e}")
             self.monitors = []
        if not self.monitors or "Mock" in self.monitors[0].name:
            self.monitor_layout.addWidget(QLabel("Could not detect any monitors.\nIs 'screeninfo' installed?"))
            return
        
        current_system_wallpaper_paths = {}
        system = platform.system()
        num_monitors_detected = len(self.monitors)
        if system == "Linux" and num_monitors_detected > 0:
            try:
                subprocess.run(["which", self.qdbus], check=True, capture_output=True) 
                raw_paths = WallpaperManager.get_current_system_wallpaper_path_kde(num_monitors_detected, self.qdbus)
                current_system_wallpaper_paths = self._get_rotated_map_for_ui(raw_paths)
            except (FileNotFoundError, subprocess.CalledProcessError): pass 
            except Exception as e: print(f"KDE retrieval failed unexpectedly: {e}")

        monitors_to_show = physical_monitors
        for monitor in monitors_to_show:
            system_index = -1
            for i, sys_mon in enumerate(system_monitors):
                if (sys_mon.x == monitor.x and sys_mon.y == monitor.y and
                    sys_mon.width == monitor.width and sys_mon.height == monitor.height):
                    system_index = i
                    break
            if system_index == -1: continue
            monitor_id = str(system_index) 
            drop_widget = MonitorDropWidget(monitor, monitor_id)
            drop_widget.image_dropped.connect(self.on_image_dropped)
            drop_widget.double_clicked.connect(self.handle_monitor_double_click)
            try: drop_widget.clear_requested_id.connect(self.handle_clear_monitor_queue)
            except AttributeError: pass
            
            current_image = self.monitor_image_paths.get(monitor_id)
            image_path_to_display = current_image
            if not image_path_to_display:
                system_wallpaper_path = current_system_wallpaper_paths.get(monitor_id)
                if system_wallpaper_path and Path(system_wallpaper_path).exists():
                    image_path_to_display = system_wallpaper_path
            if image_path_to_display: drop_widget.set_image(image_path_to_display)
            else: drop_widget.clear() 
            self.monitor_layout.addWidget(drop_widget)
            self.monitor_widgets[monitor_id] = drop_widget
        self.check_all_monitors_set()

    def on_image_dropped(self, monitor_id: str, image_path: str):
        if self.background_type != "Image": self.background_type_combo.setCurrentText("Image")
        if monitor_id not in self.monitor_slideshow_queues: self.monitor_slideshow_queues[monitor_id] = []
        if self.slideshow_enabled_checkbox.isChecked() or image_path not in self.monitor_slideshow_queues[monitor_id]:
            self.monitor_slideshow_queues[monitor_id].append(image_path)
        self.monitor_image_paths[monitor_id] = image_path
        self.monitor_current_index[monitor_id] = -1 
        self.monitor_widgets[monitor_id].set_image(image_path)
        self.check_all_monitors_set()
        
    def _get_gnome_assignment_map(self, source_paths: Dict[str, str]) -> Dict[str, str]:
        n = len(self.monitors)
        if n == 0: return {}
        rotated_map = {}
        for current_monitor_id_str in source_paths.keys():
            current_monitor_id = int(current_monitor_id_str)
            prev_monitor_index = (current_monitor_id - 1 + n) % n
            prev_monitor_id_str = str(prev_monitor_index)
            path_from_prev = source_paths.get(prev_monitor_id_str)
            rotated_map[current_monitor_id_str] = path_from_prev
        return rotated_map

    def _get_kde_assignment_map(self, source_paths: Dict[str, str]) -> Dict[str, str]:
        n = len(self.monitors)
        if n == 0: return {}
        rotated_map = {}
        for current_monitor_id_str in source_paths.keys():
            current_monitor_id = int(current_monitor_id_str)
            prev_monitor_index = (current_monitor_id - 1 + n) % n
            prev_monitor_id_str = str(prev_monitor_index)
            path_from_prev = source_paths.get(prev_monitor_id_str)
            rotated_map[current_monitor_id_str] = path_from_prev
        return rotated_map
    
    def _get_windows_assignment_map(self, source_paths: Dict[str, str]) -> Dict[str, str]:
        n = len(self.monitors)
        rotated_map = source_paths.copy()
        for current_monitor_id_str in source_paths.keys():
            current_monitor_id = int(current_monitor_id_str)
            prev_monitor_index = (current_monitor_id - 1 + n) % n
            prev_monitor_id_str = str(prev_monitor_index)
            rotated_map[current_monitor_id_str] = source_paths.get(prev_monitor_id_str)
        return rotated_map
    
    def _get_current_system_image_paths_for_all(self) -> Dict[str, Optional[str]]:
        system = platform.system()
        num_monitors = len(self.monitors)
        current_paths = {}
        if num_monitors == 0: return current_paths
        if system == "Linux":
            try:
                subprocess.run(["which", self.qdbus], check=True, capture_output=True) 
                raw_paths = WallpaperManager.get_current_system_wallpaper_path_kde(num_monitors, self.qdbus)
                current_paths = self._get_rotated_map_for_ui(raw_paths)
            except (FileNotFoundError, subprocess.CalledProcessError, Exception): pass 
        return current_paths
    
    def run_wallpaper_worker(self, slideshow_mode=False):
        if self.current_wallpaper_worker:
            print("Wallpaper worker is already running.")
            return

        if self.background_type == "Solid Color":
            path_map = {str(mid): self.solid_color_hex for mid in range(len(self.monitors))}
            style_to_use = "SolidColor"
            final_path_map = path_map 
        else:
            if not any(self.monitor_image_paths.values()):
                if not slideshow_mode:
                    QMessageBox.warning(self, "Incomplete", "No images have been dropped on the monitors.")
                return
            
            # Using imported helper
            if ImageScannerWorker is None:
                QMessageBox.warning(self, "Missing Helpers", "The ImageScannerWorker or ImageLoaderWorker could not be imported.")
                return

            if not slideshow_mode:
                current_system_paths = self._get_current_system_image_paths_for_all()
                path_map = current_system_paths.copy()
                for monitor_id in [str(i) for i in range(len(self.monitors))]:
                    user_path = self.monitor_image_paths.get(monitor_id)
                    if user_path: path_map[monitor_id] = user_path
                    elif monitor_id not in path_map:
                        widget = self.monitor_widgets.get(monitor_id)
                        if widget and widget.image_path: path_map[monitor_id] = widget.image_path
                        else: path_map[monitor_id] = None 
            else:
                path_map = self.monitor_image_paths.copy()

            system = platform.system()
            if system == "Linux":
                try:
                    subprocess.run(["which", self.qdbus], check=True, capture_output=True)
                    desktop = "KDE"
                except (FileNotFoundError, subprocess.CalledProcessError): desktop = "Gnome"
                except: desktop = None
            elif system == "Windows": desktop = "Windows"
            else: desktop = None
            
            if desktop == "Gnome": final_path_map = self._get_gnome_assignment_map(path_map)
            elif desktop == "KDE": final_path_map = self._get_kde_assignment_map(path_map)
            elif desktop == "Windows":
                if WallpaperManager.COM_AVAILABLE: final_path_map = self._get_windows_assignment_map(path_map)
                else:
                    path_to_set = next((p for p in path_map.values() if p), None)
                    final_path_map = {'0': path_to_set} if path_to_set else {}
            else: final_path_map = path_map
            style_to_use = self.wallpaper_style

        monitors = self.monitors
        if not slideshow_mode: self.lock_ui_for_wallpaper()
        
        self.current_wallpaper_worker = WallpaperWorker(final_path_map, monitors, self.qdbus, wallpaper_style=style_to_use)
        self.current_wallpaper_worker.signals.status_update.connect(self.handle_wallpaper_status)
        self.current_wallpaper_worker.signals.work_finished.connect(self.handle_wallpaper_finished)
        self.current_wallpaper_worker.signals.work_finished.connect(lambda: setattr(self, 'current_wallpaper_worker', None))
        QThreadPool.globalInstance().start(self.current_wallpaper_worker)

    def stop_wallpaper_worker(self):
        if self.current_wallpaper_worker:
            self.current_wallpaper_worker.stop()
            self.handle_wallpaper_status("Manual stop requested.")
            self.unlock_ui_for_wallpaper()
            self.current_wallpaper_worker = None

    def lock_ui_for_wallpaper(self):
        self.set_wallpaper_btn.setText("Applying (Click to Stop)")
        self.set_wallpaper_btn.setStyleSheet(STYLE_STOP_ACTION)
        self.set_wallpaper_btn.setEnabled(True)
        self.slideshow_group.setEnabled(False) 
        self.scan_scroll_area.setEnabled(False)
        self.scan_directory_path.setEnabled(False) 
        self.style_combo.setEnabled(False)
        self.background_type_combo.setEnabled(False) 
        self.solid_color_widget.setEnabled(False)    
        for widget in self.monitor_widgets.values(): widget.setEnabled(False)
        QApplication.processEvents()
        
    def unlock_ui_for_wallpaper(self):
        self.set_wallpaper_btn.setText("Set Wallpaper")
        self.set_wallpaper_btn.setStyleSheet(STYLE_START_ACTION)
        self.slideshow_group.setEnabled(True)
        self.scan_scroll_area.setEnabled(True)
        self.scan_directory_path.setEnabled(True)
        self.style_combo.setEnabled(True)
        self.background_type_combo.setEnabled(True) 
        self.solid_color_widget.setEnabled(True) 
        for widget in self.monitor_widgets.values(): widget.setEnabled(True)
        self._update_background_type(self.background_type)
        self.check_all_monitors_set()
        QApplication.processEvents()

    @Slot(str)
    def handle_wallpaper_status(self, msg: str):
        print(f"[WallpaperWorker] {msg}")

    @Slot(bool, str)
    def handle_wallpaper_finished(self, success: bool, message: str):
        is_slideshow_active = (self.slideshow_timer and self.slideshow_timer.isActive())
        if success:
            if not is_slideshow_active and self.background_type != "Solid Color":
                QMessageBox.information(self, "Success", "Wallpaper has been updated!")
                for monitor_id, path in self.monitor_image_paths.items():
                    if path and monitor_id in self.monitor_widgets:
                        self.monitor_widgets[monitor_id].set_image(path)
            elif self.background_type == "Solid Color":
                QMessageBox.information(self, "Success", f"Solid color background set to {self.solid_color_hex}!")
        else:
            if "manually cancelled" not in message.lower():
                if is_slideshow_active:
                    print(f"Slideshow Error: Failed to set wallpaper: {message}")
                    self.stop_slideshow()
                else:
                    QMessageBox.critical(self, "Error", f"Failed to set wallpaper:\n{message}")
        if not is_slideshow_active: self.unlock_ui_for_wallpaper()
        
    def browse_scan_directory(self):
        if self.background_type == "Solid Color":
            QMessageBox.warning(self, "Mode Conflict", "Cannot browse directory while Solid Color background is selected.")
            return

        if ImageScannerWorker is None:
            QMessageBox.warning(self, "Missing Helpers", "The ImageScannerWorker or ImageLoaderWorker could not be imported.")
            return
            
        start_dir = self.last_browsed_scan_dir
        options = QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        directory = QFileDialog.getExistingDirectory(self, "Select directory to scan", start_dir, options)
        
        if directory:
            self.last_browsed_scan_dir = directory
            self.scan_directory_path.setText(directory)
            self.populate_scan_image_gallery(directory)

    def populate_scan_image_gallery(self, directory: str):
        if self.background_type == "Solid Color": return 

        self.scanned_dir = directory
        
        # We need a separate dialog for the "Scanning" phase (before loading)
        self.scan_dialog = QProgressDialog("Scanning directory...", "Cancel", 0, 0, self)
        self.scan_dialog.setWindowModality(Qt.WindowModal)
        self.scan_dialog.setWindowTitle("Please Wait")
        self.scan_dialog.setMinimumDuration(0) 
        self.scan_dialog.canceled.connect(self.cancel_scanning) 
        self.scan_dialog.show()
        
        # Ensure dialog visibility
        loop = QEventLoop()
        QTimer.singleShot(1, loop.quit)
        loop.exec()

        self.scanner_worker = ImageScannerWorker(directory)
        
        # --- FIX: Ensure the thread is set and connected for clean up ---
        if self.scanner_thread and self.scanner_thread.isRunning():
             self.scanner_thread.quit()
             self.scanner_thread.wait() # Wait for the old thread to finish
             self.scanner_thread.deleteLater()
             self.scanner_thread = None

        self.scanner_thread = QThread() 
        self.scanner_worker.moveToThread(self.scanner_thread) 
        
        self.scanner_thread.started.connect(self.scanner_worker.run_scan)
        self.scanner_worker.scan_finished.connect(self.display_scan_results)
        self.scanner_worker.scan_error.connect(self.handle_scan_error)
        
        self.scanner_worker.scan_finished.connect(self.scanner_thread.quit)
        self.scanner_worker.scan_finished.connect(self.scanner_worker.deleteLater)
        self.scanner_thread.finished.connect(self.scanner_thread.deleteLater)
        
        # Clear thread reference when finished/deleted
        self.scanner_thread.finished.connect(lambda: setattr(self, 'scanner_thread', None))
        
        self.scanner_thread.start()

    def cancel_scanning(self):
        # Specific cancellation for the scanner thread
        if self.scanner_thread is not None and self.scanner_thread.isRunning():
            self.scanner_thread.quit()
            # The finished signal will trigger deleteLater and set the reference to None.
            
        if self.scan_dialog:
            self.scan_dialog.close()

    @Slot(list)
    def display_scan_results(self, image_paths: list[str]):
        if self.scan_dialog: self.scan_dialog.close()
        
        if self.background_type == "Solid Color": return 

        self.clear_gallery_widgets() 
        self.path_to_label_map.clear()
        
        self.check_all_monitors_set() 
        
        if not image_paths:
            self.show_placeholder("No supported images found.")
            return
        
        # Hand over to Base Class to load the images
        self.start_loading_gallery(image_paths)

    @Slot(str)
    def handle_thumbnail_double_click(self, image_path: str):
        self.handle_full_image_preview(image_path)

    def handle_scan_error(self, message: str):
        if self.scan_dialog: self.scan_dialog.close()
        self.clear_gallery_widgets()
        QMessageBox.warning(self, "Error Scanning", message)
        self.show_placeholder("Browse for a directory.")

    def collect(self) -> dict:
        return {
            "monitor_queues": self.monitor_slideshow_queues,
            "wallpaper_style": self.wallpaper_style,
            "background_type": self.background_type, 
            "solid_color_hex": self.solid_color_hex, 
        }

    def get_default_config(self) -> Dict[str, Any]:
        default_style = self.style_combo.itemText(0) if self.style_combo.count() > 0 else "Fill"
        return {
            "scan_directory": "",
            "wallpaper_style": default_style,
            "slideshow_enabled": False,
            "interval_minutes": 5,
            "interval_seconds": 0,
            "background_type": "Image", 
            "solid_color_hex": "#000000" 
        }
    
    def set_config(self, config: Dict[str, Any]):
        try:
            if "scan_directory" in config:
                self.scan_directory_path.setText(config.get("scan_directory", ""))
                if os.path.isdir(config["scan_directory"]):
                    self.populate_scan_image_gallery(config["scan_directory"])
            if "wallpaper_style" in config:
                self.style_combo.setCurrentText(config.get("wallpaper_style", "Fill"))
            if "slideshow_enabled" in config:
                self.slideshow_enabled_checkbox.setChecked(config.get("slideshow_enabled", False))
            if "interval_minutes" in config:
                self.interval_min_spinbox.setValue(config.get("interval_minutes", 5))
            if "interval_seconds" in config:
                self.interval_sec_spinbox.setValue(config.get("interval_seconds", 0))
            if "solid_color_hex" in config:
                self.solid_color_hex = config.get("solid_color_hex", "#000000")
                self.solid_color_preview.setStyleSheet(f"background-color: {self.solid_color_hex}; border: 1px solid #4f545c;")
            if "background_type" in config:
                self.background_type_combo.setCurrentText(config.get("background_type", "Image"))
            QMessageBox.information(self, "Config Loaded", "Configuration applied successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Config Error", f"Failed to apply configuration:\n{e}")
