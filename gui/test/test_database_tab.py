import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QWidget

from gui.src.tabs.database.database_tab import DatabaseTab
from gui.src.tabs.database.scan_metadata_tab import ScanMetadataTab
from gui.src.tabs.database.search_tab import SearchTab

# --- DatabaseTab Tests ---


class TestDatabaseTab:
    @pytest.fixture
    def mock_db_cls(self):
        with patch("gui.src.tabs.database.database_tab.ImageDatabase") as mock:
            yield mock

    def test_init(self, q_app):
        tab = DatabaseTab()
        assert isinstance(tab, QWidget)
        assert tab.db is None

    def test_connect_database(self, q_app, mock_db_cls):
        # Mock connection fields
        tab = DatabaseTab()
        tab.db_host.setText("localhost")
        tab.db_port.setText("5432")
        tab.db_user.setText("user")
        tab.db_password.setText("pass")
        tab.db_name.setText("test_db")

        # Mock internal update methods to avoid complexity
        tab.update_statistics = MagicMock()
        tab._refresh_all_group_combos = MagicMock()
        tab.refresh_subgroup_autocomplete = MagicMock()
        tab.refresh_tags_list = MagicMock()
        tab.refresh_groups_list = MagicMock()
        tab.refresh_subgroups_list = MagicMock()

        with patch("gui.src.tabs.database.database_tab.QMessageBox.information"):
            tab.connect_database()

        mock_db_cls.assert_called_once()
        assert tab.db is not None

    def test_reset_database_no_connection(self, q_app):
        tab = DatabaseTab()
        with patch(
            "gui.src.tabs.database.database_tab.QMessageBox.warning"
        ) as mock_warn:
            tab.reset_database()
            mock_warn.assert_called()


# --- ScanMetadataTab Tests ---


class TestScanMetadataTab:
    def test_init(self, q_app):
        # ScanMetadataTab requires a db_tab_ref
        mock_db_tab = MagicMock()
        # Mock valid local path or os.getcwd for last_browsed_scan_dir
        with patch("gui.src.tabs.database.scan_metadata_tab.LOCAL_SOURCE_PATH", "/tmp"):
            tab = ScanMetadataTab(mock_db_tab)
            assert isinstance(tab, QWidget)
            assert tab.db_tab_ref == mock_db_tab

    def test_cancel_loading(self, q_app):
        mock_db_tab = MagicMock()
        with patch("gui.src.tabs.database.scan_metadata_tab.LOCAL_SOURCE_PATH", "/tmp"):
            tab = ScanMetadataTab(mock_db_tab)
            mock_thread = MagicMock()
            mock_thread.isRunning.return_value = True
            tab.scan_thread = mock_thread

            tab.cancel_loading()

            mock_thread.requestInterruption.assert_called()
            mock_thread.quit.assert_called()


# --- SearchTab Tests ---


class TestSearchTab:
    @pytest.fixture
    def mock_worker(self):
        with patch("gui.src.tabs.database.search_tab.SearchWorker") as mock:
            yield mock

    def test_init(self, q_app):
        mock_db_tab = MagicMock()
        tab = SearchTab(mock_db_tab)
        assert isinstance(tab, QWidget)

    def test_perform_search_no_db(self, q_app, mock_worker):
        mock_db_tab = MagicMock()
        mock_db_tab.db = None
        tab = SearchTab(mock_db_tab)

        with patch("gui.src.tabs.database.search_tab.QMessageBox.warning") as mock_warn:
            tab.perform_search()
            mock_warn.assert_called()
            mock_worker.assert_not_called()

    def test_perform_search_success(self, q_app, mock_worker):
        mock_db_tab = MagicMock()
        mock_db_tab.db = MagicMock()  # DB connected

        tab = SearchTab(mock_db_tab)
        tab.show()  # Ensure widgets are initialized if needed

        worker_instance = mock_worker.return_value

        # Since perform_search uses QThreadPool.globalInstance().start(worker)
        # we can't easily check if global thread pool started it unless we mock QThreadPool
        with patch("gui.src.tabs.database.search_tab.QThreadPool") as MockThreadPool:
            tab.perform_search()

            mock_worker.assert_called()
            MockThreadPool.globalInstance().start.assert_called_with(worker_instance)
