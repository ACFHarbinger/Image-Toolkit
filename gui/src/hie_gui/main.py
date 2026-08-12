"""Standalone HIE PySide6 application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMainWindow

from .hie_tab import HieTab


def create_window() -> QMainWindow:
    window = QMainWindow()
    window.setWindowTitle("Hybrid Image Editor")
    window.setCentralWidget(HieTab())
    window.resize(1100, 720)
    return window


def main() -> int:
    app = QApplication(sys.argv)
    window = create_window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
