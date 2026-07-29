"""Regression test for the deleteOrphaned crash class in the *linked-panel*
topology (issue #81) -- gui/test/core/test_wallpaper_scan_race.py only
exercises a single WallpaperCommonBase instance switching directories
rapidly; the real Wallpaper tab always has TWO linked instances
(system_display/monitor_display, see wallpaper_tab.py) that mirror each
other's directory via a `directory_scanned` signal
(`peer.populate_scan_image_gallery(directory, emit_signal=False)`) and
share a single, aliased `_initial_pixmap_cache` dict object. A crash
report reproduced with the real two-panel app (round 14/15,
hs_err_pid518912.log -- QSocketNotifier::setEnabled(bool) SIGSEGV) kept
recurring even after every single-instance fix landed, so this test
builds the same two-linked-instance topology `wallpaper_tab.py` actually
uses and drives rapid switching through *one* panel, exactly like a real
user browsing in the System Display sub-tab while Monitor Display mirrors
it silently.
"""

import time

import pytest
from gui.src.helpers import ImageScannerWorker, VideoScannerWorker
from gui.src.tabs.core.elements.common import wallpaper_common_base
from gui.src.tabs.core.elements.common.wallpaper_common_base import (
    WallpaperCommonBase,
)
from PySide6.QtWidgets import QGridLayout, QScrollArea, QWidget

pytestmark = pytest.mark.gui

_SCAN_DELAY_S = 0.1


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

    def _generate_video_thumbnail(self, path):
        return None

    def create_gallery_label(self, path, size):
        return QWidget()

    def get_default_config(self):
        return {}

    def set_config(self, config):
        pass


class DelayedImageScannerWorker(ImageScannerWorker):
    """Real ImageScannerWorker with an artificial delay, matching
    test_wallpaper_scan_race.py's approach -- forces reliable overlap
    between successive scans without depending on real filesystem/thread
    scheduling timing."""

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


def _link_panels(a: ConcreteWallpaperBase, b: ConcreteWallpaperBase) -> None:
    """Mirrors wallpaper_tab.py's WallpaperTab.__init__ wiring exactly:
    shared _initial_pixmap_cache object (aliased, not copied), mutual
    linked_tabs, and directory_scanned cross-connected with
    emit_signal=False on the receiving side to avoid infinite ping-pong."""
    a.linked_tabs = [b]
    b.linked_tabs = [a]
    b._initial_pixmap_cache = a._initial_pixmap_cache
    a.directory_scanned.connect(
        lambda directory: b.populate_scan_image_gallery(directory, emit_signal=False)
    )
    b.directory_scanned.connect(
        lambda directory: a.populate_scan_image_gallery(directory, emit_signal=False)
    )


def _pump(seconds: float) -> None:
    from PySide6.QtWidgets import QApplication

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.02)


class TestLinkedPanelRapidSwitchRace:
    def test_two_linked_panels_survive_rapid_switching(
        self, q_app, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(
            wallpaper_common_base._scan_pipeline, "ImageScannerWorker", DelayedImageScannerWorker
        )
        video_registry = []
        monkeypatch.setattr(
            wallpaper_common_base._scan_pipeline,
            "VideoScannerWorker",
            _make_spying_video_scanner_worker(video_registry),
        )

        system_display = ConcreteWallpaperBase()
        monitor_display = ConcreteWallpaperBase()
        _link_panels(system_display, monitor_display)

        dir_a = tmp_path / "image_dir"
        dir_b = tmp_path / "video_dir"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "pic1.png").write_bytes(b"\x00")
        (dir_b / "pic2.png").write_bytes(b"\x00")

        # Drive every switch through system_display only -- monitor_display
        # mirrors via directory_scanned exactly like the real Wallpaper tab.
        # No exception escaping any of these calls (Qt swallows exceptions
        # raised inside slots/timer callbacks rather than propagating them
        # to this call, so a crash-adjacent state shows up as a hang or a
        # bad final state, not necessarily a raised Python exception here)
        # is the first-order thing this test checks, via the assertions
        # below rather than a bare try/except.
        system_display.populate_scan_image_gallery(str(dir_a))
        system_display.populate_scan_image_gallery(str(dir_b))
        system_display.populate_scan_image_gallery(str(dir_a))
        system_display.populate_scan_image_gallery(str(dir_b))

        # Let everything settle: all scans finish and every queued signal
        # (including stale ones, and each panel's own peer-triggered scan)
        # gets delivered by the real event loop.
        _pump(2.0)

        def _safe_is_running(worker):
            try:
                return worker.isRunning()
            except RuntimeError:
                return False

        def _safe_directory(worker):
            try:
                return worker.directory
            except RuntimeError:
                return None

        live_workers = [w for w in video_registry if _safe_is_running(w)]
        # At most one VideoScannerWorker per panel (2 panels) should still
        # be alive/running once everything settles.
        assert len(live_workers) <= 2, (
            f"expected at most 2 live VideoScannerWorkers (one per linked "
            f"panel) after rapid switching settled across BOTH panels, "
            f"found {len(live_workers)} -- a stale scan_finished orphaned "
            f"a worker in the linked-panel topology (see "
            f".agent/cache/gallery_crash_deleteorphaned_2026-07-27.md)"
        )

        final_dir = str(dir_b)
        for w in video_registry:
            d = _safe_directory(w)
            if d not in (final_dir, None) and _safe_is_running(w):
                pytest.fail(
                    f"VideoScannerWorker for superseded directory {d!r} "
                    f"still running after settling -- orphaned in the "
                    f"linked-panel topology"
                )

        # Both panels should have ended up scanning the final directory,
        # not stuck on a stale one from mid-switch.
        assert system_display.scanned_dir == final_dir
        assert monitor_display.scanned_dir == final_dir
