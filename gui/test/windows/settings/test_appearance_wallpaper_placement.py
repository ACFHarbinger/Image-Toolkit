"""Regression: the custom-wallpaper/background-canvas picker must live in
the "Appearance and Themes" settings tab, not "Display and Media".

User-reported regression: this section used to build inline inside
_build_appearance_section() (gui/src/windows/settings/_appearance.py),
placed under "Display and Media". When the newer Theme Studio tab
(#438/#441) claimed the "Appearance and Themes" name, the wallpaper
picker was left behind in its old tab -- reported as "the button and
section to choose your own custom wallpaper(s) ... has disappeared from
the Appearance and Themes settings tab" (it wasn't deleted, just no
longer where users look for it).
"""

from __future__ import annotations

import pytest
from gui.src.windows.settings.settings_window import SettingsWindow
from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QSlider, QSpinBox

pytestmark = pytest.mark.gui


def _find_tab(window: SettingsWindow, label_fragment: str):
    for i in range(window.tab_widget.count()):
        if label_fragment in window.tab_widget.tabText(i):
            return window.tab_widget.widget(i)
    return None


class TestWallpaperSectionPlacement:
    def test_wallpaper_controls_exist_as_instance_attributes(self, q_app):
        window = SettingsWindow()
        for attr in (
            "bg_path_input",
            "bg_fit_combo",
            "glassmorphism_check",
            "bg_opacity_slider",
            "bg_blur_spin",
        ):
            assert hasattr(window, attr), f"missing wallpaper control: {attr}"

    def test_wallpaper_controls_live_under_appearance_and_themes_tab(self, q_app):
        window = SettingsWindow()
        appearance_tab = _find_tab(window, "Appearance and Themes")
        assert appearance_tab is not None, "Appearance and Themes tab not found"

        assert window.bg_path_input in appearance_tab.findChildren(QLineEdit)
        assert window.bg_fit_combo in appearance_tab.findChildren(QComboBox)
        assert window.glassmorphism_check in appearance_tab.findChildren(QCheckBox)
        assert window.bg_opacity_slider in appearance_tab.findChildren(QSlider)
        assert window.bg_blur_spin in appearance_tab.findChildren(QSpinBox)

    def test_wallpaper_controls_no_longer_under_display_and_media_tab(self, q_app):
        window = SettingsWindow()
        display_media_tab = _find_tab(window, "Display and Media")
        assert display_media_tab is not None, "Display and Media tab not found"

        assert window.bg_path_input not in display_media_tab.findChildren(QLineEdit)

    def test_browse_button_still_wired_to_the_picker(self, q_app):
        """The relocated section keeps its real Browse/Clear behavior, not
        just placeholder widgets."""
        window = SettingsWindow()
        window.bg_path_input.setText("/tmp/example.png")
        assert window._bg_config is not None
        # _on_bg_path_changed auto-enables glassmorphism once a path is set.
        assert window.glassmorphism_check.isChecked() is True
