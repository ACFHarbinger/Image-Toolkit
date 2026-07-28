"""Regression test for the deleteOrphaned crash class (issue #81).

Reproduces the rapid-directory-switching race described in
.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md (Addendum 9):
switching directories several times in quick succession (image -> video ->
image -> video, ...) can let a *stale* ImageScannerWorker.scan_finished
signal -- queued before the user's next switch, delivered after -- start a
brand-new VideoScannerWorker for a directory the user has already navigated
away from, with nothing left to stop or wait for it. That orphaned worker
is the actual mechanism behind the real SIGSEGVs reported against issue
#81: it can still be running when a *later* switch tears down/rebuilds the
gallery widgets its thumbnail_ready signal targets.

A real SIGSEGV can't be caught in-process, so this test asserts the
underlying invariant directly: after several rapid switches settle, at
most one VideoScannerWorker should ever have been left alive, and it
must belong to the directory the user last switched to.
"""

import time

import pytest
from gui.src.helpers import ImageScannerWorker, VideoScannerWorker
from gui.src.tabs.core.elements.common import wallpaper_common_base
from gui.src.tabs.core.elements.common.wallpaper_common_base import (
    WallpaperCommonBase,
)
from PySide6.QtCore import QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QGridLayout, QScrollArea, QWidget

pytestmark = pytest.mark.gui

# How long each fake image scan artificially takes before completing. Long
# enough that a rapid-fire next populate_scan_image_gallery() call is
# guaranteed to observe the previous scan as still isRunning(), short
# enough to keep the test fast.
_SCAN_DELAY_S = 0.15


class ConcreteWallpaperBase(WallpaperCommonBase):
    def __init__(self):
        super().__init__()
        self.gallery_scroll_area = QScrollArea()
        self.gallery_widget = QWidget()
        self.gallery_layout = QGridLayout()
        self.gallery_widget.setLayout(self.gallery_layout)
        self.gallery_scroll_area.setWidget(self.gallery_widget)

    def create_card_widget(self, path, pixmap=None):
        label = QWidget()
        return label

    def update_card_pixmap(self, widget, pixmap, label_ref=None):
        pass

    def _generate_video_thumbnail(self, path):
        return None

    # pyrefly: ignore [bad-override]
    def create_gallery_label(self, path, size):
        return QWidget()

    def get_default_config(self):
        return {}

    def set_config(self, config):
        pass


class DelayedImageScannerWorker(ImageScannerWorker):
    """Real ImageScannerWorker, but run() is artificially slowed down so
    the test can reliably force overlap between successive scans without
    depending on real filesystem/thread scheduling timing."""

    def run(self):
        time.sleep(_SCAN_DELAY_S)
        super().run()


def _make_spying_video_scanner_worker(registry):
    class SpyingVideoScannerWorker(VideoScannerWorker):
        def __init__(self, directory, *args, **kwargs):
            super().__init__(directory, *args, **kwargs)
            self.stop_called = False
            registry.append(self)

        def stop(self):
            self.stop_called = True
            super().stop()

    return SpyingVideoScannerWorker


@pytest.fixture
def wallpaper_base(q_app, monkeypatch):
    monkeypatch.setattr(wallpaper_common_base, "ImageScannerWorker", DelayedImageScannerWorker)
    video_registry = []
    monkeypatch.setattr(
        wallpaper_common_base,
        "VideoScannerWorker",
        _make_spying_video_scanner_worker(video_registry),
    )
    base = ConcreteWallpaperBase()
    # pyrefly: ignore [missing-attribute]
    base.video_registry = video_registry
    yield base
    base._stop_scanner_threads()


def _pump_until(condition, timeout_s=5.0, interval_s=0.02):
    """Repeatedly process the real Qt event loop (delivering any queued
    cross-thread signals, not just DeferredDelete) until condition() is
    true or timeout elapses -- simulates the event loop eventually
    catching up between rapid user actions, as it would in the real app."""
    from PySide6.QtWidgets import QApplication

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if condition():
            return True
        time.sleep(interval_s)
    return condition()


