import json
import time
from unittest.mock import MagicMock, mock_open, patch

import cv2
import pytest
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from gui.src.tabs.core.convert_tab import ConvertTab
from gui.src.tabs.core.extractor_tab import ExtractorTab
from gui.src.tabs.core.merge_tab import MergeTab
from gui.src.tabs.core.similarity_tab import SimilarityTab
from gui.src.tabs.core.wallpaper_tab import WallpaperTab

pytestmark = pytest.mark.gui


# --- ConvertTab Tests ---
class TestConvertTab:
    @pytest.fixture
    def mock_worker(self):
        with patch(
            "gui.src.tabs.core.format_subtab._conversion_worker.ConversionWorker"
        ) as mock:
            yield mock

    def test_init(self, q_app):
        tab = ConvertTab()
        assert isinstance(tab, QWidget)
        assert tab.format_subtab.input_path is not None

    def test_start_conversion_no_files(self, q_app, mock_worker):
        # Mock message box to avoid blocking
        with patch(
            "gui.src.tabs.core.format_subtab._conversion_worker.QMessageBox"
        ) as mock_mb:
            tab = ConvertTab()
            tab.format_subtab.collect_paths = MagicMock(return_value=[])

            tab.format_subtab.start_conversion_worker()

            mock_worker.assert_not_called()
            mock_mb.warning.assert_called()

    def test_start_conversion_success(self, q_app, mock_worker):
        with patch(
            "gui.src.tabs.core.format_subtab._conversion_worker.os.path.isdir",
            return_value=True,
        ):
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
            patch(
                "gui.src.tabs.core.wallpaper_tab.system_display_subtab._wallpaper_worker.WallpaperWorker"
            ),
            patch(
                "gui.src.tabs.core.wallpaper_tab.common.wallpaper_common_base._monitor_layout.get_monitors",
                return_value=[mock_monitor],
            ),
        ):
            yield

    def test_init(self, q_app, mock_deps):
        # WallpaperTab takes a db_tab_ref arg
        tab = WallpaperTab(db_tab_ref=MagicMock())
        assert isinstance(tab, QWidget)
        assert tab.monitor_display._btn_delete.objectName() == "btn_danger"
        assert tab.monitor_display._btn_inapp_slideshow.objectName() == "btn_success"
        assert tab.monitor_display._btn_daemon_slideshow.objectName() == "btn_success"

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

    def test_set_active_queue_wallpaper_keeps_slideshow_ui_enabled(
        self, q_app, mock_deps, tmp_path
    ):
        class WorkerSignals(QObject):
            status_update = Signal(str)
            work_finished = Signal(bool, str)

        class FakeWallpaperWorker:
            instance = None

            def __init__(self, *args, **kwargs):
                self.signals = WorkerSignals()
                self.stopped = False
                FakeWallpaperWorker.instance = self

            def stop(self):
                self.stopped = True

        first = tmp_path / "first.png"
        second = tmp_path / "second.png"
        first.write_bytes(b"first")
        second.write_bytes(b"second")

        with (
            patch(
                "gui.src.tabs.core.wallpaper_tab.system_display_subtab._wallpaper_worker.WallpaperWorker",
                FakeWallpaperWorker,
            ),
            patch(
                "gui.src.tabs.core.wallpaper_tab.system_display_subtab._wallpaper_worker.QThreadPool"
            ),
        ):
            tab = WallpaperTab(db_tab_ref=MagicMock())
            system = tab.system_display
            system.background_type = "Slideshow"
            system.monitor_image_paths["0"] = str(first)
            system.monitor_slideshow_queues["0"] = [str(first), str(second)]
            system.monitor_current_index["0"] = 0
            system.set_wallpaper_btn.setText("Slideshow Running (Stop)")
            system.slideshow_timer = QTimer(system)
            system.slideshow_timer.start(60_000)

            tab.monitor_display._set_specific_wallpaper("0", str(second), 1)

            assert system.monitor_image_paths["0"] == str(second)
            assert system.monitor_current_index["0"] == 1
            for panel in (system, tab.monitor_display):
                assert panel.gallery_scroll_area.isEnabled()
                assert all(
                    widget.isEnabled() for widget in panel.monitor_widgets.values()
                )
            assert FakeWallpaperWorker.instance is not None

            FakeWallpaperWorker.instance.signals.work_finished.emit(
                True, "Wallpaper applied successfully."
            )
            q_app.processEvents()

            assert system.current_wallpaper_worker is None
            for panel in (system, tab.monitor_display):
                assert panel.gallery_scroll_area.isEnabled()
                assert all(
                    widget.isEnabled() for widget in panel.monitor_widgets.values()
                )
            assert system.set_wallpaper_btn.text() == "Slideshow Running (Stop)"
            tab.close()

    def test_locked_worker_completion_restores_ui_during_slideshow(
        self, q_app, mock_deps, tmp_path
    ):
        class WorkerSignals(QObject):
            status_update = Signal(str)
            work_finished = Signal(bool, str)

        class FakeWallpaperWorker:
            instance = None

            def __init__(self, *args, **kwargs):
                self.signals = WorkerSignals()
                FakeWallpaperWorker.instance = self

            def stop(self):
                pass

        image = tmp_path / "wallpaper.png"
        image.write_bytes(b"wallpaper")

        with (
            patch(
                "gui.src.tabs.core.wallpaper_tab.system_display_subtab._wallpaper_worker.WallpaperWorker",
                FakeWallpaperWorker,
            ),
            patch(
                "gui.src.tabs.core.wallpaper_tab.system_display_subtab._wallpaper_worker.QThreadPool"
            ),
        ):
            tab = WallpaperTab(db_tab_ref=MagicMock())
            system = tab.system_display
            system.background_type = "Slideshow"
            system.monitor_image_paths["0"] = str(image)
            system.monitor_slideshow_queues["0"] = [str(image)]
            system.slideshow_timer = QTimer(system)
            system.slideshow_timer.start(60_000)

            system.run_wallpaper_worker(slideshow_mode=False)

            assert not system.gallery_scroll_area.isEnabled()
            assert all(
                not widget.isEnabled() for widget in system.monitor_widgets.values()
            )

            assert FakeWallpaperWorker.instance is not None
            FakeWallpaperWorker.instance.signals.work_finished.emit(
                True, "Wallpaper applied successfully."
            )
            q_app.processEvents()

            assert system.gallery_scroll_area.isEnabled()
            assert all(widget.isEnabled() for widget in system.monitor_widgets.values())
            assert system.set_wallpaper_btn.text() == "Slideshow Running (Stop)"
            tab.close()

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
        # pyrefly: ignore [bad-argument-type]
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
            # pyrefly: ignore [bad-argument-type]
            tab.system_display.cancel_loading()
            tab.system_display.countdown_timer.stop.assert_not_called()

        # When daemon is NOT active, cancel_loading SHOULD stop the countdown timer
        with patch.object(tab.system_display, "_is_daemon_running_config", return_value=False):
            # pyrefly: ignore [bad-argument-type]
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
                # pyrefly: ignore [bad-argument-type]
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
        from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab import (
            _VIDEO_DURATION_CACHE,
            _get_video_duration,
        )

        # Clear cache first
        _VIDEO_DURATION_CACHE.clear()

        video_path = "/tmp/dummy_test_video.mp4"

        with patch(
            "gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._traversal.subprocess.run"
        ) as mock_run:
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
        from gui.src.tabs.core.wallpaper_tab.graph.data_schema import GraphData, NodeData
        g = GraphData()
        g.nodes["node1"] = NodeData(node_id="node1", file_path="dummy.jpg")
        tab.monitor_display._graphs["0"] = g
        tab.monitor_display._current_monitor_id = "0"

        assert "node1" in tab.monitor_display._graphs["0"].nodes

        from PySide6.QtWidgets import QMessageBox
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes) as mock_q:
            # pyrefly: ignore [bad-argument-type]
            tab.monitor_display.clear_monitor_graph("0")
            mock_q.assert_called_once()

        assert not tab.monitor_display._graphs["0"].nodes

    def test_clear_monitor_graph_from_system_tab(self, q_app, mock_deps):
        tab = WallpaperTab(db_tab_ref=MagicMock())
        tab.system_display._monitor_display_ref = tab.monitor_display

        from gui.src.tabs.core.wallpaper_tab.graph.data_schema import GraphData, NodeData
        g = GraphData()
        g.nodes["node1"] = NodeData(node_id="node1", file_path="dummy.jpg")
        tab.monitor_display._graphs["0"] = g
        tab.monitor_display._current_monitor_id = "0"

        from PySide6.QtWidgets import QMessageBox
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes) as mock_q:
            # pyrefly: ignore [bad-argument-type]
            tab.system_display.clear_monitor_graph("0")
            mock_q.assert_called_once()

        assert not tab.monitor_display._graphs["0"].nodes



