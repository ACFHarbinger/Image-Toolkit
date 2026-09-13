"""Live theme refresh for baked-in component QSS (#620 / R4.3)."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from gui.src.theming.theme_api import (
    ThemedQss,
    color,
    current_base,
    qss,
    refresh_component_styles,
    set_current_base,
)


def test_qss_returns_themed_fragment_and_tracks_widget(q_app) -> None:
    set_current_base("dark")
    label = QLabel()
    sheet = qss("muted_label")
    assert isinstance(sheet, ThemedQss)
    assert sheet.component == "muted_label"
    label.setStyleSheet(sheet)
    assert color("muted_text", base="dark") in label.styleSheet()


def test_refresh_rewrites_dark_placeholders_to_light(q_app) -> None:
    set_current_base("dark")
    label = QLabel()
    label.setStyleSheet(qss("muted_label"))
    dark_muted = color("muted_text", base="dark")
    light_muted = color("muted_text", base="light")
    assert dark_muted != light_muted
    assert dark_muted in label.styleSheet()

    n = refresh_component_styles(base="light")
    assert n >= 1
    assert current_base() == "light"
    assert light_muted in label.styleSheet()
    assert dark_muted not in label.styleSheet()


def test_raw_stylesheet_is_not_refreshed(q_app) -> None:
    set_current_base("dark")
    label = QLabel()
    label.setStyleSheet(qss("muted_label"))
    label.setStyleSheet("color: #ff00ff;")
    refresh_component_styles(base="light")
    assert label.styleSheet() == "color: #ff00ff;"


def test_color_follows_current_base() -> None:
    set_current_base("dark")
    dark = color("text")
    set_current_base("light")
    light = color("text")
    assert dark != light
    set_current_base("dark")