class TestRapidDirectorySwitchRace:
    def test_four_rapid_switches_leave_at_most_one_live_video_worker(
        self, wallpaper_base, tmp_path
    ):
        dir_a = tmp_path / "image_dir"
        dir_b = tmp_path / "video_dir"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "pic1.png").write_bytes(b"\x00")
        (dir_b / "pic2.png").write_bytes(b"\x00")

        # Matches the user's exact repro: restore dir_a, browse dir_b
        # immediately, switch back to dir_a, then browse dir_b again --
        # four rapid, back-to-back switches with no waiting in between.
        wallpaper_base.populate_scan_image_gallery(str(dir_a))
        wallpaper_base.populate_scan_image_gallery(str(dir_b))
        wallpaper_base.populate_scan_image_gallery(str(dir_a))
        wallpaper_base.populate_scan_image_gallery(str(dir_b))

        # Let everything settle: all four image scans finish, and every
        # queued scan_finished signal (including any stale ones) gets
        # delivered by the real event loop.
        assert _pump_until(
            lambda: wallpaper_base.img_scanner_thread is None
            and (
                wallpaper_base.vid_scanner_worker is None
                or not wallpaper_base.vid_scanner_worker.isRunning()
            ),
            timeout_s=5.0,
        ), "scanners never settled -- rapid switching may have deadlocked"

        # Drain a bit more so any last stale signal has a chance to fire.
        for _ in range(10):
            from PySide6.QtWidgets import QApplication

            QApplication.processEvents()
            time.sleep(0.02)

        def _safe_is_running(worker):
            # A deleteLater()'d worker whose C++ object has already been
            # destroyed is definitionally not running/orphaned -- it was
            # properly torn down, not leaked.
            try:
                return worker.isRunning()
            except RuntimeError:
                return False

        def _safe_directory(worker):
            try:
                return worker.directory
            except RuntimeError:
                return None

        # The real invariant: exactly one VideoScannerWorker should ever be
        # created for this sequence -- the one legitimately started once
        # the FINAL image scan (dir_b) finishes. A stale scan_finished
        # signal (from any of the three superseded image scans) reaching
        # _on_image_scan_finished() unconditionally starts a brand-new
        # VideoScannerWorker for whatever self.scanned_dir happened to be
        # at that moment -- even if that extra worker later gets stopped
        # on the *next* switch (delayed cleanup), it still existed and ran
        # for a window where it could have delivered thumbnail_ready into
        # gallery widgets mid-teardown. Counting total creations catches
        # that window even when isRunning() has since gone False.
        assert len(wallpaper_base.video_registry) == 1, (
            f"expected exactly one VideoScannerWorker to ever be created "
            f"across these four rapid switches, found "
            f"{len(wallpaper_base.video_registry)} -- one or more stale "
            f"scan_finished signals reached _on_image_scan_finished() and "
            f"started an extra worker for a directory the user had "
            f"already navigated away from (see Addendum 9 in "
            f".agent/cache/gallery_crash_deleteorphaned_2026-07-27.md)"
        )

        live_workers = [w for w in wallpaper_base.video_registry if _safe_is_running(w)]
        assert len(live_workers) <= 1, (
            f"expected at most one live VideoScannerWorker after rapid "
            f"switching settled, found {len(live_workers)} -- a stale "
            f"scan_finished signal orphaned a worker for a directory the "
            f"user already navigated away from (see Addendum 9 in "
            f".agent/cache/gallery_crash_deleteorphaned_2026-07-27.md)"
        )

        # Every VideoScannerWorker actually created for a directory other
        # than the final one must have been stopped, not silently
        # abandoned -- an unstopped worker is free to deliver
        # thumbnail_ready into gallery widgets that later teardown
        # already deleted.
        stale_unstopped = [
            w
            for w in wallpaper_base.video_registry
            if _safe_directory(w) not in (str(dir_b), None)
            and not w.stop_called
            and _safe_is_running(w)
        ]
        assert not stale_unstopped, (
            "a VideoScannerWorker for a superseded directory was left "
            "running and was never stopped"
        )

        if wallpaper_base.vid_scanner_worker is not None:
            assert _safe_directory(wallpaper_base.vid_scanner_worker) in (
                str(dir_b),
                None,
            )
