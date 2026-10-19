"""Tests for the standalone GUI composition boundary."""

from csg_gui.app import build_window
from PySide6.QtWidgets import QTabWidget


def test_build_window_composes_four_workspaces(q_app):
    window = build_window()

    tabs = window.centralWidget()
    assert isinstance(tabs, QTabWidget)
    assert tabs.count() == 4
    assert [tabs.tabText(index) for index in range(tabs.count())] == [
        "Colorization",
        "Animation",
        "Puppeteering",
        "Reference Coloring (Editor)",
    ]
    assert window.windowTitle() == "Cel-Shaded-Generator"

    window.close()
