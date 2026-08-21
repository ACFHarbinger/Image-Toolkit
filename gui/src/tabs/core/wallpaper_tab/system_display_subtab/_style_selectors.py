"""Wallpaper/video style selection and background-type visibility switching.

Extracted from ``system_display_subtab.py`` -- pure code motion, no logic
change (see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import platform
from typing import Mapping, Optional, Tuple, Union, cast

from backend.src.constants import WALLPAPER_STYLES
from PySide6.QtCore import Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QWidget

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...protos.system_display_subtab import SystemDisplaySubTabHostProtocol


class _StyleSelectorsMixin:
    """Resolve platform-relevant styles and wire the style/background-type combos."""

    def _get_relevant_styles(self: "SystemDisplaySubTabHostProtocol") -> Mapping[str, Optional[Union[str, int, Tuple[str, str]]]]:
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
    def _update_wallpaper_style(self: "SystemDisplaySubTabHostProtocol", style_name: str):
        self.wallpaper_style = style_name

    @Slot(str)
    def _update_video_style(self: "SystemDisplaySubTabHostProtocol", style_name: str):
        self.video_style = style_name

    @Slot(bool)
    def _on_video_runtime_interval_toggled(self: "SystemDisplaySubTabHostProtocol", checked: bool):
        self.interval_min_spinbox.setEnabled(not checked)
        self.interval_sec_spinbox.setEnabled(not checked)
        self._sync_daemon_config()

    @Slot(str)
    def _update_background_type(self: "SystemDisplaySubTabHostProtocol", type_name: str):
        self.background_type = type_name

        is_solid_color = type_name == "Solid Color"
        is_slideshow = type_name == "Slideshow"
        is_video_slideshow = type_name == "Smart Video Slideshow"
        is_video_static = type_name == "Smart Video"

        self.slideshow_group.setVisible(is_slideshow or is_video_slideshow)
        self.btn_daemon_toggle.setVisible(is_slideshow or is_video_slideshow)
        self.btn_view_logs.setVisible(is_slideshow or is_video_slideshow)
        self.solid_color_widget.setVisible(is_solid_color)

        self.chk_video_runtime_interval.setVisible(is_video_slideshow)
        if not is_video_slideshow:
            self.chk_video_runtime_interval.setChecked(False)

        self.playback_order_label.setVisible(is_slideshow or is_video_slideshow)
        self.playback_order_combo.setVisible(is_slideshow or is_video_slideshow)

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
        self.gallery_scroll_area.setEnabled(main_controls_enabled)  # pyrefly: ignore [missing-attribute]

        if is_solid_color and self.slideshow_timer and self.slideshow_timer.isActive():
            self.stop_slideshow()

        self.check_all_monitors_set()

    @Slot()
    def select_solid_color(self: "SystemDisplaySubTabHostProtocol"):
        initial_color = QColor(self.solid_color_hex)
        color = QColorDialog.getColor(
            initial_color, cast(QWidget, self), "Select Solid Background Color"
        )
        if color.isValid():
            self.solid_color_hex = color.name().upper()
            self.solid_color_preview.setStyleSheet(
                f"background-color: {self.solid_color_hex}; border: 1px solid #4f545c;"
            )
            self.check_all_monitors_set()


__all__ = ["_StyleSelectorsMixin"]
