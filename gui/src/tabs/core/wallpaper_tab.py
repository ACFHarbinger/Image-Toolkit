import os
import sys
import cv2
import json
import shutil
import platform
import subprocess

from pathlib import Path
from screeninfo import get_monitors, Monitor
from typing import Dict, List, Optional, Tuple, Any
from PySide6.QtCore import (
    Qt,
    QThreadPool,
    QThread,
    QTimer,
    Slot,
    QPoint,
    QEvent,
    QRect,
)
from PySide6.QtGui import QPixmap, QAction, QColor, QImage, QCursor
from PySide6.QtWidgets import (
    QGroupBox,
    QComboBox,
    QMenu,
    QWidget,
    QLabel,
    QPushButton,
    QGridLayout,
    QSpinBox,
    QHBoxLayout,
    QLineEdit,
    QFileDialog,
    QScrollArea,
    QMessageBox,
    QApplication,
    QColorDialog,
    QVBoxLayout,
)
from ...classes import AbstractClassSingleGallery
from ...helpers import ImageScannerWorker, WallpaperWorker, VideoScannerWorker
from ...windows import SlideshowQueueWindow, ImagePreviewWindow
from ...components import (
    MonitorDropWidget,
    DraggableLabel,
    MarqueeScrollArea,
    DraggableMonitorContainer,
)
from ...styles.style import apply_shadow_effect, STYLE_START_ACTION, STYLE_STOP_ACTION
from backend.src.utils.definitions import (
    WALLPAPER_STYLES,
    SUPPORTED_VIDEO_FORMATS,
    DAEMON_CONFIG_PATH,
    ROOT_DIR,
)
from backend.src.core import WallpaperManager


