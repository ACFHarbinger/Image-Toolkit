"""Full UI construction for ``SystemDisplaySubTab``.

Extracted from ``SystemDisplaySubTab.__init__`` -- pure code motion, no
logic change, to keep the file under the codebase's 500-code-line
convention (§5.17).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, cast

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .....components.tag_chip_widget import FlowLayout
from .....styles import STYLE_START_ACTION, apply_shadow_effect, set_button_role

if TYPE_CHECKING:
    from ...protos.system_display_subtab import SystemDisplaySubTabHostProtocol


class _UIBuilderMixin:
    """Builds the scrollable content area: monitor layout, settings, gallery, action bar."""

    gallery_layout: Optional[QGridLayout]

    def _build_ui(self: "SystemDisplaySubTabHostProtocol"):
        self.pagination_widget = self.create_pagination_controls()

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        self.main_scroll_area = QScrollArea()
        self.main_scroll_area.setWidgetResizable(True)
        self.main_scroll_area.setWidget(content_widget)

        main_layout = QVBoxLayout(cast(QWidget, self))
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.main_scroll_area)
        cast(QWidget, self).setLayout(main_layout)

        cast(QWidget, self).setAcceptDrops(True)

        app = QApplication.instance()
        if app is not None:
            self_widget = cast(QWidget, self)
            app.installEventFilter(self_widget)
            # Nothing calls removeEventFilter on a plain deleteLater()/GC
            # teardown (only close() runs closeEvent), so also drop the
            # app-wide filter the moment the C++ object is destroyed --
            # otherwise every subsequent event in the whole app routes
            # through a dead wrapper and the UI stops responding to clicks.
            self_widget.destroyed.connect(
                lambda *_a, _app=app, _obj=self_widget: _app.removeEventFilter(_obj)
            )
        self.main_scroll_area.viewport().setAcceptDrops(True)

        layout_group = self.create_monitor_layout_section(
            "Monitor Layout (Drag to Reorder, Drop images/videos to set)"
        )
        content_layout.addWidget(layout_group)

        settings_group = QGroupBox("Wallpaper Settings")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setContentsMargins(10, 20, 10, 10)

        self._build_background_type_row(settings_layout)
        self._build_slideshow_group(settings_layout)
        self._build_solid_color_row(settings_layout)
        self._build_style_selectors(settings_layout)
        self._build_scan_directory_row(settings_layout)

        content_layout.addWidget(settings_group)

        self._build_gallery_section(content_layout)

        self.playback_order_combo.currentTextChanged.connect(self._sync_daemon_config)
        self.interval_min_spinbox.valueChanged.connect(self._sync_daemon_config)
        self.interval_sec_spinbox.valueChanged.connect(self._sync_daemon_config)
        self.style_combo.currentTextChanged.connect(self._sync_daemon_config)
        self.video_style_combo.currentTextChanged.connect(self._sync_daemon_config)
        self.background_type_combo.currentTextChanged.connect(self._sync_daemon_config)

        self._update_background_type(self.background_type)
        self.populate_monitor_layout()
        self.check_all_monitors_set()
        self.stop_slideshow()

    def _build_background_type_row(self: "SystemDisplaySubTabHostProtocol", settings_layout) -> None:
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

    def _build_slideshow_group(self: "SystemDisplaySubTabHostProtocol", settings_layout) -> None:
        self.slideshow_group = QWidget()
        # FlowLayout, not QHBoxLayout: this row packs an interval control
        # plus 5 buttons (incl. "Fetch Current Wallpapers"/"Skip Current
        # Wallpapers") -- too wide for the app's 800px minimum width in a
        # single non-wrapping row.
        slideshow_layout = FlowLayout(self.slideshow_group)
        slideshow_layout.setContentsMargins(0, 10, 0, 10)

        self.interval_container = QWidget()
        interval_layout = QHBoxLayout(self.interval_container)
        interval_layout.setContentsMargins(0, 0, 0, 0)
        interval_layout.setSpacing(6)

        interval_layout.addWidget(QLabel("Interval:"))
        self.interval_min_spinbox = QSpinBox()
        self.interval_min_spinbox.setRange(0, 60)
        self.interval_min_spinbox.setValue(5)
        self.interval_min_spinbox.setFixedWidth(50)
        interval_layout.addWidget(self.interval_min_spinbox)
        interval_layout.addWidget(QLabel("min"))

        self.interval_sec_spinbox = QSpinBox()
        self.interval_sec_spinbox.setRange(0, 59)
        self.interval_sec_spinbox.setValue(0)
        self.interval_sec_spinbox.setFixedWidth(50)
        interval_layout.addWidget(self.interval_sec_spinbox)
        interval_layout.addWidget(QLabel("sec"))

        slideshow_layout.addWidget(self.interval_container)

        self.chk_video_runtime_interval = QCheckBox("Use Video Runtime as Interval")
        self.chk_video_runtime_interval.setToolTip(
            "Instead of a fixed interval, wait for each video's own runtime "
            "before advancing to the next wallpaper. Falls back to the "
            "fixed interval above for images or when a video's duration "
            "can't be determined."
        )
        self.chk_video_runtime_interval.setVisible(False)
        self.chk_video_runtime_interval.toggled.connect(
            self._on_video_runtime_interval_toggled
        )
        slideshow_layout.addWidget(self.chk_video_runtime_interval)

        # Right-anchors Timer + the action buttons as a group, same as the
        # QHBoxLayout.addStretch(1) this row had before it became a
        # FlowLayout (f588bc27) -- FlowLayout.addStretch() (§ tag_chip_widget)
        # now supports this while still wrapping at narrow widths.
        slideshow_layout.addStretch(1)

        self.countdown_label = QLabel("Timer: --:--")
        self.countdown_label.setStyleSheet(
            "color: #2ecc71; font-weight: bold; font-size: 14px;"
        )
        self.countdown_label.setFixedWidth(100)
        slideshow_layout.addWidget(self.countdown_label)

        self.set_wallpaper_btn = QPushButton("Set Wallpaper")
        self.set_wallpaper_btn.setStyleSheet(STYLE_START_ACTION)
        self.set_wallpaper_btn.clicked.connect(self.handle_set_wallpaper_click)
        slideshow_layout.addWidget(self.set_wallpaper_btn)

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

        if self._reconcile_daemon_liveness_on_startup():
            self.btn_daemon_toggle.setText("Stop Background Daemon")
            self.btn_daemon_toggle.setChecked(True)
            set_button_role(self.btn_daemon_toggle, "danger")
            QTimer.singleShot(1000, self._start_daemon_countdown_if_active)
        else:
            self.btn_daemon_toggle.setText("Start Background Daemon")
            self.btn_daemon_toggle.setChecked(False)
            set_button_role(self.btn_daemon_toggle, "success")

        settings_layout.addWidget(self.slideshow_group)
        self.slideshow_group.setVisible(True)

        QTimer.singleShot(0, self._apply_vault_slideshow_defaults)

    def _build_solid_color_row(self: "SystemDisplaySubTabHostProtocol", settings_layout) -> None:
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

    def _build_style_selectors(self: "SystemDisplaySubTabHostProtocol", settings_layout) -> None:
        self.style_layout_widget = QWidget()
        style_layout = QHBoxLayout(self.style_layout_widget)
        style_layout.setContentsMargins(0, 0, 0, 0)

        self.style_combo = QComboBox()
        initial_styles = self._get_relevant_styles()
        self.style_combo.addItems(initial_styles.keys())  # pyrefly: ignore [bad-argument-type]
        self.style_combo.setCurrentText(list(initial_styles.keys())[0])
        self.wallpaper_style = list(initial_styles.keys())[0]
        self.style_combo.currentTextChanged.connect(self._update_wallpaper_style)

        self.style_label = QLabel("Image Style:")
        style_layout.addWidget(self.style_label)
        style_layout.addWidget(self.style_combo)

        self.video_style_combo = QComboBox()
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

        self.playback_order_label = QLabel("Order:")
        style_layout.addWidget(self.playback_order_label)
        self.playback_order_combo = QComboBox()
        self.playback_order_combo.addItems(
            ["Sequential", "Reverse Sequential", "Random"]
        )
        self.playback_order_combo.setCurrentText("Sequential")
        self.playback_order_combo.setFixedWidth(120)
        style_layout.addWidget(self.playback_order_combo)

        style_layout.addStretch(1)
        settings_layout.addWidget(self.style_layout_widget)

    def _build_scan_directory_row(self: "SystemDisplaySubTabHostProtocol", settings_layout) -> None:
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

    def _build_gallery_section(self: "SystemDisplaySubTabHostProtocol", content_layout) -> None:
        # Virtual-scroll gallery (GUI/UX §2.1 Option A) — replaces the
        # MarqueeScrollArea + QGridLayout grid; pagination is dropped.
        self.gallery = self._build_virtual_gallery()
        self.gallery_scroll_area = self.gallery  # setEnabled() callers

        content_layout.addWidget(self.search_input)
        content_layout.addWidget(self.gallery, 1)

    def _build_action_row(self: "SystemDisplaySubTabHostProtocol", content_layout) -> None:
        pass


__all__ = ["_UIBuilderMixin"]
