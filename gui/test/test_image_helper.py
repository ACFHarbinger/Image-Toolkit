import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import QThreadPool
from PySide6.QtGui import QPixmap

from gui.helpers.image.image_loader_worker import ImageLoaderWorker
from gui.helpers.image.image_scan_worker import ImageScannerWorker

# --- ImageLoaderWorker Tests ---

class TestImageLoaderWorker:
    def test_run(self, q_app):
        # We can test the actual logic or mocking QPixmap if needed.
        # Since we shouldn't rely on existing files, let's patch QPixmap
        
        with patch("gui.helpers.image.image_loader_worker.QPixmap") as MockPixmap:
            # Setup mock pixmap behavior
            mock_inst = MagicMock()
            MockPixmap.return_value = mock_inst
            mock_inst.isNull.return_value = False
            mock_inst.scaled.return_value = MagicMock()
            
            worker = ImageLoaderWorker("/tmp/fake.jpg", 100)
            
            # Catch signals
            results = []
            worker.signals.result.connect(lambda p, px: results.append((p, px)))
            
            worker.run()
            
            assert len(results) == 1
            assert results[0][0] == "/tmp/fake.jpg"
            mock_inst.scaled.assert_called()

    def test_run_failure(self, q_app):
        with patch("gui.helpers.image.image_loader_worker.QPixmap") as MockPixmap:
            mock_inst = MagicMock()
            MockPixmap.return_value = mock_inst
            mock_inst.isNull.return_value = True # Load failed
            
            worker = ImageLoaderWorker("/tmp/bad.jpg", 100)
            
            results = []
            worker.signals.result.connect(lambda p, px: results.append((p, px)))
            
            worker.run()
            
            assert len(results) == 1
            assert results[0][0] == "/tmp/bad.jpg"
            # Should return a (likely null) pixmap, but we just check signal emitted

# --- ImageScannerWorker Tests ---

class TestImageScannerWorker:
    def test_run_scan(self, q_app, tmp_path):
        # Create dummy structure
        d = tmp_path / "images"
        d.mkdir()
        (d / "test1.jpg").touch()
        (d / "test2.png").touch()
        (d / "ignore.txt").touch()
        
        worker = ImageScannerWorker([str(d)])
        
        finished_signals = []
        worker.scan_finished.connect(lambda r: finished_signals.append(r))
        
        worker.run_scan()
        
        assert len(finished_signals) == 1
        found = finished_signals[0]
        assert len(found) == 2
        assert any("test1.jpg" in f for f in found)

    def test_error(self, q_app):
        # Test error signal by passing None or invalid types that might cause crash if not handled,
        # or mock os.scandir to raise
        worker = ImageScannerWorker([])
        
        error_signals = []
        worker.scan_error.connect(lambda e: error_signals.append(e))
        
        worker.run_scan()
        
        assert len(error_signals) == 1
        assert "No valid directories" in error_signals[0]
