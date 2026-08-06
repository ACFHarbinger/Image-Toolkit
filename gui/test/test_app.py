"""Tests for the standalone GUI composition boundary."""

from PySide6.QtWidgets import QTabWidget

from cel_shaded_generator_gui.app import build_window


def test_build_window_composes_three_workspaces(q_app):
    window = build_window()

    tabs = window.centralWidget()
    assert isinstance(tabs, QTabWidget)
    assert tabs.count() == 3
    assert [tabs.tabText(index) for index in range(tabs.count())] == [
        "Colorization",
        "Animation",
        "Puppeteering",
    ]
    assert window.windowTitle() == "Cel-Shaded-Generator"

    window.close()
