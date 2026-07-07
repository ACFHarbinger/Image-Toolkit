from unittest.mock import MagicMock, patch

import pytest
from gui.src.tabs.web.drive_sync_tab import DriveSyncTab
from gui.src.tabs.web.image_crawler_tab import ImageCrawlTab
from gui.src.tabs.web.reverse_search_tab import ReverseImageSearchTab
from gui.src.tabs.web.web_requests_tab import WebRequestsTab
from PySide6.QtWidgets import QWidget

pytestmark = pytest.mark.gui

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
        with (
            patch("gui.src.tabs.web.drive_sync_tab.GoogleDriveSyncWorker") as mock_gd,
            patch("gui.src.tabs.web.drive_sync_tab.LogWindow") as mock_log,
        ):
            yield mock_gd, mock_log

    def test_init(self, q_app, mock_vault):
        tab = DriveSyncTab(mock_vault)
        assert isinstance(tab, QWidget)

    def test_view_remote_map(self, q_app, mock_vault, mock_workers):
        mock_gd, mock_log = mock_workers
        tab = DriveSyncTab(mock_vault)
        tab.remote_path.setText("/Backups")

        # Mock file existence checks/paths
        with (
            patch("gui.src.tabs.web.drive_sync_tab.os.path.isdir", return_value=True),
            patch("gui.src.tabs.web.drive_sync_tab.QThreadPool.globalInstance") as mock_pool,
        ):
            # Ensure "Google Drive (Service Account)" is selected (default)
            tab.view_remote_map()

            mock_gd.assert_called()
            mock_pool.return_value.start.assert_called()


# --- ImageCrawlTab Tests ---


