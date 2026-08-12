"""Standalone HIE PySide6 application entry point.

Run with `python -m main [--image PATH]` (or the `hie-gui` entry point) from `gui/src`.
"""

from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication, QMainWindow

from hie_tab import HieTab


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hie-gui", description="Standalone Hybrid Image Editor")
    parser.add_argument("--image", help="open this image file on startup")
    return parser


def create_window(*, image: str | None = None) -> QMainWindow:
    window = QMainWindow()
    window.setWindowTitle("Hybrid Image Editor")
    tab = HieTab()
    window.setCentralWidget(tab)
    window.resize(1100, 720)
    if image:
        # Deferred: the window isn't shown yet, but load_image_path only
        # touches the (already-constructed) viewport/document state, not
        # anything that needs a visible/mapped window.
        if not tab.load_image_path(image):
            print(f"hie-gui: could not open image: {image}", file=sys.stderr)
    return window


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    app = QApplication(sys.argv[:1])
    window = create_window(image=args.image)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
