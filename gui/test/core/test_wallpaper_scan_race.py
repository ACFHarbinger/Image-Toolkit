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
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QGridLayout, QScrollArea, QWidget

from gui.src.helpers import ImageScannerWorker
from gui.src.tabs.core.wallpaper_tab.common import wallpaper_common_base
from gui.src.tabs.core.wallpaper_tab.common.wallpaper_common_base import (
    WallpaperCommonBase,
)

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


class TestWallpaperGalleryLoading:
    def test_settle_waits_for_gallery_workers_before_releasing_pending_switch(
        self, q_app, monkeypatch
    ):
        """Linked panels must not overlap their thumbnail populations.

        Image/video directory scans can finish before the QRunnables started
        by ``start_loading_gallery()``. Releasing the pipeline at that point
        starts the mirrored panel's population against the same native/Qt
        boundaries, the crash shape seen when browsing a large directory.
        """
        panel = ConcreteWallpaperBase()
        panel._scan_pipeline_busy = True
        panel._pending_scan_request = ("/next", False)
        active_counts = iter((1, 0))
        panel.thread_pool.activeThreadCount = lambda: next(active_counts)
        scheduled = []
        monkeypatch.setattr(
            wallpaper_common_base._scan_pipeline.QTimer,
            "singleShot",
            lambda delay, callback: scheduled.append((delay, callback)),
        )

        panel._settle_scan_pipeline()

        assert panel._scan_pipeline_busy is True
        assert panel._pending_scan_request == ("/next", False)
        assert len(scheduled) == 1
        assert scheduled[0][0] == 25

        scheduled.pop()[1]()

        assert panel._scan_pipeline_busy is False
        assert panel._pending_scan_request is None
        assert len(scheduled) == 1
        assert scheduled[0][0] == 0

    def test_image_scan_appends_with_one_gallery_rebuild(self, q_app):
        panel = ConcreteWallpaperBase()
        panel.master_image_paths = ["existing.png"]
        panel.start_loading_gallery = MagicMock()
        panel.refresh_gallery_view = MagicMock()
        panel._start_video_scan = MagicMock()

        panel._on_image_scan_finished(["existing.png", "new.png"])

        panel.start_loading_gallery.assert_called_once_with(
            ["new.png"], show_progress=False, append=True
        )
        panel.refresh_gallery_view.assert_not_called()

    def test_video_scan_appends_with_one_gallery_rebuild(self, q_app):
        panel = ConcreteWallpaperBase()
        panel.master_image_paths = ["existing.png"]
        panel.start_loading_gallery = MagicMock()
        panel.refresh_gallery_view = MagicMock()
        panel._settle_scan_pipeline = MagicMock()

        panel._on_video_scan_finished(["clip.mp4"])

        panel.start_loading_gallery.assert_called_once_with(
            ["clip.mp4"], show_progress=False, append=True
        )
        panel.refresh_gallery_view.assert_not_called()

    def test_startup_thumbnail_is_scaled_and_cached(self, q_app, tmp_path):
        path = tmp_path / "large.png"
        image = QImage(800, 400, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.red)
        assert image.save(str(path))

        panel = ConcreteWallpaperBase()
        panel.thumbnail_size = 96
        thumb = panel._get_or_generate_thumbnail(str(path))

        assert thumb is not None
        assert not thumb.isNull()
        assert thumb.width() <= 96
        assert thumb.height() <= 96
        cached = panel._initial_pixmap_cache.get(str(path))
        assert cached is not None
        assert cached.width() <= 96
        assert cached.height() <= 96
