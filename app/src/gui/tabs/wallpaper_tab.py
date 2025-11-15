import os
import ctypes
import platform
import subprocess
if platform.system() == "Windows": import winreg

from PIL import Image
from math import floor
from pathlib import Path
from screeninfo import get_monitors, Monitor
from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import Qt, QThreadPool, QThread, QTimer, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox,
    QWidget, QLabel, QPushButton, QMessageBox, QApplication,
    QLineEdit, QFileDialog, QScrollArea, QGridLayout, QSpinBox, QCheckBox, 
)
from .base_tab import BaseTab
from ..windows import SlideshowQueueWindow
from ..components import MonitorDropWidget, DraggableImageLabel
from ..helpers import ImageScannerWorker, BatchThumbnailLoaderWorker
from ..styles.style import apply_shadow_effect


class WallpaperTab(BaseTab):
    
    # --- CORE METHODS MOVED TO TOP FOR INITIALIZATION SAFETY ---

    @Slot()
    def _is_slideshow_validation_ready(self) -> Tuple[bool, int]:
        """
        Checks if slideshow preconditions are met: all active monitors must have 
        the same, non-zero number of images in their queue.
        Returns (is_ready, queue_length).
        """
        monitor_ids = list(self.monitor_widgets.keys())
        num_monitors = len(monitor_ids)
        
        if num_monitors == 0:
            return False, 0
            
        queue_lengths = [len(self.monitor_slideshow_queues.get(mid, [])) for mid in monitor_ids]
        
        if not all(length > 0 for length in queue_lengths):
            # One or more queues are empty
            return False, 0

        first_length = queue_lengths[0]
        if not all(length == first_length for length in queue_lengths):
            # Not all queue lengths are equal
            return False, 0
            
        return True, first_length

    @Slot()
    def check_all_monitors_set(self):
        """
        Enables the 'Set Wallpaper' button based on either standard or slideshow mode requirements.
        """
        
        if self.slideshow_timer and self.slideshow_timer.isActive():
             return

        if self.set_wallpaper_btn.text() in ["Missing Pillow", "Missing screeninfo", "Missing Helpers"]:
             return
            
        target_monitor_ids = list(self.monitor_widgets.keys())
        num_monitors = len(target_monitor_ids)
        
        # Check standard single-image requirement
        set_count = sum(1 for mid in target_monitor_ids if mid in self.monitor_image_paths and self.monitor_image_paths[mid])
        all_set_single = set_count == num_monitors

        is_ready, queue_len = self._is_slideshow_validation_ready()

        if self.slideshow_enabled_checkbox.isChecked():
            # Slideshow mode active
            if is_ready:
                 self.set_wallpaper_btn.setEnabled(True)
                 self.set_wallpaper_btn.setText(f"Start Slideshow ({queue_len} images per display)")
            else:
                 self.set_wallpaper_btn.setEnabled(False)
                 self.set_wallpaper_btn.setText("Slideshow (Fix image counts)")
                 
        elif all_set_single:
            # Standard mode ready
            self.set_wallpaper_btn.setText("Set Wallpaper")
            self.set_wallpaper_btn.setEnabled(True)
        else:
            # Standard mode waiting
            missing = num_monitors - set_count
            self.set_wallpaper_btn.setText(f"Set Wallpaper ({missing} more)")
            self.set_wallpaper_btn.setEnabled(False)

    # --- END CORE METHODS ---


    def __init__(self, db_tab_ref, dropdown=True): # Keep signature consistent
        super().__init__()
        self.db_tab_ref = db_tab_ref
        
        self.monitors: List[Monitor] = []
        self.monitor_widgets: Dict[str, MonitorDropWidget] = {}
        
        # FIX: Initialize all required dictionaries here
        self.monitor_image_paths: Dict[str, str] = {}
        self.monitor_slideshow_queues: Dict[str, List[str]] = {} 
        self.monitor_current_index: Dict[str, int] = {}
        
        # --- Slideshow State ---
        self.slideshow_timer: Optional[QTimer] = None
        self.countdown_timer: Optional[QTimer] = None
        self.time_remaining_sec: int = 0
        self.interval_sec: int = 0
        self.open_queue_windows: List[QWidget] = [] 
        
        layout = QVBoxLayout(self)
        
        # --- Monitor Layout Group ---
        layout_group = QGroupBox("Monitor Layout (Drop images here, double-click to see queue)")
        layout_group.setStyleSheet("""
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
        """)
        
        self.monitor_layout_container = QWidget()
        self.monitor_layout = QHBoxLayout(self.monitor_layout_container)
        self.monitor_layout.setSpacing(15)
        self.monitor_layout.setAlignment(Qt.AlignCenter)
        
        layout_group.setLayout(self.monitor_layout)
        layout.addWidget(layout_group)

        # --- Slideshow Controls Group (UPDATED FOR SECONDS) ---
        self.slideshow_group = QGroupBox("Slideshow Settings (Per-Monitor Cycle)")
        self.slideshow_group.setStyleSheet(layout_group.styleSheet())
        slideshow_layout = QHBoxLayout(self.slideshow_group)
        slideshow_layout.setContentsMargins(10, 20, 10, 10)

        # Slideshow Enabled Checkbox
        self.slideshow_enabled_checkbox = QCheckBox("Enable Slideshow")
        self.slideshow_enabled_checkbox.setToolTip("Cycles through dropped images on each monitor. All monitors must have the same number of dropped images.")
        slideshow_layout.addWidget(self.slideshow_enabled_checkbox)

        # Interval Spinboxes (Minutes and Seconds)
        slideshow_layout.addWidget(QLabel("Interval:"))
        
        # Minutes Spinbox
        self.interval_min_spinbox = QSpinBox()
        self.interval_min_spinbox.setRange(0, 60)
        self.interval_min_spinbox.setValue(5) # Default 5 minutes
        self.interval_min_spinbox.setFixedWidth(50)
        slideshow_layout.addWidget(self.interval_min_spinbox)
        slideshow_layout.addWidget(QLabel("min"))

        # Seconds Spinbox
        self.interval_sec_spinbox = QSpinBox()
        self.interval_sec_spinbox.setRange(0, 59) # Range 0 to 59 seconds
        self.interval_sec_spinbox.setValue(0) 
        self.interval_sec_spinbox.setFixedWidth(50)
        slideshow_layout.addWidget(self.interval_sec_spinbox)
        slideshow_layout.addWidget(QLabel("sec"))

        slideshow_layout.addStretch(1)
        
        # Countdown Label (New UI element)
        self.countdown_label = QLabel("Timer: --:--")
        self.countdown_label.setStyleSheet("color: #2ecc71; font-weight: bold; font-size: 14px;")
        self.countdown_label.setFixedWidth(100)
        slideshow_layout.addWidget(self.countdown_label)

        layout.addWidget(self.slideshow_group)
        # -------------------------------------

        # --- NEW: Scan Directory Section ---
        scan_group = QGroupBox("Scan Directory (Image Source)")
        scan_group.setStyleSheet("""
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
        """)
        
        scan_layout = QVBoxLayout()
        scan_layout.setContentsMargins(10, 20, 10, 10) 
        
        # Directory path selection
        scan_dir_layout = QHBoxLayout()
        self.scan_directory_path = QLineEdit()
        self.scan_directory_path.setPlaceholderText("Select directory to scan...")
        btn_browse_scan = QPushButton("Browse...")
        btn_browse_scan.clicked.connect(self.browse_scan_directory)
        apply_shadow_effect(btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3)

        scan_dir_layout.addWidget(self.scan_directory_path)
        scan_dir_layout.addWidget(btn_browse_scan)
        scan_layout.addLayout(scan_dir_layout)
        
        scan_group.setLayout(scan_layout)
        layout.addWidget(scan_group)

        # --- NEW: Thumbnail Gallery Scroll Area ---
        self.thumbnail_size = 150
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width

        self.scan_scroll_area = QScrollArea() 
        self.scan_scroll_area.setWidgetResizable(True)
        self.scan_scroll_area.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")

        self.scan_thumbnail_widget = QWidget()
        self.scan_thumbnail_widget.setStyleSheet("QWidget { background-color: #2c2f33; }")

        self.scan_thumbnail_layout = QGridLayout(self.scan_thumbnail_widget)
        self.scan_thumbnail_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        
        self.scan_scroll_area.setWidget(self.scan_thumbnail_widget)
        
        layout.addWidget(self.scan_scroll_area, 1) # Give this stretch
        
        # --- Action Buttons (Original) ---
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)
        
        self.refresh_btn = QPushButton("Refresh Layout")
        self.refresh_btn.setStyleSheet("background-color: #f1c40f; color: black; padding: 10px; border-radius: 8px; font-weight: bold;")
        apply_shadow_effect(self.refresh_btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.refresh_btn.clicked.connect(self.handle_refresh_layout)
        action_layout.addWidget(self.refresh_btn)
        
        self.set_wallpaper_btn = QPushButton("Set Wallpaper")
        self.set_wallpaper_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white; font-weight: bold; font-size: 16px;
                padding: 14px; border-radius: 10px; min-height: 44px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #764ba2, stop:1 #667eea); }
            QPushButton:disabled { background: #4f545c; color: #a0a000; }
            QPushButton:pressed { background: #5a67d8; }
        """)
        apply_shadow_effect(self.set_wallpaper_btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.set_wallpaper_btn.clicked.connect(self.handle_set_wallpaper_click)
        action_layout.addWidget(self.set_wallpaper_btn, 1) # Give it stretch
        
        layout.addLayout(action_layout)
        
        self.setLayout(layout)

        # --- NEW: State for scanner ---
        self.threadpool = QThreadPool.globalInstance()
        self.scanned_dir = None
        try:
            base_dir = Path.cwd()
            while base_dir.name != 'Image-Toolkit' and base_dir.parent != base_dir:
                base_dir = base_dir.parent
            if base_dir.name == 'Image-Toolkit':
                self.last_browsed_scan_dir = str(base_dir / 'data')
            else:
                self.last_browsed_scan_dir = str(Path.cwd() / 'data')
        except Exception:
             self.last_browsed_scan_dir = os.getcwd() 
        
        self.scan_image_list: list[str] = []
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None
        self.path_to_label_map = {}
        
        # Initial setup (Original)
        self.populate_monitor_layout()
        self.check_dependencies()
        self.check_all_monitors_set()
        self.stop_slideshow()

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
        if self.slideshow_timer and self.slideshow_timer.isActive():
            self.stop_slideshow()
        elif self.slideshow_enabled_checkbox.isChecked():
            self.start_slideshow()
        else:
            self.stop_slideshow()
            self.set_wallpaper()

    @Slot()
    def start_slideshow(self):
        """Initializes the slideshow queues and starts the timers."""
        
        num_monitors = len(self.monitor_widgets)

        # 1. Validation check for equal queue length
        is_ready, queue_len = self._is_slideshow_validation_ready()
        
        if num_monitors == 0:
            QMessageBox.warning(self, "Slideshow Error", "No monitors detected or configured.")
            self.slideshow_enabled_checkbox.setChecked(False)
            return
            
        if not is_ready:
            QMessageBox.critical(self, "Slideshow Error", 
                                 "To start the slideshow, all monitors must have the EXACT same, non-zero number of images dropped on them.")
            self.slideshow_enabled_checkbox.setChecked(False)
            return

        # 2. Stop any existing timer
        self.stop_slideshow() 
        
        # 3. Initialize current index for all monitors to -1 (so first cycle increments to 0)
        for mid in self.monitor_widgets.keys():
            self.monitor_current_index[mid] = -1 

        # 4. Calculate interval and initialize timers
        interval_minutes = self.interval_min_spinbox.value()
        interval_seconds = self.interval_sec_spinbox.value()
        
        # Calculate total seconds
        self.interval_sec = (interval_minutes * 60) + interval_seconds
        
        if self.interval_sec <= 0: # Ensure a non-zero interval
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
                                f"Per-monitor slideshow started with {queue_len} images per monitor, cycling every {interval_minutes} minutes and {interval_seconds} seconds.")
        
        # Immediately set the first set of wallpapers (index 0)
        self._cycle_slideshow_wallpaper()

        # Update button text to reflect the running state
        self.set_wallpaper_btn.setText(f"Slideshow Running (Stop)")
        self.set_wallpaper_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; /* Red color for stop */
                color: white; font-weight: bold; font-size: 16px;
                padding: 14px; border-radius: 10px; min-height: 44px;
            }
            QPushButton:hover { background-color: #c0392b; }
            QPushButton:disabled { background: #718096; }
            QPushButton:pressed { background: #a52a2a; }
        """)
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

        # Close any open queue windows
        for win in list(self.open_queue_windows):
            if win.isVisible():
                win.close()
        self.open_queue_windows.clear()
        
        # Reset slideshow-specific state
        self.monitor_current_index.clear()
        self.time_remaining_sec = 0
        self.countdown_label.setText("Timer: --:--")

        # Reset UI
        self.slideshow_enabled_checkbox.setChecked(False)
        self.set_wallpaper_btn.setText("Set Wallpaper")
        self.set_wallpaper_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white; font-weight: bold; font-size: 16px;
                padding: 14px; border-radius: 10px; min-height: 44px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #764ba2, stop:1 #667eea); }
            QPushButton:disabled { background: #4f545c; color: #a0a000; }
            QPushButton:pressed { background: #5a67d8; }
        """)
        self.check_all_monitors_set() 

    @Slot()
    def _cycle_slideshow_wallpaper(self):
        """Advances the index for each monitor and applies the new set of images."""
        
        monitor_ids = list(self.monitor_widgets.keys())
        if not monitor_ids: return 
        
        current_queue_length = len(self.monitor_slideshow_queues.get(monitor_ids[0], []))
        
        try:
            # 1. Update the current image path dictionary and advance index
            new_monitor_paths = {}
            
            for monitor_id in monitor_ids:
                
                # Get current index and queue
                current_index = self.monitor_current_index.get(monitor_id, -1)
                queue = self.monitor_slideshow_queues.get(monitor_id, [])

                # Determine next index (cycle back to 0 if max queue length reached)
                next_index = (current_index + 1) % current_queue_length
                
                # Assign the image path based on the new index
                new_monitor_paths[monitor_id] = queue[next_index]
                
                # Update the index tracker
                self.monitor_current_index[monitor_id] = next_index
                 
            # 2. Update the monitor_image_paths storage (used by set_wallpaper)
            self.monitor_image_paths = new_monitor_paths
                 
            # 3. Apply the wallpaper and update visual drop zones (if possible)
            self.set_wallpaper(slideshow_mode=True)
            for monitor_id, path in new_monitor_paths.items():
                 self.monitor_widgets[monitor_id].set_image(path)
            
            # 4. Reset the countdown timer
            self.time_remaining_sec = self.interval_sec
            
        except Exception as e:
            QMessageBox.critical(self, "Slideshow Cycle Error", f"Failed to cycle wallpaper: {str(e)}")
            self.stop_slideshow()
    
    @Slot(str)
    def handle_monitor_double_click(self, monitor_id: str):
        """Opens a new non-modal window to display the image queue for the clicked monitor."""
        
        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        monitor_name = self.monitor_widgets[monitor_id].monitor.name
        
        # Check if a window for this monitor is already open
        for win in self.open_queue_windows:
            if isinstance(win, SlideshowQueueWindow) and win.monitor_id == monitor_id:
                win.activateWindow()
                return

        # Pass the current monitor ID to the window for callback purposes
        window = SlideshowQueueWindow(monitor_name, monitor_id, queue)
        window.setAttribute(Qt.WA_DeleteOnClose)
        
        # Connect the signal from the window to a slot in this class
        window.queue_reordered.connect(self.on_queue_reordered)
        
        def remove_closed_win(event):
            if window in self.open_queue_windows:
                 self.open_queue_windows.remove(window)
            event.accept()

        window.closeEvent = remove_closed_win
        
        window.show()
        self.open_queue_windows.append(window)

    @Slot(str, list)
    def on_queue_reordered(self, monitor_id: str, new_queue: List[str]):
        """Slot to receive the updated queue from the SlideshowQueueWindow."""
        self.monitor_slideshow_queues[monitor_id] = new_queue
        
        # Reset the index for this monitor to ensure it starts from the new top
        self.monitor_current_index[monitor_id] = -1 
        
        # Update the currently displayed image path
        new_first_image = new_queue[0] if new_queue else None
        self.monitor_image_paths[monitor_id] = new_first_image
        
        # Update the visual drop widget
        if new_first_image and self.monitor_widgets[monitor_id].image_path != new_first_image:
            self.monitor_widgets[monitor_id].set_image(new_first_image)
        elif not new_first_image:
            self.monitor_widgets[monitor_id].update_text()
        
        # The following line was removed to stop the popup:
        # monitor_name = self.monitor_widgets[monitor_id].monitor.name
        # QMessageBox.information(self, "Queue Updated", f"Queue order for {monitor_name} has been updated.")
        
        # Re-check slideshow readiness (important if the queue became empty or uneven)
        self.check_all_monitors_set()


    # --- MODIFIED: Refresh Layout Handler ---
    @Slot()
    def handle_refresh_layout(self):
        """
        Refreshes monitor layout, clears dropped images, clears the scanned gallery,
        and resets the scanned directory path.
        """
        self.stop_slideshow() 
        
        # Clear all state related to dropped/scanned images
        self.monitor_slideshow_queues.clear()
        self.monitor_current_index.clear()
        self.monitor_image_paths.clear() 
        
        self.scan_directory_path.clear()
        self.scanned_dir = None
        self.scan_image_list = []
        
        self.clear_scan_image_gallery() 
        
        self.populate_monitor_layout() 
        
        self.check_all_monitors_set()
        
        columns = self.calculate_columns()
        ready_label = QLabel("Layout Refreshed. Browse for a directory.")
        ready_label.setAlignment(Qt.AlignCenter)
        ready_label.setStyleSheet("color: #b9bbbe;")
        self.scan_thumbnail_layout.addWidget(ready_label, 0, 0, 1, columns)

    # --- check_dependencies Method (Unchanged) ---
    def check_dependencies(self):
        """Checks for external dependencies and OS support."""
        
        if Image is None:
            QMessageBox.warning(self, "Missing Dependency",
                                "The 'Pillow' (PIL) library is not installed.\n"
                                "Cannot load or resize images.\n"
                                "Please run: pip install Pillow")
            self.set_wallpaper_btn.setEnabled(False)
            self.set_wallpaper_btn.setText("Missing Pillow")
        
        elif "Mock" in get_monitors()[0].name:
             QMessageBox.warning(self, "Missing Dependency",
                                "The 'screeninfo' library is not installed or failed to load.\n"
                                "Cannot detect monitor layout.\n"
                                "Please run: pip install screeninfo")
             self.set_wallpaper_btn.setEnabled(False)
             self.set_wallpaper_btn.setText("Missing screeninfo")
        
        elif ImageScannerWorker is None:
             QMessageBox.warning(self, "Missing Helpers",
                                "The ImageScannerWorker or BatchThumbnailLoaderWorker could not be imported.\n"
                                "Directory scanning will be disabled.")
             
        # Enable the button if all checks passed
        if not self.set_wallpaper_btn.text() in ["Missing Pillow", "Missing screeninfo", "Missing Helpers"]:
             self.set_wallpaper_btn.setText("Set Wallpaper")
             self.set_wallpaper_btn.setEnabled(True) 

    
    # --- populate_monitor_layout Method (Modified to connect double-click) ---
    def populate_monitor_layout(self):
        """
        Clears and recreates the monitor drop widgets based on
        the current system monitor layout, showing only one for Windows.
        """
        # Clear existing layout
        for i in reversed(range(self.monitor_layout.count())): 
            widget = self.monitor_layout.takeAt(i).widget()
            if widget is not None:
                widget.deleteLater()
        self.monitor_widgets.clear()
        
        try:
            # Sort by x-position to match left-to-right visual order
            self.monitors = sorted(get_monitors(), key=lambda m: m.x) 
        except Exception as e:
             QMessageBox.critical(self, "Error", f"Could not get monitor info: {e}")
             self.monitors = []
             
        if not self.monitors or "Mock" in self.monitors[0].name:
            self.monitor_layout.addWidget(QLabel("Could not detect any monitors.\nIs 'screeninfo' installed?"))
            return

        monitors_to_show = self.monitors

        # CHECK 1: If Windows, only show the first monitor
        if platform.system() == "Windows":
             monitors_to_show = [self.monitors[0]]
             label = QLabel("Windows only supports one wallpaper across all screens.")
             label.setStyleSheet("color: #7289da;")
             self.monitor_layout.addWidget(label)


        for i, monitor in enumerate(monitors_to_show):
            monitor_index_in_original_list = self.monitors.index(monitor)
            monitor_id = str(monitor_index_in_original_list + 1) 

            drop_widget = MonitorDropWidget(monitor, monitor_id)
            # Connect single-click to standard drop/set logic
            drop_widget.image_dropped.connect(self.on_image_dropped)
            
            # Connect double-click to open queue window
            drop_widget.double_clicked.connect(self.handle_monitor_double_click)
            
            # Restore image path if available (use the current displayed image path)
            current_image = self.monitor_image_paths.get(monitor_id)
            if current_image:
                drop_widget.set_image(current_image)
            
            self.monitor_layout.addWidget(drop_widget)
            self.monitor_widgets[monitor_id] = drop_widget
        
        self.check_all_monitors_set()

    # MODIFIED: on_image_dropped now manages the image queue
    def on_image_dropped(self, monitor_id: str, image_path: str):
        """
        Slot to add the dropped image to the monitor's specific queue, 
        and display the last dropped image for visual confirmation.
        """
        if monitor_id not in self.monitor_slideshow_queues:
            self.monitor_slideshow_queues[monitor_id] = []
        
        # Add the new path to the queue
        self.monitor_slideshow_queues[monitor_id].append(image_path)
        
        # For immediate visual feedback (non-slideshow mode)
        self.monitor_image_paths[monitor_id] = image_path
        
        # Update the visual drop zone to show the latest image
        self.monitor_widgets[monitor_id].set_image(image_path)
        
        # Update button text to show queue count
        self.check_all_monitors_set()
        
    # --- set_wallpaper Method (Unchanged logic for setting wallpaper from self.monitor_image_paths) ---
    def set_wallpaper(self, slideshow_mode=False):
        """
        Applies a different image to each monitor based on self.monitor_image_paths.
        """
        target_monitor_ids = list(self.monitor_widgets.keys()) 
        required_image_paths = [self.monitor_image_paths.get(mid) for mid in target_monitor_ids]
        valid_image_paths = [p for p in required_image_paths if p]
        
        if not slideshow_mode and len(valid_image_paths) != len(target_monitor_ids):
            QMessageBox.warning(self, "Incomplete", "Not all monitors have valid images assigned.")
            return

        if not slideshow_mode:
             self.set_wallpaper_btn.setEnabled(False)
             self.set_wallpaper_btn.setText("Applying...")
             QApplication.processEvents() 
        
        try:
            if platform.system() == "Windows":
                 # --- Windows Implementation (Single Wallpaper enforced) ---
                 if not valid_image_paths: return
                 single_image_path = valid_image_paths[0] 
                 save_path = str(Path(single_image_path).resolve())

                 if not slideshow_mode:
                     QMessageBox.information(self, "Windows Note", "Windows only supports a single wallpaper file via this tool.")
                 
                 key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                      "Control Panel\\Desktop", 0, winreg.KEY_SET_VALUE)
                 winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, "4") 
                 winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "0") 
                 winreg.CloseKey(key)

                 SPI_SETDESKWALLPAPER = 20
                 SPIF_UPDATEINIFILE = 0x01
                 SPIF_SENDWININICHANGE = 0x02
                 
                 ctypes.windll.user32.SystemParametersInfoW(
                     SPI_SETDESKWALLPAPER, 
                     0, 
                     save_path, 
                     SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE
                 )
                    
            elif platform.system() == "Linux":
                
                # --- Linux (KDE) Implementation (Per-Monitor) ---
                try:
                    subprocess.run(["which", "qdbus6"], check=True, capture_output=True)
                    
                    script_parts = []
                    for i, path in enumerate(valid_image_paths):
                        file_uri = f"file://{Path(path).resolve()}"
                        script_parts.append(
                            f'd = desktops()[{i}]; d.currentConfigGroup = Array("Wallpaper", "org.kde.image", "General"); d.writeConfig("Image", "{file_uri}"); d.writeConfig("FillMode", 1);'
                        )
                        
                    full_script = "".join(script_parts)
                    
                    if script_parts:
                         full_script += "d.reloadConfig();"

                    qdbus_command = (
                        f"qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript '{full_script}'"
                    )

                    subprocess.run(qdbus_command, shell=True, check=True, capture_output=True, text=True)
                    
                    if not slideshow_mode:
                        QMessageBox.information(self, "KDE Note", "Wallpaper configuration updated. The desktop should refresh shortly.")
                    
                except FileNotFoundError:
                    # --- Linux (GNOME/Other) Fallback (Spanned, stitches all images) ---
                    if not slideshow_mode:
                        QMessageBox.warning(self, "Linux Note", "KDE Plasma ('qdbus6') not detected. Falling back to GNOME 'spanned' method.")
                    
                    total_width = sum(m.width for m in self.monitors)
                    max_height = max(m.height for m in self.monitors)
                    spanned_image = Image.new('RGB', (total_width, max_height))
                    
                    current_x = 0
                    for i, monitor in enumerate(self.monitors):
                        if i < len(valid_image_paths):
                            img = Image.open(valid_image_paths[i])
                            img = img.resize((monitor.width, monitor.height), Image.Resampling.LANCZOS)
                            spanned_image.paste(img, (current_x, 0))
                            current_x += img.width

                    home_dir = os.path.expanduser('~')
                    save_path = os.path.join(home_dir, ".spanned_wallpaper.jpg")
                    spanned_image.save(save_path, "JPEG", quality=95)
                    file_uri = f"file://{save_path}"

                    subprocess.run(
                        ["gsettings", "set", "org.gnome.desktop.background", "picture-options", "spanned"],
                        check=True, capture_output=True, text=True
                    )
                    subprocess.run(
                        ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", file_uri],
                        check=True, capture_output=True, text=True
                    )
                    subprocess.run(
                        ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", file_uri],
                        check=True, capture_output=True, text=True
                    )
                except subprocess.CalledProcessError as e:
                    error_message = f"Failed to set wallpaper on Linux.\nError: {e.stderr}"
                    QMessageBox.critical(self, "Error", error_message)
                    raise
                
            else:
                 if not slideshow_mode:
                    QMessageBox.warning(self, "Unsupported OS", 
                                     f"Wallpaper setting for {platform.system()} is not supported.")
                 return

            if not slideshow_mode:
                QMessageBox.information(self, "Success", "Wallpaper has been updated!")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {str(e)}")
        
        finally:
            if not slideshow_mode:
                self.check_all_monitors_set()

    # --- Other Methods (Scan and Gallery Unchanged) ---
    def browse_scan_directory(self):
        """Select directory to scan and display image thumbnails."""
        if ImageScannerWorker is None:
            self.check_dependencies()
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

    def _create_thumbnail_placeholder(self, index: int, path: str):
        columns = self.calculate_columns()
        row = index // columns
        col = index % columns
        draggable_label = DraggableImageLabel(path, self.thumbnail_size) 
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
            widget_width = self.scan_thumbnail_widget.parentWidget().width()
        
        if widget_width <= 0:
            return 4 
        
        columns = widget_width // self.approx_item_width
        return max(1, columns)

    # --- Original collect() method (Unchanged) ---
    def collect(self) -> dict:
        """Collect current state (for consistency with other tabs)."""
        return {
            "monitor_queues": self.monitor_slideshow_queues,
        }
