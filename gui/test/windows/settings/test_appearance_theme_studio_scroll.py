"""Regression: the "Appearance and Themes" tab must scroll instead of
compressing its content.

User-reported regression: after the wallpaper-picker section was relocated
into this tab (see test_appearance_wallpaper_placement.py), the tab's total
content height exceeded the available space. Because this was the only
settings tab NOT wrapped in a QScrollArea (every sibling tab is built via
settings_window.py's local create_tab_scroll_area() helper), Qt compressed
the whole tab's layout -- squeezing the ThemeStudioPanel's own Typography
row (Font family/Scale/Weight) down to unreadable, garbled-looking widgets.

Fix: _build_theme_studio_tab() now wraps its content in its own
QScrollArea(setWidgetResizable(True)), matching every sibling tab.
"""

from __future__ import annotations

import pytest
from gui.src.windows.settings.settings_window import SettingsWindow
from PySide6.QtWidgets import QScrollArea

pytestmark = pytest.mark.gui


def _find_tab(window: SettingsWindow, label_fragment: str):
    for i in range(window.tab_widget.count()):
        if label_fragment in window.tab_widget.tabText(i):
            return window.tab_widget.widget(i)
    return None


class TestAppearanceTabScrolls:
    def test_appearance_tab_is_wrapped_in_a_scroll_area(self, q_app):
        window = SettingsWindow()
        appearance_tab = _find_tab(window, "Appearance and Themes")
        assert appearance_tab is not None, "Appearance and Themes tab not found"

        scroll_areas = appearance_tab.findChildren(QScrollArea)
        assert scroll_areas, "Appearance and Themes tab has no QScrollArea wrapper"
        assert any(sa.widgetResizable() for sa in scroll_areas)

    def test_theme_studio_typography_controls_keep_normal_size_hint(self, q_app):
        """The Typography row's controls must not be squeezed below a
        sane minimum height by the tab's outer layout."""
        from PySide6.QtWidgets import QComboBox

        window = SettingsWindow()
        typography_controls = window.theme_studio.findChildren(QComboBox)
        assert typography_controls, "expected at least one QComboBox in ThemeStudioPanel"
        for combo in typography_controls:
            assert combo.sizeHint().height() >= 20, (
                f"{combo.objectName() or combo}: sizeHint height "
                f"{combo.sizeHint().height()} looks squeezed"
            )

    def test_wallpaper_and_typography_controls_still_coexist(self, q_app):
        """Both the relocated wallpaper section and the pre-existing
        Typography controls must be reachable under the same tab."""
        window = SettingsWindow()
        appearance_tab = _find_tab(window, "Appearance and Themes")
        assert appearance_tab is not None

        assert hasattr(window, "bg_path_input")
        assert hasattr(window, "theme_studio")
        # Both must be descendants of the same tab page (through the scroll
        # area's viewport), not orphaned elsewhere.
        from PySide6.QtWidgets import QLineEdit

        assert window.bg_path_input in appearance_tab.findChildren(QLineEdit)
