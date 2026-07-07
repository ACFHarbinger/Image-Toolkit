import json
import time
from unittest.mock import MagicMock, mock_open, patch

import cv2
import pytest
from gui.src.tabs.core.convert_tab import ConvertTab
from gui.src.tabs.core.similarity_tab import SimilarityTab
from gui.src.tabs.core.extractor_tab import ExtractorTab
from gui.src.tabs.core.merge_tab import MergeTab
from gui.src.tabs.core.wallpaper_tab import WallpaperTab
from PySide6.QtWidgets import QWidget

pytestmark = pytest.mark.gui


# --- ConvertTab Tests ---
class TestConvertTab:
    @pytest.fixture
    def mock_worker(self):
        with patch("gui.src.tabs.core.elements.format_subtab.ConversionWorker") as mock:
            yield mock

    def test_init(self, q_app):
        tab = ConvertTab()
        assert isinstance(tab, QWidget)
        assert tab.format_subtab.input_path is not None

    def test_start_conversion_no_files(self, q_app, mock_worker):
        # Mock message box to avoid blocking
        with patch("gui.src.tabs.core.elements.format_subtab.QMessageBox") as mock_mb:
            tab = ConvertTab()
            tab.format_subtab.collect_paths = MagicMock(return_value=[])

            tab.format_subtab.start_conversion_worker()

            mock_worker.assert_not_called()
            mock_mb.warning.assert_called()

    def test_start_conversion_success(self, q_app, mock_worker):
        with patch("gui.src.tabs.core.elements.format_subtab.os.path.isdir", return_value=True):
            tab = ConvertTab()
            tab.format_subtab.input_path.setText("/tmp/in")
            tab.format_subtab.collect_paths = MagicMock(return_value=["/tmp/in/a.jpg"])

            # Setup worker mock instance
            worker_instance = mock_worker.return_value
            worker_instance.isRunning.return_value = False

            tab.format_subtab.start_conversion_worker()

            mock_worker.assert_called()
            worker_instance.start.assert_called()


# --- WallpaperTab Tests ---


