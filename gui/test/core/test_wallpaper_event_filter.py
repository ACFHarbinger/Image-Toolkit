"""Regression tests for the WallpaperCommonBase app-wide event filter.

``SystemDisplaySubTab`` installs itself as a *QApplication* event filter and
nothing ever removed it. Once the widget was torn down, every event in the
whole app kept routing through the now-dead C++ wrapper, raising
``RuntimeError`` on each one and leaving the app unclickable (event loop
still running, so not "frozen"). The filter must now evict itself on the
first sign of a dead wrapper.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QWidget

from gui.src.tabs.core.wallpaper_tab.common.wallpaper_common_base._event_filter import (
    _EventFilterMixin,
)

pytestmark = pytest.mark.gui


class _StaleFilter(_EventFilterMixin, QWidget):
    """Stand-in whose isVisible() blows up like a deleted C++ wrapper."""

    def __init__(self):
        super().__init__()
        self._filtering_event = False
        self._raise_on_visible = False

    def isVisible(self):  # noqa: N802 - Qt override
        if self._raise_on_visible:
            raise RuntimeError("Internal C++ object (_StaleFilter) already deleted.")
        return super().isVisible()


def test_event_filter_evicts_itself_when_self_is_dead(q_app):
    flt = _StaleFilter()
    q_app.installEventFilter(flt)
    try:
        flt._raise_on_visible = True
        probe = QObject()
        ev = QEvent(QEvent.Type.MouseButtonPress)

        # Must swallow the RuntimeError and report "not filtered".
        assert flt.eventFilter(probe, ev) is False

        # Delivering a real event through the app must no longer raise: the
        # filter has removed itself. (Sending to `probe` routes through every
        # installed app filter.)
        q_app.sendEvent(probe, QEvent(QEvent.Type.User))
    finally:
        q_app.removeEventFilter(flt)
        flt.deleteLater()


def test_event_filter_passthrough_when_alive_and_hidden(q_app):
    flt = _StaleFilter()
    flt.hide()
    try:
        probe = QObject()
        ev = QEvent(QEvent.Type.MouseButtonPress)
        # Hidden but alive: quiet no-op passthrough, no exception, returns False.
        assert flt.eventFilter(probe, ev) is False
    finally:
        flt.deleteLater()
