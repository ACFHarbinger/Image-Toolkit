"""Regression test for the deleteOrphaned crash class in the *linked-panel*
topology (issue #81) -- the real Wallpaper tab always has TWO linked
instances (system_display/monitor_display, see wallpaper_tab.py) that
mirror each other's directory via a `directory_scanned` signal
(`peer.populate_scan_image_gallery(directory, emit_signal=False)`) and
share a single, aliased `_initial_pixmap_cache` dict object.

Video-directory scanning (VideoScannerWorker) -- the original trigger for
this crash class -- was removed entirely (2026-08-01) after 22+ rounds of
fixes failed to close it. See Addendum 23 in
.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md. The peer-
reentrancy guard tested below (Addendum 21) applies to the image-only
scan pipeline that remains, regardless of whether video scanning ever
existed, so it's kept.
"""

from __future__ import annotations

import time

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QGridLayout, QScrollArea, QWidget

from gui.src.tabs.core.wallpaper_tab.common import wallpaper_common_base
from gui.src.tabs.core.wallpaper_tab.common.wallpaper_common_base import (
    WallpaperCommonBase,
)
from gui.src.helpers import ImageScannerWorker

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

    # pyrefly: ignore [bad-override]
    def create_gallery_label(self, path, size):
        return QWidget()

    def get_default_config(self):
        return {}

    def set_config(self, config):
        pass


class DelayedImageScannerWorker(ImageScannerWorker):
    """Real ImageScannerWorker with an artificial delay, so a test can
    reliably force overlap between successive scans without depending on
    real filesystem/thread scheduling timing."""

    def run(self):
        time.sleep(_SCAN_DELAY_S)
        super().run()


def _link_panels(a: ConcreteWallpaperBase, b: ConcreteWallpaperBase) -> None:
    """Mirrors wallpaper_tab.py's WallpaperTab.__init__ wiring exactly:
    shared _initial_pixmap_cache object (aliased, not copied), mutual
    linked_tabs, and directory_scanned cross-connected with
    emit_signal=False on the receiving side to avoid infinite ping-pong."""
    a.linked_tabs = [b]
    b.linked_tabs = [a]
    b._initial_pixmap_cache = a._initial_pixmap_cache
    a.directory_scanned.connect(
        # pyrefly: ignore [bad-argument-type]
        lambda directory: b.populate_scan_image_gallery(directory, emit_signal=False)
    )
    b.directory_scanned.connect(
        # pyrefly: ignore [bad-argument-type]
        lambda directory: a.populate_scan_image_gallery(directory, emit_signal=False)
    )


def _pump(seconds: float) -> None:
    from PySide6.QtWidgets import QApplication

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.02)