# --- SimilarityTab Tests (formerly DeleteTab) ---


class TestSimilarityTab:
    def test_init(self, q_app):
        with patch("gui.src.tabs.core.similarity_tab._deletion.DeletionWorker"):
            tab = SimilarityTab()
            assert isinstance(tab, QWidget)


# --- MergeTab Tests ---


class TestMergeTab:
    def test_init(self, q_app):
        tab = MergeTab()
        assert isinstance(tab, QWidget)
        assert tab.run_button.objectName() == "btn_success"
        assert tab.cancel_button.objectName() == "btn_danger"

    def test_event_filter_blocks_ctrl_wheel(self, q_app):
        from PySide6.QtCore import QPoint, QPointF, Qt
        from PySide6.QtGui import QWheelEvent

        tab = MergeTab()
        # Simulated Ctrl + Wheel event
        ctrl_wheel_event = QWheelEvent(
            QPointF(100, 100),
            QPointF(100, 100),
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.ControlModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False
        )

        # eventFilter should return True to block scrolling
        blocked = tab.eventFilter(tab.page_scroll, ctrl_wheel_event)
        assert blocked is True

        # Simulated standard Wheel event (No modifiers)
        standard_wheel_event = QWheelEvent(
            QPointF(100, 100),
            QPointF(100, 100),
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False
        )

        # eventFilter should return False to allow normal scrolling
        blocked_standard = tab.eventFilter(tab.page_scroll, standard_wheel_event)
        assert blocked_standard is False