class TestWallpaperTab:
    @pytest.fixture
    def mock_deps(self):
        from screeninfo import Monitor
        mock_monitor = Monitor(name="Display1", x=0, y=0, width=1920, height=1080, is_primary=True)
        with (
            patch("gui.src.tabs.core.elements.system_display_subtab.WallpaperWorker"),
            patch("gui.src.tabs.core.elements.common.wallpaper_common_base.ImageScannerWorker"),
            patch("gui.src.tabs.core.elements.common.wallpaper_common_base.VideoScannerWorker"),
            patch(
                "gui.src.tabs.core.elements.common.wallpaper_common_base.get_monitors",
                return_value=[mock_monitor],
            ),
        ):
            yield

    def test_init(self, q_app, mock_deps):
        # WallpaperTab takes a db_tab_ref arg
        tab = WallpaperTab(db_tab_ref=MagicMock())
        assert isinstance(tab, QWidget)

    def test_monitor_display_populated_on_init(self, q_app, mock_deps):
        tab = WallpaperTab(db_tab_ref=MagicMock())
        assert len(tab.monitor_display._monitors) == 1
        assert tab.monitor_display._monitors[0].name == "Display1"

    def test_update_background_type(self, q_app, mock_deps):
        tab = WallpaperTab(db_tab_ref=MagicMock())
        tab.show()  # Ensure widgets can be effectively visible

        tab.system_display._update_background_type("Solid Color")
        assert tab.system_display.solid_color_widget.isVisible()

        tab.system_display._update_background_type("Slideshow")
        assert tab.system_display.slideshow_group.isVisible()

    def test_swap_monitors(self, q_app, mock_deps):
        tab = WallpaperTab(db_tab_ref=MagicMock())

        # Setup 2 monitors (mock_deps already provides 1, let's ensure we have 2)
        m1 = MagicMock(name="Monitor1")
        m2 = MagicMock(name="Monitor2")
        tab.system_display.monitors = [m1, m2]

        # Manually populate monitor_widgets
        w1 = MagicMock()
        w1.monitor = m1
        w2 = MagicMock()
        w2.monitor = m2
        tab.system_display.monitor_widgets = {"0": w1, "1": w2}

        # Set initial states
        tab.system_display.monitor_image_paths = {"0": "path1.jpg", "1": "path2.jpg"}
        tab.system_display.monitor_slideshow_queues = {"0": ["path1.jpg"], "1": ["path2.jpg"]}
        tab.system_display.monitor_current_index = {"0": 0, "1": 0}

        # Perform swap
        tab.system_display.swap_monitors("0", "1")

        # Verify swapped states
        assert tab.system_display.monitor_image_paths["0"] == "path2.jpg"
        assert tab.system_display.monitor_image_paths["1"] == "path1.jpg"
        assert tab.system_display.monitor_slideshow_queues["0"] == ["path2.jpg"]
        assert tab.system_display.monitor_slideshow_queues["1"] == ["path1.jpg"]

        # Verify UI updates
        w1.set_image.assert_called_with("path2.jpg", None)
        w2.set_image.assert_called_with("path1.jpg", None)

    def test_cancel_loading_with_daemon_active(self, q_app, mock_deps):
        tab = WallpaperTab(db_tab_ref=MagicMock())
        tab.system_display.countdown_timer = MagicMock()
        tab.system_display.countdown_timer.isActive.return_value = True

        # When daemon is active, cancel_loading should NOT stop the countdown timer
        with patch.object(tab.system_display, "_is_daemon_running_config", return_value=True):
            tab.system_display.cancel_loading()
            tab.system_display.countdown_timer.stop.assert_not_called()

        # When daemon is NOT active, cancel_loading SHOULD stop the countdown timer
        with patch.object(tab.system_display, "_is_daemon_running_config", return_value=False):
            tab.system_display.cancel_loading()
            tab.system_display.countdown_timer.stop.assert_called_once()

    def test_start_daemon_countdown_if_active_calculates_remaining_time(
        self, q_app, mock_deps
    ):
        tab = WallpaperTab(db_tab_ref=MagicMock())

        # Mock daemon running
        with patch.object(tab.system_display, "_is_daemon_running_config", return_value=True):
            # Mock the daemon config JSON reading
            mock_config = {
                "interval_seconds": 300,
                "last_change_timestamp": int(time.time()) - 100,
            }
            with patch("builtins.open", mock_open(read_data=json.dumps(mock_config))):
                tab.system_display._start_daemon_countdown_if_active()
                # 300 interval - 100 elapsed = 200 remaining (give or take a second due to timing)
                assert 195 <= tab.system_display.time_remaining_sec <= 200

    def test_monitor_display_selection_signal_once(self, q_app, mock_deps):
        tab = WallpaperTab(db_tab_ref=MagicMock())
        widget = tab.monitor_display.monitor_widgets.get("0")
        assert widget is not None

        with patch.object(tab.monitor_display, "_select_monitor") as mock_select:
            # Emit clicked
            widget.clicked.emit("0")
            mock_select.assert_called_once_with("0")

    def test_video_duration_caching(self, q_app):
        from gui.src.tabs.core.elements.monitor_display_subtab import (
            _VIDEO_DURATION_CACHE,
            _get_video_duration,
        )

        # Clear cache first
        _VIDEO_DURATION_CACHE.clear()

        video_path = "/tmp/dummy_test_video.mp4"

        with patch("gui.src.tabs.core.elements.monitor_display_subtab.subprocess.run") as mock_run:
            mock_run.return_value.stdout = " 12.34 \n"

            # First call
            dur1 = _get_video_duration(video_path)
            assert dur1 == 12.34
            mock_run.assert_called_once()

            # Second call (should be cached)
            dur2 = _get_video_duration(video_path)
            assert dur2 == 12.34
            assert mock_run.call_count == 1
            assert _VIDEO_DURATION_CACHE[video_path] == 12.34

    def test_clear_monitor_graph(self, q_app, mock_deps):
        tab = WallpaperTab(db_tab_ref=MagicMock())
        from gui.src.tabs.core.elements.graph.data import GraphData, NodeData
        g = GraphData()
        g.nodes["node1"] = NodeData(node_id="node1", file_path="dummy.jpg")
        tab.monitor_display._graphs["0"] = g
        tab.monitor_display._current_monitor_id = "0"

        assert "node1" in tab.monitor_display._graphs["0"].nodes

        from PySide6.QtWidgets import QMessageBox
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes) as mock_q:
            tab.monitor_display.clear_monitor_graph("0")
            mock_q.assert_called_once()

        assert not tab.monitor_display._graphs["0"].nodes

    def test_clear_monitor_graph_from_system_tab(self, q_app, mock_deps):
        tab = WallpaperTab(db_tab_ref=MagicMock())
        tab.system_display._monitor_display_ref = tab.monitor_display

        from gui.src.tabs.core.elements.graph.data import GraphData, NodeData
        g = GraphData()
        g.nodes["node1"] = NodeData(node_id="node1", file_path="dummy.jpg")
        tab.monitor_display._graphs["0"] = g
        tab.monitor_display._current_monitor_id = "0"

        from PySide6.QtWidgets import QMessageBox
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes) as mock_q:
            tab.system_display.clear_monitor_graph("0")
            mock_q.assert_called_once()

        assert not tab.monitor_display._graphs["0"].nodes