class TestImageCrawlTab:
    @pytest.fixture
    def mock_worker(self):
        with patch("gui.src.tabs.web.image_crawler_tab.ImageCrawlWorker") as mock:
            yield mock

    def test_init(self, q_app):
        # Mock LogWindow to prevent showing
        with patch("gui.src.tabs.web.image_crawler_tab.LogWindow"):
            tab = ImageCrawlTab()
            assert isinstance(tab, QWidget)

    def test_start_crawl_no_dir(self, q_app, mock_worker):
        with patch("gui.src.tabs.web.image_crawler_tab.LogWindow"):
            tab = ImageCrawlTab()
            tab.download_dir_path.clear()

            with patch("gui.src.tabs.web.image_crawler_tab.QMessageBox.warning") as mock_warn:
                tab.start_crawl()
                mock_warn.assert_called()
                mock_worker.assert_not_called()

    def test_start_crawl_success(self, q_app, mock_worker):
        with patch("gui.src.tabs.web.image_crawler_tab.LogWindow"):
            tab = ImageCrawlTab()
            tab.download_dir_path.setText("/tmp/down")
            tab.crawler_type_combo.setCurrentIndex(0)  # General

            tab.start_crawl()

            mock_worker.assert_called()
            mock_worker.return_value.start.assert_called()

    def test_selection_mode_config(self, q_app):
        with patch("gui.src.tabs.web.image_crawler_tab.LogWindow"):
            tab = ImageCrawlTab()
            # Default value
            assert tab.selection_mode_combo.currentText() == "Download All (Default)"

            # Switch to Manual Selection
            tab.selection_mode_combo.setCurrentIndex(1)
            assert tab.selection_mode_combo.currentText() == "Manual Selection"

            # Switch to Automated Selection
            tab.selection_mode_combo.setCurrentIndex(2)
            assert tab.selection_mode_combo.currentText() == "Automated Selection"

    def test_on_crawl_done_manual_selection_accept(self, q_app):
        with (
            patch("gui.src.tabs.web.image_crawler_tab.LogWindow"),
            patch("gui.src.windows.crawler_selection_dialogs.ManualSelectionDialog") as mock_dialog_class,
            patch("gui.src.tabs.web.image_crawler_tab.QMessageBox.information"),
            patch("gui.src.tabs.web.image_crawler_tab.os.path.exists", return_value=True),
            patch("gui.src.tabs.web.image_crawler_tab.os.remove") as mock_remove,
        ):
            tab = ImageCrawlTab()
            tab.selection_mode_combo.setCurrentIndex(1)  # Manual Selection
            tab.downloaded_files = ["/tmp/img1.png", "/tmp/img2.png"]

            # Mock the dialog instance
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = 1  # Accepted
            # Mock checkboxes: img1 is kept, img2 is pruned
            chk1 = MagicMock()
            chk1.isChecked.return_value = True
            chk2 = MagicMock()
            chk2.isChecked.return_value = False
            mock_dialog.checkboxes = {"/tmp/img1.png": chk1, "/tmp/img2.png": chk2}
            mock_dialog_class.return_value = mock_dialog

            tab.on_crawl_done(2, "Crawl finished. Downloaded **2** image(s)!")

            # /tmp/img2.png should be removed along with its metadata
            mock_remove.assert_any_call("/tmp/img2.png")
            mock_remove.assert_any_call("/tmp/img2.json")
            # /tmp/img1.png and its metadata should not be removed
            with pytest.raises(AssertionError):
                mock_remove.assert_any_call("/tmp/img1.png")
            with pytest.raises(AssertionError):
                mock_remove.assert_any_call("/tmp/img1.json")

    def test_on_crawl_done_manual_selection_reject(self, q_app):
        with (
            patch("gui.src.tabs.web.image_crawler_tab.LogWindow"),
            patch("gui.src.windows.crawler_selection_dialogs.ManualSelectionDialog") as mock_dialog_class,
            patch("gui.src.tabs.web.image_crawler_tab.QMessageBox.information"),
            patch("gui.src.tabs.web.image_crawler_tab.os.path.exists", return_value=True),
            patch("gui.src.tabs.web.image_crawler_tab.os.remove") as mock_remove,
        ):
            tab = ImageCrawlTab()
            tab.selection_mode_combo.setCurrentIndex(1)  # Manual Selection
            tab.downloaded_files = ["/tmp/img1.png", "/tmp/img2.png"]

            # Mock the dialog instance to return Cancel/Rejected
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = 0  # Rejected
            mock_dialog_class.return_value = mock_dialog

            tab.on_crawl_done(2, "Crawl finished. Downloaded **2** image(s)!")

            # Both files and their metadata should be removed
            mock_remove.assert_any_call("/tmp/img1.png")
            mock_remove.assert_any_call("/tmp/img1.json")
            mock_remove.assert_any_call("/tmp/img2.png")
            mock_remove.assert_any_call("/tmp/img2.json")

    def test_on_crawl_done_automated_selection_accept(self, q_app):
        with (
            patch("gui.src.tabs.web.image_crawler_tab.LogWindow"),
            patch("gui.src.windows.crawler_selection_dialogs.DuplicateConfigDialog") as mock_config_dialog_class,
            patch("gui.src.windows.crawler_selection_dialogs.DeduplicationPruningDialog") as mock_prune_dialog_class,
            patch("gui.src.windows.crawler_selection_dialogs.run_duplicate_scan", return_value={}),
            patch("gui.src.tabs.web.image_crawler_tab.QMessageBox.information"),
            patch("gui.src.tabs.web.image_crawler_tab.os.path.exists", return_value=True),
            patch("gui.src.tabs.web.image_crawler_tab.os.remove") as mock_remove,
        ):
            tab = ImageCrawlTab()
            tab.selection_mode_combo.setCurrentIndex(2)  # Automated Selection
            tab.downloaded_files = ["/tmp/img1.png", "/tmp/img2.png"]

            # Mock config dialog
            mock_config_dialog = MagicMock()
            mock_config_dialog.exec.return_value = 1  # Accepted
            mock_config_dialog.get_config.return_value = {}
            mock_config_dialog_class.return_value = mock_config_dialog

            # Mock pruning dialog
            mock_prune_dialog = MagicMock()
            mock_prune_dialog.exec.return_value = 1  # Accepted
            # Mock checkboxes: img1 is kept, img2 is pruned
            chk1 = MagicMock()
            chk1.isChecked.return_value = True
            chk2 = MagicMock()
            chk2.isChecked.return_value = False
            mock_prune_dialog.checkboxes = {"/tmp/img1.png": chk1, "/tmp/img2.png": chk2}
            mock_prune_dialog_class.return_value = mock_prune_dialog

            tab.on_crawl_done(2, "Crawl finished. Downloaded **2** image(s)!")

            # /tmp/img2.png and metadata should be removed
            mock_remove.assert_any_call("/tmp/img2.png")
            mock_remove.assert_any_call("/tmp/img2.json")
            # /tmp/img1.png and metadata should not be removed
            with pytest.raises(AssertionError):
                mock_remove.assert_any_call("/tmp/img1.png")
            with pytest.raises(AssertionError):
                mock_remove.assert_any_call("/tmp/img1.json")

    def test_on_crawl_done_automated_selection_reject(self, q_app):
        with (
            patch("gui.src.tabs.web.image_crawler_tab.LogWindow"),
            patch("gui.src.windows.crawler_selection_dialogs.DuplicateConfigDialog") as mock_config_dialog_class,
            patch("gui.src.tabs.web.image_crawler_tab.QMessageBox.information"),
            patch("gui.src.tabs.web.image_crawler_tab.os.path.exists", return_value=True),
            patch("gui.src.tabs.web.image_crawler_tab.os.remove") as mock_remove,
        ):
            tab = ImageCrawlTab()
            tab.selection_mode_combo.setCurrentIndex(2)  # Automated Selection
            tab.downloaded_files = ["/tmp/img1.png", "/tmp/img2.png"]

            # Mock config dialog to return Cancel
            mock_config_dialog = MagicMock()
            mock_config_dialog.exec.return_value = 0  # Rejected
            mock_config_dialog_class.return_value = mock_config_dialog

            tab.on_crawl_done(2, "Crawl finished. Downloaded **2** image(s)!")

            # All files and metadata should be removed
            mock_remove.assert_any_call("/tmp/img1.png")
            mock_remove.assert_any_call("/tmp/img1.json")
            mock_remove.assert_any_call("/tmp/img2.png")
            mock_remove.assert_any_call("/tmp/img2.json")


