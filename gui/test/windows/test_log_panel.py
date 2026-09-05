"""Unit tests for LogHub and GlobalLogPanel (§2.17)."""

import logging

import pytest
from gui.src.windows.logging.log_hub import LogEntry, LogHub, UnifiedLogHandler
from gui.src.windows.logging.log_panel import GlobalLogPanel


def test_log_entry_formatting():
    entry = LogEntry(
        timestamp="12:00:00",
        level="ERROR",
        source="database",
        message="Connection failed",
    )
    assert entry.level_order == 40
    assert "[12:00:00]" in entry.formatted_line()
    assert "[ERROR  ]" in entry.formatted_line()
    assert "[database]" in entry.formatted_line()
    assert "Connection failed" in entry.formatted_line()


def test_log_hub_lifecycle_and_counters():
    hub = LogHub(max_entries=10)
    assert hub.error_count == 0
    assert hub.warning_count == 0

    hub.info("Application initialized", source="core")
    hub.warning("Low disk space", source="system")
    hub.error("File not found", source="io")
    hub.critical("Kernel panic", source="core")

    assert len(hub.entries()) == 4
    assert hub.warning_count == 1
    assert hub.error_count == 2

    # Verify max_entries ring buffer eviction
    for i in range(15):
        hub.info(f"Entry {i}", source="test")

    assert len(hub.entries()) == 10

    # Clear
    hub.clear()
    assert len(hub.entries()) == 0
    assert hub.error_count == 0
    assert hub.warning_count == 0


def test_unified_log_handler():
    hub = LogHub()
    handler = UnifiedLogHandler(hub=hub, source="backend_test")
    logger = logging.getLogger("test_logger")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    record = logger.makeRecord(
        name="test_logger",
        level=logging.WARNING,
        fn="test.py",
        lno=10,
        msg="Test warning message",
        args=(),
        exc_info=None,
    )
    handler.emit(record)

    # Process events to allow queued connection
    entries = hub.entries()
    assert len(entries) == 1
    assert entries[0].level == "WARNING"
    assert "Test warning message" in entries[0].message
    assert entries[0].source == "backend_test"


@pytest.mark.gui
def test_global_log_panel_widget(q_app):
    hub = LogHub()
    panel = GlobalLogPanel(hub=hub)

    hub.info("Starting worker", source="extractor")
    hub.warning("Deprecated configuration", source="config")
    hub.error("Database connection refused", source="database")

    # Initial full text
    plain_text = panel.log_output.toPlainText()
    assert "Starting worker" in plain_text
    assert "Deprecated configuration" in plain_text
    assert "Database connection refused" in plain_text
    assert "✕ 1  ⚠ 1" in panel.badge_label.text()

    # Filter by level: ERROR+
    panel.level_combo.setCurrentText("ERROR+")
    filtered_text = panel.log_output.toPlainText()
    assert "Starting worker" not in filtered_text
    assert "Deprecated configuration" not in filtered_text
    assert "Database connection refused" in filtered_text

    # Filter by search text
    panel.level_combo.setCurrentText("All Levels")
    panel.search_edit.setText("worker")
    search_text = panel.log_output.toPlainText()
    assert "Starting worker" in search_text
    assert "Database connection refused" not in search_text

    # Clear
    panel._clear_logs()
    assert panel.log_output.toPlainText() == ""
    assert "✓ Ready" in panel.badge_label.text()