# --- SimilarityTab Tests (formerly DeleteTab) ---


class TestSimilarityTab:
    def test_init(self, q_app):
        with patch("gui.src.tabs.core.similarity_tab.DeletionWorker"):
            tab = SimilarityTab()
            assert isinstance(tab, QWidget)


# --- MergeTab Tests ---


class TestMergeTab:
    def test_init(self, q_app):
        tab = MergeTab()
        assert isinstance(tab, QWidget)


# --- ExtractorTab Tests ---


class TestExtractorTab:
    def test_init(self, q_app):
        # Patch to avoid actual multimedia initialization
        with (
            patch("gui.src.tabs.core.extractor_tab.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab.QAudioOutput"),
        ):
            tab = ExtractorTab()
            assert isinstance(tab, QWidget)

    def test_cancel_loading_does_not_stop_player(self, q_app):
        # Patch QMediaPlayer to avoid actual media player initialization and track calls
        with (
            patch(
                "gui.src.tabs.core.extractor_tab.QMediaPlayer"
            ) as mock_player_cls,
            patch("gui.src.tabs.core.extractor_tab.QAudioOutput"),
        ):
            mock_player = MagicMock()
            mock_player_cls.return_value = mock_player

            tab = ExtractorTab()
            tab.media_player = mock_player

            # Call cancel_loading, which is triggered during gallery refreshes
            tab.cancel_loading()

            # Verify stop was NOT called (this ensures the fix for the reported bug)
            mock_player.stop.assert_not_called()

    def test_native_resolution_target_size(self, q_app):
        # If cv2 is globally mocked in conftest.py, configure it
        if hasattr(cv2, "CAP_PROP_FRAME_WIDTH") and not isinstance(
            cv2.CAP_PROP_FRAME_WIDTH, int
        ):
            cv2.CAP_PROP_FRAME_WIDTH = 3
            cv2.CAP_PROP_FRAME_HEIGHT = 4

        with (
            patch("gui.src.tabs.core.extractor_tab.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab.QAudioOutput"),
        ):
            mock_vc = MagicMock()
            mock_vc.get.side_effect = lambda prop: {
                3: 1280,  # cv2.CAP_PROP_FRAME_WIDTH
                4: 720,  # cv2.CAP_PROP_FRAME_HEIGHT
            }.get(prop, 0)

            # Setup a helper context manager to conditionally patch if cv2 is real
            from contextlib import nullcontext

            ctx = (
                patch.object(cv2, "VideoCapture", return_value=mock_vc)
                if not isinstance(cv2.VideoCapture, MagicMock)
                else nullcontext()
            )

            if isinstance(cv2.VideoCapture, MagicMock):
                cv2.VideoCapture.return_value = mock_vc

            with ctx:
                tab = ExtractorTab()
                tab.video_path = __file__
                tab.combo_extract_size.setCurrentText("Native")

                # With no vertical checkbox set
                tab.check_extract_vertical.setChecked(False)
                assert tab._get_target_size() == (1280, 720)

                # With vertical checkbox set -> flip dimensions
                tab.check_extract_vertical.setChecked(True)
                assert tab._get_target_size() == (720, 1280)

    def test_has_extracted_files_regex(self, q_app):
        with (
            patch("gui.src.tabs.core.extractor_tab.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab.QAudioOutput"),
        ):
            tab = ExtractorTab()
            tab._extracted_stems_cache.clear()
            tab._extracted_stems_cache.add("my_cool_video")

            assert tab._has_extracted_files("/path/to/my_cool_video.mp4") is True
            assert tab._has_extracted_files("/path/to/other.mp4") is False

    def test_set_config_quiet_and_force_load(self, q_app, tmp_path):
        with (
            patch("gui.src.tabs.core.extractor_tab.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab.QAudioOutput"),
        ):
            tab = ExtractorTab()
            dummy_video = tmp_path / "dummy_video.mp4"
            dummy_video.write_text("dummy")

            config = {
                "source_directory": str(tmp_path),
                "extraction_directory": str(tmp_path),
                "active_videos_config": {str(dummy_video): {}},
                "video_path": str(dummy_video)
            }

            tab.load_media = MagicMock()

            with patch("gui.src.tabs.core.extractor_tab.QMessageBox") as mock_box:
                tab.set_config(config, quiet=True)
                mock_box.information.assert_not_called()
                tab.load_media.assert_called_with(str(dummy_video), force=True)


