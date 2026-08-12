"""Standalone PySide6 entry point; embedding can reuse ``create_window``."""

from __future__ import annotations

import sys


def create_window():
    from PySide6.QtWidgets import QLabel, QMainWindow

    window = QMainWindow()
    window.setWindowTitle("Hybrid Image Editor")
    window.setCentralWidget(QLabel("HIE GUI shell ready for Image-Toolkit embedding."))
    return window


def main() -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = create_window()
    window.resize(900, 600)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
