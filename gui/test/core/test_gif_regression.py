"""Regression: GIF must be created on disk both when the extraction queue is
disabled and when exactly 1 item is queued (previously the file landed in the
default extraction dir while the user's configured output dir stayed empty --
see startup-prefs fix)."""

import subprocess
import time
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.gui


def _make_real_video(tmp_path):
    video_path = tmp_path / "realsource.mp4"
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", "testsrc=duration=3:size=320x240:rate=24",
         "-pix_fmt", "yuv420p", str(video_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if r.returncode != 0:
        pytest.skip("ffmpeg unavailable")
    return video_path


def _make_tab(tmp_path):
    from gui.src.elements.core.extractor_tab import ExtractorTab

    with (
        patch("gui.src.elements.core.extractor_tab._media_player.QMediaPlayer"),
        patch("gui.src.elements.core.extractor_tab._media_player.QAudioOutput"),
    ):
        tab = ExtractorTab()
    mock_player = MagicMock()
    mock_player.position.return_value = 0
    mock_player.duration.return_value = 0
    tab._media_player = mock_player
    tab.extraction_dir = tmp_path / "out"
    tab.extraction_dir.mkdir(exist_ok=True)
    return tab


class TestGifRegression:
    def test_non_queue_gif_creates_file(self, q_app, tmp_path):
        """Queue DISABLED: extract_range_as_gif -> GifCreationWorker must
        create the gif on disk."""
        from PySide6.QtWidgets import QApplication

        video_path = _make_real_video(tmp_path)
        tab = _make_tab(tmp_path)
        tab.video_path = str(video_path)
        tab.extraction_queue_enabled = False
        tab.start_time_ms = 0
        tab.end_time_ms = 3000
        tab.spin_gif_fps.setValue(24)
        tab.combo_engine.setCurrentText("FFmpeg")
        tab.cuts_ms = []

        # Monkeypatch the modal success dialog so the test doesn't block
        with patch(
            "gui.src.elements.core.extractor_tab._extraction_workers.QMessageBox.information"
        ):
            tab.extract_range_as_gif()
            deadline = time.time() + 20
            while tab.active_extraction_worker is not None and time.time() < deadline:
                QApplication.processEvents()
                time.sleep(0.05)

        out_gif = tab.extraction_dir / "realsource_0ms_3000ms.gif"
        assert out_gif.exists(), "non-queue gif must be created on disk"

    def test_single_item_queue_gif_creates_file(self, q_app, tmp_path):
        """Queue ENABLED with exactly 1 item: process_queue must create it."""
        from PySide6.QtWidgets import QApplication

        video_path = _make_real_video(tmp_path)
        tab = _make_tab(tmp_path)
        tab.video_path = str(video_path)
        tab.extraction_queue_enabled = True
        tab.start_time_ms = 0
        tab.end_time_ms = 3000
        tab.spin_gif_fps.setValue(24)
        tab.combo_engine.setCurrentText("FFmpeg")
        tab.cuts_ms = []

        with patch(
            "gui.src.elements.core.extractor_tab._queue_management.QMessageBox.information"
        ):
            tab._run_gif_extraction(0, 3000)
            assert len(tab.extraction_queue) == 1
            tab.process_queue()
            deadline = time.time() + 20
            while tab.active_queue_worker is not None and time.time() < deadline:
                QApplication.processEvents()
                time.sleep(0.05)

        out_gif = tab.extraction_dir / "realsource_0ms_3000ms.gif"
        assert out_gif.exists(), "single-item queue gif must be created on disk"
