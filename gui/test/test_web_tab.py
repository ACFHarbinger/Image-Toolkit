import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QWidget

from gui.tabs.web.drive_sync_tab import DriveSyncTab
from gui.tabs.web.image_crawler_tab import ImageCrawlTab
from gui.tabs.web.reverse_search_tab import ReverseImageSearchTab
from gui.tabs.web.web_requests_tab import WebRequestsTab

# --- DriveSyncTab Tests ---

class TestDriveSyncTab:
    @pytest.fixture
    def mock_vault(self):
        vault = MagicMock()
        # Key must match stem of SERVICE_ACCOUNT_FILE (image_toolkit_service.json)
        # Dictionary must not be empty to pass 'if not sa_data:' check
        vault.api_credentials = {"image_toolkit_service": {"some_key": "some_value"}}
        return vault

    @pytest.fixture
    def mock_workers(self):
        with patch("gui.tabs.web.drive_sync_tab.GoogleDriveSyncWorker") as mock_gd, \
             patch("gui.tabs.web.drive_sync_tab.LogWindow") as mock_log:
            yield mock_gd, mock_log

    def test_init(self, q_app, mock_vault):
        tab = DriveSyncTab(mock_vault)
        assert isinstance(tab, QWidget)

    def test_view_remote_map(self, q_app, mock_vault, mock_workers):
        mock_gd, mock_log = mock_workers
        tab = DriveSyncTab(mock_vault)
        tab.remote_path.setText("/Backups")
        
        # Mock file existence checks/paths
        with patch("gui.tabs.web.drive_sync_tab.os.path.isdir", return_value=True), \
             patch("gui.tabs.web.drive_sync_tab.QThreadPool.globalInstance") as mock_pool:
            
            # Ensure "Google Drive (Service Account)" is selected (default)
            tab.view_remote_map()
            
            mock_gd.assert_called()
            mock_pool.return_value.start.assert_called()

# --- ImageCrawlTab Tests ---

class TestImageCrawlTab:
    @pytest.fixture
    def mock_worker(self):
        with patch("gui.tabs.web.image_crawler_tab.ImageCrawlWorker") as mock:
            yield mock

    def test_init(self, q_app):
        # Mock LogWindow to prevent showing
        with patch("gui.tabs.web.image_crawler_tab.LogWindow"):
            tab = ImageCrawlTab()
            assert isinstance(tab, QWidget)

    def test_start_crawl_no_dir(self, q_app, mock_worker):
        with patch("gui.tabs.web.image_crawler_tab.LogWindow"):
            tab = ImageCrawlTab()
            tab.download_dir_path.clear()
            
            with patch("gui.tabs.web.image_crawler_tab.QMessageBox.warning") as mock_warn:
                tab.start_crawl()
                mock_warn.assert_called()
                mock_worker.assert_not_called()

    def test_start_crawl_success(self, q_app, mock_worker):
        with patch("gui.tabs.web.image_crawler_tab.LogWindow"):
            tab = ImageCrawlTab()
            tab.download_dir_path.setText("/tmp/down")
            tab.crawler_type_combo.setCurrentIndex(0) # General
            
            tab.start_crawl()
            
            mock_worker.assert_called()
            mock_worker.return_value.start.assert_called()

# --- ReverseImageSearchTab Tests ---

class TestReverseImageSearchTab:
    @pytest.fixture
    def mock_deps(self):
        with patch("gui.tabs.web.reverse_search_tab.ImageScannerWorker"), \
             patch("gui.tabs.web.reverse_search_tab.ReverseSearchWorker") as mock_search, \
             patch("gui.tabs.web.reverse_search_tab.ImageLoaderWorker"):
            yield mock_search

    def test_init(self, q_app):
        tab = ReverseImageSearchTab()
        assert isinstance(tab, QWidget)

    def test_start_search_no_selection(self, q_app, mock_deps):
        tab = ReverseImageSearchTab()
        tab.selected_source_path = None
        tab.start_search()
        mock_deps.assert_not_called()

    def test_start_search_success(self, q_app, mock_deps):
        tab = ReverseImageSearchTab()
        tab.selected_source_path = "/tmp/img.jpg"
        
        with patch("gui.tabs.web.reverse_search_tab.QThreadPool.globalInstance") as mock_pool:
            tab.start_search()
            mock_deps.assert_called()
            mock_pool.return_value.start.assert_called()

# --- WebRequestsTab Tests ---

class TestWebRequestsTab:
    @pytest.fixture
    def mock_worker(self):
        with patch("gui.tabs.web.web_requests_tab.WebRequestsWorker") as mock:
            yield mock

    def test_init(self, q_app):
        with patch("gui.tabs.web.web_requests_tab.LogWindow"):
            tab = WebRequestsTab()
            assert isinstance(tab, QWidget)

    def test_start_requests_validation(self, q_app):
        with patch("gui.tabs.web.web_requests_tab.LogWindow"):
            tab = WebRequestsTab()
            # Missing URL
            with patch("gui.tabs.web.web_requests_tab.QMessageBox.warning") as mock_warn:
                tab.start_requests()
                mock_warn.assert_called()

    def test_start_requests_success(self, q_app, mock_worker):
        with patch("gui.tabs.web.web_requests_tab.LogWindow"):
            tab = WebRequestsTab()
            tab.url_input.setText("https://google.com")
            tab.request_list_widget.addItem("[GET]")
            tab.action_list_widget.addItem("Print Response URL")
            
            tab.start_requests()
            
            mock_worker.assert_called()
            mock_worker.return_value.start.assert_called()
