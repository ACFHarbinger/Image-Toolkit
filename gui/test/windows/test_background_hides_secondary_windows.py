"""Exit-to-background must hide *every* window, not just the parentless ones.

Leaving a secondary window (Settings, Cloud Compute, image preview, config
dialog …) visible while the app is "in background" shows a second
Image-Toolkit icon in the taskbar. Settings / Cloud Compute are parented to
the main window, so they never appear in ``QApplication.topLevelWidgets()`` —
the regression that kept the second icon around.
"""

from __future__ import annotations

import contextlib

import pytest
from gui.src.windows.main._lifecycle import collect_background_windows
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

pytestmark = pytest.mark.gui


def test_parentless_and_parented_windows_are_both_collected(q_app):
    main = QWidget()
    main.setWindowTitle("main")
    parentless = QWidget()
    parentless.setWindowTitle("preview")  # e.g. an image preview window
    # Settings / Cloud Compute are created as Window(self) — parented, but
    # still real windows with their own taskbar button.
    parented = QWidget(main)
    parented.setWindowFlag(Qt.WindowType.Window, True)
    parented.setWindowTitle("settings")

    for w in (main, parentless, parented):
        w.show()
    q_app.processEvents()
    try:
        collected = collect_background_windows(main)

        assert main not in collected
        assert parentless in collected
        assert parented in collected, (
            "the parented Settings/Cloud-Compute-style window must be collected"
        )

        for w in collected:
            w.hide()
        assert not parentless.isVisible()
        assert not parented.isVisible()
    finally:
        for w in (parented, parentless, main):
            with contextlib.suppress(Exception):
                w.close()


def test_hidden_and_popup_windows_are_skipped(q_app):
    main = QWidget()
    hidden_win = QWidget()
    popup = QWidget(None, Qt.WindowType.Popup)
    main.show()
    hidden_win.show()
    hidden_win.hide()
    popup.show()
    q_app.processEvents()
    try:
        collected = collect_background_windows(main)
        assert hidden_win not in collected  # not visible
        assert popup not in collected  # Popup type never has a taskbar entry
    finally:
        for w in (popup, hidden_win, main):
            with contextlib.suppress(Exception):
                w.close()


def test_restore_shows_tracked_windows(q_app):
    main = QWidget()
    other = QWidget(main)
    other.setWindowFlag(Qt.WindowType.Window, True)
    main.show()
    other.show()
    q_app.processEvents()
    try:
        tracked = collect_background_windows(main)
        for w in tracked:
            w.hide()
        assert not other.isVisible()

        # mirrors _tray_show_window()
        for w in tracked:
            with contextlib.suppress(RuntimeError):
                w.show()
        assert other.isVisible()
    finally:
        for w in (other, main):
            with contextlib.suppress(Exception):
                w.close()