class WallpaperTab(AbstractClassSingleGallery):

    @Slot()
    def _is_slideshow_validation_ready(self) -> Tuple[bool, int]:
        monitor_ids = list(self.monitor_widgets.keys())
        if not monitor_ids:
            return False, 0
        total_images = 0
        all_queues_empty = True
        for mid in monitor_ids:
            queue_len = len(self.monitor_slideshow_queues.get(mid, []))
            if queue_len > 0:
                all_queues_empty = False
            total_images += queue_len
        return not all_queues_empty, total_images

    def _start_daemon_countdown_if_active(self):
        if self._is_daemon_running_config():
            try:
                with open(DAEMON_CONFIG_PATH, "r") as f:
                    data = json.load(f)
                    self.interval_sec = data.get("interval_seconds", 300)
                    self.time_remaining_sec = self.interval_sec
                    
                    if not hasattr(self, "countdown_timer") or not self.countdown_timer:
                        self.countdown_timer = QTimer(self)
                        self.countdown_timer.timeout.connect(self.update_countdown)
                    
                    if not self.countdown_timer.isActive():
                        self.countdown_timer.start(1000)
            except:
                pass

    @Slot()
    def check_all_monitors_set(self):
        if self.slideshow_timer and self.slideshow_timer.isActive():
            return
        if self.current_wallpaper_worker:
            return
        self.set_wallpaper_btn.setStyleSheet(STYLE_START_ACTION)
        target_monitor_ids = list(self.monitor_widgets.keys())
        num_monitors = len(target_monitor_ids)
        set_count = sum(
            1
            for mid in target_monitor_ids
            if mid in self.monitor_image_paths and self.monitor_image_paths[mid]
        )
        is_ready, total_images = self._is_slideshow_validation_ready()

        if self.background_type == "Solid Color":
            self.set_wallpaper_btn.setText(f"Set Solid Color ({self.solid_color_hex})")
            self.set_wallpaper_btn.setEnabled(num_monitors > 0)
            return

        if self.background_type == "Slideshow":
            if is_ready:
                self.set_wallpaper_btn.setEnabled(True)
                self.set_wallpaper_btn.setText(
                    f"Start Slideshow ({total_images} total items)"
                )
            else:
                self.set_wallpaper_btn.setEnabled(False)
                self.set_wallpaper_btn.setText("Slideshow (Drop images/videos)")

        elif self.background_type == "Smart Video Wallpaper":
            if is_ready:
                self.set_wallpaper_btn.setText(
                    f"Start Video Slideshow ({total_images} items)"
                )
                self.set_wallpaper_btn.setEnabled(True)
            else:
                self.set_wallpaper_btn.setText("Set Video (0 items)")
                self.set_wallpaper_btn.setEnabled(False)

        elif set_count > 0:
            self.set_wallpaper_btn.setText("Set Wallpaper")
            self.set_wallpaper_btn.setEnabled(True)
        else:
            self.set_wallpaper_btn.setText("Set Wallpaper (0 items)")
            self.set_wallpaper_btn.setEnabled(False)

    def __init__(self, db_tab_ref):
        super().__init__()
        self.db_tab_ref = db_tab_ref
        if os.environ.get("DESKTOP_SESSION", "").lower() in ["plasma", "kde"]:
            try:
                if shutil.which("qdbus6"):
                    self.qdbus = "qdbus6"
                elif shutil.which("qdbus"):
                    self.qdbus = "qdbus"
                else:
                    self.qdbus = None
                    print("Warning: qdbus not found.")
            except Exception:
                self.qdbus = None
        else:
            self.qdbus = None

        self.monitors: List[Monitor] = []
        self.monitor_widgets: Dict[str, MonitorDropWidget] = {}

        self.monitor_image_paths: Dict[str, str] = {}
        self.monitor_slideshow_queues: Dict[str, List[str]] = {}
        self.monitor_current_index: Dict[str, int] = {}

        self._initial_pixmap_cache: Dict[str, QPixmap] = {}

        self.current_wallpaper_worker: Optional[WallpaperWorker] = None

        self.slideshow_timer: Optional[QTimer] = None
        self.countdown_timer: Optional[QTimer] = None
        self.time_remaining_sec: int = 0
        self.interval_sec: int = 0
        self.open_queue_windows: List[QWidget] = []
        self.open_image_preview_windows: List[QWidget] = []

        self.wallpaper_style: str = "Fill"
        self.video_style: str = "Scaled and Cropped"  # Default for video
        self.background_type: str = "Image"
        self.solid_color_hex: str = "#000000"

        self.img_scanner_worker: Optional[Any] = None
        self.img_scanner_thread: Optional[QThread] = None
        self.vid_scanner_worker: Optional[VideoScannerWorker] = None

        self.scanned_dir = None
        self.path_to_label_map = {}
        self._filtering_event = False

        # --- FIX: Debounce pagination updates to avoid OOM from millions of QActions ---
        self._pagination_debounce_timer = QTimer()
        self._pagination_debounce_timer.setSingleShot(True)
        self._pagination_debounce_timer.setInterval(200) # 200ms debounce
        self._pagination_debounce_timer.timeout.connect(self._update_pagination_ui)

        self.pagination_widget = self.create_pagination_controls()

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        self.main_scroll_area = QScrollArea()
        self.main_scroll_area.setWidgetResizable(True)
        self.main_scroll_area.setWidget(content_widget)

        # Install global event filter to handle wheel and autoscrolling during drag
        QApplication.instance().installEventFilter(self)
        self.main_scroll_area.viewport().setAcceptDrops(True)

        main_tab_layout = QVBoxLayout(self)
        main_tab_layout.setContentsMargins(0, 0, 0, 0)
        main_tab_layout.addWidget(self.main_scroll_area)
        self.setLayout(main_tab_layout)

        # Enable drops to handle autoscrolling during drag
        self.setAcceptDrops(True)

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

        layout_group = QGroupBox(
            "Monitor Layout (Drag to Reorder, Drop images/videos to set)"
        )
        layout_group.setStyleSheet(group_box_style)

        self.monitor_layout_container = DraggableMonitorContainer()
        # self.monitor_layout is deprecated; communicate with container directly

        gb_layout = QVBoxLayout(layout_group)
        gb_layout.addWidget(self.monitor_layout_container)

        content_layout.addWidget(layout_group)

        settings_group = QGroupBox("Wallpaper Settings")
        settings_group.setStyleSheet(group_box_style)
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setContentsMargins(10, 20, 10, 10)

        background_type_layout = QHBoxLayout()
        self.background_type_combo = QComboBox()
        self.background_type_combo.addItems(
            ["Image", "Slideshow", "Smart Video Wallpaper", "Solid Color"]
        )
        self.background_type_combo.setCurrentText(self.background_type)
        self.background_type_combo.currentTextChanged.connect(
            self._update_background_type
        )

        background_type_layout.addWidget(QLabel("Background Type:"))
        background_type_layout.addWidget(self.background_type_combo)
        background_type_layout.addStretch(1)
        settings_layout.addLayout(background_type_layout)

        self.slideshow_group = QWidget()
        slideshow_layout = QHBoxLayout(self.slideshow_group)
        slideshow_layout.setContentsMargins(0, 10, 0, 10)

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
        self.countdown_label.setStyleSheet(
            "color: #2ecc71; font-weight: bold; font-size: 14px;"
        )
        self.countdown_label.setFixedWidth(100)
        slideshow_layout.addWidget(self.countdown_label)

        # Add Daemon Button
        self.btn_daemon_toggle = QPushButton("Start Background Daemon")
        self.btn_daemon_toggle.setCheckable(True)
        self.btn_daemon_toggle.clicked.connect(self.toggle_slideshow_daemon)
        self.btn_daemon_toggle.setStyleSheet(
            "background-color: #2c3e50; color: white; padding: 5px;"
        )
        slideshow_layout.addWidget(self.btn_daemon_toggle)

        # Check initial state
        if self._is_daemon_running_config():
            self.btn_daemon_toggle.setText("Stop Background Daemon")
            self.btn_daemon_toggle.setChecked(True)
            self.btn_daemon_toggle.setStyleSheet(
                "background-color: #c0392b; color: white; padding: 5px;"
            )
            # Start visual countdown for daemon
            QTimer.singleShot(1000, self._start_daemon_countdown_if_active)
        else:
            self.btn_daemon_toggle.setText("Start Background Daemon")
            self.btn_daemon_toggle.setChecked(False)
            self.btn_daemon_toggle.setStyleSheet(
                "background-color: #27ae60; color: white; padding: 5px;"
            )

        settings_layout.addWidget(self.slideshow_group)
        self.slideshow_group.setVisible(False)

        self.solid_color_widget = QWidget()
        self.solid_color_layout = QHBoxLayout(self.solid_color_widget)
        self.solid_color_layout.setContentsMargins(0, 0, 0, 0)

        self.solid_color_preview = QLabel(" ")
        self.solid_color_preview.setFixedSize(20, 20)
        self.solid_color_preview.setStyleSheet(
            f"background-color: {self.solid_color_hex}; border: 1px solid #4f545c;"
        )

        btn_select_color = QPushButton("Select Color...")
        btn_select_color.clicked.connect(self.select_solid_color)

        self.solid_color_layout.addWidget(QLabel("Color:"))
        self.solid_color_layout.addWidget(self.solid_color_preview)
        self.solid_color_layout.addWidget(btn_select_color)
        self.solid_color_layout.addStretch(1)

        settings_layout.addWidget(self.solid_color_widget)
        self.solid_color_widget.setVisible(False)

        self.style_layout_widget = QWidget()
        style_layout = QHBoxLayout(self.style_layout_widget)
        style_layout.setContentsMargins(0, 0, 0, 0)

        # --- IMAGE STYLE COMBO ---
        self.style_combo = QComboBox()
        self.style_combo.setStyleSheet(
            "QComboBox { padding: 5px; border-radius: 4px; }"
        )
        initial_styles = self._get_relevant_styles()
        self.style_combo.addItems(initial_styles.keys())
        self.style_combo.setCurrentText(list(initial_styles.keys())[0])
        self.wallpaper_style = list(initial_styles.keys())[0]
        self.style_combo.currentTextChanged.connect(self._update_wallpaper_style)

        self.style_label = QLabel("Image Style:")
        style_layout.addWidget(self.style_label)
        style_layout.addWidget(self.style_combo)

        # --- NEW: VIDEO STYLE COMBO ---
        self.video_style_combo = QComboBox()
        self.video_style_combo.setStyleSheet(
            "QComboBox { padding: 5px; border-radius: 4px; }"
        )
        # Video options: Stretch, Keep Proportions, Scaled and Cropped
        self.video_style_combo.addItems(
            ["Stretch", "Keep Proportions", "Scaled and Cropped"]
        )
        self.video_style_combo.setCurrentText(self.video_style)
        self.video_style_combo.currentTextChanged.connect(self._update_video_style)
        self.video_style_combo.setVisible(False)  # Hidden by default

        self.video_style_label = QLabel("Video Style:")
        self.video_style_label.setVisible(False)
        style_layout.addWidget(self.video_style_label)
        style_layout.addWidget(self.video_style_combo)

        style_layout.addStretch(1)
        settings_layout.addWidget(self.style_layout_widget)

        settings_layout.addWidget(QLabel("<hr>"))

        settings_layout.addWidget(QLabel("Scan Directory (Image Source):"))
        scan_dir_layout = QHBoxLayout()
        self.scan_directory_path = QLineEdit()
        self.scan_directory_path.setPlaceholderText("Select directory to scan...")
        btn_browse_scan = QPushButton("Browse...")
        btn_browse_scan.clicked.connect(self.browse_scan_directory)
        apply_shadow_effect(
            btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )

        scan_dir_layout.addWidget(self.scan_directory_path)
        scan_dir_layout.addWidget(btn_browse_scan)
        settings_layout.addLayout(scan_dir_layout)

        content_layout.addWidget(settings_group)

        self.gallery_scroll_area = MarqueeScrollArea()
        self.gallery_scroll_area.setWidgetResizable(True)
        self.gallery_scroll_area.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.gallery_scroll_area.setMinimumHeight(600)

        self.scan_thumbnail_widget = QWidget()
        self.scan_thumbnail_widget.setStyleSheet(
            "QWidget { background-color: #2c2f33; }"
        )

        self.scan_thumbnail_layout = QGridLayout(self.scan_thumbnail_widget)
        self.scan_thumbnail_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.gallery_scroll_area.setWidget(self.scan_thumbnail_widget)

        content_layout.addWidget(self.search_input)
        content_layout.addWidget(self.gallery_scroll_area, 1)

        content_layout.addWidget(
            self.pagination_widget, 0, Qt.AlignmentFlag.AlignCenter
        )

        self.gallery_scroll_area = self.gallery_scroll_area
        self.gallery_layout = self.scan_thumbnail_layout

        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)

        self.set_wallpaper_btn = QPushButton("Set Wallpaper")
        self.set_wallpaper_btn.setStyleSheet(STYLE_START_ACTION)
        apply_shadow_effect(
            self.set_wallpaper_btn,
            color_hex="#000000",
            radius=8,
            x_offset=0,
            y_offset=3,
        )
        self.set_wallpaper_btn.clicked.connect(self.handle_set_wallpaper_click)
        action_layout.addWidget(self.set_wallpaper_btn, 1)

        content_layout.addLayout(action_layout)

        self.populate_monitor_layout()
        self.check_all_monitors_set()
        self.stop_slideshow()

    def _get_daemon_script_path(self):
        # Assumption: repo root is 3 levels up from this file (gui/tabs/wallpaper_tab.py)
        # Adjust based on actual structure if needed, or search.
        # Trying to find 'backend' package.
        script_path = ROOT_DIR / "backend" / "src" / "utils" / "slideshow_daemon.py"
        if script_path.exists():
            return str(script_path)

        current_dir = Path(__file__).resolve().parent
        # Go up until we find 'backend' folder
        root = current_dir
        while not (root / "backend").exists() and root != root.parent:
            root = root.parent

        script_path = root / "backend" / "src" / "utils" / "slideshow_daemon.py"
        if not script_path.exists():
            # Fallback try
            script_path = root / "slideshow_daemon.py"

        return str(script_path)

    def _is_daemon_running_config(self):
        if not DAEMON_CONFIG_PATH.exists():
            return False
        try:
            with open(DAEMON_CONFIG_PATH, "r") as f:
                data = json.load(f)
                return data.get("running", False)
        except:
            return False

    def toggle_slideshow_daemon(self):
        start = not self._is_daemon_running_config()

        style_to_use = (
            f"SmartVideoWallpaper::{self.video_style}"
            if self.background_type == "Smart Video Wallpaper"
            else self.wallpaper_style
        )

        config = {
            "running": start,
            "interval_seconds": (self.interval_min_spinbox.value() * 60)
            + self.interval_sec_spinbox.value(),
            "style": style_to_use,
            "monitor_queues": self.monitor_slideshow_queues,
            "current_paths": self.monitor_image_paths,
            "monitor_geometries": {
                str(i): {"x": m.x, "y": m.y, "width": m.width, "height": m.height}
                for i, m in enumerate(self.monitors)
            },
        }

        # Save config
        try:
            with open(DAEMON_CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save daemon config: {e}")
            return

        if start:
            # Launch process
            script_path = self._get_daemon_script_path()
            if not os.path.exists(script_path):
                QMessageBox.critical(
                    self, "Error", f"Daemon script not found at:\n{script_path}"
                )
                return

            try:
                # Launch detached process
                if platform.system() == "Windows":
                    subprocess.Popen(
                        [sys.executable, script_path],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                else:
                    subprocess.Popen(
                        [sys.executable, script_path],
                        start_new_session=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )

                self.btn_daemon_toggle.setText("Stop Background Daemon")
                self.btn_daemon_toggle.setChecked(True)
                self.btn_daemon_toggle.setStyleSheet(
                    "background-color: #c0392b; color: white; padding: 5px;"
                )
                
                # Start countdown
                self.interval_sec = config["interval_seconds"]
                self.time_remaining_sec = self.interval_sec
                if not hasattr(self, "countdown_timer") or not self.countdown_timer:
                    self.countdown_timer = QTimer(self)
                    self.countdown_timer.timeout.connect(self.update_countdown)
                
                if not self.countdown_timer.isActive():
                    self.countdown_timer.start(1000)

                QMessageBox.information(
                    self,
                    "Daemon Started",
                    "Background slideshow started. It will continue running even if you close this app.",
                )

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to start daemon: {e}")
        else:
            # Stopping is handled by the daemon itself watching the config "running": false
            self.btn_daemon_toggle.setText("Start Background Daemon")
            self.btn_daemon_toggle.setChecked(False)
            self.btn_daemon_toggle.setStyleSheet(
                "background-color: #27ae60; color: white; padding: 5px;"
            )
            
            # Stop visual countdown if no local slideshow is running
            if (not self.slideshow_timer or not self.slideshow_timer.isActive()) and \
               self.countdown_timer and self.countdown_timer.isActive():
                self.countdown_timer.stop()
                self.countdown_label.setText("Timer: --:--")
            QMessageBox.information(
                self, "Daemon Stopped", "Background slideshow stopped."
            )

    def _get_relevant_styles(self) -> Dict[str, str]:
        system = platform.system()
        if system == "Windows":
            return WALLPAPER_STYLES["Windows"]
        elif system == "Linux":
            if self.qdbus:
                return WALLPAPER_STYLES["KDE"]
            else:
                return WALLPAPER_STYLES["GNOME"]
        else:
            return {"Default (System)": None}

    @Slot(str)
    def _update_wallpaper_style(self, style_name: str):
        self.wallpaper_style = style_name

    @Slot(str)
    def _update_video_style(self, style_name: str):
        self.video_style = style_name

    @Slot(str)
    def _update_background_type(self, type_name: str):
        self.background_type = type_name

        is_solid_color = type_name == "Solid Color"
        is_slideshow = type_name == "Slideshow"
        is_video = type_name == "Smart Video Wallpaper"
        is_image = type_name == "Image"

        self.solid_color_widget.setVisible(is_solid_color)
        self.slideshow_group.setVisible(is_slideshow or is_video)

        main_controls_enabled = not is_solid_color

        # Toggle Image Style vs Video Style UI
        self.style_layout_widget.setVisible(main_controls_enabled)

        if is_video:
            self.style_combo.setVisible(False)
            self.style_label.setVisible(False)
            self.video_style_combo.setVisible(True)
            self.video_style_label.setVisible(True)
        else:
            self.style_combo.setVisible(True)
            self.style_label.setVisible(True)
            self.video_style_combo.setVisible(False)
            self.video_style_label.setVisible(False)

        self.scan_directory_path.setEnabled(main_controls_enabled)
        self.gallery_scroll_area.setEnabled(main_controls_enabled)

        if is_solid_color and self.slideshow_timer and self.slideshow_timer.isActive():
            self.stop_slideshow()

        self.check_all_monitors_set()

    @Slot()
    def select_solid_color(self):
        initial_color = QColor(self.solid_color_hex)
        color = QColorDialog.getColor(
            initial_color, self, "Select Solid Background Color"
        )
        if color.isValid():
            self.solid_color_hex = color.name().upper()
            self.solid_color_preview.setStyleSheet(
                f"background-color: {self.solid_color_hex}; border: 1px solid #4f545c;"
            )
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
        elif self.background_type in ["Slideshow", "Smart Video Wallpaper"]:
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
            QMessageBox.warning(
                self,
                "Slideshow Error",
                "Slideshow is disabled when Solid Color mode is selected.",
            )
            return
        is_ready, total_images = self._is_slideshow_validation_ready()
        if num_monitors == 0:
            QMessageBox.warning(
                self, "Slideshow Error", "No monitors detected or configured."
            )
            return
        if not is_ready:
            QMessageBox.critical(
                self,
                "Slideshow Error",
                "To start the slideshow, at least one monitor must have images dropped on it.",
            )
            return
        self.stop_slideshow()
        for mid in self.monitor_widgets.keys():
            self.monitor_current_index[mid] = -1
        interval_minutes = self.interval_min_spinbox.value()
        interval_seconds = self.interval_sec_spinbox.value()
        self.interval_sec = (interval_minutes * 60) + interval_seconds
        if self.interval_sec <= 0:
            QMessageBox.critical(
                self,
                "Slideshow Error",
                "Slideshow interval must be greater than 0 seconds.",
            )
            return
        interval_ms = self.interval_sec * 1000
        self.time_remaining_sec = self.interval_sec
        self.slideshow_timer = QTimer(self)
        self.slideshow_timer.timeout.connect(self._cycle_slideshow_wallpaper)
        self.slideshow_timer.start(interval_ms)
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)
        QMessageBox.information(
            self,
            "Slideshow Started",
            f"Per-monitor slideshow started with {total_images} total items, cycling every {interval_minutes} minutes and {interval_seconds} seconds.",
        )
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
            QMessageBox.information(
                self, "Slideshow Stopped", "Wallpaper slideshow stopped."
            )

        if self.countdown_timer and self.countdown_timer.isActive():
            self.countdown_timer.stop()
            self.countdown_timer.deleteLater()
            self.countdown_timer = None

        self.stop_wallpaper_worker()

        for win in list(self.open_queue_windows):
            if win.isVisible():
                win.close()
        self.open_queue_windows.clear()

        for win in list(self.open_image_preview_windows):
            if win.isVisible():
                win.close()
        self.open_image_preview_windows.clear()

        self.monitor_current_index.clear()
        self.time_remaining_sec = 0
        self.countdown_label.setText("Timer: --:--")

        self.unlock_ui_for_wallpaper()

    @Slot()
    def _cycle_slideshow_wallpaper(self):
        monitor_ids = list(self.monitor_widgets.keys())
        if not monitor_ids:
            return
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
                    new_monitor_paths[monitor_id] = self.monitor_image_paths.get(
                        monitor_id
                    )
                    self.monitor_current_index[monitor_id] = -1
            if not has_valid_path_to_set:
                self.stop_slideshow()
                return
            self.monitor_image_paths = new_monitor_paths
            self.run_wallpaper_worker(slideshow_mode=True)
            for monitor_id, path in new_monitor_paths.items():
                if monitor_id in self.monitor_widgets and path:
                    # Pass the cached thumbnail if available, otherwise just path
                    thumb = self._initial_pixmap_cache.get(path)
                    self.monitor_widgets[monitor_id].set_image(path, thumb)
            self.time_remaining_sec = self.interval_sec
        except Exception as e:
            QMessageBox.critical(
                self, "Slideshow Cycle Error", f"Failed to cycle wallpaper: {str(e)}"
            )
            self.stop_slideshow()

    @Slot(str)
    def handle_monitor_double_click(self, monitor_id: str):
        if self.background_type == "Solid Color":
            return
        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        monitor_name = self.monitor_widgets[monitor_id].monitor.name
        for win in self.open_queue_windows:
            if isinstance(win, SlideshowQueueWindow) and win.monitor_id == monitor_id:
                win.activateWindow()
                return

        # Pass the global pixmap cache so the QueueWindow can show videos too
        window = SlideshowQueueWindow(
            monitor_name, monitor_id, queue, pixmap_cache=self._initial_pixmap_cache
        )
        window.setAttribute(Qt.WA_DeleteOnClose)
        window.queue_reordered.connect(self.on_queue_reordered)
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
        if image_path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
            try:
                if platform.system() == "Windows":
                    os.startfile(image_path)
                elif platform.system() == "Linux":
                    subprocess.Popen(["xdg-open", image_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.Popen(["open", image_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                QMessageBox.warning(
                    self, "Video Error", f"Could not launch video player: {e}"
                )
            return

        all_paths_list = (
            sorted(self.gallery_image_paths)
            if self.gallery_image_paths
            else [image_path]
        )
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
            image_path=image_path,
            db_tab_ref=None,
            parent=self,
            all_paths=all_paths_list,
            start_index=start_index,
        )
        window.setAttribute(Qt.WA_DeleteOnClose)

        def remove_closed_win(event: Any):
            if window in self.open_image_preview_windows:
                self.open_image_preview_windows.remove(window)
            event.accept()

        window.closeEvent = remove_closed_win
        window.show()
        self.open_image_preview_windows.append(window)

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        if self.background_type == "Solid Color":
            return
        menu = QMenu(self)

        is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
        view_text = "Play Video" if is_video else "View Full Size Preview"

        view_action = QAction(view_text, self)
        view_action.triggered.connect(lambda: self.handle_full_image_preview(path))
        menu.addAction(view_action)

        if self.monitor_widgets:
            menu.addSeparator()
            add_menu = menu.addMenu("Add to Monitor Queue")
            for monitor_id, widget in self.monitor_widgets.items():
                monitor_name = widget.monitor.name
                action = QAction(f"{monitor_name} (ID: {monitor_id})", self)
                action.triggered.connect(
                    lambda checked, mid=monitor_id, img_path=path: self.on_image_dropped(
                        mid, img_path
                    )
                )
                add_menu.addAction(action)
        menu.addSeparator()
        delete_action = QAction("🗑️ Delete File (Permanent)", self)
        delete_action.triggered.connect(lambda: self.handle_delete_image(path))
        menu.addAction(delete_action)
        menu.exec(global_pos)

    @Slot(str)
    def handle_delete_image(self, path: str):
        if not path or not Path(path).exists():
            QMessageBox.warning(
                self, "Delete Error", "File not found or path is invalid."
            )
            return
        filename = os.path.basename(path)
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to PERMANENTLY delete the file:\n\n**{filename}**\n\nThis action cannot be undone!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.No:
            return
        try:
            os.remove(path)

            if path in self.gallery_image_paths:
                self.gallery_image_paths.remove(path)

            if path in self.path_to_label_map:
                widget = self.path_to_label_map.pop(path)
                widget.deleteLater()

            for mid in self.monitor_slideshow_queues:
                self.monitor_slideshow_queues[mid] = [
                    p for p in self.monitor_slideshow_queues[mid] if p != path
                ]
            for mid, current_path in self.monitor_image_paths.items():
                if current_path == path:
                    self.monitor_image_paths[mid] = None
                    self.monitor_widgets[mid].clear()

            self.refresh_gallery_view()
            self.check_all_monitors_set()
            QMessageBox.information(
                self, "Success", f"File deleted successfully: {filename}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Deletion Failed", f"Could not delete the file: {e}"
            )

    @Slot(str, list)
    def on_queue_reordered(self, monitor_id: str, new_queue: List[str]):
        self.monitor_slideshow_queues[monitor_id] = new_queue
        self.monitor_current_index[monitor_id] = -1
        new_first_image = new_queue[0] if new_queue else None
        self.monitor_image_paths[monitor_id] = new_first_image

        if new_first_image:
            # Try to get thumbnail from cache
            thumb = self._initial_pixmap_cache.get(new_first_image)
            self.monitor_widgets[monitor_id].set_image(new_first_image, thumb)
        else:
            self.monitor_widgets[monitor_id].clear()
        self.check_all_monitors_set()

    @Slot(str)
    def handle_clear_monitor_queue(self, monitor_id: str):
        if monitor_id not in self.monitor_widgets:
            return
        monitor_name = self.monitor_widgets[monitor_id].monitor.name
        if monitor_id in self.monitor_slideshow_queues:
            self.monitor_slideshow_queues[monitor_id].clear()
        if monitor_id in self.monitor_image_paths:
            self.monitor_image_paths[monitor_id] = None
        if monitor_id in self.monitor_current_index:
            self.monitor_current_index[monitor_id] = -1

        system = platform.system()
        num_monitors_detected = len(self.monitors)
        current_system_wallpaper_paths = {}
        if system == "Linux" and num_monitors_detected > 0:
            try:
                if self.qdbus:
                    raw_paths = WallpaperManager.get_current_system_wallpaper_path_kde(
                        self.monitors, self.qdbus
                    )
                    current_system_wallpaper_paths = self._get_rotated_map_for_ui(
                        raw_paths
                    )
            except Exception as e:
                print(f"KDE retrieval failed unexpectedly: {e}")

        system_wallpaper_path = current_system_wallpaper_paths.get(monitor_id)
        if system_wallpaper_path and Path(system_wallpaper_path).exists():
            thumb = self._initial_pixmap_cache.get(system_wallpaper_path)
            self.monitor_widgets[monitor_id].set_image(system_wallpaper_path, thumb)
        else:
            self.monitor_widgets[monitor_id].clear()
        self.check_all_monitors_set()
        QMessageBox.information(
            self,
            "Monitor Cleared",
            f"All pending items and the slideshow queue for **{monitor_name}** have been cleared.\n\nThe system's current background remains unchanged.",
        )



    def populate_monitor_layout(self):
        self.monitor_layout_container.clear_widgets()

        self.monitor_widgets.clear()
        try:
            system_monitors = get_monitors()
            physical_monitors = sorted(system_monitors, key=lambda m: m.x)
            self.monitors = system_monitors
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not get monitor info: {e}")
            self.monitors = []
        if not self.monitors or "Mock" in self.monitors[0].name:
            self.monitor_layout_container.addWidget(
                QLabel("Could not detect any monitors.\nIs 'screeninfo' installed?")
            )
            return

        current_system_wallpaper_paths = {}
        system = platform.system()
        num_monitors_detected = len(self.monitors)
        if system == "Linux" and num_monitors_detected > 0:
            try:
                if self.qdbus:
                    current_system_wallpaper_paths = WallpaperManager.get_current_system_wallpaper_path_kde(
                        self.monitors, self.qdbus
                    )
            except Exception as e:
                print(f"KDE retrieval failed unexpectedly: {e}")

        # Reverting strict sorting to respect User's original order / requests
        monitors_to_show = self.monitors

        monitor_id_to_widget = {}
        for i, monitor in enumerate(self.monitors):
            monitor_id = str(i)
            drop_widget = MonitorDropWidget(monitor, monitor_id)
            drop_widget.image_dropped.connect(self.on_image_dropped)
            drop_widget.double_clicked.connect(self.handle_monitor_double_click)
            drop_widget.clear_requested_id.connect(self.handle_clear_monitor_queue)
            self.monitor_widgets[monitor_id] = drop_widget

            current_image = self.monitor_image_paths.get(monitor_id)
            image_path_to_display = current_image

            # Fallback to system wallpaper if app hasn't set one yet
            if not image_path_to_display:
                system_wallpaper_path = current_system_wallpaper_paths.get(monitor_id)
                if system_wallpaper_path and Path(system_wallpaper_path).exists():
                    image_path_to_display = system_wallpaper_path

            if image_path_to_display:
                # 1. Try to get thumbnail from cache
                thumb = self._initial_pixmap_cache.get(image_path_to_display)

                # --- ADDED: Check for video if thumb is missing ---
                if thumb is None and image_path_to_display.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                    # For video files, we can just pass the path; the widget handles thumbnail generation/preview
                    pass 
                drop_widget.set_image(image_path_to_display, thumb)
                # ---------------------------------------------------

            else:
                drop_widget.clear()

            monitor_id_to_widget[monitor_id] = drop_widget
            self.monitor_widgets[monitor_id] = drop_widget

        for monitor in monitors_to_show:
            system_index = -1
            for i, sys_mon in enumerate(system_monitors):
                if (
                    sys_mon.x == monitor.x
                    and sys_mon.y == monitor.y
                    and sys_mon.width == monitor.width
                    and sys_mon.height == monitor.height
                ):
                    system_index = i
                    break
            if system_index != -1:
                monitor_id = str(system_index)
                if monitor_id in monitor_id_to_widget:
                    self.monitor_layout_container.addWidget(
                        monitor_id_to_widget[monitor_id]
                    )

        self.check_all_monitors_set()

    def on_image_dropped(self, monitor_id: str, image_path: str):
        is_video = image_path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
        if is_video and self.background_type == "Image":
            self.background_type_combo.setCurrentText("Smart Video Wallpaper")
        elif not is_video and self.background_type == "Smart Video Wallpaper":
            pass

        if self.background_type == "Solid Color":
            self.background_type_combo.setCurrentText("Image")

        if monitor_id not in self.monitor_slideshow_queues:
            self.monitor_slideshow_queues[monitor_id] = []
        if image_path not in self.monitor_slideshow_queues[monitor_id]:
            self.monitor_slideshow_queues[monitor_id].append(image_path)

        self.monitor_image_paths[monitor_id] = image_path
        self.monitor_current_index[monitor_id] = -1

        thumb = self._initial_pixmap_cache.get(image_path)

        # --- ADDED: Check for video if thumb is missing ---
        if not thumb and is_video:
            thumb = self._generate_video_thumbnail(image_path)
            if thumb:
                self._initial_pixmap_cache[image_path] = thumb
        # ---------------------------------------------------

        self.monitor_widgets[monitor_id].set_image(image_path, thumb)
        self.check_all_monitors_set()

        # Auto-save changes to daemon config if it exists/is running
        # This ensures the background daemon picks up the new queue immediately
        if self._is_daemon_running_config():
            self.toggle_slideshow_daemon()  # Re-saves config and restarts/keeps running



    def _get_rotated_map_for_ui(self, raw_paths: Dict[int, str]) -> Dict[str, str]:
        """
        Maps the raw (int indices) paths from KDE into the UI's (str indices) map.
        In the future, complex rotation/reordering logic can go here.
        For now, we map str(i) -> path.
        """
        mapped = {}
        for idx, path in raw_paths.items():
             mapped[str(idx)] = path
        return mapped

    def _get_current_system_image_paths_for_all(self) -> Dict[str, Optional[str]]:
        system = platform.system()
        num_monitors = len(self.monitors)
        current_paths = {}
        if num_monitors == 0:
            return current_paths
        if system == "Linux":
            try:
                if self.qdbus:
                    raw_paths = WallpaperManager.get_current_system_wallpaper_path_kde(
                        self.monitors, self.qdbus
                    )
                    current_paths = self._get_rotated_map_for_ui(raw_paths)
            except Exception:
                pass
        return current_paths

    def run_wallpaper_worker(self, slideshow_mode=False):
        if self.current_wallpaper_worker:
            print("Wallpaper worker is already running.")
            return

        if self.background_type == "Solid Color":
            path_map = {
                str(mid): self.solid_color_hex for mid in range(len(self.monitors))
            }
            style_to_use = "SolidColor"
            final_path_map = path_map
        else:
            if not any(self.monitor_image_paths.values()):
                if not slideshow_mode:
                    QMessageBox.warning(
                        self,
                        "Incomplete",
                        "No images/videos have been dropped on the monitors.",
                    )
                return

            if ImageScannerWorker is None:
                QMessageBox.warning(
                    self,
                    "Missing Helpers",
                    "The ImageScannerWorker or ImageLoaderWorker could not be imported.",
                )
                return

            if not slideshow_mode:
                current_system_paths = self._get_current_system_image_paths_for_all()
                path_map = current_system_paths.copy()
                for monitor_id in [str(i) for i in range(len(self.monitors))]:
                    user_path = self.monitor_image_paths.get(monitor_id)
                    if user_path:
                        path_map[monitor_id] = user_path
                    elif monitor_id not in path_map:
                        widget = self.monitor_widgets.get(monitor_id)
                        if widget and widget.image_path:
                            path_map[monitor_id] = widget.image_path
                        else:
                            path_map[monitor_id] = None
            else:
                path_map = self.monitor_image_paths.copy()

            system = platform.system()
            if system == "Linux":
                try:
                    if self.qdbus:
                        desktop = "KDE"
                    else:
                        desktop = "Gnome"
                except:
                    desktop = None
            elif system == "Windows":
                desktop = "Windows"
            else:
                desktop = None

            if self.background_type == "Smart Video Wallpaper":
                # --- CHANGE: Pass the selected VIDEO STYLE here ---
                style_to_use = f"SmartVideoWallpaper::{self.video_style}"
            else:
                style_to_use = self.wallpaper_style

            if desktop == "Windows" and not WallpaperManager.COM_AVAILABLE:
                path_to_set = next((p for p in path_map.values() if p), None)
                final_path_map = {"0": path_to_set} if path_to_set else {}
            else:
                final_path_map = path_map

        monitors = self.monitors
        if not slideshow_mode:
            self.lock_ui_for_wallpaper()

        monitor_geometries = {
            str(i): {"x": m.x, "y": m.y} for i, m in enumerate(self.monitors)
        }

        self.current_wallpaper_worker = WallpaperWorker(
            final_path_map,
            monitors,
            self.qdbus,
            wallpaper_style=style_to_use,
        )
        self.current_wallpaper_worker.signals.status_update.connect(
            self.handle_wallpaper_status
        )
        self.current_wallpaper_worker.signals.work_finished.connect(
            self.handle_wallpaper_finished
        )
        self.current_wallpaper_worker.signals.work_finished.connect(
            lambda: setattr(self, "current_wallpaper_worker", None)
        )
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
        self.gallery_scroll_area.setEnabled(False)
        self.scan_directory_path.setEnabled(False)
        self.style_combo.setEnabled(False)
        self.video_style_combo.setEnabled(False)  # Disable video style too
        self.background_type_combo.setEnabled(False)
        self.solid_color_widget.setEnabled(False)
        for widget in self.monitor_widgets.values():
            widget.setEnabled(False)
        QApplication.processEvents()

    def unlock_ui_for_wallpaper(self):
        self.set_wallpaper_btn.setText("Set Wallpaper")
        self.set_wallpaper_btn.setStyleSheet(STYLE_START_ACTION)
        self.slideshow_group.setEnabled(True)
        self.gallery_scroll_area.setEnabled(True)
        self.scan_directory_path.setEnabled(True)
        self.style_combo.setEnabled(True)
        self.video_style_combo.setEnabled(True)
        self.background_type_combo.setEnabled(True)
        self.solid_color_widget.setEnabled(True)
        for widget in self.monitor_widgets.values():
            widget.setEnabled(True)
        self._update_background_type(self.background_type)
        self.check_all_monitors_set()
        QApplication.processEvents()

    @Slot(str)
    def handle_wallpaper_status(self, msg: str):
        print(f"[WallpaperWorker] {msg}")

    @Slot(bool, str)
    def handle_wallpaper_finished(self, success: bool, message: str):
        is_slideshow_active = self.slideshow_timer and self.slideshow_timer.isActive()
        if success:
            if not is_slideshow_active and self.background_type != "Solid Color":
                QMessageBox.information(self, "Success", "Wallpaper has been updated!")
                for monitor_id, path in self.monitor_image_paths.items():
                    if path and monitor_id in self.monitor_widgets:
                        thumb = self._initial_pixmap_cache.get(path)
                        self.monitor_widgets[monitor_id].set_image(path, thumb)
            elif self.background_type == "Solid Color":
                QMessageBox.information(
                    self,
                    "Success",
                    f"Solid color background set to {self.solid_color_hex}!",
                )
        else:
            if "manually cancelled" not in message.lower():
                if is_slideshow_active:
                    print(f"Slideshow Error: Failed to set wallpaper: {message}")
                    self.stop_slideshow()
                else:
                    QMessageBox.critical(
                        self, "Error", f"Failed to set wallpaper:\n{message}"
                    )
        if not is_slideshow_active:
            self.unlock_ui_for_wallpaper()

    def browse_scan_directory(self):
        if self.background_type == "Solid Color":
            QMessageBox.warning(
                self,
                "Mode Conflict",
                "Cannot browse directory while Solid Color background is selected.",
            )
            return

        if ImageScannerWorker is None:
            QMessageBox.warning(
                self,
                "Missing Helpers",
                "The ImageScannerWorker or ImageLoaderWorker could not be imported.",
            )
            return

        start_dir = self.last_browsed_scan_dir
        options = (
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        directory = QFileDialog.getExistingDirectory(
            self, "Select directory to scan", start_dir, options
        )

        if directory:
            self.last_browsed_scan_dir = directory
            self.scan_directory_path.setText(directory)
            self.populate_scan_image_gallery(directory)

    def create_gallery_label(self, path: str, size: int) -> QLabel:
        draggable_label = DraggableLabel(path, size)
        draggable_label.setAlignment(Qt.AlignCenter)

        # Connect signals
        draggable_label.path_double_clicked.connect(self.handle_thumbnail_double_click)
        draggable_label.path_right_clicked.connect(self.show_image_context_menu)
        
        # Track label for internal WallpaperTab logic
        self.path_to_label_map[path] = draggable_label
        
        return draggable_label

    def populate_scan_image_gallery(self, directory: str):
        if self.background_type == "Solid Color":
            return

        self.scanned_dir = directory
        self.clear_gallery_widgets()
        self.path_to_label_map.clear()
        self._initial_pixmap_cache.clear()
        self.cancel_loading()
        self.gallery_image_paths = []

        if self.img_scanner_thread is not None:
            if self.img_scanner_thread.isRunning():
                self.img_scanner_thread.requestInterruption()
                self.img_scanner_thread.quit()
                self.img_scanner_thread.wait()

            self.img_scanner_thread.deleteLater()
            self.img_scanner_thread = None

        if self.vid_scanner_worker is not None:
            self.vid_scanner_worker.stop()
            self.vid_scanner_worker = None

        self.img_scanner_worker = ImageScannerWorker(directory)
        self.img_scanner_thread = QThread()
        self.img_scanner_worker.moveToThread(self.img_scanner_thread)

        self.img_scanner_thread.started.connect(self.img_scanner_worker.run_scan)
        self.img_scanner_worker.scan_finished.connect(self._on_image_scan_finished)
        self.img_scanner_worker.scan_error.connect(self.handle_scan_error)

        self.img_scanner_worker.scan_finished.connect(self.img_scanner_thread.quit)
        self.img_scanner_thread.finished.connect(self.img_scanner_thread.deleteLater)
        self.img_scanner_thread.finished.connect(
            lambda: setattr(self, "img_scanner_thread", None)
        )

        self.img_scanner_thread.start()

    @Slot(list)
    def _on_image_scan_finished(self, image_paths: list[str]):
        if image_paths:
            self.start_loading_gallery(image_paths, show_progress=False, append=False)
        else:
            self.refresh_gallery_view()

        if self.scanned_dir:
            self.vid_scanner_worker = VideoScannerWorker(self.scanned_dir)
            self.vid_scanner_worker.signals.thumbnail_ready.connect(
                self._add_video_thumbnail_manual
            )
            self.vid_scanner_worker.signals.finished.connect(
                self._on_video_scan_finished
            )
            QThreadPool.globalInstance().start(self.vid_scanner_worker)

    @Slot()
    def _on_video_scan_finished(self):
        pass

    @Slot(str, QImage)
    def _add_video_thumbnail_manual(self, path: str, q_image: QImage):
        if path in self.gallery_image_paths:
            return
        
        pixmap = QPixmap.fromImage(q_image)

        # Handle Failed Loads
        if pixmap.isNull():
            if not hasattr(self, "_failed_paths"):
                self._failed_paths = set()
            self._failed_paths.add(path)

        self.gallery_image_paths.append(path)
        self._initial_pixmap_cache[path] = pixmap
        # Debounce the UI update to avoid freezing on massive updates
        self._pagination_debounce_timer.start()

        total_items = len(self.gallery_image_paths)
        start_index = self.current_page * self.page_size
        end_index = start_index + self.page_size
        item_index = total_items - 1

        if start_index <= item_index < end_index:
            card = self.create_card_widget(path, pixmap)

            if self.gallery_layout:
                current_count = self.gallery_layout.count()
                cols = self.calculate_columns()
                row = current_count // cols
                col = current_count % cols

                self.gallery_layout.addWidget(
                    card, row, col, Qt.AlignLeft | Qt.AlignTop
                )

            self.path_to_card_widget[path] = card
            self.path_to_label_map[path] = card

    def _handle_autoscroll(self, global_pos: QPoint):
        """Scrolls the main scroll area if the drag is near the top or bottom edges."""
        if not hasattr(self, "main_scroll_area") or not self.isVisible():
            return

        vbar = self.main_scroll_area.verticalScrollBar()
        if not vbar or not vbar.isVisible():
            return

        # Get viewport rect in global coordinates
        viewport = self.main_scroll_area.viewport()
        vp_global_pos = viewport.mapToGlobal(QPoint(0, 0))
        vp_global_rect = QRect(vp_global_pos, viewport.size())
        
        # Relaxed Bounds Check:
        # Check if X is within valid range (with some buffer)
        # We don't strictly check Y because user might drag below the viewport to scroll down
        buffer = 50
        if (global_pos.x() < vp_global_rect.left() - buffer) or \
           (global_pos.x() > vp_global_rect.right() + buffer):
            # print(f"[DEBUG] Autoscroll Ignored: Out of X bounds. Pos: {global_pos.x()}, Rect: {vp_global_rect}")
            return

        # Threshold and speed
        height = vp_global_rect.height()
        threshold = 120 
        scroll_step = 20

        # Relative Y to the TOP of the viewport
        rel_y = global_pos.y() - vp_global_rect.top()
        
        if rel_y < threshold:
            vbar.setValue(vbar.value() - scroll_step)
        elif rel_y > height - threshold:
            vbar.setValue(vbar.value() + scroll_step)

    def eventFilter(self, watched, event):
        if self._filtering_event:
            return False
            
        # We catch events globally but only act if we are visible
        self._filtering_event = True
        try:
            if not self.isVisible():
                return False
        finally:
            self._filtering_event = False

        if event.type() == QEvent.Wheel:
            # Note: Wheel events are typically suppressed by QDrag.exec() on many platforms.
            # This handler is kept in case the platform allows it.
            if QApplication.mouseButtons() & Qt.LeftButton:
                global_pos = QCursor.pos()
                if self.rect().contains(self.mapFromGlobal(global_pos)):
                    vbar = self.main_scroll_area.verticalScrollBar()
                    if vbar and vbar.isVisible():
                        delta = event.angleDelta().y()
                        vbar.setValue(vbar.value() - delta)
                        return True

        elif event.type() in (QEvent.DragMove, QEvent.DragEnter):
            # Globally catch drag moves to handle autoscroll even over child widgets
            self._handle_autoscroll(QCursor.pos())

        return super().eventFilter(watched, event)

    def cancel_scanning(self):
        if self.img_scanner_thread and self.img_scanner_thread.isRunning():
            self.img_scanner_thread.quit()

    @Slot(list)
    def display_scan_results(self, image_paths: list[str]):
        if self.background_type == "Solid Color":
            return
        self.clear_gallery_widgets()
        self.path_to_label_map.clear()
        self.check_all_monitors_set()
        final_paths = sorted(list(set(image_paths)))
        if not final_paths:
            return
        self.start_loading_gallery(final_paths)

    @Slot(str)
    def handle_thumbnail_double_click(self, image_path: str):
        self.handle_full_image_preview(image_path)

    def handle_scan_error(self, message: str):
        self.clear_gallery_widgets()
        QMessageBox.warning(self, "Error Scanning", message)
        self.common_show_placeholder("Browse for a directory.")

    def collect(self) -> dict:
        monitor_order = []
        monitor_layout = []
        if isinstance(self.monitor_layout_container, DraggableMonitorContainer):
            # Legacy flat order
            # Iterate through rows and columns to preserve visual order (flattened)
            for row in self.monitor_layout_container.rows:
                for widget in row:
                    if isinstance(widget, MonitorDropWidget):
                        monitor_order.append(widget.monitor_id)
            
            # New structured layout
            monitor_layout = self.monitor_layout_container.get_layout_structure()

        return {
            "scan_directory": self.scan_directory_path.text(),
            "wallpaper_style": self.wallpaper_style,
            "video_style": self.video_style,  # Capture the new video style
            "slideshow_enabled": (self.background_type == "Slideshow"),
            "interval_minutes": self.interval_min_spinbox.value(),
            "interval_seconds": self.interval_sec_spinbox.value(),
            "background_type": self.background_type,
            "solid_color_hex": self.solid_color_hex,
            "monitor_order": monitor_order,
            "monitor_layout": monitor_layout,
        }

    def get_default_config(self) -> Dict[str, Any]:
        default_style = (
            self.style_combo.itemText(0) if self.style_combo.count() > 0 else "Fill"
        )
        return {
            "scan_directory": "",
            "wallpaper_style": default_style,
            "video_style": "Scaled and Cropped",  # Default
            "slideshow_enabled": False,
            "interval_minutes": 5,
            "interval_seconds": 0,
            "background_type": "Image",
            "solid_color_hex": "#000000",
            "monitor_order": [],
            "monitor_layout": [],
        }

    def set_config(self, config: Dict[str, Any]):
        try:
            if "scan_directory" in config:
                self.scan_directory_path.setText(config.get("scan_directory", ""))
                if os.path.isdir(config["scan_directory"]):
                    self.populate_scan_image_gallery(config["scan_directory"])
            if "wallpaper_style" in config:
                self.style_combo.setCurrentText(config.get("wallpaper_style", "Fill"))

            # --- Restore video style ---
            if "video_style" in config:
                self.video_style_combo.setCurrentText(
                    config.get("video_style", "Scaled and Cropped")
                )

            if "slideshow_enabled" in config:
                enabled = config.get("slideshow_enabled", False)
                if enabled:
                    self.background_type_combo.setCurrentText("Slideshow")

            if "interval_minutes" in config:
                self.interval_min_spinbox.setValue(config.get("interval_minutes", 5))
            if "interval_seconds" in config:
                self.interval_sec_spinbox.setValue(config.get("interval_seconds", 0))
            if "solid_color_hex" in config:
                self.solid_color_hex = config.get("solid_color_hex", "#000000")
                self.solid_color_preview.setStyleSheet(
                    f"background-color: {self.solid_color_hex}; border: 1px solid #4f545c;"
                )

            if "background_type" in config:
                self.background_type_combo.setCurrentText(
                    config.get("background_type", "Image")
                )
            
            layout_restored = False
            if "monitor_layout" in config and config["monitor_layout"]:
                if isinstance(self.monitor_layout_container, DraggableMonitorContainer):
                    self.monitor_layout_container.set_layout_structure(
                        config["monitor_layout"], self.monitor_widgets
                    )
                    layout_restored = True

            if not layout_restored and "monitor_order" in config and config["monitor_order"]:
                target_order = config["monitor_order"]
                present_monitor_ids = set(self.monitor_widgets.keys())
                valid_order = [
                    mid for mid in target_order if mid in present_monitor_ids
                ]

                if isinstance(self.monitor_layout_container, DraggableMonitorContainer):
                    # Note: This resets 2D layout to a single row (flattened)
                    self.monitor_layout_container.clear_widgets()

                    # Insert in order
                    for mid in valid_order:
                        if mid in self.monitor_widgets:
                            self.monitor_layout_container.addWidget(self.monitor_widgets[mid])

                    # Add back any that weren't in the order
                    for mid, w in self.monitor_widgets.items():
                        if mid not in valid_order:
                            self.monitor_layout_container.addWidget(w)

            QMessageBox.information(
                self, "Config Loaded", "Wallpaper configuration applied successfully."
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Config Error", f"Failed to apply wallpaper configuration:\n{e}"
            )