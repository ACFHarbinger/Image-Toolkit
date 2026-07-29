"""Regression coverage for the startup-probe race guard (issue #81).

See .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md (Addenda 10-11):
deferring MainWindow construction by a fixed 400ms wasn't a reliable
enough margin against Qt Multimedia's async startup device probe, and
neither was a flat 1.5s elapsed-time floor -- the crash recurred with the
same offset three times running. gui/src/utils/startup_probe_guard.py now
tracks both the probe's real start time (a fallback ceiling) AND positive
confirmation that it actually finished (QMediaDevices' device-changed
signals, wired up in app.py), so any scanner-thread call site can defer
itself precisely instead of guessing a bigger number.
"""

import time

import pytest
from gui.src.utils import startup_probe_guard

pytestmark = pytest.mark.gui


@pytest.fixture(autouse=True)
def _reset_probe_guard_state(monkeypatch):
    # The guard's state is deliberately process-global (a single "when did
    # the app start / has the probe settled" fact) -- reset it around each
    # test so tests don't leak state into each other.
    monkeypatch.setattr(startup_probe_guard, "_probe_start_monotonic", None)
    monkeypatch.setattr(startup_probe_guard, "_probe_settled", False)
    monkeypatch.setattr(startup_probe_guard, "_probe_settled_at_elapsed_s", None)


class TestStartupProbeGuard:
    def test_remaining_is_zero_before_probe_marked_started(self):
        assert startup_probe_guard.startup_settle_remaining_ms() == 0

    def test_remaining_is_positive_immediately_after_marking(self):
        startup_probe_guard.mark_startup_probe_started()
        remaining = startup_probe_guard.startup_settle_remaining_ms()
        assert (
            0
            < remaining
            <= startup_probe_guard._STARTUP_SETTLE_CEILING_SECONDS * 1000
        )

    def test_remaining_decreases_and_settles_to_zero_at_ceiling(self, monkeypatch):
        fake_now = [1000.0]
        monkeypatch.setattr(time, "monotonic", lambda: fake_now[0])

        startup_probe_guard.mark_startup_probe_started()
        assert startup_probe_guard.startup_settle_remaining_ms() == int(
            startup_probe_guard._STARTUP_SETTLE_CEILING_SECONDS * 1000
        )

        # Halfway through the ceiling: still waiting, roughly half the
        # original margin left.
        fake_now[0] += startup_probe_guard._STARTUP_SETTLE_CEILING_SECONDS / 2
        remaining_mid = startup_probe_guard.startup_settle_remaining_ms()
        assert (
            0
            < remaining_mid
            < int(startup_probe_guard._STARTUP_SETTLE_CEILING_SECONDS * 1000)
        )

        # Past the ceiling entirely: safe to proceed even without a
        # positive confirmation.
        fake_now[0] += startup_probe_guard._STARTUP_SETTLE_CEILING_SECONDS
        assert startup_probe_guard.startup_settle_remaining_ms() == 0

    def test_never_returns_negative_past_the_ceiling(self, monkeypatch):
        fake_now = [1000.0]
        monkeypatch.setattr(time, "monotonic", lambda: fake_now[0])
        startup_probe_guard.mark_startup_probe_started()
        fake_now[0] += startup_probe_guard._STARTUP_SETTLE_CEILING_SECONDS * 10
        assert startup_probe_guard.startup_settle_remaining_ms() == 0

    def test_positive_confirmation_short_circuits_the_ceiling(self, monkeypatch):
        fake_now = [1000.0]
        monkeypatch.setattr(time, "monotonic", lambda: fake_now[0])

        startup_probe_guard.mark_startup_probe_started()
        fake_now[0] += 0.1  # well within the ceiling
        assert startup_probe_guard.startup_settle_remaining_ms() > 0

        startup_probe_guard.mark_startup_probe_settled(source="test")
        assert startup_probe_guard.startup_settle_remaining_ms() == 0

    def test_settled_before_started_records_negative_sentinel_elapsed(self):
        # Guards against a signal firing before mark_startup_probe_started()
        # has ever run (e.g. a test or alternate entry point) -- must not
        # raise, and should still flip the settled flag.
        startup_probe_guard.mark_startup_probe_settled(source="test")
        assert startup_probe_guard.startup_settle_remaining_ms() == 0


class TestWallpaperScanDefersDuringSettleWindow:
    """Confirms populate_scan_image_gallery() actually reschedules itself
    (rather than starting a scanner QThread immediately) while the probe
    guard reports time remaining -- this is the actual call site the guard
    is wired into, not just the guard module in isolation."""

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

            def deleteLater(self):
                pass

        monkeypatch.setattr(
            wallpaper_common_base._scan_pipeline, "ImageScannerWorker", RecordingImageScannerWorker
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

        # Shrink the ceiling so the deferred retry (below) fires quickly
        # and deterministically, instead of this test needing to wait out
        # the real (generous, production) 5s ceiling.
        monkeypatch.setattr(
            startup_probe_guard, "_STARTUP_SETTLE_CEILING_SECONDS", 0.05
        )

        directory = str(tmp_path)
        # Simulate the probe having just started (well within the settle
        # window, no positive confirmation yet): the very next call must
        # NOT construct a scanner worker.
        startup_probe_guard.mark_startup_probe_started()
        base.populate_scan_image_gallery(directory)

        assert started == [], (
            "populate_scan_image_gallery() started a scanner QThread while "
            "the startup probe guard still reported time remaining -- it "
            "must defer via QTimer.singleShot() instead (see "
            ".agent/cache/gallery_crash_deleteorphaned_2026-07-27.md)"
        )

        # The already-scheduled deferred retry should go on to construct
        # the worker once the (now-shrunk) ceiling has passed.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not started:
            from PySide6.QtWidgets import QApplication

            QApplication.processEvents()
            time.sleep(0.02)

        assert started == [directory]

    def test_populate_scan_proceeds_immediately_once_confirmed_settled(
        self, q_app, monkeypatch, tmp_path
    ):
        """A positive confirmation (QMediaDevices signal) should let a
        scan proceed right away, without waiting out the ceiling at all --
        this is the actual behavior difference from the old flat-timeout
        guard: a fast probe should not force a needless wait."""
        from gui.src.tabs.core.elements.common import wallpaper_common_base

        started = []

        class RecordingImageScannerWorker:
            def __init__(self, directory, *a, **kw):
                self.directory = directory
                started.append(directory)
                self.scan_finished = _NullSignal()
                self.scan_error = _NullSignal()
                self.finished = _NullSignal()

            def start(self):
                pass

            def deleteLater(self):
                pass

        monkeypatch.setattr(
            wallpaper_common_base._scan_pipeline, "ImageScannerWorker", RecordingImageScannerWorker
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
        directory = str(tmp_path)

        # Long ceiling (production-like), but a positive confirmation
        # arrives immediately -- the scan should proceed right away, not
        # wait out the ceiling.
        startup_probe_guard.mark_startup_probe_started()
        startup_probe_guard.mark_startup_probe_settled(source="test")
        base.populate_scan_image_gallery(directory)

        assert started == [directory]


class _NullSignal:
    def connect(self, *a, **kw):
        pass
