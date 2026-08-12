"""Unit tests for standalone HIE GUI runner (hie_gui.main)."""

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow
from hie_gui.main import build_parser, create_window


def test_build_parser():
    parser = build_parser()
    args = parser.parse_args(["--image", "sample.png"])
    assert args.image == "sample.png"


def test_create_window(q_app):
    window = create_window()
    assert isinstance(window, QMainWindow)
    assert window.windowTitle() == "Hybrid Image Editor"
