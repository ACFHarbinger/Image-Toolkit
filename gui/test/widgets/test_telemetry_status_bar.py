"""Tests for TelemetryStatusBar component (§2.39, #540)."""

from __future__ import annotations

import threading
from unittest.mock import patch

import pytest
from gui.src.components.widgets.telemetry_status_bar import (
    TelemetryStatusBar,
    create_telemetry_bridge,
)
from gui.src.modules.context import ModuleContext, ModuleServices
from gui.src.modules.events import EventHub, TelemetryUpdatedFact
from gui.src.modules.library_service import LIBRARY_DATABASE_SERVICE, LibraryDatabaseService
from PySide6.QtCore import QCoreApplication

pytestmark = pytest.mark.gui


class TestTelemetryStatusBar:
    def test_initial_state_and_direct_updates(self, q_app):
        bar = TelemetryStatusBar(sample_interval_ms=0)
        assert "Ready" in bar._status_label.text()
        assert "DB: Ready" in bar.db_chip.text()
        assert "Tasks: 0" in bar.task_chip.text()

        bar.set_status_message("Scanning images...", timeout_ms=0)
        assert "Scanning images..." in bar._status_label.text()

        bar.showMessage("Searching catalog...", timeout=0)
        assert "Searching catalog..." in bar._status_label.text()

        bar.set_db_status(connected=True, latency_ms=12.4)
        assert "12ms" in bar.db_chip.text()

        bar.set_db_status(connected=False)
        assert "Disconnected" in bar.db_chip.text()

        bar.set_task_count(7)
        assert "7" in bar.task_chip.text()

        bar.set_vram_status(allocated_gb=5.5, total_gb=16.0)
        assert "5.5/16.0 GB" in bar.gpu_chip.text()

        bar.dispose()

    def test_event_hub_telemetry_fact(self, q_app):
        hub = EventHub(q_app)
        bar = TelemetryStatusBar(event_hub=hub, sample_interval_ms=0)

        hub.publish(
            TelemetryUpdatedFact(
                origin="test",
                db_connected=True,
                db_latency_ms=18.0,
                task_count=4,
                vram_allocated_gb=6.2,
                vram_total_gb=24.0,
                status_message="Worker pipeline online",
            )
        )

        assert "18ms" in bar.db_chip.text()
        assert "4" in bar.task_chip.text()
        assert "6.2/24.0 GB" in bar.gpu_chip.text()
        assert "Worker pipeline online" in bar._status_label.text()

        bar.dispose()

    def test_coalesce_noisy_updates(self, q_app):
        hub = EventHub(q_app)
        bar = TelemetryStatusBar(event_hub=hub, coalesce_interval_ms=50, sample_interval_ms=0)

        # Send multiple rapid noisy facts
        hub.publish(TelemetryUpdatedFact(origin="task_a", task_count=1))
        hub.publish(TelemetryUpdatedFact(origin="task_b", task_count=2))
        hub.publish(TelemetryUpdatedFact(origin="db", db_connected=True, db_latency_ms=5.0))
        hub.publish(TelemetryUpdatedFact(origin="task_c", task_count=3))

        # Buffered before flush
        assert bar._coalesce_timer.isActive()

        # Flush coalesced updates
        bar.flush_telemetry()
        assert not bar._coalesce_timer.isActive()
        assert "3" in bar.task_chip.text()
        assert "5ms" in bar.db_chip.text()

        bar.dispose()

    def test_thread_safe_bridge(self, q_app):
        hub = EventHub(q_app)
        standalone_bridge = create_telemetry_bridge(hub)
        assert standalone_bridge is not None

        bar = TelemetryStatusBar(event_hub=hub, sample_interval_ms=0)
        bridge = bar.create_bridge()
        assert bridge is not None

        worker_error = []

        def background_worker():
            try:
                # Post fact from a non-GUI worker thread
                bridge.post(
                    TelemetryUpdatedFact(
                        origin="bg_worker",
                        task_count=9,
                        status_message="Async job started",
                    )
                )
            except Exception as e:
                worker_error.append(e)

        thread = threading.Thread(target=background_worker)
        thread.start()
        thread.join()

        assert not worker_error
        # Process queued signals on GUI event loop
        QCoreApplication.processEvents()

        assert "9" in bar.task_chip.text()
        assert "Async job started" in bar._status_label.text()

        bar.dispose()

    def test_module_context_service_integration(self, q_app):
        hub = EventHub(q_app)
        services = ModuleServices()
        db_service = LibraryDatabaseService()
        db_service.db = object()  # non-None db handle
        services.register(LIBRARY_DATABASE_SERVICE, db_service)

        context = ModuleContext(event_hub=hub, services=services)
        bar = TelemetryStatusBar(context=context, sample_interval_ms=0)

        # Trigger sampling
        bar._sample_telemetry()
        assert "DB: Ready" in bar.db_chip.text()

        bar.dispose()

    def test_construction_does_not_sample_synchronously(self, q_app):
        """Codex-style review finding: _sample_telemetry() does `import
        torch` + torch.cuda.is_available() (~0.9s cold measured), so
        calling it synchronously in __init__ would block MainWindow
        construction by that much for every experimental-shell user.
        It must be deferred to the next event-loop turn instead.
        """
        with patch.object(TelemetryStatusBar, "_sample_telemetry") as mock_sample:
            bar = TelemetryStatusBar(sample_interval_ms=3000)
            # Not called yet -- still queued for the next event-loop turn.
            mock_sample.assert_not_called()

            QCoreApplication.processEvents()
            mock_sample.assert_called_once()

            bar.dispose()

    def test_dispose_before_initial_sample_does_not_sample(self, q_app):
        """The deferred first sample must be cancelable: disposing before
        it fires must not still run it afterward (same #536 dispose-race
        class)."""
        with patch.object(TelemetryStatusBar, "_sample_telemetry") as mock_sample:
            bar = TelemetryStatusBar(sample_interval_ms=3000)
            bar.dispose()
            QCoreApplication.processEvents()

            mock_sample.assert_not_called()

    def test_layout_toggle_requested_signal(self, q_app):
        bar = TelemetryStatusBar(sample_interval_ms=0)
        toggled = []
        bar.layout_toggle_requested.connect(lambda: toggled.append(True))

        bar.layout_btn.click()
        assert toggled == [True]

        bar.dispose()