# --- ReverseImageSearchTab Tests ---


class TestReverseImageSearchTab:
    @pytest.fixture
    def mock_deps(self):
        with (
            patch("gui.src.tabs.web.reverse_search_tab.ImageScannerWorker"),
            patch("gui.src.tabs.web.reverse_search_tab.ReverseSearchWorker") as mock_search,
            patch("gui.src.tabs.web.reverse_search_tab.ImageLoaderWorker"),
        ):
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

        with patch("gui.src.tabs.web.reverse_search_tab.QThreadPool.globalInstance") as mock_pool:
            tab.start_search()
            mock_deps.assert_called()
            mock_pool.return_value.start.assert_called()


# --- WebRequestsTab Tests ---


class TestWebRequestsTab:
    @pytest.fixture
    def mock_worker(self):
        with patch("gui.src.tabs.web.web_requests_tab.WebRequestsWorker") as mock:
            yield mock

    def test_init(self, q_app):
        with patch("gui.src.tabs.web.web_requests_tab.LogWindow"):
            tab = WebRequestsTab()
            assert isinstance(tab, QWidget)

    def test_start_requests_validation(self, q_app):
        with patch("gui.src.tabs.web.web_requests_tab.LogWindow"):
            tab = WebRequestsTab()
            # Missing URL
            with patch("gui.src.tabs.web.web_requests_tab.QMessageBox.warning") as mock_warn:
                tab.start_requests()
                mock_warn.assert_called()

    def test_start_requests_success(self, q_app, mock_worker):
        with patch("gui.src.tabs.web.web_requests_tab.LogWindow"):
            tab = WebRequestsTab()
            tab.url_input.setText("https://google.com")
            tab.request_list_widget.addItem("[GET]")
            tab.action_list_widget.addItem("Print Response URL")

            tab.start_requests()

            mock_worker.assert_called()
            mock_worker.return_value.start.assert_called()