class TestPeerReentrancyGuard:
    """Addendum 21 (.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md):
    a live, telemetry+hs_err-correlated SIGSEGV inside
    QObjectPrivate::ConnectionData::deleteOrphaned was localized to a
    peer's reentrant _stop_scanner_threads() call reaching into a linked
    panel that was itself still mid-flight through its own
    populate_scan_image_gallery() call (i.e. its own _scan_pipeline_busy
    flag was still set) -- exactly the state the emitting panel is in when
    the queued directory_scanned signal it fired is delivered to the peer,
    since _scan_pipeline_busy only clears once that panel's OWN scan
    settles asynchronously, well after its populate_scan_image_gallery()
    call has already returned.
    """

    def test_peer_does_not_reenter_stop_scanner_threads_on_busy_panel(
        self, q_app, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(
            # pyrefly: ignore [implicit-import]
            wallpaper_common_base._scan_pipeline, "ImageScannerWorker", DelayedImageScannerWorker
        )

        system_display = ConcreteWallpaperBase()
        monitor_display = ConcreteWallpaperBase()
        _link_panels(system_display, monitor_display)

        target_dir = tmp_path / "some_dir"
        target_dir.mkdir()
        (target_dir / "pic.png").write_bytes(b"\x00")

        # Simulate system_display being mid-flight through its own
        # populate_scan_image_gallery() call for a different, newer switch
        # -- exactly the state it's in, per Addendum 21's telemetry trace,
        # when the peer's reentrant call reaches back into it.
        system_display._scan_pipeline_busy = True

        stop_calls = []
        monkeypatch.setattr(
            system_display, "_stop_scanner_threads", lambda: stop_calls.append(1)
        )

        # This is exactly the call the queued directory_scanned signal
        # triggers on the peer once the emitting panel's own call has
        # already returned to the event loop.
        # pyrefly: ignore [bad-argument-type]
        monitor_display.populate_scan_image_gallery(str(target_dir), emit_signal=False)
        _pump(1.0)

        assert stop_calls == [], (
            "peer's reentrant call must not invoke _stop_scanner_threads() on "
            "a linked panel that is itself still mid-flight "
            "(_scan_pipeline_busy) through its own populate_scan_image_gallery() "
            "-- see Addendum 21 in .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md"
        )

    def test_peer_still_stops_a_non_busy_panel(self, q_app, monkeypatch, tmp_path):
        """The guard must not become a blanket no-op: a linked panel that
        genuinely has stale scanner threads and is NOT mid-flight through
        its own call should still get stopped/drained as before."""
        monkeypatch.setattr(
            # pyrefly: ignore [implicit-import]
            wallpaper_common_base._scan_pipeline, "ImageScannerWorker", DelayedImageScannerWorker
        )

        system_display = ConcreteWallpaperBase()
        monitor_display = ConcreteWallpaperBase()
        _link_panels(system_display, monitor_display)

        target_dir = tmp_path / "some_dir"
        target_dir.mkdir()
        (target_dir / "pic.png").write_bytes(b"\x00")

        assert getattr(system_display, "_scan_pipeline_busy", False) is False

        stop_calls = []
        monkeypatch.setattr(
            system_display, "_stop_scanner_threads", lambda: stop_calls.append(1)
        )

        # pyrefly: ignore [bad-argument-type]
        monitor_display.populate_scan_image_gallery(str(target_dir), emit_signal=False)
        _pump(1.0)

        assert stop_calls == [1]

    def test_monitor_selection_does_not_fire_pending_timers_reentrantly(
        self, q_app, monkeypatch, tmp_path
    ):
        """Regression: _select_monitor/_select_monitor_peer must NOT pump the
        full event queue (QApplication.processEvents), because during session
        recovery that reentrantly fires the scan-dir restore timer (armed
        250ms earlier by set_config) from inside the monitor-selection call
        stack -- starting scanner QThreads mid-recovery. The user crash trace
        reached _do_pending_scan_dir_restore via _select_monitor_peer line 89
        exactly this way. The narrowed paint-only flush must leave pending
        timers/queued signals untouched during the call."""
        system_display = ConcreteWallpaperBase()
        monitor_display = ConcreteWallpaperBase()
        _link_panels(system_display, monitor_display)

        # Simulate the session-recovery state: a pending restore timer (0ms so
        # it would fire immediately if the event queue were pumped reentrantly)
        # plus a queued signal delivery, both of which a full processEvents()
        # inside _select_monitor_peer would dispatch mid-call.
        fired = []
        QTimer.singleShot(0, lambda: fired.append("timer"))
        # pyrefly: ignore [bad-argument-type]
        system_display._select_monitor_peer("0")

        assert fired == [], (
            "pending timer must NOT fire reentrantly from inside "
            "_select_monitor_peer (paint-only flush, not processEvents)"
        )

        # The timer must still fire normally once control returns to the event
        # loop -- the narrowing only removed the reentrant pump, not delivery.
        _pump(0.5)
        assert fired == ["timer"]

    def test_monitor_selection_does_not_call_full_process_events(
        self, q_app, monkeypatch, tmp_path
    ):
        """Guards the fix itself: _select_monitor/_select_monitor_peer must
        never call QApplication.processEvents() (the full pump); they now use
        sendPostedEvents(None, Paint). A future regression back to
        processEvents() reintroduces the session-recovery reentrancy."""
        import gui.src.tabs.core.wallpaper_tab.common.wallpaper_common_base._monitor_selection as ms

        calls = []
        monkeypatch.setattr(ms.QApplication, "processEvents", lambda: calls.append("processEvents"))
        monkeypatch.setattr(
            ms.QApplication, "sendPostedEvents", lambda *_: calls.append("sendPostedEvents")
        )

        system_display = ConcreteWallpaperBase()
        monitor_display = ConcreteWallpaperBase()
        _link_panels(system_display, monitor_display)

        # pyrefly: ignore [bad-argument-type]
        system_display._select_monitor("0")
        # pyrefly: ignore [bad-argument-type]
        monitor_display._select_monitor_peer("0")

        assert "processEvents" not in calls, (
            "full QApplication.processEvents() must not be called from "
            "monitor selection (reentrant timer/signal pump -- see Addendum 21)"
        )
        assert calls, "paint-only flush (sendPostedEvents) must still run"

    def test_peer_does_not_start_scan_while_primary_busy(
        self, q_app, monkeypatch, tmp_path
    ):
        """Cross-panel serialization (Addendum 26/28 crash shape): the
        recurring startup-restore crash log shows the peer's queued
        directory_scanned mirror call starting its own ImageScannerWorker
        WHILE the primary is still mid-flight -- the primary sets
        _scan_pipeline_busy BEFORE emitting directory_scanned, but the
        peer's populate only checked its OWN flag, so both panels ran
        scanner QThreads at the same instant and died in
        QObjectPrivate::connect. The peer must defer (retry timer) when any
        linked panel is busy, keeping the two scans strictly sequential."""
        monkeypatch.setattr(
            # pyrefly: ignore [implicit-import]
            wallpaper_common_base._scan_pipeline, "ImageScannerWorker", DelayedImageScannerWorker
        )

        system_display = ConcreteWallpaperBase()
        monitor_display = ConcreteWallpaperBase()
        _link_panels(system_display, monitor_display)

        target_dir = tmp_path / "some_dir"
        target_dir.mkdir()
        (target_dir / "pic.png").write_bytes(b"\x00")

        # Primary mid-flight: exactly the state it is in when the peer's
        # queued directory_scanned mirror call is delivered (primary sets
        # busy before emitting).
        system_display._scan_pipeline_busy = True
        worker_starts = []
        monkeypatch.setattr(
            # pyrefly: ignore [implicit-import]
            wallpaper_common_base._scan_pipeline,
            "ImageScannerWorker",
            lambda *a, **k: worker_starts.append(1) or DelayedImageScannerWorker(*a, **k),
        )

        # This is the queued directory_scanned mirror call.
        # pyrefly: ignore [bad-argument-type]
        monitor_display.populate_scan_image_gallery(str(target_dir), emit_signal=False)
        # Give the deferral retry a moment; the primary never settles, so the
        # peer must keep deferring and never start a second scanner.
        _pump(0.4)

        assert worker_starts == [], (
            "peer must not start its own ImageScannerWorker while the "
            "primary panel is mid-flight (_scan_pipeline_busy) -- both "
            "panels scanning at the same instant is the documented crash "
            "shape (Addendum 26/28)"
        )

    def test_peer_starts_scan_after_primary_settles(
        self, q_app, monkeypatch, tmp_path
    ):
        """Once the primary settles, the peer's deferred mirror call must go
        ahead and start its own scan -- the deferral is serialization, not a
        permanent skip."""
        monkeypatch.setattr(
            # pyrefly: ignore [implicit-import]
            wallpaper_common_base._scan_pipeline, "ImageScannerWorker", DelayedImageScannerWorker
        )

        system_display = ConcreteWallpaperBase()
        monitor_display = ConcreteWallpaperBase()
        _link_panels(system_display, monitor_display)

        target_dir = tmp_path / "some_dir"
        target_dir.mkdir()
        (target_dir / "pic.png").write_bytes(b"\x00")

        system_display._scan_pipeline_busy = True
        worker_starts = []
        monkeypatch.setattr(
            # pyrefly: ignore [implicit-import]
            wallpaper_common_base._scan_pipeline,
            "ImageScannerWorker",
            lambda *a, **k: worker_starts.append(1) or DelayedImageScannerWorker(*a, **k),
        )

        # pyrefly: ignore [bad-argument-type]
        monitor_display.populate_scan_image_gallery(str(target_dir), emit_signal=False)
        _pump(0.2)
        assert worker_starts == [], "peer must defer while primary busy"

        # Primary settles -> peer's retry proceeds.
        # pyrefly: ignore [bad-argument-type]
        system_display._settle_scan_pipeline()
        _pump(0.4)
        assert worker_starts == [1], (
            "peer must start its scan after the primary settles"
        )
