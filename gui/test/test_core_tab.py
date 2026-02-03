import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QWidget

from gui.src.tabs.core.convert_tab import ConvertTab
from gui.src.tabs.core.delete_tab import DeleteTab
from gui.src.tabs.core.image_extractor_tab import ImageExtractorTab
from gui.src.tabs.core.merge_tab import MergeTab
from gui.src.tabs.core.wallpaper_tab import WallpaperTab

# --- ConvertTab Tests ---


class TestConvertTab:
    @pytest.fixture
    def mock_worker(self):
        with patch("gui.src.tabs.core.convert_tab.ConversionWorker") as mock:
            yield mock

    def test_init(self, q_app):
        tab = ConvertTab()
        assert isinstance(tab, QWidget)
        assert tab.input_path is not None

    def test_start_conversion_no_files(self, q_app, mock_worker):
        # Mock message box to avoid blocking
        with patch("gui.src.tabs.core.convert_tab.QMessageBox") as mock_mb:
            tab = ConvertTab()
            tab.collect_paths = MagicMock(return_value=[])

            tab.start_conversion_worker()

            mock_worker.assert_not_called()
            mock_mb.warning.assert_called()

    def test_start_conversion_success(self, q_app, mock_worker):
        with patch("gui.src.tabs.core.convert_tab.os.path.isdir", return_value=True):
            tab = ConvertTab()
            tab.input_path.setText("/tmp/in")
            tab.collect_paths = MagicMock(return_value=["/tmp/in/a.jpg"])

            # Setup worker mock instance
            worker_instance = mock_worker.return_value
            worker_instance.isRunning.return_value = False

            tab.start_conversion_worker()

            mock_worker.assert_called()
            worker_instance.start.assert_called()


# --- WallpaperTab Tests ---


class TestWallpaperTab:
    @pytest.fixture
    def mock_deps(self):
        with (
            patch("gui.src.tabs.core.wallpaper_tab.WallpaperWorker"),
            patch("gui.src.tabs.core.wallpaper_tab.ImageScannerWorker"),
            patch("gui.src.tabs.core.wallpaper_tab.VideoScannerWorker"),
            patch(
                "gui.src.tabs.core.wallpaper_tab.get_monitors",
                return_value=[MagicMock(name="Monitor1")],
            ),
        ):
            yield

    def test_init(self, q_app, mock_deps):
        # WallpaperTab takes a db_tab_ref arg
        tab = WallpaperTab(db_tab_ref=MagicMock())
        assert isinstance(tab, QWidget)

    def test_update_background_type(self, q_app, mock_deps):
        tab = WallpaperTab(db_tab_ref=MagicMock())
        tab.show()  # Ensure widgets can be effectively visible

        tab._update_background_type("Solid Color")
        assert tab.solid_color_widget.isVisible()

        tab._update_background_type("Slideshow")
        assert tab.slideshow_group.isVisible()

    def test_swap_monitors(self, q_app, mock_deps):
        tab = WallpaperTab(db_tab_ref=MagicMock())

        # Setup 2 monitors (mock_deps already provides 1, let's ensure we have 2)
        m1 = MagicMock(name="Monitor1")
        m2 = MagicMock(name="Monitor2")
        tab.monitors = [m1, m2]

        # Manually populate monitor_widgets
        w1 = MagicMock()
        w1.monitor = m1
        w2 = MagicMock()
        w2.monitor = m2
        tab.monitor_widgets = {"0": w1, "1": w2}

        # Set initial states
        tab.monitor_image_paths = {"0": "path1.jpg", "1": "path2.jpg"}
        tab.monitor_slideshow_queues = {"0": ["path1.jpg"], "1": ["path2.jpg"]}
        tab.monitor_current_index = {"0": 0, "1": 0}

        # Perform swap
        tab.swap_monitors()

        # Verify swapped states
        assert tab.monitor_image_paths["0"] == "path2.jpg"
        assert tab.monitor_image_paths["1"] == "path1.jpg"
        assert tab.monitor_slideshow_queues["0"] == ["path2.jpg"]
        assert tab.monitor_slideshow_queues["1"] == ["path1.jpg"]

        # Verify UI updates
        w1.set_image.assert_called_with("path2.jpg", None)
        w2.set_image.assert_called_with("path1.jpg", None)


# --- DeleteTab Tests ---


class TestDeleteTab:
    def test_init(self, q_app):
        with (
            patch("gui.src.tabs.core.delete_tab.DeletionWorker"),
            patch("gui.src.tabs.core.delete_tab.DuplicateScanWorker"),
        ):
            tab = DeleteTab()
            assert isinstance(tab, QWidget)


# --- MergeTab Tests ---


class TestMergeTab:
    def test_init(self, q_app):
        tab = MergeTab()
        assert isinstance(tab, QWidget)


# --- ImageExtractorTab Tests ---


class TestImageExtractorTab:
    def test_init(self, q_app):
        tab = ImageExtractorTab()
        assert isinstance(tab, QWidget)
