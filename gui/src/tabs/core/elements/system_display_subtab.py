import contextlib
import json
import logging
import os
import platform
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import (
    Any,
    Dict,
    Mapping,
    Optional,
    Tuple,
    Union,
    cast,
)

from backend.src.constants import (
    DAEMON_CONFIG_PATH,
    ROOT_DIR,
    WALLPAPER_STYLES,
)
from backend.src.core import WallpaperManager
from PySide6.QtCore import (
    Qt,
    QThreadPool,
    QTimer,
    Slot,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ....components import (
    DraggableMonitorContainer,
    MarqueeScrollArea,
    MonitorDropView,
)
from ....helpers import WallpaperWorker
from ....styles import STYLE_START_ACTION, STYLE_STOP_ACTION, apply_shadow_effect
from .common.wallpaper_common_base import WallpaperCommonBase


class SystemDisplaySubTab(WallpaperCommonBase):
    """System wallpaper management subtab.

    Full-featured wallpaper setter with monitor layout, gallery,
    slideshow, daemon, and solid-color modes.
    """
    interval_min_spinbox: Any
    interval_sec_spinbox: Any
    playback_order_combo: Any
    style_combo: Any
    scan_directory_path: Any
    gallery_scroll_area: Any
    main_scroll_area: Any
    set_wallpaper_btn: Any
    background_type_combo: Any
    style_label: Any
    video_style_combo: Any
    video_style_label: Any
    style_layout_widget: Any
    status_timer: Any
    countdown_timer: Optional[QTimer]

    def __init__(self, db_tab_ref):
        super().__init__()
        self.db_tab_ref = db_tab_ref

        self.countdown_timer: Optional[QTimer] = None
        self.time_remaining_sec: int = 0
        self.interval_sec: int = 0

        self.wallpaper_style: str = "Fill"
        self.video_style: str = "Scaled and Cropped"

        self.pagination_widget = self.create_pagination_controls()

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        self.main_scroll_area = QScrollArea()
        self.main_scroll_area.setWidgetResizable(True)
        self.main_scroll_area.setWidget(content_widget)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.main_scroll_area)
        self.setLayout(main_layout)

        self.setAcceptDrops(True)

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self.main_scroll_area.viewport().setAcceptDrops(True)

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

        layout_group = self.create_monitor_layout_section(
            "Monitor Layout (Drag to Reorder, Drop images/videos to set)"
        )
        content_layout.addWidget(layout_group)

        settings_group = QGroupBox("Wallpaper Settings")
        settings_group.setStyleSheet(group_box_style)
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setContentsMargins(10, 20, 10, 10)

        background_type_layout = QHBoxLayout()
        self.background_type_combo = QComboBox()
        self.background_type_combo.addItems(
            [
                "Image",
                "Slideshow",
                "Smart Video",
                "Smart Video Slideshow",
                "Solid Color",
            ]
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
        slideshow_layout.addWidget(QLabel("Order:"))
        self.playback_order_combo = QComboBox()
        self.playback_order_combo.addItems(
            ["Sequential", "Reverse Sequential", "Random"]
        )
        self.playback_order_combo.setCurrentText("Sequential")
        self.playback_order_combo.setFixedWidth(120)
        slideshow_layout.addWidget(self.playback_order_combo)

        slideshow_layout.addStretch(1)

        self.countdown_label = QLabel("Timer: --:--")
        self.countdown_label.setStyleSheet(
            "color: #2ecc71; font-weight: bold; font-size: 14px;"
        )
        self.countdown_label.setFixedWidth(100)
        slideshow_layout.addWidget(self.countdown_label)

        self.btn_daemon_toggle = QPushButton("Start Background Daemon")
        self.btn_daemon_toggle.setCheckable(True)
        self.btn_daemon_toggle.clicked.connect(self.toggle_daemon)
        slideshow_layout.addWidget(self.btn_daemon_toggle)

        self.btn_view_logs = QPushButton("View Daemon Logs")
        self.btn_view_logs.clicked.connect(self.view_daemon_logs)
        slideshow_layout.addWidget(self.btn_view_logs)

        self.btn_fetch_current = QPushButton("Fetch Current Wallpapers")
        self.btn_fetch_current.clicked.connect(self.populate_monitor_layout)
        slideshow_layout.addWidget(self.btn_fetch_current)

        self.btn_skip_wallpapers = QPushButton("Skip Current Wallpapers")
        self.btn_skip_wallpapers.clicked.connect(self.skip_current_wallpapers)
        slideshow_layout.addWidget(self.btn_skip_wallpapers)

        if self._is_daemon_running_config():
            self.btn_daemon_toggle.setText("Stop Background Daemon")
            self.btn_daemon_toggle.setChecked(True)
            self.btn_daemon_toggle.setStyleSheet(
                "background-color: #c0392b; color: white; padding: 5px;"
            )
            QTimer.singleShot(1000, self._start_daemon_countdown_if_active)
        else:
            self.btn_daemon_toggle.setText("Start Background Daemon")
            self.btn_daemon_toggle.setChecked(False)
            self.btn_daemon_toggle.setStyleSheet(
                "background-color: #27ae60; color: white; padding: 5px;"
            )

        settings_layout.addWidget(self.slideshow_group)
        self.slideshow_group.setVisible(False)

        QTimer.singleShot(0, self._apply_vault_slideshow_defaults)

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

        self.style_combo = QComboBox()
        self.style_combo.setStyleSheet(
            "QComboBox { padding: 5px; border-radius: 4px; }"
        )
        initial_styles = self._get_relevant_styles()
        self.style_combo.addItems(initial_styles.keys()) # pyrefly: ignore [bad-argument-type]
        self.style_combo.setCurrentText(list(initial_styles.keys())[0])
        self.wallpaper_style = list(initial_styles.keys())[0]
        self.style_combo.currentTextChanged.connect(self._update_wallpaper_style)

        self.style_label = QLabel("Image Style:")
        style_layout.addWidget(self.style_label)
        style_layout.addWidget(self.style_combo)

        self.video_style_combo = QComboBox()
        self.video_style_combo.setStyleSheet(
            "QComboBox { padding: 5px; border-radius: 4px; }"
        )
        self.video_style_combo.addItems(
            ["Stretch", "Keep Proportions", "Scaled and Cropped"]
        )
        self.video_style_combo.setCurrentText(self.video_style)
        self.video_style_combo.currentTextChanged.connect(self._update_video_style)
        self.video_style_combo.setVisible(False)

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
        self.scan_directory_path.returnPressed.connect(
            lambda: self.populate_scan_image_gallery(self.scan_directory_path.text().strip())
        )
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
        self.scan_thumbnail_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        self.gallery_scroll_area.setWidget(self.scan_thumbnail_widget)

        content_layout.addWidget(self.search_input)
        content_layout.addWidget(self.gallery_scroll_area, 1)
        content_layout.addWidget(
            self.pagination_widget, 0, Qt.AlignmentFlag.AlignCenter
        )

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

        self.playback_order_combo.currentTextChanged.connect(self._sync_daemon_config)
        self.interval_min_spinbox.valueChanged.connect(self._sync_daemon_config)
        self.interval_sec_spinbox.valueChanged.connect(self._sync_daemon_config)
        self.style_combo.currentTextChanged.connect(self._sync_daemon_config)
        self.video_style_combo.currentTextChanged.connect(self._sync_daemon_config)
        self.background_type_combo.currentTextChanged.connect(self._sync_daemon_config)

        self.populate_monitor_layout()
        self.check_all_monitors_set()
        self.stop_slideshow()

    # ---- Overrides --------------------------------------------------------

    def populate_monitor_layout(self):
        super().populate_monitor_layout()
        self.check_all_monitors_set()
    # ---- Daemon -----------------------------------------------------------

    def _start_daemon_countdown_if_active(self):
        if self._is_daemon_running_config():
            try:
                with open(DAEMON_CONFIG_PATH, "r") as f:
                    data = json.load(f)
                    self.interval_sec = data.get("interval_seconds", 300)
                    last_change = data.get("last_change_timestamp", 0)
                    if last_change > 0:
                        elapsed = int(time.time()) - last_change
                        self.time_remaining_sec = max(0, self.interval_sec - elapsed)
                    else:
                        self.time_remaining_sec = self.interval_sec

                    if not hasattr(self, "countdown_timer") or not self.countdown_timer:
                        self.countdown_timer = QTimer(self)
                        self.countdown_timer.timeout.connect(self.update_countdown)

                    if not self.countdown_timer.isActive():
                        self.countdown_timer.start(1000)

                    self.update_countdown()

                    if not self.slideshow_group.isVisible():
                        self.slideshow_group.setVisible(True)
            except Exception:
                pass

    def _get_daemon_script_path(self):
        script_path = ROOT_DIR / "backend" / "src" / "utils" / "display" / "slideshow_daemon.py"
        if script_path.exists():
            return str(script_path)

        current_dir = Path(__file__).resolve().parent
        root = current_dir
        while not (root / "backend").exists() and root != root.parent:
            root = root.parent

        script_path = root / "backend" / "src" / "utils" / "display" / "slideshow_daemon.py"
        if not script_path.exists():
            script_path = root / "slideshow_daemon.py"

        return str(script_path)

    def _is_daemon_running_config(self):
        if not DAEMON_CONFIG_PATH.exists():
            return False
        try:
            with open(DAEMON_CONFIG_PATH, "r") as f:
                data = json.load(f)
                return data.get("running", False)
        except Exception:
            return False

    def _sync_daemon_config(self):
        if not self._is_daemon_running_config():
            return

        last_change_timestamp = 0
        monitor_history = getattr(self, "monitor_history", {})
        try:
            if os.path.exists(DAEMON_CONFIG_PATH):
                with open(DAEMON_CONFIG_PATH, "r") as f:
                    old_config = json.load(f)
                    last_change_timestamp = old_config.get("last_change_timestamp", 0)
                    file_history = old_config.get("monitor_history", {})
                    for k, v in file_history.items():
                        if k not in monitor_history:
                            monitor_history[k] = v
                    self.monitor_history = monitor_history
        except Exception:
            pass

        style_to_use = (
            f"SmartVideoWallpaper::{self.video_style}"
            if self.background_type in ["Smart Video", "Smart Video Slideshow"]
            else self.wallpaper_style
        )

        config = {
            "running": True,
            "interval_seconds": (self.interval_min_spinbox.value() * 60)
            + self.interval_sec_spinbox.value(),
            "style": style_to_use,
            "monitor_queues": self.monitor_slideshow_queues,
            "current_paths": self.monitor_image_paths,
            "playback_order": self.playback_order_combo.currentText(),
            "filter_directories": [],
            "monitor_geometries": {
                str(i): {"x": m.x, "y": m.y, "width": m.width, "height": m.height}
                for i, m in enumerate(self.monitors)
            },
            "last_change_timestamp": last_change_timestamp,
            "monitor_history": self.monitor_history,
        }

        try:
            with open(DAEMON_CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=4)
        except Exception:
            pass

    def toggle_daemon(self, checked: bool):
        start = checked
        if start:
            self.stop_slideshow()

        last_change_timestamp = 0
        monitor_history = getattr(self, "monitor_history", {})
        try:
            if os.path.exists(DAEMON_CONFIG_PATH):
                with open(DAEMON_CONFIG_PATH, "r") as f:
                    old_config = json.load(f)
                    last_change_timestamp = old_config.get("last_change_timestamp", 0)
                    file_history = old_config.get("monitor_history", {})
                    for k, v in file_history.items():
                        if k not in monitor_history:
                            monitor_history[k] = v
                    self.monitor_history = monitor_history
        except Exception:
            pass

        style_to_use = (
            f"SmartVideoWallpaper::{self.video_style}"
            if self.background_type in ["Smart Video", "Smart Video Slideshow"]
            else self.wallpaper_style
        )

        config = {
            "running": start,
            "interval_seconds": (self.interval_min_spinbox.value() * 60)
            + self.interval_sec_spinbox.value(),
            "style": style_to_use,
            "monitor_queues": self.monitor_slideshow_queues,
            "current_paths": self.monitor_image_paths,
            "playback_order": self.playback_order_combo.currentText(),
            "filter_directories": [],
            "monitor_geometries": {
                str(i): {"x": m.x, "y": m.y, "width": m.width, "height": m.height}
                for i, m in enumerate(self.monitors)
            },
            "last_change_timestamp": last_change_timestamp,
            "monitor_history": self.monitor_history,
        }

        try:
            with open(DAEMON_CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save daemon config: {e}")
            return

        if start:
            script_path = self._get_daemon_script_path()
            if not os.path.exists(script_path):
                QMessageBox.critical(
                    self, "Error", f"Daemon script not found at:\n{script_path}"
                )
                return
            try:
                if platform.system() == "Windows":
                    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    subprocess.Popen(
                        [sys.executable, script_path],
                        creationflags=creationflags,
                    )
                else:
                    subprocess.Popen(
                        [sys.executable, script_path],
                        start_new_session=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                self.btn_daemon_toggle.setText("Stop Background Daemon")
                self.btn_daemon_toggle.setStyleSheet(
                    "background-color: #c0392b; color: white; padding: 5px;"
                )
                self._start_daemon_countdown_if_active()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to start daemon: {e}")
        else:
            self.btn_daemon_toggle.setText("Start Background Daemon")
            self.btn_daemon_toggle.setStyleSheet(
                "background-color: #27ae60; color: white; padding: 5px;"
            )
            if hasattr(self, "countdown_timer") and self.countdown_timer:
                self.countdown_timer.stop()
            self.countdown_label.setText("Timer: --:--")

    def view_daemon_logs(self):
        log_path = Path.home() / ".image-toolkit" / "logs" / "slideshow_daemon.log"
        if not log_path.exists():
            QMessageBox.information(self, "No Logs", "No daemon log file found yet.")
            return
        try:
            if platform.system() == "Windows":
                start_fn = getattr(os, "startfile", None)
                if start_fn:
                    start_fn(str(log_path))
            elif platform.system() == "Darwin":
                subprocess.run(["open", str(log_path)])
            else:
                subprocess.run(["xdg-open", str(log_path)])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open log file: {e}")

    # ---- Style selectors --------------------------------------------------

    def _get_relevant_styles(self) -> Mapping[str, Optional[Union[str, int, Tuple[str, str]]]]:
        system = platform.system()
        if system == "Windows":
            return cast(Mapping[str, Optional[Union[str, int, Tuple[str, str]]]], WALLPAPER_STYLES["Windows"])
        elif system == "Linux":
            if self.qdbus:
                return cast(Mapping[str, Optional[Union[str, int, Tuple[str, str]]]], WALLPAPER_STYLES["KDE"])
            else:
                return cast(Mapping[str, Optional[Union[str, int, Tuple[str, str]]]], WALLPAPER_STYLES["GNOME"])
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
        is_video_slideshow = type_name == "Smart Video Slideshow"
        is_video_static = type_name == "Smart Video"

        self.slideshow_group.setVisible(is_slideshow or is_video_slideshow)
        self.btn_daemon_toggle.setVisible(is_slideshow or is_video_slideshow)
        self.btn_view_logs.setVisible(is_slideshow or is_video_slideshow)
        self.solid_color_widget.setVisible(is_solid_color)

        if is_video_static or is_video_slideshow:
            self.video_style_combo.show()
            self.video_style_label.show()
        else:
            self.video_style_combo.hide()
            self.video_style_label.hide()

        main_controls_enabled = not is_solid_color
        self.style_layout_widget.setVisible(main_controls_enabled)

        if is_video_static or is_video_slideshow:
            self.style_combo.setVisible(False)
            self.style_label.setVisible(False)
            self.video_style_combo.setVisible(True)
            self.video_style_label.setVisible(True)
        else:
            self.style_combo.setVisible(True)
            self.style_label.setVisible(True)
            self.video_style_combo.setVisible(False)
            self.video_style_label.setVisible(False)

        self._sync_daemon_config()
        self.scan_directory_path.setEnabled(main_controls_enabled)
        self.gallery_scroll_area.setEnabled(main_controls_enabled) # pyrefly: ignore [missing-attribute]

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

    # ---- Wallpaper actions ------------------------------------------------

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
        elif self.background_type in ["Slideshow", "Smart Video Slideshow"]:
            self.start_slideshow()
        else:
            if self.current_wallpaper_worker:
                self.stop_wallpaper_worker()
            else:
                self.run_wallpaper_worker()

    @Slot()
    def start_slideshow(self):
        if self._is_daemon_running_config():
            QMessageBox.warning(
                self,
                "Daemon Conflict",
                "The background slideshow daemon is currently running. "
                "Please stop it before starting a local slideshow to avoid double-transitions.",
            )
            return

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
            queue = self.monitor_slideshow_queues.get(mid, [])
            current_path = self.monitor_image_paths.get(mid)
            if current_path in queue:
                self.monitor_current_index[mid] = queue.index(current_path) # pyrefly: ignore [bad-argument-type]
            else:
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
        self._cycle_slideshow_wallpaper(increment=False)
        self.set_wallpaper_btn.setText("Slideshow Running (Stop)")
        self.set_wallpaper_btn.setStyleSheet(STYLE_STOP_ACTION)
        self.set_wallpaper_btn.setEnabled(True)

    def update_countdown(self):
        if self.time_remaining_sec % 5 == 0 or self.time_remaining_sec <= 0:
            try:
                if self._is_daemon_running_config():
                    with open(DAEMON_CONFIG_PATH, "r") as f:
                        config = json.load(f)
                        last_change = config.get("last_change_timestamp", 0)
                        interval = config.get("interval_seconds", self.interval_sec)
                        last_error = config.get("last_error")

                        if last_error:
                            self.countdown_label.setText(f"Error: {last_error[:20]}...")
                            self.countdown_label.setToolTip(last_error)
                        elif last_change > 0:
                            elapsed = int(time.time()) - last_change
                            remaining = max(0, interval - elapsed)
                            self.time_remaining_sec = remaining
                            self.countdown_label.setToolTip("")
            except Exception:
                pass

        if self.time_remaining_sec > 0:
            self.time_remaining_sec -= 1
            m, s = divmod(self.time_remaining_sec, 60)
            if "Error" not in self.countdown_label.text():
                self.countdown_label.setText(f"Timer: {m:02}:{s:02}")
        else:
            if "Error" not in self.countdown_label.text():
                self.countdown_label.setText("Timer: 00:00")
            if not self._is_daemon_running_config():
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

        if self.countdown_timer and self.countdown_timer.isActive() and not self._is_daemon_running_config():
            self.countdown_timer.stop()
            self.countdown_timer.deleteLater()
            self.countdown_timer = None

        self.stop_wallpaper_worker()
        self.check_all_monitors_set()

    def cancel_loading(self):
        super().cancel_loading()

        if self.img_scanner_worker:
            with contextlib.suppress(Exception):
                self.img_scanner_worker.stop()

        if self.vid_scanner_worker:
            with contextlib.suppress(Exception):
                self.vid_scanner_worker.stop()

        if (
            hasattr(self, "_pagination_debounce_timer")
            and self._pagination_debounce_timer.isActive()
        ):
            self._pagination_debounce_timer.stop()

        if self.slideshow_timer and self.slideshow_timer.isActive():
            self.slideshow_timer.stop()
        if self.countdown_timer and self.countdown_timer.isActive() and not self._is_daemon_running_config():
            self.countdown_timer.stop()

        for win in list(self.open_queue_windows):
            with contextlib.suppress(Exception):
                win.close()
        self.open_queue_windows.clear()

        for win in list(self.open_image_preview_windows):
            with contextlib.suppress(Exception):
                win.close()
        self.open_image_preview_windows.clear()

        for win in list(self.open_queue_windows):
            try:
                if win.isVisible():
                    win.close()
            except RuntimeError:
                pass
        self.open_queue_windows.clear()

        for win in list(self.open_image_preview_windows):
            try:
                if win.isVisible():
                    win.close()
            except RuntimeError:
                pass
        self.open_image_preview_windows.clear()

        if not self._is_daemon_running_config():
            self.monitor_current_index.clear()
            self.monitor_history.clear()
            self.time_remaining_sec = 0
            self.countdown_label.setText("Timer: --:--")

        self.unlock_ui_for_wallpaper()

    @Slot()
    def skip_current_wallpapers(self):
        if self.background_type == "Solid Color":
            return

        self._cycle_slideshow_wallpaper(increment=True)

        if self._is_daemon_running_config():
            self._sync_daemon_config()
            try:
                if os.path.exists(DAEMON_CONFIG_PATH):
                    with open(DAEMON_CONFIG_PATH, "r") as f:
                        config = json.load(f)
                    config["last_change_timestamp"] = int(time.time())
                    with open(DAEMON_CONFIG_PATH, "w") as f:
                        json.dump(config, f, indent=4)
                    self.time_remaining_sec = self.interval_sec
                    self.update_countdown()
            except Exception:
                pass
        elif self.slideshow_timer and self.slideshow_timer.isActive():
            self.slideshow_timer.start(self.interval_sec * 1000)
            self.time_remaining_sec = self.interval_sec
            if self.countdown_timer and self.countdown_timer.isActive():
                self.update_countdown()

    @Slot()
    def _cycle_slideshow_wallpaper(self, increment: bool = True):  # noqa: C901
        monitor_ids = list(self.monitor_widgets.keys())
        if not monitor_ids:
            return
        if self.background_type == "Solid Color":
            self.stop_slideshow()
            return
        try:
            new_monitor_paths: Dict[str, Optional[str]] = {}
            has_valid_path_to_set = False
            for monitor_id in monitor_ids:
                current_index = self.monitor_current_index.get(monitor_id, -1)
                queue = self.monitor_slideshow_queues.get(monitor_id, [])
                current_queue_length = len(queue)
                if current_queue_length > 0:
                    if not increment:
                        next_index = max(0, current_index)
                        playback_order = self.playback_order_combo.currentText()
                        if playback_order == "Random" and 0 <= next_index < len(queue):
                            next_path = queue[next_index]
                            if monitor_id not in self.monitor_history:
                                self.monitor_history[monitor_id] = []
                            if next_path not in self.monitor_history[monitor_id]:
                                self.monitor_history[monitor_id].append(next_path)
                    else:
                        playback_order = self.playback_order_combo.currentText()
                        if playback_order == "Random":
                            history = self.monitor_history.get(monitor_id, [])
                            valid_indices = [
                                idx
                                for idx, path in enumerate(queue)
                                if path not in history
                            ]

                            if not valid_indices:
                                current_path = (
                                    queue[current_index]
                                    if 0 <= current_index < len(queue)
                                    else None
                                )
                                if current_path and current_queue_length > 1:
                                    self.monitor_history[monitor_id] = [current_path]
                                    valid_indices = [
                                        idx
                                        for idx, path in enumerate(queue)
                                        if path != current_path
                                    ]
                                else:
                                    self.monitor_history[monitor_id] = []
                                    valid_indices = list(range(current_queue_length))

                            next_index = random.choice(valid_indices)
                            next_path = queue[next_index]
                            if monitor_id not in self.monitor_history:
                                self.monitor_history[monitor_id] = []
                            self.monitor_history[monitor_id].append(next_path)
                        elif playback_order == "Reverse Sequential":
                            if current_index == -1:
                                next_index = current_queue_length - 1
                            else:
                                next_index = (current_index - 1) % current_queue_length
                        else:
                            next_index = (current_index + 1) % current_queue_length

                    logging.info(
                        f"[SystemDisplaySubTab] Monitor {monitor_id}: current_index={current_index}, "
                        f"playback_order={self.playback_order_combo.currentText()}, "
                        f"increment={increment}, queue_length={current_queue_length} -> next_index={next_index}"
                    )

                    next_path = queue[next_index]
                    new_monitor_paths[monitor_id] = next_path
                    self.monitor_current_index[monitor_id] = next_index
                    has_valid_path_to_set = True
                else:
                    new_monitor_paths[monitor_id] = self.monitor_image_paths.get(monitor_id)
                    self.monitor_current_index[monitor_id] = -1
            if not has_valid_path_to_set:
                self.stop_slideshow()
                return
            # Mutate in place rather than reassign: monitor_image_paths is
            # shared by reference with MonitorDisplaySubTab (see
            # WallpaperTab.__init__); reassigning here would silently break
            # that link and desync the two subtabs' view of "current path".
            self.monitor_image_paths.clear()
            self.monitor_image_paths.update(new_monitor_paths)
            self.run_wallpaper_worker(slideshow_mode=True)
            for monitor_id, path in new_monitor_paths.items():
                if monitor_id in self.monitor_widgets and path:
                    thumb = self._get_or_generate_thumbnail(path)
                    self.monitor_widgets[monitor_id].set_image(path, thumb)
            self.time_remaining_sec = self.interval_sec
        except Exception as e:
            QMessageBox.critical(
                self, "Slideshow Cycle Error", f"Failed to cycle wallpaper: {str(e)}"
            )
            self.stop_slideshow()

    # ---- Monitor interaction ----------------------------------------------

    # ---- Wallpaper worker -------------------------------------------------

    def run_wallpaper_worker(self, slideshow_mode=False):  # noqa: C901
        from ....helpers import ImageScannerWorker
        if self.current_wallpaper_worker:
            print("Wallpaper worker is already running.")
            return

        path_map: Dict[str, Optional[str]]
        final_path_map: Dict[str, Optional[str]]

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
                    desktop = "KDE" if self.qdbus else "Gnome"
                except Exception:
                    desktop = None
            elif system == "Windows":
                desktop = "Windows"
            else:
                desktop = None

            if self.background_type in ["Smart Video", "Smart Video Slideshow"]:
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
        self.gallery_scroll_area.setEnabled(False) # pyrefly: ignore [missing-attribute]
        self.scan_directory_path.setEnabled(False)
        self.style_combo.setEnabled(False)
        self.video_style_combo.setEnabled(False)
        self.background_type_combo.setEnabled(False)
        self.solid_color_widget.setEnabled(False)
        for widget in self.monitor_widgets.values():
            widget.setEnabled(False)
        QApplication.processEvents()

    def unlock_ui_for_wallpaper(self):
        self.set_wallpaper_btn.setText("Set Wallpaper")
        self.set_wallpaper_btn.setStyleSheet(STYLE_START_ACTION)
        self.slideshow_group.setEnabled(True)
        self.gallery_scroll_area.setEnabled(True) # pyrefly: ignore [missing-attribute]
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
                        thumb = self._get_or_generate_thumbnail(path)
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

    def _apply_vault_slideshow_defaults(self):
        main_win = self.window()
        if not (main_win and hasattr(main_win, "cached_creds")):
            return
        prefs = main_win.cached_creds.get("preferences", {})
        if self.interval_min_spinbox.value() == 5:
            vault_min = prefs.get("slideshow_interval_min", 5)
            self.interval_min_spinbox.setValue(vault_min)
        if self.interval_sec_spinbox.value() == 0:
            vault_sec = prefs.get("slideshow_interval_sec", 0)
            self.interval_sec_spinbox.setValue(vault_sec)
        if self.playback_order_combo.currentText() == "Sequential":
            vault_order = prefs.get("slideshow_order", "Sequential")
            self.playback_order_combo.setCurrentText(vault_order)

    # ---- Config -----------------------------------------------------------

    def collect(self) -> dict:
        monitor_order = []
        monitor_layout = []
        if isinstance(self.monitor_layout_container, DraggableMonitorContainer):
            for row in self.monitor_layout_container.rows:
                for widget in row:
                    if isinstance(widget, MonitorDropView):
                        monitor_order.append(widget.monitor_id)
            monitor_layout = self.monitor_layout_container.get_layout_structure()

        return {
            "scan_directory": self.scan_directory_path.text(),
            "wallpaper_style": self.wallpaper_style,
            "video_style": self.video_style,
            "slideshow_enabled": (self.background_type == "Slideshow"),
            "interval_minutes": self.interval_min_spinbox.value(),
            "interval_seconds": self.interval_sec_spinbox.value(),
            "background_type": self.background_type,
            "solid_color_hex": self.solid_color_hex,
            "playback_order": self.playback_order_combo.currentText(),
            "monitor_order": monitor_order,
            "monitor_layout": monitor_layout,
            "monitor_queues": self.monitor_slideshow_queues,
            "monitor_image_paths": self.monitor_image_paths,
        }

    def get_default_config(self) -> Dict[str, Any]:
        default_style = (
            self.style_combo.itemText(0) if self.style_combo.count() > 0 else "Fill"
        )
        return {
            "scan_directory": "",
            "wallpaper_style": default_style,
            "video_style": "Scaled and Cropped",
            "slideshow_enabled": False,
            "interval_minutes": 5,
            "interval_seconds": 0,
            "background_type": "Image",
            "solid_color_hex": "#000000",
            "monitor_order": [],
            "monitor_layout": [],
        }

    def set_config(self, config: Dict[str, Any]):  # noqa: C901
        try:
            if "scan_directory" in config:
                self.scan_directory_path.setText(config.get("scan_directory", ""))
                if os.path.isdir(config["scan_directory"]):
                    self.populate_scan_image_gallery(config["scan_directory"])
            if "wallpaper_style" in config:
                self.style_combo.setCurrentText(config.get("wallpaper_style", "Fill"))
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
            if "playback_order" in config:
                self.playback_order_combo.setCurrentText(
                    config.get("playback_order", "Sequential")
                )

            layout_restored = False
            if "monitor_layout" in config and config["monitor_layout"] and isinstance(self.monitor_layout_container, DraggableMonitorContainer):
                    self.monitor_layout_container.set_layout_structure(
                        config["monitor_layout"], self.monitor_widgets
                    )
                    layout_restored = True

            if (
                not layout_restored
                and "monitor_order" in config
                and config["monitor_order"]
            ):
                target_order = config["monitor_order"]
                present_monitor_ids = set(self.monitor_widgets.keys())
                valid_order = [
                    mid for mid in target_order if mid in present_monitor_ids
                ]

                if isinstance(self.monitor_layout_container, DraggableMonitorContainer):
                    self.monitor_layout_container.clear_widgets()
                    for mid in valid_order:
                        if mid in self.monitor_widgets:
                            self.monitor_layout_container.addWidget(self.monitor_widgets[mid]) # pyrefly: ignore [bad-argument-type]
                    for mid, w in self.monitor_widgets.items():
                        if mid not in valid_order:
                            self.monitor_layout_container.addWidget(w) # pyrefly: ignore [bad-argument-type]

            # Both monitor_slideshow_queues and monitor_image_paths are
            # shared by reference with MonitorDisplaySubTab (see
            # WallpaperTab.__init__); mutate them in place instead of
            # reassigning, or session restore silently breaks that link and
            # the Monitor Display subtab's queue/current-path edits stop
            # being visible to this tab's run_wallpaper_worker().
            if "monitor_queues" in config:
                self.monitor_slideshow_queues.clear()
                self.monitor_slideshow_queues.update(config.get("monitor_queues", {}))
            if "monitor_image_paths" in config:
                saved_paths = config.get("monitor_image_paths", {})
                self.monitor_image_paths.clear()
                self.monitor_image_paths.update(saved_paths)
                for mid, path in saved_paths.items():
                    if mid in self.monitor_widgets and path:
                        if Path(path).exists():
                            thumb = self._get_or_generate_thumbnail(path)
                            self.monitor_widgets[mid].set_image(path, thumb)
                        else:
                            self.monitor_image_paths[mid] = None
                            self.monitor_widgets[mid].clear()
        except Exception as e:
            QMessageBox.critical(
                self, "Config Error", f"Failed to apply wallpaper configuration:\n{e}"
            )

        if self._is_daemon_running_config():
            self._start_daemon_countdown_if_active()
        self.wallpapers_changed.emit()