class TestListingsTab:
    def test_listings_tab_init(self, q_app):
        from gui.src.tabs.core.listings_tab import ListingsTab

        tab = ListingsTab()
        assert isinstance(tab, QWidget)
        assert tab.tab_widget.count() == 2
        assert tab.tab_widget.tabText(0) == "🎬 Content Listings"
        assert tab.tab_widget.tabText(1) == "👥 Entity Listings"
        assert tab.content_listings is not None
        assert tab.entity_listings is not None

    def test_listing_images_subdirectory(self):
        from pathlib import Path

        from gui.src.tabs.core.elements.common.listings_common import LISTING_IMAGES_DIR

        assert LISTING_IMAGES_DIR is not None
        assert isinstance(LISTING_IMAGES_DIR, Path)
        assert LISTING_IMAGES_DIR.name == "listing-images"

    def test_generate_thumbnail_from_file(self, tmp_path):
        from gui.src.tabs.core.elements.common.listings_common import generate_thumbnail_from_file

        # Create a mock image file
        img_src = tmp_path / "test_image.png"
        img_src.write_bytes(b"dummy image data")

        dest = tmp_path / "dest_image.png"
        success = generate_thumbnail_from_file(str(img_src), str(dest))
        assert success
        assert dest.exists()
        assert dest.read_bytes() == b"dummy image data"

        # Create a non-existent file
        assert not generate_thumbnail_from_file("non_existent_file.pdf", str(dest))

    def test_sync_no_vault(self, q_app, monkeypatch):
        from gui.src.tabs.core.listings_tab import ListingsTab

        tab = ListingsTab()

        warning_called = False

        def mock_warning(parent, title, text):
            nonlocal warning_called
            warning_called = True
            assert "Vault manager is not initialized" in text

        from PySide6.QtWidgets import QMessageBox

        monkeypatch.setattr(QMessageBox, "warning", mock_warning)

        tab.content_listings._synchronize_listings()
        assert warning_called

    def test_sync_with_mock_vault(self, q_app, monkeypatch, tmp_path):
        import json

        import backend.src.constants as udef
        from gui.src.tabs.core.listings_tab import ListingsTab
        from PySide6.QtWidgets import QMessageBox

        # Override ROOT_DIR for tests to prevent modifying actual project files
        monkeypatch.setattr(udef, "ROOT_DIR", tmp_path)

        class MockSecureJsonVault:
            def __init__(self, key, path):
                self.path = path

            def saveData(self, data):
                with open(self.path, "w") as f:
                    f.write(data)

            def loadData(self):
                with open(self.path, "r") as f:
                    return f.read()

        class MockVaultManager:
            def __init__(self):
                self.secret_key = "dummy_key"
                self.raw_password = "dummy_password"
                self.account_name = "dummy_account"
                self.SecureJsonVault = MockSecureJsonVault

        vault_manager = MockVaultManager()
        tab = ListingsTab(vault_manager=vault_manager)

        # Inject entries and stub save/load
        tab.content_listings._entries = [{"id": "1", "name": "Local 1"}]

        # Mock message boxes to avoid blocking
        monkeypatch.setattr(QMessageBox, "information", lambda *args: None)

        with (
            patch("gui.src.tabs.core.elements.common.listings_common.base.fetch_all_listings_secure", return_value=[]),
            patch("gui.src.tabs.core.elements.common.listings_common.base.delete_listing_secure"),
            patch("gui.src.tabs.core.elements.common.listings_common.base.insert_listing_secure"),
        ):
            # 1. Update Backup should generate the encrypted file since it doesn't exist
            tab.content_listings._update_encrypted_backup()
        tab.content_listings._backup_worker.wait()  # Wait for QThread to finish!

        enc_file = tmp_path / "assets" / "secrets" / "listings.json.enc"
        assert enc_file.exists()

        # Load encrypted data
        with open(enc_file, "r") as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["id"] == "1"

        # 2. Add another remote entry directly to mock a remote update
        remote_data = [{"id": "1", "name": "Local 1"}, {"id": "2", "name": "Remote 2"}]
        with open(enc_file, "w") as f:
            json.dump(remote_data, f)

        # 3. Synchronize - should load from backup and merge
        with (
            patch("gui.src.tabs.core.elements.common.listings_common.base.fetch_all_listings_secure", return_value=[]),
            patch("gui.src.tabs.core.elements.common.listings_common.base.delete_listing_secure"),
            patch("gui.src.tabs.core.elements.common.listings_common.base.insert_listing_secure"),
        ):
            tab.content_listings._synchronize_listings()
            tab.content_listings._sync_worker.wait()  # Wait for QThread to finish!
            q_app.processEvents()
        assert len(tab.content_listings._entries) == 2
