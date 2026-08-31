"""The process must carry one stable WM identity so background mode does not
spawn a second taskbar icon (the QSystemTrayIcon surface would otherwise get
its own Wayland app_id).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from backend.src.app import APP_DESKTOP_FILE_NAME, set_app_identity
from PySide6.QtWidgets import QApplication

pytestmark = pytest.mark.gui


def test_set_app_identity_sets_desktop_file_name(q_app):
    set_app_identity(q_app)
    assert QApplication.desktopFileName() == APP_DESKTOP_FILE_NAME
    assert QApplication.applicationName() == "Image Toolkit"


def test_desktop_entry_startupwmclass_matches():
    entry = Path(__file__).parents[3] / "desktop" / "ImageToolkit.desktop"
    text = entry.read_text()
    assert f"StartupWMClass={APP_DESKTOP_FILE_NAME}" in text, (
        "desktop/ImageToolkit.desktop StartupWMClass must match "
        "APP_DESKTOP_FILE_NAME so X11 WM_CLASS grouping works too"
    )
