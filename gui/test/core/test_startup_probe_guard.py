"""Regression coverage for the round-11 startup-probe race guard (issue #81).

See .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md (Addendum 10):
deferring MainWindow construction by a fixed 400ms wasn't a reliable
enough margin against Qt Multimedia's async startup device probe when
login/vault-unlock happened quickly -- the crash recurred with the
simplest possible repro (auto-restore + one immediate manual browse).
gui/src/utils/startup_probe_guard.py tracks the probe's real start time
so any scanner-thread call site can compute a hard floor to defer
against, instead of relying on how long window construction happened to
take.
"""

import time

import pytest
from gui.src.utils import startup_probe_guard

pytestmark = pytest.mark.gui


@pytest.fixture(autouse=True)
def _reset_probe_guard_state(monkeypatch):
    # The guard's start time is deliberately a module-level global (a
    # single, process-wide "when did the app start" fact) -- reset it
    # around each test so tests don't leak state into each other.
    monkeypatch.setattr(startup_probe_guard, "_probe_start_monotonic", None)


class TestStartupProbeGuard:
    def test_remaining_is_zero_before_probe_marked_started(self):
        assert startup_probe_guard.startup_settle_remaining_ms() == 0

    def test_remaining_is_positive_immediately_after_marking(self):
        startup_probe_guard.mark_startup_probe_started()
        remaining = startup_probe_guard.startup_settle_remaining_ms()
        assert 0 < remaining <= startup_probe_guard._STARTUP_SETTLE_SECONDS * 1000

    def test_remaining_decreases_and_settles_to_zero(self, monkeypatch):
        fake_now = [1000.0]
        monkeypatch.setattr(time, "monotonic", lambda: fake_now[0])

        startup_probe_guard.mark_startup_probe_started()
        assert startup_probe_guard.startup_settle_remaining_ms() == int(
            startup_probe_guard._STARTUP_SETTLE_SECONDS * 1000
        )

        # Halfway through the settle window: still waiting, roughly half
        # the original margin left.
        fake_now[0] += startup_probe_guard._STARTUP_SETTLE_SECONDS / 2
        remaining_mid = startup_probe_guard.startup_settle_remaining_ms()
        assert 0 < remaining_mid < int(startup_probe_guard._STARTUP_SETTLE_SECONDS * 1000)

        # Past the settle window entirely: safe to proceed.
        fake_now[0] += startup_probe_guard._STARTUP_SETTLE_SECONDS
        assert startup_probe_guard.startup_settle_remaining_ms() == 0

    def test_never_returns_negative_past_the_window(self, monkeypatch):
        fake_now = [1000.0]
        monkeypatch.setattr(time, "monotonic", lambda: fake_now[0])
        startup_probe_guard.mark_startup_probe_started()
        fake_now[0] += startup_probe_guard._STARTUP_SETTLE_SECONDS * 10
        assert startup_probe_guard.startup_settle_remaining_ms() == 0


class TestWallpaperScanDefersDuringSettleWindow:
    """Confirms populate_scan_image_gallery() actually reschedules itself
    (rather than starting a scanner QThread immediately) while the probe
    guard reports time remaining -- this is the actual call site round 11
    added the guard to, not just the guard module in isolation."""

    def test_populate_scan_defers_a_scanner_thread_start(self, q_app, monkeypatch, tmp_path):
        from gui.src.tabs.core.elements.common import wallpaper_common_base

        started = []

        class RecordingImageScannerWorker:
            def __init__(self, directory, *a, **kw):
                self.directory = directory
                started.append(directory)
                # Minimal QThread-shaped stub -- never actually started,
                # this test only needs to prove *whether* a worker gets
                # constructed at all while the guard says "not yet".
                self.scan_finished = _NullSignal()
                self.scan_error = _NullSignal()
                self.finished = _NullSignal()

            def start(self):
                pass

        monkeypatch.setattr(
            wallpaper_common_base, "ImageScannerWorker", RecordingImageScannerWorker
        )

        from gui.src.classes.abstract_class_single_gallery import (
            AbstractClassSingleGallery,
        )
        from PySide6.QtWidgets import QGridLayout, QScrollArea, QWidget

        class Concrete(wallpaper_common_base.WallpaperCommonBase):
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

        base = Concrete()

        # Shrink the settle window so the deferred retry (below) fires
        # quickly and deterministically, instead of this test needing to
        # wait out the real (generous, production) 1.5s margin.
        monkeypatch.setattr(startup_probe_guard, "_STARTUP_SETTLE_SECONDS", 0.05)

        directory = str(tmp_path)
        # Simulate the probe having just started (well within the settle
        # window): the very next call must NOT construct a scanner worker.
        startup_probe_guard.mark_startup_probe_started()
        base.populate_scan_image_gallery(directory)

        assert started == [], (
            "populate_scan_image_gallery() started a scanner QThread while "
            "the startup probe guard still reported time remaining -- it "
            "must defer via QTimer.singleShot() instead (see Addendum 10 "
            "in .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md)"
        )

        # The already-scheduled deferred retry should go on to construct
        # the worker once the (now-shrunk) settle window has passed.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not started:
            from PySide6.QtWidgets import QApplication

            QApplication.processEvents()
            time.sleep(0.02)

        assert started == [directory]


class _NullSignal:
    def connect(self, *a, **kw):
        pass
