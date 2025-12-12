import pytest
from unittest.mock import MagicMock, patch

from gui.helpers.web.web_requests_worker import WebRequestsWorker
from gui.helpers.web.reverse_search_worker import ReverseSearchWorker
from gui.helpers.web.google_drive_sync_worker import GoogleDriveSyncWorker

# --- WebRequestsWorker Tests ---

class TestWebRequestsWorker:
    def test_run(self, q_app):
        # web_requests_worker.py imports WebRequestsLogic from backend.src.web
        # We need to patch where it is used.
        # But wait, imports in python are weird if we patch sys.modules.
        # Let's patch "gui.helpers.web.web_requests_worker.WebRequestsLogic"
        
        with patch("gui.helpers.web.web_requests_worker.WebRequestsLogic") as MockLogic:
            mock_inst = MagicMock()
            MockLogic.return_value = mock_inst
            
            worker = WebRequestsWorker({"url": "http://test.com"})
            
            # Setup signal emission from the logic mock
            # The worker connects logic signals to its own signals.
            # We can verify that connection or trigger them.
            
            status = []
            worker.status.connect(lambda s: status.append(s))
            
            finished = []
            worker.finished.connect(lambda m: finished.append(m))
            
            # When run call logic.run()
            # We can make logic.run side effect emitting signals if we really want to test the connection.
            def side_effect():
                # Manually emit signals via the mock objects that were connected?
                # The worker connects: self.logic.on_status.connect(self.status.emit)
                # So mock_inst.on_status is a MagicMock which has .connect called.
                # We can't easily emit from a MagicMock signal unless we set it up as a real Signal or use callbacks.
                pass
            
            mock_inst.run.side_effect = side_effect
            
            worker.run()
            
            MockLogic.assert_called_with({"url": "http://test.com"})
            mock_inst.run.assert_called()
            
            # We at least get the "Starting requests..." status from the worker itself
            assert "Starting requests..." in status

# --- ReverseSearchWorker Tests ---

class TestReverseSearchWorker:
    def test_run(self, q_app):
        # Imports ReverseImageSearchCrawler from backend
        with patch("gui.helpers.web.reverse_search_worker.ReverseImageSearchCrawler") as MockCrawler:
            mock_inst = MagicMock()
            MockCrawler.return_value = mock_inst
            
            worker = ReverseSearchWorker("/tmp/img.jpg", 100, 100, "Chrome")
            
            worker.run()
            
            MockCrawler.assert_called()
            mock_inst.perform_reverse_search.assert_called()

# --- SyncWorker Tests (Google Drive as generic representative) ---

class TestGoogleDriveSyncWorker:
    def test_run(self, q_app):
        # Imports GoogleDriveSync from backend
        with patch("gui.helpers.web.google_drive_sync_worker.GoogleDriveSync") as MockLogic:
            mock_inst = MagicMock()
            MockLogic.return_value = mock_inst
            
            # Pass required args with valid auth config to avoid ValueError
            auth = {"mode": "service_account", "service_account_data": {}}
            worker = GoogleDriveSyncWorker(auth, "/tmp/local", "/tmp/remote", False)
            
            worker.run()
            
            MockLogic.assert_called()
            mock_inst.execute_sync.assert_called()
