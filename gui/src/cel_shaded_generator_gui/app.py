"""Standalone desktop application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from cel_shaded_generator_gui.tabs.animation_tab import MangaAnimationTab
from cel_shaded_generator_gui.tabs.colorization_tab import MangaColorizationTab
from cel_shaded_generator_gui.tabs.puppeteering_tab import MangaPuppeteeringTab


def build_window() -> QMainWindow:
    """Build the main window without starting the event loop.

    Keeping construction separate makes installed-wheel smoke tests possible
    and gives future hosts, including Krita, a reusable composition boundary.
    """
    tabs = QTabWidget()
    tabs.addTab(MangaColorizationTab(), "Colorization")
    tabs.addTab(MangaAnimationTab(), "Animation")
    tabs.addTab(MangaPuppeteeringTab(), "Puppeteering")

    window = QMainWindow()
    window.setWindowTitle("Cel-Shaded-Generator")
    window.setCentralWidget(tabs)
    window.resize(1400, 900)
    return window


def main() -> int:
    """Launch the standalone desktop application."""
    app = QApplication.instance() or QApplication(sys.argv)
    window = build_window()
    window.show()
    return app.exec()
