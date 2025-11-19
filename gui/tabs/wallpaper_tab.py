import os
import platform
import subprocess
import json

from math import floor
from pathlib import Path
from screeninfo import get_monitors, Monitor
from typing import Dict, List, Optional, Tuple, Any
from PySide6.QtGui import QPixmap, QAction, QColor
from PySide6.QtCore import (
    QTimer, Slot, QPoint,
    Qt, QThreadPool, QThread,
) 
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, 
    QGroupBox, QComboBox, QMenu,
    QWidget, QLabel, QPushButton, 
    QGridLayout, QSpinBox, QCheckBox,
    QLineEdit, QFileDialog, QScrollArea, 
    QMessageBox, QApplication, QColorDialog,
)
from .base_tab import BaseTab
from ..windows import SlideshowQueueWindow, ImagePreviewWindow
from ..components import MonitorDropWidget, DraggableImageLabel 
from ..helpers import ImageScannerWorker, BatchThumbnailLoaderWorker, WallpaperWorker
from ..styles.style import apply_shadow_effect, STYLE_SYNC_RUN, STYLE_SYNC_STOP
from backend.src.utils.definitions import WALLPAPER_STYLES
from backend.src.core import WallpaperManager


class WallpaperTab(BaseTab):
    
    @Slot()
    def _is_slideshow_validation_ready(self) -> Tuple[bool, int]:
        """
        MODIFIED: Checks if slideshow preconditions are met: at least one monitor
        must have a non-empty queue. The returned integer is the total number 
        of unique images in all queues combined (for display/info only).
        Returns (is_ready, total_unique_images).
        """
        monitor_ids = list(self.monitor_widgets.keys())
        
        if not monitor_ids:
            return False, 0
            
        total_images = 0
        all_queues_empty = True
        
        for mid in monitor_ids:
            queue_len = len(self.monitor_slideshow_queues.get(mid, []))
            if queue_len > 0:
                all_queues_empty = False
            total_images += queue_len # Sum of all images across all queues
            
        # The requirement is now simply that at least one queue is not empty.
        is_ready = not all_queues_empty

        return is_ready, total_images

    @Slot()
    def check_all_monitors_set(self):
        """
        Enables the 'Set Wallpaper' button based on either standard, slideshow, 
        or solid color mode requirements.
        """
        
        if self.slideshow_timer and self.slideshow_timer.isActive():
             return

        if self.current_wallpaper_worker:
            return

        if self.set_wallpaper_btn.text() in ["Missing Pillow", "Missing screeninfo", "Missing Helpers", "Missing Wallpaper Module"]:
             self.set_wallpaper_btn.setText("Set Wallpaper")
            
        target_monitor_ids = list(self.monitor_widgets.keys())
        num_monitors = len(target_monitor_ids)
        
        set_count = sum(1 for mid in target_monitor_ids if mid in self.monitor_image_paths and self.monitor_image_paths[mid])
        
        # --- MODIFIED: Removed the "all_set_single" check for standard mode. ---
        # The button is now enabled if any image is set (set_count > 0) OR if the slideshow is ready.
        is_ready, total_images = self._is_slideshow_validation_ready()

        # --- NEW LOGIC: Solid Color takes precedence over image paths ---
        if self.background_type == "Solid Color":
            self.set_wallpaper_btn.setText(f"Set Solid Color ({self.solid_color_hex})")
            # Solid color can always be set if monitors exist
            self.set_wallpaper_btn.setEnabled(num_monitors > 0)
            return
        # --- END NEW LOGIC ---

        if self.slideshow_enabled_checkbox.isChecked():
            if is_ready:
                 self.set_wallpaper_btn.setEnabled(True)
                 # MODIFIED: Text changed to reflect total images across all queues
                 self.set_wallpaper_btn.setText(f"Start Slideshow ({total_images} total images)")
            else:
                 self.set_wallpaper_btn.setEnabled(False)
                 self.set_wallpaper_btn.setText("Slideshow (Drop images)")
                 
        elif set_count > 0: # --- MODIFIED: Only require at least one image set ---
            self.set_wallpaper_btn.setText("Set Wallpaper")
            self.set_wallpaper_btn.setEnabled(True)
        else:
            self.set_wallpaper_btn.setText("Set Wallpaper (0 images)")
            self.set_wallpaper_btn.setEnabled(False)


    def __init__(self, db_tab_ref, dropdown=True):
        super().__init__()
        self.db_tab_ref = db_tab_ref
        
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
        
        self.wallpaper_style: str = "Fill" # Default style

        # --- NEW STATE VARIABLES ---
        self.background_type: str = "Image" # Image, Solid Color
        self.solid_color_hex: str = "#000000" # Default to black
        # --- END NEW STATE VARIABLES ---

        # --- MODIFICATION START: Create main content widget and scroll area ---
        # 1. Create the content widget to hold all UI elements
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # 2. Create the main scroll area for the entire tab
        main_scroll_area = QScrollArea()
        main_scroll_area.setWidgetResizable(True)
        main_scroll_area.setWidget(content_widget)
        
        # 3. Set the WallpaperTab's layout to hold only the main scroll area
        main_tab_layout = QVBoxLayout(self)
        main_tab_layout.setContentsMargins(0, 0, 0, 0) # Remove margins from the main layout
        main_tab_layout.addWidget(main_scroll_area)
        self.setLayout(main_tab_layout) 
        # --- MODIFICATION END ---
        
        # Style for all QGroupBoxes
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

        # Slideshow Enabled Checkbox
        self.slideshow_enabled_checkbox = QCheckBox("Enable Slideshow")
        self.slideshow_enabled_checkbox.setToolTip("Cycles through dropped images on each monitor.")
        slideshow_layout.addWidget(self.slideshow_enabled_checkbox)

        # Interval Spinboxes
        slideshow_layout.addWidget(QLabel("Interval:"))
        
        # Minutes Spinbox
        self.interval_min_spinbox = QSpinBox()
        self.interval_min_spinbox.setRange(0, 60)
        self.interval_min_spinbox.setValue(5)
        self.interval_min_spinbox.setFixedWidth(50)
        slideshow_layout.addWidget(self.interval_min_spinbox)
        slideshow_layout.addWidget(QLabel("min"))

        # Seconds Spinbox
        self.interval_sec_spinbox = QSpinBox()
        self.interval_sec_spinbox.setRange(0, 59)
        self.interval_sec_spinbox.setValue(0) 
        self.interval_sec_spinbox.setFixedWidth(50)
        slideshow_layout.addWidget(self.interval_sec_spinbox)
        slideshow_layout.addWidget(QLabel("sec"))

        slideshow_layout.addStretch(1)
        
        # Countdown Label
        self.countdown_label = QLabel("Timer: --:--")
        self.countdown_label.setStyleSheet("color: #2ecc71; font-weight: bold; font-size: 14px;")
        self.countdown_label.setFixedWidth(100)
        slideshow_layout.addWidget(self.countdown_label)

        content_layout.addWidget(self.slideshow_group) 

        
        # START Combined Settings Group (Wallpaper Style + Scan Directory)
        settings_group = QGroupBox("Wallpaper Settings")
        settings_group.setStyleSheet(group_box_style)
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setContentsMargins(10, 20, 10, 10)
        
        # --- NEW: Background Type Selection ---
        background_type_layout = QHBoxLayout()
        self.background_type_combo = QComboBox()
        self.background_type_combo.addItems(["Image", "Solid Color"])
        self.background_type_combo.setCurrentText(self.background_type)
        self.background_type_combo.currentTextChanged.connect(self._update_background_type)

        background_type_layout.addWidget(QLabel("Background Type:"))
        background_type_layout.addWidget(self.background_type_combo)
        background_type_layout.addStretch(1)
        settings_layout.addLayout(background_type_layout)

        # NEW: Solid Color Selection (initially hidden)
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
        self.solid_color_widget.setVisible(False) # Hide by default
        
        settings_layout.addWidget(QLabel("<hr>")) 
        # --- END NEW: Background Type Selection ---

        # Wallpaper Style Section (formerly style_group)
        style_layout = QHBoxLayout()
        self.style_combo = QComboBox()
        self.style_combo.setStyleSheet("QComboBox { padding: 5px; border-radius: 4px; }")
        
        # Determine initial style options based on OS
        initial_styles = self._get_relevant_styles()
        self.style_combo.addItems(initial_styles.keys())
        self.style_combo.setCurrentText(list(initial_styles.keys())[0])
        self.wallpaper_style = list(initial_styles.keys())[0]
        
        # Connect the change handler
        self.style_combo.currentTextChanged.connect(self._update_wallpaper_style)

        style_layout.addWidget(QLabel("Image Style:"))
        style_layout.addWidget(self.style_combo)
        style_layout.addStretch(1)
        settings_layout.addLayout(style_layout)
        
        # Separator line for visual clarity
        settings_layout.addWidget(QLabel("<hr>")) 

        # Scan Directory Section (formerly scan_group)
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
        # END Combined Settings Group

        # Thumbnail Gallery Scroll Area
        self.thumbnail_size = 150
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width

        self.scan_scroll_area = QScrollArea() 
        self.scan_scroll_area.setWidgetResizable(True)
        self.scan_scroll_area.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")

        # Set minimum height for the main gallery scroll area (half of 1200, matching merge_tab)
        self.scan_scroll_area.setMinimumHeight(600) 

        self.scan_thumbnail_widget = QWidget()
        self.scan_thumbnail_widget.setStyleSheet("QWidget { background-color: #2c2f33; }")

        self.scan_thumbnail_layout = QGridLayout(self.scan_thumbnail_widget)
        self.scan_thumbnail_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        
        self.scan_scroll_area.setWidget(self.scan_thumbnail_widget)
        
        content_layout.addWidget(self.scan_scroll_area, 1) 
        
        # Action Buttons
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)
        
        self.refresh_btn = QPushButton("Refresh Layout")
        self.refresh_btn.setStyleSheet("background-color: #f1c40f; color: black; padding: 10px; border-radius: 8px; font-weight: bold;")
        apply_shadow_effect(self.refresh_btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.refresh_btn.clicked.connect(self.handle_refresh_layout)
        action_layout.addWidget(self.refresh_btn)
        
        self.set_wallpaper_btn = QPushButton("Set Wallpaper")
        self.set_wallpaper_btn.setStyleSheet(STYLE_SYNC_RUN)
        apply_shadow_effect(self.set_wallpaper_btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.set_wallpaper_btn.clicked.connect(self.handle_set_wallpaper_click)
        action_layout.addWidget(self.set_wallpaper_btn, 1)
        
        content_layout.addLayout(action_layout) 

        # State for scanner
        self.threadpool = QThreadPool.globalInstance()
        self.scanned_dir = None
        try:
            base_dir = Path.cwd()
            while base_dir.name != 'Image-Toolkit' and base_dir.parent != base_dir:
                base_dir = base_dir.parent
            if base_dir.name == 'Image-Toolkit':
                self.last_browsed_scan_dir = str(base_dir / 'data')
            else:
                self.last_browsed_scan_dir = os.getcwd() 
        except Exception:
             self.last_browsed_scan_dir = os.getcwd() 
        
        self.scan_image_list: list[str] = []
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None
        self.path_to_label_map = {}
        
        # Initial setup
        self.populate_monitor_layout()
        self.check_all_monitors_set()
        self.stop_slideshow()
        
    def _get_relevant_styles(self) -> Dict[str, str]:
        """Returns the dictionary of relevant styles based on the current OS."""
        system = platform.system()
        if system == "Windows":
            return WALLPAPER_STYLES["Windows"]
        elif system == "Linux":
            # Assume KDE/GNOME, check for KDE first
            try:
                subprocess.run(["which", "qdbus6"], check=True, capture_output=True)
                return WALLPAPER_STYLES["KDE"]
            except (FileNotFoundError, subprocess.CalledProcessError):
                # Fallback to GNOME/Spanned
                return WALLPAPER_STYLES["GNOME"]
            except:
                return {"Default (System)": None}
        else:
            return {"Default (System)": None}


    @Slot(str)
    def _update_wallpaper_style(self, style_name: str):
        """Updates the selected wallpaper style."""
        self.wallpaper_style = style_name

    # --- NEW METHODS ---
    @Slot(str)
    def _update_background_type(self, type_name: str):
        """Updates the selected background type and toggles control visibility."""
        self.background_type = type_name
        
        is_solid_color = (type_name == "Solid Color")
        
        # Toggle visibility of color controls
        self.solid_color_widget.setVisible(is_solid_color)
        
        # Toggle visibility/enablement of image-specific controls
        style_enabled = not is_solid_color
        self.style_combo.setEnabled(style_enabled)
        
        # Also toggle the scan directory group and the slideshow group
        self.scan_directory_path.setEnabled(style_enabled)
        self.scan_scroll_area.setEnabled(style_enabled)
        self.slideshow_group.setEnabled(style_enabled)
        
        # If switching to solid color, stop slideshow if running
        if is_solid_color and self.slideshow_timer and self.slideshow_timer.isActive():
            self.stop_slideshow()
            
        self.check_all_monitors_set()


    @Slot()
    def select_solid_color(self):
        """Opens the color dialog to select the solid background color."""
        initial_color = QColor(self.solid_color_hex)
        color = QColorDialog.getColor(initial_color, self, "Select Solid Background Color")

        if color.isValid():
            self.solid_color_hex = color.name().upper()
            self.solid_color_preview.setStyleSheet(f"background-color: {self.solid_color_hex}; border: 1px solid #4f545c;")
            self.check_all_monitors_set() # Update button text/state

    # --- Slideshow Handlers ---

    @Slot()
    def update_countdown(self):
        """Updates the UI countdown label every second."""
        if self.time_remaining_sec > 0:
            self.time_remaining_sec -= 1
            minutes = floor(self.time_remaining_sec / 60)
            seconds = self.time_remaining_sec % 60
            self.countdown_label.setText(f"Timer: {minutes:02d}:{seconds:02d}")
        else:
            self.countdown_label.setText("Timer: 00:00")
    
    @Slot()
    def handle_set_wallpaper_click(self):
        """Handles the click event for the main 'Set Wallpaper' button."""
        
        # If solid color is selected, run worker regardless of slideshow state
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
        """Initializes the slideshow queues and starts the timers."""
        
        num_monitors = len(self.monitor_widgets)
        
        # Solid color mode cannot run slideshow
        if self.background_type == "Solid Color":
             QMessageBox.warning(self, "Slideshow Error", "Slideshow is disabled when Solid Color mode is selected.")
             self.slideshow_enabled_checkbox.setChecked(False)
             return
        
        # MODIFIED: Removed the check for equal queue length (is_ready only checks non-empty)
        is_ready, total_images = self._is_slideshow_validation_ready()
        
        if num_monitors == 0:
            QMessageBox.warning(self, "Slideshow Error", "No monitors detected or configured.")
            self.slideshow_enabled_checkbox.setChecked(False)
            return
            
        if not is_ready:
            QMessageBox.critical(self, "Slideshow Error", 
                                 "To start the slideshow, at least one monitor must have images dropped on it.")
            self.slideshow_enabled_checkbox.setChecked(False)
            return

        self.stop_slideshow() 
        
        for mid in self.monitor_widgets.keys():
            # Ensure index is set to -1 so the first cycle starts at 0
            self.monitor_current_index[mid] = -1 

        interval_minutes = self.interval_min_spinbox.value()
        interval_seconds = self.interval_sec_spinbox.value()
        
        self.interval_sec = (interval_minutes * 60) + interval_seconds
        
        if self.interval_sec <= 0:
            QMessageBox.critical(self, "Slideshow Error", "Slideshow interval must be greater than 0 seconds.")
            self.slideshow_enabled_checkbox.setChecked(False)
            return

        interval_ms = self.interval_sec * 1000

        self.time_remaining_sec = self.interval_sec

        # Long interval timer (triggers wallpaper change)
        self.slideshow_timer = QTimer(self)
        self.slideshow_timer.timeout.connect(self._cycle_slideshow_wallpaper)
        self.slideshow_timer.start(interval_ms)
        
        # Short interval timer (updates UI countdown)
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)

        QMessageBox.information(self, "Slideshow Started", 
                                f"Per-monitor slideshow started with {total_images} total images, cycling every {interval_minutes} minutes and {interval_seconds} seconds.")
        
        # Immediately set the first set of wallpapers (index 0)
        self._cycle_slideshow_wallpaper()

        # Update button text to reflect the running state
        self.set_wallpaper_btn.setText(f"Slideshow Running (Stop)")
        self.set_wallpaper_btn.setStyleSheet(STYLE_SYNC_STOP)
        self.set_wallpaper_btn.setEnabled(True)


    @Slot()
    def stop_slideshow(self):
        """Stops the QTimers and resets state."""
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
            if win.isVisible():
                win.close()
        self.open_queue_windows.clear()
        
        # Close any open image preview windows as well
        for win in list(self.open_image_preview_windows):
            if win.isVisible():
                win.close()
        self.open_image_preview_windows.clear()
        
        self.monitor_current_index.clear()
        self.time_remaining_sec = 0
        self.countdown_label.setText("Timer: --:--")

        self.slideshow_enabled_checkbox.setChecked(False)
        self.unlock_ui_for_wallpaper()

    @Slot()
    def _cycle_slideshow_wallpaper(self):
        """
        Advances the index for each monitor, applies the new set of images.
        Cycles based on each monitor's individual queue length.
        """
        
        monitor_ids = list(self.monitor_widgets.keys())
        if not monitor_ids: return 
        
        # Solid color mode cannot run slideshow
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
                    # Calculate the next index, cycling within this specific queue's length
                    next_index = (current_index + 1) % current_queue_length
                    
                    path = queue[next_index]
                    
                    new_monitor_paths[monitor_id] = path
                    self.monitor_current_index[monitor_id] = next_index
                    has_valid_path_to_set = True
                else:
                    # If queue is empty, maintain the current path (which might be None)
                    new_monitor_paths[monitor_id] = self.monitor_image_paths.get(monitor_id)
                    self.monitor_current_index[monitor_id] = -1 # Reset index for empty queue

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
        """Opens a new non-modal window to display the image queue for the clicked monitor."""
        
        # If solid color is selected, double click does nothing
        if self.background_type == "Solid Color":
            return
            
        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        monitor_name = self.monitor_widgets[monitor_id].monitor.name
        
        for win in self.open_queue_windows:
            if isinstance(win, SlideshowQueueWindow) and win.monitor_id == monitor_id:
                win.activateWindow()
                return

        window = SlideshowQueueWindow(monitor_name, monitor_id, queue)
        window.setAttribute(Qt.WA_DeleteOnClose)
        
        window.queue_reordered.connect(self.on_queue_reordered)
        
        # This makes the right-click menu item (and double-click) functional.
        window.image_preview_requested.connect(self.handle_full_image_preview)
        
        def remove_closed_win(event: Any):
            if window in self.open_queue_windows:
                 self.open_queue_windows.remove(window)
            event.accept()

        window.closeEvent = remove_closed_win
        
        window.show()
        self.open_queue_windows.append(window)

    @Slot(str)
    def handle_full_image_preview(self, image_path: str):
        """
        Generic slot to open a full-size image preview. 
        It uses the list of all scanned images for navigation.
        """
        
        # 1. Prepare navigation list (all scanned images)
        all_paths_list = sorted(self.scan_image_list)
        
        # 2. Find the index of the clicked image within the list
        try:
            start_index = all_paths_list.index(image_path)
        except ValueError:
            # If the clicked image isn't in the scan list (e.g., from a queue), open it standalone.
            all_paths_list = [image_path]
            start_index = 0
            
        # Check if the image is already open
        for win in list(self.open_image_preview_windows):
            # Check by path for a unique identifier
            if isinstance(win, ImagePreviewWindow) and win.image_path == image_path:
                win.activateWindow()
                return

        # Instantiate the ImagePreviewWindow from the components module
        window = ImagePreviewWindow(
            image_path=image_path, 
            db_tab_ref=None, 
            parent=self, 
            all_paths=all_paths_list, 
            start_index=start_index
        )
        window.setAttribute(Qt.WA_DeleteOnClose)
        
        def remove_closed_win(event: Any):
            if window in self.open_image_preview_windows:
                 self.open_image_preview_windows.remove(window)
            event.accept()

        window.closeEvent = remove_closed_win
        
        window.show()
        self.open_image_preview_windows.append(window)

    # --- NEW METHOD: Context Menu Handler for DraggableImageLabel ---
    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        """
        Displays a context menu for the clicked image thumbnail, offering 
        View and Add to Queue options.
        """
        # If solid color is selected, context menu doesn't apply
        if self.background_type == "Solid Color":
            return
            
        menu = QMenu(self)
        
        # 1. View Full Size (Triggers the new navigation-enabled handler)
        view_action = QAction("View Full Size Preview", self)
        view_action.triggered.connect(lambda: self.handle_full_image_preview(path))
        menu.addAction(view_action)
        
        # 2. Add to Queue Submenu
        if self.monitor_widgets:
            menu.addSeparator()
            
            add_menu = menu.addMenu("Add to Monitor Queue")
            
            # Iterate through available monitors
            for monitor_id, widget in self.monitor_widgets.items():
                monitor_name = widget.monitor.name
                action = QAction(f"{monitor_name} (ID: {monitor_id})", self)
                # Use a lambda function to capture both the path and the monitor_id
                action.triggered.connect(lambda checked, mid=monitor_id, img_path=path: self.on_image_dropped(mid, img_path))
                add_menu.addAction(action)
        
        menu.exec(global_pos)
    # --- END NEW METHOD ---


    @Slot(str, list)
    def on_queue_reordered(self, monitor_id: str, new_queue: List[str]):
        """Slot to receive the updated queue from the SlideshowQueueWindow."""
        self.monitor_slideshow_queues[monitor_id] = new_queue
        
        # Reset index because the queue order has changed
        self.monitor_current_index[monitor_id] = -1 
        
        new_first_image = new_queue[0] if new_queue else None
        self.monitor_image_paths[monitor_id] = new_first_image
        
        if new_first_image and self.monitor_widgets[monitor_id].image_path != new_first_image:
            self.monitor_widgets[monitor_id].set_image(new_first_image)
        elif not new_first_image:
            self.monitor_widgets[monitor_id].clear() # Use clear() for consistency
        
        self.check_all_monitors_set()
        
    # NEW SLOT: Handles right-click clear action from MonitorDropWidget
    @Slot(str)
    def handle_clear_monitor_queue(self, monitor_id: str):
        """
        Clears the image queue and local path for the specified monitor, 
        leaving the system's current wallpaper untouched, but restores 
        the system wallpaper image preview immediately.
        """
        
        if monitor_id not in self.monitor_widgets:
            return

        monitor_name = self.monitor_widgets[monitor_id].monitor.name
        
        # 1. Clear state (Soft Clear)
        if monitor_id in self.monitor_slideshow_queues:
            self.monitor_slideshow_queues[monitor_id].clear()
        
        # Clear the local path (this is the key step for the soft clear)
        if monitor_id in self.monitor_image_paths:
            self.monitor_image_paths[monitor_id] = None
            
        if monitor_id in self.monitor_current_index:
            self.monitor_current_index[monitor_id] = -1
        
        # 2. Re-read System Wallpaper and Update UI Immediately
        
        system = platform.system()
        num_monitors_detected = len(self.monitors)
        
        current_system_wallpaper_paths = {}

        # Only attempt to re-read and display the system background on Linux/KDE
        if system == "Linux" and num_monitors_detected > 0:
            try:
                # Check for KDE presence (qdbus6)
                subprocess.run(["which", "qdbus6"], check=True, capture_output=True) 
                
                # Retrieve raw paths
                raw_paths = WallpaperManager.get_current_system_wallpaper_path_kde(num_monitors_detected)
                
                # Apply rotation to align KDE IDs with UI Physical Order
                current_system_wallpaper_paths = self._get_rotated_map_for_ui(raw_paths)
                
            except (FileNotFoundError, subprocess.CalledProcessError):
                # Fallback or ignore for GNOME/other Linux
                pass 
            except Exception as e:
                print(f"KDE retrieval failed unexpectedly: {e}")
        
        # 3. Update the specific MonitorDropWidget
        system_wallpaper_path = current_system_wallpaper_paths.get(monitor_id)

        if system_wallpaper_path and Path(system_wallpaper_path).exists():
            # If system wallpaper path is found, display it immediately
            self.monitor_widgets[monitor_id].set_image(system_wallpaper_path)
        else:
            # Otherwise, clear the image and show the default text
            self.monitor_widgets[monitor_id].clear() 

        # 4. Check buttons (in case clearing the last queue affects slideshow readiness)
        self.check_all_monitors_set()

        QMessageBox.information(self, "Monitor Cleared", 
                                f"All pending images and the slideshow queue for **{monitor_name}** have been cleared.\n\n"
                                f"The system's current background remains unchanged.")


    @Slot()
    def handle_refresh_layout(self):
        """
        Refreshes monitor layout, clears dropped images, clears the scanned gallery,
        and resets the scanned directory path.
        """
        self.stop_slideshow() 
        
        self.monitor_slideshow_queues.clear()
        self.monitor_current_index.clear()
        self.monitor_image_paths.clear() 
        
        self.scan_directory_path.clear()
        self.scanned_dir = None
        self.scan_image_list = []
        
        self.clear_scan_image_gallery() 
        
        # Reset background type to default when refreshing
        self.background_type_combo.setCurrentText("Image")
        
        self.populate_monitor_layout() 
        
        self.check_all_monitors_set()
        
        columns = self.calculate_columns()
        ready_label = QLabel("Layout Refreshed. Browse for a directory.")
        ready_label.setAlignment(Qt.AlignCenter)
        ready_label.setStyleSheet("color: #b9bbbe;")
        self.scan_thumbnail_layout.addWidget(ready_label, 0, 0, 1, columns)

    # --- HELPER METHOD FOR ROTATION FIX (UI Display) ---
    def _get_rotated_map_for_ui(self, source_paths: Dict[str, str]) -> Dict[str, str]:
        """
        Applies a rotational correction (Right Circular Shift) to retrieved 
        system paths to align them with the UI's physical monitor order. 
        This mirrors the logic in _get_kde_assignment_map for correction.
        """
        n = len(self.monitors)
        if n == 0:
            return {}
            
        rotated_map = {}
        
        # Iterate over all system monitor IDs (0, 1, 2...)
        for current_monitor_id_str in [str(i) for i in range(n)]:
            current_monitor_id = int(current_monitor_id_str)
            
            # The path for Monitor 'i' (UI's order) should come from Monitor 'i+1' in the map, 
            # with the last monitor getting the path from the first monitor (index 0).
            # Source path index is (current_index + 1) % n.
            source_monitor_index = (current_monitor_id + 1) % n
            source_monitor_id_str = str(source_monitor_index)
            
            path_from_source = source_paths.get(source_monitor_id_str)
            rotated_map[current_monitor_id_str] = path_from_source
            
        return rotated_map
    # --- END NEW HELPER METHOD ---
    
    def populate_monitor_layout(self):
        """
        Clears and recreates the monitor drop widgets.
        Now queries the current system wallpaper path if no image has been dropped.
        """
        for i in reversed(range(self.monitor_layout.count())): 
            widget = self.monitor_layout.takeAt(i).widget()
            if widget is not None:
                widget.deleteLater()
        self.monitor_widgets.clear()
        
        try:
            system_monitors = get_monitors()
            # Sort by X coordinate for physical display in the UI
            physical_monitors = sorted(system_monitors, key=lambda m: m.x)
            
            self.monitors = system_monitors

        except Exception as e:
             QMessageBox.critical(self, "Error", f"Could not get monitor info: {e}")
             self.monitors = []
             
        if not self.monitors or "Mock" in self.monitors[0].name:
            self.monitor_layout.addWidget(QLabel("Could not detect any monitors.\nIs 'screeninfo' installed?"))
            return

        # --- Check system and retrieve ALL current paths once ---
        current_system_wallpaper_paths = {}
        system = platform.system()
        num_monitors_detected = len(self.monitors)

        if system == "Linux" and num_monitors_detected > 0:
            try:
                # Check for KDE presence (qdbus6)
                subprocess.run(["which", "qdbus6"], check=True, capture_output=True) 
                
                # Retrieve raw paths from KDE
                raw_paths = WallpaperManager.get_current_system_wallpaper_path_kde(num_monitors_detected)
                
                # APPLY ROTATION to align KDE IDs (raw_paths) with UI Physical Order (monitor_id)
                current_system_wallpaper_paths = self._get_rotated_map_for_ui(raw_paths)
                
            except (FileNotFoundError, subprocess.CalledProcessError):
                # Fallback or ignore for GNOME/other Linux
                pass 
            except Exception as e:
                print(f"KDE retrieval failed unexpectedly: {e}")

        # --- End System check and retrieval ---

        # Show all physical monitors for placement
        monitors_to_show = physical_monitors
        for monitor in monitors_to_show:
            
            # Find the original system index (display priority) associated with this physical monitor
            system_index = -1
            for i, sys_mon in enumerate(system_monitors):
                if (sys_mon.x == monitor.x and 
                    sys_mon.y == monitor.y and
                    sys_mon.width == monitor.width and 
                    sys_mon.height == monitor.height):
                    system_index = i
                    break
            
            if system_index == -1:
                print(f"Warning: Could not map physical monitor {monitor.name} back to system index.")
                continue

            # The monitor_id is the system's priority index (0, 1, 2, ...), which dictates wallpaper assignment
            monitor_id = str(system_index) 

            drop_widget = MonitorDropWidget(monitor, monitor_id)
            drop_widget.image_dropped.connect(self.on_image_dropped)
            drop_widget.double_clicked.connect(self.handle_monitor_double_click)
            
            # NEW CONNECTION: Connect the right-click signal
            try:
                drop_widget.clear_requested_id.connect(self.handle_clear_monitor_queue)
            except AttributeError:
                 print(f"Warning: MonitorDropWidget is missing 'clear_requested_id' signal. Right-click clear will not work.")
            
            current_image = self.monitor_image_paths.get(monitor_id)
            
            # --- Load current system wallpaper if no image is dropped ---
            image_path_to_display = current_image
            
            if not image_path_to_display:
                # Use the path from the ROTATED map
                system_wallpaper_path = current_system_wallpaper_paths.get(monitor_id)
                
                if system_wallpaper_path and Path(system_wallpaper_path).exists():
                    image_path_to_display = system_wallpaper_path

            if image_path_to_display:
                drop_widget.set_image(image_path_to_display)
            else:
                 drop_widget.clear() 
            
            # --- End Load current system wallpaper ---
            
            # Add to the layout in the physical X-axis order
            self.monitor_layout.addWidget(drop_widget)
            self.monitor_widgets[monitor_id] = drop_widget
        
        self.check_all_monitors_set()

    def on_image_dropped(self, monitor_id: str, image_path: str):
        """
        Slot to add the dropped image to the monitor's specific queue, 
        and display the last dropped image for visual confirmation.
        """
        # Automatically switch to Image mode if dropping an image
        if self.background_type != "Image":
            self.background_type_combo.setCurrentText("Image")
            
        if monitor_id not in self.monitor_slideshow_queues:
            self.monitor_slideshow_queues[monitor_id] = []
        
        self.monitor_slideshow_queues[monitor_id].append(image_path)
        
        # When a new image is dropped, it becomes the current image
        self.monitor_image_paths[monitor_id] = image_path
        
        # Reset current index so the slideshow starts from the newly dropped image
        self.monitor_current_index[monitor_id] = -1 

        self.monitor_widgets[monitor_id].set_image(image_path)
        
        self.check_all_monitors_set()
        
    def _get_gnome_assignment_map(self, source_paths: Dict[str, str]) -> Dict[str, str]:
        """
        Reintroduces the corrective shift/rotation required by the underlying 
        system/worker to ensure the image assigned to System ID N lands on Monitor N.
        Monitor 0 gets image from N-1, Monitor 1 gets image from 0, etc.
        """
        n = len(self.monitors)
        if n == 0:
            return {}
            
        rotated_map = {}
        
        # Iterate over all system monitor IDs present in the paths dictionary
        for current_monitor_id_str in source_paths.keys():
            current_monitor_id = int(current_monitor_id_str)
            
            # The assignment logic requires Monitor 'i' to take the path intended for Monitor 'i-1'
            # We use the length of the system_monitors list (n) for the modulo calculation.
            prev_monitor_index = (current_monitor_id - 1 + n) % n
            
            # Use the previous monitor's system index (ID) to fetch the path
            prev_monitor_id_str = str(prev_monitor_index)
            
            path_from_prev = source_paths.get(prev_monitor_id_str)
            rotated_map[current_monitor_id_str] = path_from_prev
        return rotated_map

    def _get_kde_assignment_map(self, source_paths: Dict[str, str]) -> Dict[str, str]:
        """
        Applies a rotational correction to map the UI's monitor order (based on 
        screeninfo's system index) to the internal screen indices used by KDE.
        It uses the same right circular shift as the GNOME implementation.
        """
        n = len(self.monitors)
        if n == 0:
            return {}
            
        rotated_map = {}
        
        # Iterate over all system monitor IDs present in the paths dictionary
        for current_monitor_id_str in source_paths.keys():
            current_monitor_id = int(current_monitor_id_str)
            
            # The assignment logic requires Monitor 'i' to take the path intended for Monitor 'i-1'
            # (Right Circular Shift on Source Paths)
            # Use n for the modulo calculation.
            prev_monitor_index = (current_monitor_id - 1 + n) % n
            
            # Use the previous monitor's system index (ID) to fetch the path
            prev_monitor_id_str = str(prev_monitor_index)
            
            path_from_prev = source_paths.get(prev_monitor_id_str)
            rotated_map[current_monitor_id_str] = path_from_prev
        return rotated_map
    
    def _get_windows_assignment_map(self, source_paths: Dict[str, str]) -> Dict[str, str]:
        # NOTE: This implementation performs the same right circular shift as Linux
        # if the goal is to align the UI's physical order (sorted by X) with the OS's internal ID.
        # This rotation logic is applied to Windows here to match the Linux fixes, 
        # but the actual requirement for Windows COM API (IDesktopWallpaper) may vary.
        n = len(self.monitors)
        rotated_map = source_paths.copy()
        for current_monitor_id_str in source_paths.keys():
            current_monitor_id = int(current_monitor_id_str)
            prev_monitor_index = (current_monitor_id - 1 + n) % n
            prev_monitor_id_str = str(prev_monitor_index)
            rotated_map[current_monitor_id_str] = source_paths.get(prev_monitor_id_str)
        return rotated_map
    
    def run_wallpaper_worker(self, slideshow_mode=False):
        """
        Initializes and runs the wallpaper worker on a separate thread.
        """
        if self.current_wallpaper_worker:
            print("Wallpaper worker is already running.")
            return

        # --- NEW LOGIC: Handle Solid Color mode ---
        if self.background_type == "Solid Color":
            # For solid color, the 'path_map' will contain the color hex for all monitors
            path_map = {str(mid): self.solid_color_hex for mid in range(len(self.monitors))}
            style_to_use = "SolidColor" # Sentinel value for the worker
        else:
            # Existing logic for image mode
            if not any(self.monitor_image_paths.values()):
                if not slideshow_mode:
                    QMessageBox.warning(self, "Incomplete", "No images have been dropped on the monitors.")
                return
                
            if ImageScannerWorker is None:
                QMessageBox.warning(self, "Missing Helpers",
                                    "The ImageScannerWorker or BatchThumbnailLoaderWorker could not be imported.\n"
                                    "Directory scanning will be disabled.")
                return

            # Apply the necessary rotational map correction before passing to the worker
            system = platform.system()
            if system == "Linux":
                # Assume KDE/GNOME, check for KDE first
                try:
                    subprocess.run(["which", "qdbus6"], check=True, capture_output=True)
                    desktop = "KDE"
                except (FileNotFoundError, subprocess.CalledProcessError):
                    desktop = "Gnome"
                except:
                    desktop = None
            elif system == "Windows":
                desktop = "Windows"
            else:
                desktop = None
            
            if desktop == "Gnome":
                path_map = self._get_gnome_assignment_map(self.monitor_image_paths)
            elif desktop == "KDE":
                path_map = self._get_kde_assignment_map(self.monitor_image_paths)
            elif desktop == "Windows":
                path_map = self._get_windows_assignment_map(self.monitor_image_paths)
            else:
                path_map = self.monitor_image_paths

            style_to_use = self.wallpaper_style
        # --- END NEW LOGIC ---

        monitors = self.monitors
        if not slideshow_mode:
            self.lock_ui_for_wallpaper()
        
        # Pass the selected style (or sentinel value)
        self.current_wallpaper_worker = WallpaperWorker(
            path_map, 
            monitors, 
            wallpaper_style=style_to_use
        )
        self.current_wallpaper_worker.signals.status_update.connect(self.handle_wallpaper_status)
        self.current_wallpaper_worker.signals.work_finished.connect(self.handle_wallpaper_finished)
        
        self.current_wallpaper_worker.signals.work_finished.connect(
            lambda: setattr(self, 'current_wallpaper_worker', None)
        )
        
        QThreadPool.globalInstance().start(self.current_wallpaper_worker)

    def stop_wallpaper_worker(self):
        """
        Stops the currently running wallpaper worker, if any.
        """
        if self.current_wallpaper_worker:
            self.current_wallpaper_worker.stop()
            self.handle_wallpaper_status("Manual stop requested.")
            self.unlock_ui_for_wallpaper()
            self.current_wallpaper_worker = None

    def lock_ui_for_wallpaper(self):
        """Locks the UI when the manual wallpaper worker is running."""
        self.set_wallpaper_btn.setText("Applying (Click to Stop)")
        self.set_wallpaper_btn.setStyleSheet(STYLE_SYNC_STOP)
        self.set_wallpaper_btn.setEnabled(True)
        
        self.refresh_btn.setEnabled(False)
        # Disable all UI elements that initiate a new worker or change state
        self.slideshow_group.setEnabled(False) 
        self.scan_scroll_area.setEnabled(False)
        self.scan_directory_path.setEnabled(False) 
        self.style_combo.setEnabled(False)
        self.background_type_combo.setEnabled(False) # <-- NEW
        self.solid_color_widget.setEnabled(False)    # <-- NEW
        
        # Also disable monitor drop widgets during application
        for widget in self.monitor_widgets.values():
            widget.setEnabled(False)
            
        QApplication.processEvents()
        
    def unlock_ui_for_wallpaper(self):
        """Unlocks the UI when the manual wallpaper worker is finished."""
        self.set_wallpaper_btn.setText("Set Wallpaper")
        self.set_wallpaper_btn.setStyleSheet(STYLE_SYNC_RUN)
        
        self.refresh_btn.setEnabled(True)
        self.slideshow_group.setEnabled(True)
        self.scan_scroll_area.setEnabled(True)
        self.scan_directory_path.setEnabled(True)
        self.style_combo.setEnabled(True)
        self.background_type_combo.setEnabled(True) # <-- NEW
        self.solid_color_widget.setEnabled(True) # <-- NEW
        
        # Re-enable monitor drop widgets
        for widget in self.monitor_widgets.values():
            widget.setEnabled(True)
            
        # Re-apply visibility/enablement based on the current background type
        self._update_background_type(self.background_type)

        self.check_all_monitors_set()
        QApplication.processEvents()

    @Slot(str)
    def handle_wallpaper_status(self, msg: str):
        """
        Handles status updates from the worker.
        """
        print(f"[WallpaperWorker] {msg}")

    @Slot(bool, str)
    def handle_wallpaper_finished(self, success: bool, message: str):
        """
        Handles the finished signal from the worker.
        """
        is_slideshow_active = (self.slideshow_timer and self.slideshow_timer.isActive())

        if success:
            if not is_slideshow_active and self.background_type != "Solid Color":
                QMessageBox.information(self, "Success", "Wallpaper has been updated!")
                
                # Update the displayed image using the last path that was set
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
        
        if not is_slideshow_active:
            self.unlock_ui_for_wallpaper()
    
    def browse_scan_directory(self):
        """Select directory to scan and display image thumbnails."""
        # Check for solid color mode before scanning
        if self.background_type == "Solid Color":
            QMessageBox.warning(self, "Mode Conflict", "Cannot browse directory while Solid Color background is selected.")
            return

        if ImageScannerWorker is None:
            QMessageBox.warning(self, "Missing Helpers",
                                "The ImageScannerWorker or BatchThumbnailLoaderWorker could not be imported.\n"
                                "Directory scanning will be disabled.")
            return
            
        start_dir = self.last_browsed_scan_dir
        options = QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        
        directory = QFileDialog.getExistingDirectory(
            self, 
            "Select directory to scan", 
            start_dir, 
            options
        )
        
        if directory:
            self.last_browsed_scan_dir = directory
            self.scan_directory_path.setText(directory)
            self.populate_scan_image_gallery(directory)

    def populate_scan_image_gallery(self, directory: str):
        """Initiates scanning on a separate thread and sets up the gallery structure."""
        if self.background_type == "Solid Color":
             return # Skip if in solid color mode

        self.scanned_dir = directory
        self.clear_scan_image_gallery()
        
        loading_label = QLabel("Scanning directory, please wait...")
        loading_label.setAlignment(Qt.AlignCenter)
        loading_label.setStyleSheet("color: #b9bbbe;")
        self.scan_thumbnail_layout.addWidget(loading_label, 0, 0, 1, 10) 
        
        self.worker = ImageScannerWorker(directory)
        self.thread = QThread() 
        self.worker.moveToThread(self.thread) 
        
        self.thread.started.connect(self.worker.run_scan)
        self.worker.scan_finished.connect(self.display_scan_results)
        self.worker.scan_error.connect(self.handle_scan_error)
        
        self.worker.scan_finished.connect(self.thread.quit)
        self.worker.scan_finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.thread.start()

    def display_scan_results(self, image_paths: list[str]):
        """
        Receives image paths from the worker thread, creates placeholders, and starts 
        a single BatchThumbnailLoaderWorker to progressively load and display images.
        """
        if self.background_type == "Solid Color":
             return # Skip if in solid color mode

        self.clear_scan_image_gallery() 
        self.scan_image_list = image_paths
        
        self.check_all_monitors_set() 
        
        columns = self.calculate_columns()
        
        if not self.scan_image_list:
            no_images_label = QLabel("No supported images found.")
            no_images_label.setAlignment(Qt.AlignCenter)
            no_images_label.setStyleSheet("color: #b9bbbe;")
            self.scan_thumbnail_layout.addWidget(no_images_label, 0, 0, 1, columns)
            return
        
        worker = BatchThumbnailLoaderWorker(self.scan_image_list, self.thumbnail_size)
        thread = QThread()

        self.current_thumbnail_loader_worker = worker
        self.current_thumbnail_loader_thread = thread
        
        worker.moveToThread(thread)
        
        thread.started.connect(worker.run_load_batch)
        worker.create_placeholder.connect(self._create_thumbnail_placeholder)
        worker.thumbnail_loaded.connect(self.update_thumbnail_slot)
        
        worker.loading_finished.connect(thread.quit)
        worker.loading_finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._cleanup_thumbnail_thread_ref)

        worker.loading_finished.connect(self._display_load_complete_message)
        
        thread.start()
        
    @Slot(str)
    def handle_thumbnail_double_click(self, image_path: str):
        """Opens a non-modal window to display the full image using ImagePreviewWindow."""
        
        # This handles the navigation setup for the double-click/right-click action
        self.handle_full_image_preview(image_path)


    def _create_thumbnail_placeholder(self, index: int, path: str):
        columns = self.calculate_columns()
        row = index // columns
        col = index % columns
        draggable_label = DraggableImageLabel(path, self.thumbnail_size) 
        
        # Connect the double click signal, assuming DraggableImageLabel emits `path_double_clicked(str)`
        draggable_label.path_double_clicked.connect(self.handle_thumbnail_double_click)
        
        # --- NEW: Connect Right Click ---
        draggable_label.path_right_clicked.connect(self.show_image_context_menu)
        self.scan_thumbnail_layout.addWidget(draggable_label, row, col)
        self.path_to_label_map[path] = draggable_label 
        self.scan_thumbnail_widget.update()
        QApplication.processEvents()

    @Slot(int, QPixmap, str)
    def update_thumbnail_slot(self, index: int, pixmap: QPixmap, path: str):
        label = self.path_to_label_map.get(path)
        if label is None: return

        if not pixmap.isNull():
            label.setPixmap(pixmap) 
            label.setText("") 
            label.setStyleSheet("border: 1px solid #4f545c;")
        else:
            label.setText("Load Error")
            label.setStyleSheet("border: 1px solid #e74c3c; background-color: #4f545c; font-size: 8px;")

    def _cleanup_thumbnail_thread_ref(self):
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None

    def _display_load_complete_message(self):
        image_count = len(self.scan_image_list)
        if image_count > 0:
            QMessageBox.information(
                self, 
                "Scan Complete", 
                f"Finished loading **{image_count}** images from the directory. They are now available in the gallery below.",
                QMessageBox.StandardButton.Ok
            )

    def clear_scan_image_gallery(self):
        if self.current_thumbnail_loader_thread and self.current_thumbnail_loader_thread.isRunning():
            self.current_thumbnail_loader_thread.quit()
        
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None
        self.path_to_label_map = {} 

        while self.scan_thumbnail_layout.count():
            item = self.scan_thumbnail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        
        self.scan_image_list = []

    def handle_scan_error(self, message: str):
        self.clear_scan_image_gallery() 
        QMessageBox.warning(self, "Error Scanning", message)
        ready_label = QLabel("Browse for a directory.")
        ready_label.setAlignment(Qt.AlignCenter)
        ready_label.setStyleSheet("color: #b9bbbe;")
        self.scan_thumbnail_layout.addWidget(ready_label, 0, 0, 1, 1)

    def calculate_columns(self) -> int:
        widget_width = self.scan_thumbnail_widget.width()
        if widget_width <= 0:
            try:
                # Use the width of the containing scroll area/widget if the thumbnail widget hasn't been laid out yet
                widget_width = self.scan_scroll_area.width()
            except AttributeError:
                 widget_width = 800
        
        if widget_width <= 0:
            return 4 
        
        columns = widget_width // self.approx_item_width
        return max(1, columns)

    def collect(self) -> dict:
        """Collect current state (for consistency with other tabs)."""
        return {
            "monitor_queues": self.monitor_slideshow_queues,
            "wallpaper_style": self.wallpaper_style,
            "background_type": self.background_type, # <-- NEW
            "solid_color_hex": self.solid_color_hex, # <-- NEW
        }

    def get_default_config(self) -> Dict[str, Any]:
        """Returns the default configuration dictionary for this tab."""
        # Get the default style from the combo box
        default_style = self.style_combo.itemText(0) if self.style_combo.count() > 0 else "Fill"
        
        return {
            "scan_directory": "",
            "wallpaper_style": default_style,
            "slideshow_enabled": False,
            "interval_minutes": 5,
            "interval_seconds": 0,
            "background_type": "Image", # <-- NEW
            "solid_color_hex": "#000000" # <-- NEW
        }
    
    def set_config(self, config: Dict[str, Any]):
        """Applies a loaded configuration to the tab's UI elements."""
        try:
            if "scan_directory" in config:
                self.scan_directory_path.setText(config.get("scan_directory", ""))
                # Optionally auto-populate if directory is valid
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

            # --- NEW CONFIG LOADING ---
            if "solid_color_hex" in config:
                self.solid_color_hex = config.get("solid_color_hex", "#000000")
                self.solid_color_preview.setStyleSheet(f"background-color: {self.solid_color_hex}; border: 1px solid #4f545c;")
            
            if "background_type" in config:
                # Set background type last to trigger visibility logic
                self.background_type_combo.setCurrentText(config.get("background_type", "Image"))
            # --- END NEW CONFIG LOADING ---

            QMessageBox.information(self, "Config Loaded", "Configuration applied successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Config Error", f"Failed to apply configuration:\n{e}")