# --- ExtractorTab Tests ---


class TestExtractorTab:
    def test_skip_runtime_seeks_forward_and_clamps_at_video_end(self, q_app):
        with (
            patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
        ):
            tab = ExtractorTab()
            tab.duration_ms = 10_000
            tab.slider.setRange(0, 10_000)
            tab.slider.setValue(8_000)
            tab.skip_minutes_spinbox.setValue(0)
            tab.skip_seconds_spinbox.setValue(5)
            tab.skip_microseconds_spinbox.setValue(0)
            tab._seek_to = MagicMock()

            tab.skip_video_runtime()

            tab._seek_to.assert_called_once_with(10_000)

    def test_skip_runtime_combines_minutes_seconds_and_microseconds(self, q_app):
        with (
            patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
        ):
            tab = ExtractorTab()
            tab.duration_ms = 100_000
            tab.slider.setRange(0, 100_000)
            tab.slider.setValue(1_000)
            tab.skip_minutes_spinbox.setValue(1)
            tab.skip_seconds_spinbox.setValue(2)
            tab.skip_microseconds_spinbox.setValue(500_000)
            tab._seek_to = MagicMock()

            tab.skip_video_runtime()

            tab._seek_to.assert_called_once_with(63_500)

    def test_init(self, q_app):
        # Patch to avoid actual multimedia initialization
        with (
            patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
        ):
            tab = ExtractorTab()
            assert isinstance(tab, QWidget)

    def test_cancel_loading_does_not_stop_player(self, q_app):
        # Patch QMediaPlayer to avoid actual media player initialization and track calls
        with (
            patch(
                "gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"
            ) as mock_player_cls,
            patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
        ):
            mock_player = MagicMock()
            mock_player_cls.return_value = mock_player

            tab = ExtractorTab()
            tab._media_player = mock_player

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
            patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
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
            patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
        ):
            tab = ExtractorTab()
            tab._extracted_stems_cache.clear()
            tab._extracted_stems_cache.add("my_cool_video")

            assert tab._has_extracted_files("/path/to/my_cool_video.mp4") is True
            assert tab._has_extracted_files("/path/to/other.mp4") is False

    def test_browse_output_directory_does_not_change_source(self, q_app, tmp_path):
        source_dir = tmp_path / "source"
        output_dir = tmp_path / "output"
        source_dir.mkdir()
        output_dir.mkdir()
        (source_dir / "video.mp4").touch()

        with (
            patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
            patch(
                "gui.src.tabs.core.extractor_tab._video_session_history.QFileDialog.getExistingDirectory",
                return_value=str(output_dir),
            ),
        ):
            tab = ExtractorTab()
            tab.scan_directory(str(source_dir))

            tab.browse_extraction_directory()

            assert tab.line_edit_dir.text() == str(source_dir)
            assert tab.line_edit_extract_dir.text() == str(output_dir)

    def test_scan_directory_ignores_output_directory(self, q_app, tmp_path):
        source_dir = tmp_path / "source"
        output_dir = tmp_path / "output"
        source_dir.mkdir()
        output_dir.mkdir()
        (source_dir / "video.mp4").touch()
        (output_dir / "clip.mp4").touch()

        with (
            patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
        ):
            tab = ExtractorTab()
            tab.scan_directory(str(source_dir))
            tab.extraction_dir = output_dir

            tab.scan_directory(str(output_dir))

            assert tab.line_edit_dir.text() == str(source_dir)
            assert str(source_dir / "video.mp4") in tab.source_path_to_widget
            assert str(output_dir / "clip.mp4") not in tab.source_path_to_widget

    def test_snapshot_save_does_not_change_source_directory(
        self, q_app, tmp_path, monkeypatch
    ):
        source_dir = tmp_path / "source"
        output_dir = tmp_path / "output"
        source_dir.mkdir()
        output_dir.mkdir()
        video_path = source_dir / "clip.mp4"
        video_path.touch()

        with (
            patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
        ):
            tab = ExtractorTab()
            tab.extraction_dir = output_dir
            tab.line_edit_extract_dir.setText(str(output_dir))
            tab.scan_directory(str(source_dir))
            tab.video_path = str(video_path)
            tab.start_time_ms = 1000
            tab.end_time_ms = 2000
            tab.extraction_queue_enabled = False

            mock_player = MagicMock()
            mock_player.playbackState.return_value = 0
            mock_player.position.return_value = 1000
            tab._media_player = mock_player

            from PySide6.QtGui import QImage

            mock_image = QImage(16, 16, QImage.Format.Format_RGB32)
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
            mock_dlg.selected_image = mock_image
            mock_dlg.selected_frame_idx = 24
            mock_dlg.fps = 24.0

            monkeypatch.setattr(
                "gui.src.tabs.core.extractor_tab._extraction_execution.FrameSelectionDialog",
                lambda *args, **kwargs: mock_dlg,
            )
            monkeypatch.setattr(
                "gui.src.tabs.core.extractor_tab._extraction_execution.QMessageBox.critical",
                lambda *args, **kwargs: None,
            )
            monkeypatch.setattr(tab, "_get_target_size", lambda: None)

            tab.extract_single_frame()

            assert tab.line_edit_dir.text() == str(source_dir)
            saved_path = output_dir / "clip_snap_1000ms.png"
            assert saved_path.exists()

    def test_set_config_quiet_and_force_load(self, q_app, tmp_path):
        with (
            patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
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

            with patch("gui.src.tabs.core.extractor_tab._config_methods.QMessageBox") as mock_box:
                tab.set_config(config, quiet=True)
                mock_box.information.assert_not_called()
                tab.load_media.assert_called_with(str(dummy_video), force=True, defer_player=True)


class TestListingsTab:
    @pytest.fixture(autouse=True)
    def close_listings_tabs(self, q_app):
        """Keep ListingsTab instances from leaking across sibling tests."""
        from gui.src.tabs.database.listings_tab import ListingsTab

        yield
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, ListingsTab):
                widget.close()
                widget.deleteLater()
        for _ in range(5):
            QApplication.processEvents()

    def test_listings_tab_init(self, q_app):
        from gui.src.tabs.database.listings_tab import ListingsTab

        tab = ListingsTab()
        assert isinstance(tab, QWidget)
        assert tab.tab_widget.count() == 2
        assert tab.tab_widget.tabText(0) == "🎬 Series Listings"
        assert tab.tab_widget.tabText(1) == "👥 Entity Listings"
        assert tab.series_listings is not None
        assert tab.entity_listings is not None

    def test_listing_images_subdirectory(self):
        from pathlib import Path

        from gui.src.elements.database.common.listings_common import LISTING_IMAGES_DIR

        assert LISTING_IMAGES_DIR is not None
        assert isinstance(LISTING_IMAGES_DIR, Path)
        assert LISTING_IMAGES_DIR.name == "listing-images"

    def test_generate_thumbnail_from_file(self, tmp_path):
        from gui.src.elements.database.common.listings_common import generate_thumbnail_from_file

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
        from gui.src.tabs.database.listings_tab import ListingsTab

        tab = ListingsTab()

        warning_called = False

        def mock_warning(parent, title, text):
            nonlocal warning_called
            warning_called = True
            assert "Vault manager is not initialized" in text

        from PySide6.QtWidgets import QMessageBox

        monkeypatch.setattr(QMessageBox, "warning", mock_warning)

        tab.series_listings._synchronize_listings()
        assert warning_called

    def test_sync_with_mock_vault(self, q_app, monkeypatch, tmp_path):
        import json

        import backend.src.constants as udef
        from PySide6.QtWidgets import QMessageBox

        from gui.src.tabs.database.listings_tab import ListingsTab

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

            def shutdown(self):
                pass

        # Mock message boxes to avoid blocking -- QMessageBox.critical/warning
        # too, not just information: get_library_db() calls critical() on a
        # real (failed) connection attempt, which blocks forever under
        # headless/offscreen test mode with nothing to dismiss it.
        monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
        monkeypatch.setattr(QMessageBox, "critical", lambda *args: None)
        monkeypatch.setattr(QMessageBox, "warning", lambda *args: None)

        # get_library_db() is patched for the whole test, not just around
        # _synchronize_listings(): ListingsTab construction itself can
        # trigger a real (and here undesired) library.db connection attempt
        # via the series/entity listings subtabs' initial load.
        with (
            patch(
                "gui.src.tabs.database.series_listings_subtab._backup_sync.get_library_db",
                return_value=MagicMock(),
            ),
            patch(
                "gui.src.helpers.web.sync_backup_worker.MediaRepo"
            ) as mock_media_repo_cls,
        ):
            vault_manager = MockVaultManager()
            tab = ListingsTab(vault_manager=vault_manager)

            # Inject entries and stub save/load
            tab.series_listings._entries = [{"id": "1", "name": "Local 1"}]

            # 1. Update Backup should generate the encrypted file since it
            # doesn't exist -- writes self._entries straight to the
            # encrypted JSON file, no DB touch (see
            # _backup_sync.py:_update_encrypted_backup).
            tab.series_listings._update_encrypted_backup()
            tab.series_listings._backup_worker.wait()  # Wait for QThread to finish!

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

            # 3. Synchronize - should load from backup and merge, persisting
            # via MediaRepo.save_media (unified DB, DB.5) rather than the
            # retired base.*_listing_secure functions this test used to
            # (incorrectly) mock -- see issue #175.
            tab.series_listings._synchronize_listings()
            tab.series_listings._sync_worker.wait()  # Wait for QThread to finish!
            q_app.processEvents()
        assert mock_media_repo_cls.return_value.save_media.call_count == 2
        assert len(tab.series_listings._entries) == 2
