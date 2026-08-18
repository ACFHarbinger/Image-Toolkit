"""Regression tests for image-directory scanning in WallpaperCommonBase.

Video-directory scanning (VideoScannerWorker) -- and the rapid-switch race
this file originally tested against -- was removed entirely (2026-08-01)
after 22+ rounds of fixes failed to close the deleteOrphaned/
QObjectPrivate::connect() crash class it kept triggering. See Addendum 23
in .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md. Only image
directory scanning, which was never implicated in that crash class,
remains -- and the one surviving Addendum 22 mitigation (disconnecting a
worker's signals before any teardown) is still tested below.
"""

from __future__ import annotations

import contextlib

import pytest
from gui.src.tabs.core.wallpaper_tab.common.wallpaper_common_base import (
    WallpaperCommonBase,
)
from gui.src.helpers import ImageScannerWorker
from PySide6.QtWidgets import QGridLayout, QScrollArea, QWidget

pytestmark = pytest.mark.gui


class ConcreteWallpaperBase(WallpaperCommonBase):
    def __init__(self):
        super().__init__()
        self.gallery_scroll_area = QScrollArea()
        self.gallery_widget = QWidget()
        self.gallery_layout = QGridLayout()
        self.gallery_widget.setLayout(self.gallery_layout)
        self.gallery_scroll_area.setWidget(self.gallery_widget)

    def create_card_widget(self, path, pixmap=None):
        return QWidget()

    def update_card_pixmap(self, widget, pixmap, label_ref=None):
        pass

    # pyrefly: ignore [bad-override]
    def create_gallery_label(self, path, size):
        return QWidget()

    def get_default_config(self):
        return {}

    def set_config(self, config):
        pass


class TestSignalDisconnectBeforeTeardown:
    """Addendum 22 (.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md):
    a telemetry+hs_err-correlated crash showed a worker's own thread still
    actively emitting a signal -- touching its own QObject's connection
    list -- at the exact moment an unrelated widget teardown's
    connection-list cleanup ran concurrently on another thread.
    _stop_scanner_threads() now disconnects a worker's signals up front,
    before any stop/wait/teardown, so there is nothing left for a later,
    concurrent deleteOrphaned() to race against for that specific worker.
    This test confirms the disconnect actually takes effect, not just
    that it's attempted without raising.
    """

    def test_stop_scanner_threads_disconnects_img_scanner_signals(self, q_app, tmp_path):
        panel = ConcreteWallpaperBase()
        worker = ImageScannerWorker(str(tmp_path))
        panel.img_scanner_thread = worker

        received = []
        worker.scan_finished.connect(lambda paths: received.append(paths))

        # pyrefly: ignore [bad-argument-type]
        panel._stop_scanner_threads()

        # _stop_scanner_threads()'s own trailing sendPostedEvents(None,
        # QEvent.Type.DeferredDelete) flush processes this worker's
        # deleteLater() synchronously (confirmed live via Addendum 22's
        # gdb backtrace: sendPostedEvents -> ~QWidget -> ... -> deleteOrphaned),
        # so the C++ object may already be fully destroyed here, not just
        # disconnected -- an even stronger guarantee against a stale
        # delivery than disconnection alone. Either outcome is acceptable;
        # what matters is the old slot is never reached.
        with contextlib.suppress(RuntimeError, TypeError):
            worker.scan_finished.emit(["stale.png"])
        assert received == [], (
            "scan_finished must be disconnected before any teardown -- "
            "a stale emit reached a slot that should no longer be connected"
        )
