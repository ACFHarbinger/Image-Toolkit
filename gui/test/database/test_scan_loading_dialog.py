"""Scan & Tag: native-dialog option + scanner GC guard (#478 sweep)."""

from unittest.mock import MagicMock

from PySide6.QtWidgets import QFileDialog

from gui.src.constants.ui import DIALOG_OPTS
from gui.src.helpers.image.image_scan_worker import ImageScannerWorker
from gui.src.tabs.database.scan_metadata_tab._scan_loading import _ScanLoadingMixin


def test_image_scanner_worker_run_is_gc_guarded():
    assert ImageScannerWorker.run.__wrapped__ is not None  # @gc_disabled_run
    assert ImageScannerWorker.run.__wrapped__ is not ImageScannerWorker.run


def test_browse_scan_directory_forces_non_native_dialog(monkeypatch):
    captured = {}

    def fake_get(parent, caption, start_dir, options=None):
        captured["options"] = options
        return ""

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", fake_get)
    host = MagicMock()
    host.last_browsed_scan_dir = "/tmp"
    _ScanLoadingMixin.browse_scan_directory(host)
    assert captured["options"] is not None
    assert captured["options"] & DIALOG_OPTS



