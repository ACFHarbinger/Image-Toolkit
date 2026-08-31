"""Exit-to-background must hide *every* top-level window, not just the main one.

Leaving a secondary window (Settings, image preview, …) visible while the app
is "in background" shows a second Image-Toolkit icon in the taskbar.
"""

from __future__ import annotations

import contextlib

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMenu, QWidget

pytestmark = pytest.mark.gui


def _hide_other_top_levels(main: QWidget) -> list[QWidget]:
    """The loop from MainWindow.closeEvent's minimize-to-tray branch."""
    hidden: list[QWidget] = []
    for w in QApplication.topLevelWidgets():
        if w is main or isinstance(w, QMenu) or not w.isVisible():
            continue
        if w.windowType() in (Qt.WindowType.Popup, Qt.WindowType.ToolTip):
            continue
        with contextlib.suppress(Exception):
            w.hide()
            hidden.append(w)
    return hidden


def test_secondary_windows_hidden_and_restored(q_app):
    main = QWidget()
    main.setWindowTitle("main")
    settings = QWidget()
    settings.setWindowTitle("settings")
    preview = QWidget()
    preview.setWindowTitle("preview")
    for w in (main, settings, preview):
        w.show()
    try:
        assert settings.isVisible() and preview.isVisible()

        hidden = _hide_other_top_levels(main)

        assert set(hidden) == {settings, preview}
        assert not settings.isVisible()
        assert not preview.isVisible()
        assert main.isVisible()  # main is hidden separately by self.hide()

        # _tray_show_window restores them
        for w in hidden:
            w.show()
        assert settings.isVisible() and preview.isVisible()
    finally:
        for w in (main, settings, preview):
            w.close()


def test_a_closed_secondary_window_is_not_tracked(q_app):
    main = QWidget()
    other = QWidget()
    main.show()
    other.show()
    other.hide()  # already not visible
    try:
        hidden = _hide_other_top_levels(main)
        assert other not in hidden
    finally:
        main.close()
        other.close()
