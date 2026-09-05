"""WindowManager contract tests (#528)."""

from __future__ import annotations

import contextlib

import pytest
from gui.src.windows.main._lifecycle import collect_background_windows
from gui.src.windows.main._notify import (
    show_main_status,
    show_toast_notification,
    show_tray_notification,
)
from gui.src.windows.window_manager import WindowManager, register_window
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

pytestmark = pytest.mark.gui


@pytest.fixture(autouse=True)
def _reset_window_manager():
    WindowManager.reset()
    yield
    WindowManager.reset()


def test_register_and_main_role(q_app):
    main = QWidget()
    other = QWidget()
    register_window(main, role="main")
    register_window(other)

    mgr = WindowManager.instance()
    assert mgr.main_window() is main
    assert set(mgr.iter_windows()) == {main, other}


def test_destroyed_window_is_dropped(q_app):
    from PySide6.QtCore import QEvent

    main = QWidget()
    secondary = QWidget()
    secondary.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    register_window(main, role="main")
    register_window(secondary)
    secondary.close()
    q_app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    q_app.processEvents()

    mgr = WindowManager.instance()
    assert mgr.main_window() is main
    assert secondary not in list(mgr.iter_windows())


def test_explicit_deregister(q_app):
    main = QWidget()
    other = QWidget()
    register_window(main, role="main")
    register_window(other)
    WindowManager.instance().deregister(other)
    assert other not in list(WindowManager.instance().iter_windows())
    assert WindowManager.instance().main_window() is main


def test_notify_helpers_use_registered_main(q_app):
    main = QWidget()
    main._calls: list[tuple] = []

    def show_status(message, timeout_ms=3000):
        main._calls.append(("status", message, timeout_ms))

    def show_toast(message, toast_type="info", duration_ms=2500):
        main._calls.append(("toast", message, toast_type, duration_ms))

    def tray_notify(title, message, timeout_ms=4000):
        main._calls.append(("tray", title, message, timeout_ms))

    main.show_status = show_status
    main.show_toast = show_toast
    main.tray_notify = tray_notify
    register_window(main, role="main")

    show_main_status("hello", 1234)
    show_toast_notification("toast", "warn", 999)
    show_tray_notification("T", "M", 111)

    assert main._calls == [
        ("status", "hello", 1234),
        ("toast", "toast", "warn", 999),
        ("tray", "T", "M", 111),
    ]


def test_notify_helpers_noop_without_main(q_app):
    # Must not raise when nothing is registered.
    show_main_status("x")
    show_toast_notification("x")
    show_tray_notification("t", "m")


def test_collect_background_windows_uses_registry(q_app):
    main = QWidget()
    main.setWindowTitle("main")
    parentless = QWidget()
    parentless.setWindowTitle("preview")
    parented = QWidget(main)
    parented.setWindowFlag(Qt.WindowType.Window, True)
    parented.setWindowTitle("settings")

    register_window(main, role="main")
    register_window(parentless)
    register_window(parented)

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
    register_window(main, role="main")
    register_window(hidden_win)
    register_window(popup)
    main.show()
    hidden_win.show()
    hidden_win.hide()
    popup.show()
    q_app.processEvents()
    try:
        collected = collect_background_windows(main)
        assert hidden_win not in collected
        assert popup not in collected
    finally:
        for w in (popup, hidden_win, main):
            with contextlib.suppress(Exception):
                w.close()


def test_unregistered_windows_are_not_collected(q_app):
    """Registry is the source of truth — unregistered windows are ignored."""
    main = QWidget()
    orphan = QWidget()
    register_window(main, role="main")
    main.show()
    orphan.show()
    q_app.processEvents()
    try:
        collected = collect_background_windows(main)
        assert orphan not in collected
    finally:
        for w in (orphan, main):
            with contextlib.suppress(Exception):
                w.close()
