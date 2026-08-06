"""Shared pytest configuration for the standalone GUI package."""

from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

# Qt tests run headlessly in local and CI environments.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def q_app() -> QApplication:
    """Provide one QApplication for the standalone GUI test session."""
    return QApplication.instance() or QApplication([])
