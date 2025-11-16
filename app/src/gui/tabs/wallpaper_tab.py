import os
import platform
import subprocess

from math import floor
from pathlib import Path
from screeninfo import get_monitors, Monitor
from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import Qt, QThreadPool, QThread, QTimer, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox, QComboBox,
    QWidget, QLabel, QPushButton, QMessageBox, QApplication,
    QLineEdit, QFileDialog, QScrollArea, QGridLayout, QSpinBox, QCheckBox, 
)
from .base_tab import BaseTab
from ..windows import SlideshowQueueWindow
from ..components import MonitorDropWidget, DraggableImageLabel
from ..helpers import ImageScannerWorker, BatchThumbnailLoaderWorker, WallpaperWorker
from ..styles.style import apply_shadow_effect, STYLE_SYNC_RUN, STYLE_SYNC_STOP
from ..utils.app_definitions import WALLPAPER_STYLES


class WallpaperTab(BaseTab):
    
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
            return False, 0

        first_length = queue_lengths[0]
        if not all(length == first_length for length in queue_lengths):
            return False, 0
            
        return True, first_length

    @Slot()
    def check_all_monitors_set(self):
        """
        Enables the 'Set Wallpaper' button based on either standard or slideshow mode requirements.
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
        all_set_single = set_count == num_monitors

        is_ready, queue_len = self._is_slideshow_validation_ready()

        if self.slideshow_enabled_checkbox.isChecked():
            if is_ready:
                 self.set_wallpaper_btn.setEnabled(True)
                 self.set_wallpaper_btn.setText(f"Start Slideshow ({queue_len} images per display)")
            else:
                 self.set_wallpaper_btn.setEnabled(False)
                 self.set_wallpaper_btn.setText("Slideshow (Fix image counts)")
                 
        elif all_set_single:
            self.set_wallpaper_btn.setText("Set Wallpaper")
            self.set_wallpaper_btn.setEnabled(True)
        else:
            missing = num_monitors - set_count
            self.set_wallpaper_btn.setText(f"Set Wallpaper ({missing} more)")
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
        
        self.wallpaper_style: str = "Fill" # Default style

        layout = QVBoxLayout(self)
        
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
        layout.addWidget(layout_group)

        # Slideshow Controls Group
        self.slideshow_group = QGroupBox("Slideshow Settings (Per-Monitor Cycle)")
        self.slideshow_group.setStyleSheet(group_box_style)
        slideshow_layout = QHBoxLayout(self.slideshow_group)
        slideshow_layout.setContentsMargins(10, 20, 10, 10)

        # Slideshow Enabled Checkbox
        self.slideshow_enabled_checkbox = QCheckBox("Enable Slideshow")
        self.slideshow_enabled_checkbox.setToolTip("Cycles through dropped images on each monitor. All monitors must have the same number of dropped images.")
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

        layout.addWidget(self.slideshow_group)

        
        # START Combined Settings Group (Wallpaper Style + Scan Directory)
        settings_group = QGroupBox("Settings")
        settings_group.setStyleSheet(group_box_style)
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setContentsMargins(10, 20, 10, 10)
        
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

        style_layout.addWidget(QLabel("Global Style:"))
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
        
        layout.addWidget(settings_group)
        # END Combined Settings Group

        # Thumbnail Gallery Scroll Area
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
        
        layout.addWidget(self.scan_scroll_area, 1)
        
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
        
        layout.addLayout(action_layout)
        
        self.setLayout(layout)

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
            if self.current_wallpaper_worker:
                self.stop_wallpaper_worker()
            else:
                self.run_wallpaper_worker()

    @Slot()
    def start_slideshow(self):
        """Initializes the slideshow queues and starts the timers."""
        
        num_monitors = len(self.monitor_widgets)

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

        self.stop_slideshow() 
        
        for mid in self.monitor_widgets.keys():
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
                                f"Per-monitor slideshow started with {queue_len} images per monitor, cycling every {interval_minutes} minutes and {interval_seconds} seconds.")
        
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
        
        self.monitor_current_index.clear()
        self.time_remaining_sec = 0
        self.countdown_label.setText("Timer: --:--")

        self.slideshow_enabled_checkbox.setChecked(False)
        self.unlock_ui_for_wallpaper()

    @Slot()
    def _cycle_slideshow_wallpaper(self):
        """
        Advances the index for each monitor, applies the new set of images.
        """
        
        monitor_ids = list(self.monitor_widgets.keys())
        if not monitor_ids: return 
        
        n = len(monitor_ids)
        if n == 0:
            self.stop_slideshow()
            return

        current_queue_length = len(self.monitor_slideshow_queues.get(monitor_ids[0], []))
        if current_queue_length == 0:
            self.stop_slideshow()
            return
        
        try:
            new_monitor_paths = {}
            
            for monitor_id in monitor_ids:
                
                current_index = self.monitor_current_index.get(monitor_id, -1)
                queue = self.monitor_slideshow_queues.get(monitor_id, [])

                next_index = (current_index + 1) % current_queue_length
                
                new_monitor_paths[monitor_id] = queue[next_index]
                
                self.monitor_current_index[monitor_id] = next_index
                 
            self.monitor_image_paths = new_monitor_paths
                 
            self.run_wallpaper_worker(slideshow_mode=True)
            
            for monitor_id, path in new_monitor_paths.items():
                 if monitor_id in self.monitor_widgets:
                    self.monitor_widgets[monitor_id].set_image(path)
            
            self.time_remaining_sec = self.interval_sec
            
        except Exception as e:
            QMessageBox.critical(self, "Slideshow Cycle Error", f"Failed to cycle wallpaper: {str(e)}")
            self.stop_slideshow()
    
    @Slot(str)
    def handle_monitor_double_click(self, monitor_id: str):
        """Opens a new non-modal window to display the image queue for the clicked monitor."""
        
        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        monitor_name = self.monitor_widgets[monitor_id].monitor.name
        
        for win in self.open_queue_windows:
            if isinstance(win, SlideshowQueueWindow) and win.monitor_id == monitor_id:
                win.activateWindow()
                return

        window = SlideshowQueueWindow(monitor_name, monitor_id, queue)
        window.setAttribute(Qt.WA_DeleteOnClose)
        
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
        
        self.monitor_current_index[monitor_id] = -1 
        
        new_first_image = new_queue[0] if new_queue else None
        self.monitor_image_paths[monitor_id] = new_first_image
        
        if new_first_image and self.monitor_widgets[monitor_id].image_path != new_first_image:
            self.monitor_widgets[monitor_id].set_image(new_first_image)
        elif not new_first_image:
            self.monitor_widgets[monitor_id].update_text()
        
        self.check_all_monitors_set()


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
        
        self.populate_monitor_layout() 
        
        self.check_all_monitors_set()
        
        columns = self.calculate_columns()
        ready_label = QLabel("Layout Refreshed. Browse for a directory.")
        ready_label.setAlignment(Qt.AlignCenter)
        ready_label.setStyleSheet("color: #b9bbbe;")
        self.scan_thumbnail_layout.addWidget(ready_label, 0, 0, 1, columns)

    
    def populate_monitor_layout(self):
        """
        Clears and recreates the monitor drop widgets.
        Visually displays monitors sorted by their physical X-coordinate (left to right),
        while ensuring the internal assignment uses the correct system priority index.
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

        monitors_to_show = physical_monitors

        if platform.system() == "Windows":
             primary_monitor = next((m for m in system_monitors if m.is_primary), system_monitors[0])
             monitors_to_show = [primary_monitor]
             label = QLabel("Windows only supports one wallpaper across all screens.")
             label.setStyleSheet("color: #7289da;")
             self.monitor_layout.addWidget(label)


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
                print(f"Warning: Could not map physical monitor {monitor.name} to system index.")
                continue

            # The monitor_id is the system's priority index (0, 1, 2, ...), which dictates wallpaper assignment
            monitor_id = str(system_index) 

            drop_widget = MonitorDropWidget(monitor, monitor_id)
            drop_widget.image_dropped.connect(self.on_image_dropped)
            drop_widget.double_clicked.connect(self.handle_monitor_double_click)
            
            current_image = self.monitor_image_paths.get(monitor_id)
            if current_image:
                drop_widget.set_image(current_image)
            
            # Add to the layout in the physical X-axis order
            self.monitor_layout.addWidget(drop_widget)
            self.monitor_widgets[monitor_id] = drop_widget
        
        self.check_all_monitors_set()

    def on_image_dropped(self, monitor_id: str, image_path: str):
        """
        Slot to add the dropped image to the monitor's specific queue, 
        and display the last dropped image for visual confirmation.
        """
        if monitor_id not in self.monitor_slideshow_queues:
            self.monitor_slideshow_queues[monitor_id] = []
        
        self.monitor_slideshow_queues[monitor_id].append(image_path)
        
        self.monitor_image_paths[monitor_id] = image_path
        
        self.monitor_widgets[monitor_id].set_image(image_path)
        
        self.check_all_monitors_set()
        
    def _get_assignment_map(self, source_paths: Dict[str, str]) -> Dict[str, str]:
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
        
    
    def run_wallpaper_worker(self, slideshow_mode=False):
        """
        Initializes and runs the wallpaper worker on a separate thread.
        """
        if self.current_wallpaper_worker:
            print("Wallpaper worker is already running.")
            return

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
        path_map = self._get_assignment_map(self.monitor_image_paths)
        monitors = self.monitors
        
        if not slideshow_mode:
            self.lock_ui_for_wallpaper()
        
        # Pass the selected wallpaper style
        self.current_wallpaper_worker = WallpaperWorker(
            path_map, 
            monitors, 
            wallpaper_style=self.wallpaper_style
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
        self.slideshow_group.setEnabled(False)
        self.scan_scroll_area.setEnabled(False)
        self.scan_directory_path.setEnabled(False) # Disable path field
        self.style_combo.setEnabled(False) # Disable style selection
        QApplication.processEvents()
        
    def unlock_ui_for_wallpaper(self):
        """Unlocks the UI when the manual wallpaper worker is finished."""
        self.set_wallpaper_btn.setText("Set Wallpaper")
        self.set_wallpaper_btn.setStyleSheet(STYLE_SYNC_RUN)
        
        self.refresh_btn.setEnabled(True)
        self.slideshow_group.setEnabled(True)
        self.scan_scroll_area.setEnabled(True)
        self.scan_directory_path.setEnabled(True) # Enable path field
        self.style_combo.setEnabled(True) # Enable style selection
        
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
            if not is_slideshow_active:
                QMessageBox.information(self, "Success", "Wallpaper has been updated!")
                
                for monitor_id, path in self.monitor_image_paths.items():
                    if path and monitor_id in self.monitor_widgets:
                        self.monitor_widgets[monitor_id].set_image(path)
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
            try:
                widget_width = self.scan_thumbnail_widget.parentWidget().width()
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
        }
