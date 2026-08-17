"""Faithful repro: GIF must land in extraction_dir on disk AND in gallery.
Uses a real directory (not tmp) so path semantics match the real app."""
import os
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


class TestGifDiskVsGallery:
    def _make_tab(self, tmp_path, out_dir):
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
        tab.extraction_dir = out_dir
        tab.line_edit_extract_dir.setText(str(out_dir))
        out_dir.mkdir(parents=True, exist_ok=True)
        return tab

    def _wait(self, tab, attr, timeout=20):
        from PySide6.QtWidgets import QApplication

        deadline = time.time() + timeout
        while getattr(tab, attr) is not None and time.time() < deadline:
            QApplication.processEvents()
            time.sleep(0.05)

    def test_queue_disabled_gif_on_disk_and_gallery(self, q_app, tmp_path):
        video_path = _make_real_video(tmp_path)
        out_dir = tmp_path / "real_out"
        tab = self._make_tab(tmp_path, out_dir)
        tab.video_path = str(video_path)
        tab.extraction_queue_enabled = False
        tab.start_time_ms = 0
        tab.end_time_ms = 3000
        tab.spin_gif_fps.setValue(24)
        tab.combo_engine.setCurrentText("FFmpeg")
        tab.cuts_ms = []

        with patch(
            "gui.src.elements.core.extractor_tab._extraction_workers.QMessageBox.information"
        ):
            tab.extract_range_as_gif()
            self._wait(tab, "active_extraction_worker")

        expected = out_dir / "realsource_0ms_3000ms.gif"
        print("disk entries:", os.listdir(out_dir))
        print("expected:", expected)
        print("master_image_paths:", tab.master_image_paths)
        assert expected.exists(), f"gif must be on disk in {out_dir}"
        assert str(expected) in tab.master_image_paths

    def test_single_item_queue_gif_on_disk_and_gallery(self, q_app, tmp_path):
        video_path = _make_real_video(tmp_path)
        out_dir = tmp_path / "real_out2"
        tab = self._make_tab(tmp_path, out_dir)
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
            self._wait(tab, "active_queue_worker")

        expected = out_dir / "realsource_0ms_3000ms.gif"
        print("disk entries:", os.listdir(out_dir))
        print("expected:", expected)
        print("master_image_paths:", tab.master_image_paths)
        print("extraction_metadata keys:", list(tab.extraction_metadata.keys()))
        assert expected.exists(), f"gif must be on disk in {out_dir}"
        assert str(expected) in tab.master_image_paths
