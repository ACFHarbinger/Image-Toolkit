from __future__ import annotations

import pytest
from gui.src.protos.widgets.telemetry_status_bar import TelemetryStatusBar

pytestmark = pytest.mark.gui

class TestTelemetryStatusBar:
    def test_telemetry_status_bar_updates(self, q_app):
        bar = TelemetryStatusBar()
        assert "Ready" in bar._status_label.text()
        bar.set_status_message("Scanning images...", timeout_ms=0)
        assert "Scanning images..." in bar._status_label.text()
        bar.set_db_status(connected=True, latency_ms=15.0)
        assert "15ms" in bar.db_chip.text()
        bar.set_db_status(connected=False)
        assert "Disconnected" in bar.db_chip.text()
        bar.set_task_count(5)
        assert "5" in bar.task_chip.text()
