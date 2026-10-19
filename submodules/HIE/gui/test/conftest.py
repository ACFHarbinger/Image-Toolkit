"""Pytest fixtures for HIE PySide6 GUI tests."""

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture
def q_app():
    """Ensure QApplication instance exists for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
