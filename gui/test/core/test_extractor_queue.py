"""Reproduction + regression tests for the extraction queue (#queue-bugs).

Symptoms under test:
1. A GIF added to the queue, when processed, must produce a file on disk.
2. Completed queue items must be removed from the queue list promptly
   (per-item), not only after the whole queue finishes.
3. Completed queue extractions must be recorded in recent extractions
   (extraction history) like non-queue extractions.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.gui


@pytest.fixture(autouse=True)
def _isolate_extraction_history(tmp_path, monkeypatch):
    """The conftest's mock_image_toolkit_paths patches backend.src.constants,
    but _video_session_history binds IMAGE_TOOLKIT_DIR at import time, so the
    extraction-history JSON still points at the real home dir. Route it to the
    per-test tmp dir to keep queue recording tests isolated."""
    import gui.src.elements.core.extractor_tab._video_session_history as vsh

    monkeypatch.setattr(vsh, "IMAGE_TOOLKIT_DIR", tmp_path)


class TestExtractorTabQueue:
    def _make_tab(self, tmp_path):
        from gui.src.elements.core.extractor_tab import ExtractorTab

        video_path = tmp_path / "episode.mp4"
        video_path.write_text("dummy")
        with (
            patch("gui.src.elements.core.extractor_tab._media_player.QMediaPlayer"),
            patch("gui.src.elements.core.extractor_tab._media_player.QAudioOutput"),
        ):
            tab = ExtractorTab()
        mock_player = MagicMock()
        mock_player.position.return_value = 0
        mock_player.duration.return_value = 0
        tab._media_player = mock_player
        tab.video_path = str(video_path)
        tab.extraction_dir = tmp_path / "out"
        tab.extraction_dir.mkdir(exist_ok=True)
        return tab, video_path

    def test_gif_queue_item_config_has_output_dir(self, q_app, tmp_path):
        """The queue config for a GIF must include every key the worker
        reads, including output_dir (worker writes into it)."""
        tab, video_path = self._make_tab(tmp_path)
        tab.extraction_queue_enabled = True
        tab.start_time_ms = 0
        tab.end_time_ms = 3000
        tab.spin_gif_fps.setValue(24)
        tab.combo_engine.setCurrentText("FFmpeg")
        tab.cuts_ms = []

        tab._run_gif_extraction(0, 3000)

        assert len(tab.extraction_queue) == 1
        cfg = tab.extraction_queue[0]
        assert cfg["type"] == "gif"
        assert cfg["video_path"] == str(video_path)
        assert cfg["output_dir"] == str(tab.extraction_dir)
        assert cfg["start_ms"] == 0
        assert cfg["end_ms"] == 3000

    def test_queue_finished_records_recent_extractions(self, q_app, tmp_path):
        """_on_queue_processing_finished must record completed extractions
        into extraction history (recent extractions), same as the non-queue
        paths do."""
        tab, video_path = self._make_tab(tmp_path)
        out_file = tab.extraction_dir / "test_0ms_3000ms.gif"
        out_file.write_text("gif")

        tab._on_queue_processing_finished(
            [{"status": "success", "output_path": str(out_file)}]
        )

        assert str(out_file) in tab.extraction_metadata
        assert any(
            run.get("timestamp") is not None for run in tab.recent_runs
        ), "queue completion should create a recent-extraction entry"

    def test_queue_finished_clears_queue_and_loads_gallery(self, q_app, tmp_path):
        tab, video_path = self._make_tab(tmp_path)
        out_file = tab.extraction_dir / "test_0ms_3000ms.gif"
        out_file.write_text("gif")
        tab.extraction_queue.append(
            {
                "type": "gif",
                "video_path": str(video_path),
                "start_ms": 0,
                "end_ms": 3000,
                "output_dir": str(tab.extraction_dir),
            }
        )
        tab._update_queue_ui()
        assert tab.queue_list.count() == 1

        tab._on_queue_processing_finished(
            [{"status": "success", "output_path": str(out_file)}]
        )

        assert tab.extraction_queue == []
        assert tab.queue_list.count() == 0
        assert str(out_file) in tab.master_image_paths

    def test_real_gif_through_worker_produces_file(self, q_app, tmp_path):
        """TRUE end-to-end: build the queue config exactly as the tab does,
        run the real sequential worker, and the gif must exist + be recorded.
        Uses a real tiny mp4 (ffmpeg) so the worker's ffmpeg call succeeds."""
        import subprocess

        from gui.src.helpers.core.queue_execution_worker import (
            QueueExecutionWorker,
        )

        video_path = tmp_path / "realsource.mp4"
        r = subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "testsrc=duration=3:size=320x240:rate=24",
                "-pix_fmt", "yuv420p", str(video_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if r.returncode != 0:
            pytest.skip("ffmpeg unavailable in test env")

        tab, _ = self._make_tab(tmp_path)
        tab.video_path = str(video_path)  # real video, not the dummy
        tab.extraction_queue_enabled = True
        tab.start_time_ms = 0
        tab.end_time_ms = 3000
        tab.spin_gif_fps.setValue(24)
        tab.combo_engine.setCurrentText("FFmpeg")
        tab.cuts_ms = []

        tab._run_gif_extraction(0, 3000)
        assert len(tab.extraction_queue) == 1

        worker = QueueExecutionWorker(list(tab.extraction_queue), parallel=False)
        worker.signals.finished.connect(tab._on_queue_processing_finished)
        worker.run()

        out_gif = tab.extraction_dir / "realsource_0ms_3000ms.gif"
        assert out_gif.exists(), "gif file must be produced from queued item"
        assert tab.extraction_queue == []
        assert str(out_gif) in tab.master_image_paths
        assert str(out_gif) in tab.extraction_metadata

    def test_process_queue_via_threadpool_full_flow(self, q_app, tmp_path):
        """Drive the real process_queue() button path: queue a GIF, click
        process, wait for the async worker, verify file + history + queue."""
        import subprocess
        import time

        video_path = tmp_path / "realsource.mp4"
        r = subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "testsrc=duration=3:size=320x240:rate=24",
                "-pix_fmt", "yuv420p", str(video_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if r.returncode != 0:
            pytest.skip("ffmpeg unavailable in test env")

        from PySide6.QtWidgets import QApplication

        tab, _ = self._make_tab(tmp_path)
        tab.video_path = str(video_path)
        tab.extraction_queue_enabled = True
        tab.start_time_ms = 0
        tab.end_time_ms = 3000
        tab.spin_gif_fps.setValue(24)
        tab.combo_engine.setCurrentText("FFmpeg")
        tab.cuts_ms = []

        tab._run_gif_extraction(0, 3000)
        tab.process_queue()

        # Wait for the async worker (finished handler clears active_queue_worker)
        deadline = time.time() + 20
        while tab.active_queue_worker is not None and time.time() < deadline:
            QApplication.processEvents()
            time.sleep(0.05)

        out_gif = tab.extraction_dir / "realsource_0ms_3000ms.gif"
        assert tab.active_queue_worker is None
        assert out_gif.exists(), "gif must be produced via the real queue flow"
        assert tab.extraction_queue == []
        assert str(out_gif) in tab.master_image_paths
        assert str(out_gif) in tab.gallery_image_paths
        # The gif must also be recorded into recent extractions, like the
        # non-queue extraction paths do (symptom: queue results missing).
        assert str(out_gif) in tab.extraction_metadata

    def test_item_completed_records_and_removes_per_item(self, q_app, tmp_path):
        """The per-item signal (previously never connected) must record each
        successful extraction AND remove that item from the queue list."""
        tab, video_path = self._make_tab(tmp_path)
        f1 = tab.extraction_dir / "a.gif"
        f2 = tab.extraction_dir / "b.gif"
        f1.write_text("gif")
        f2.write_text("gif")
        tab.extraction_queue.append(
            {"type": "gif", "video_path": str(video_path), "start_ms": 0,
             "end_ms": 1000, "output_dir": str(tab.extraction_dir),
             "use_ffmpeg": True, "fps": 24}
        )
        tab.extraction_queue.append(
            {"type": "gif", "video_path": str(video_path), "start_ms": 1000,
             "end_ms": 2000, "output_dir": str(tab.extraction_dir),
             "use_ffmpeg": True, "fps": 24}
        )
        tab._update_queue_ui()
        assert tab.queue_list.count() == 2

        item1 = tab.extraction_queue[0]
        item2 = tab.extraction_queue[1]
        tab._on_queue_item_completed(
            0, {"status": "success", "output_path": str(f1)}, item1
        )

        assert tab.queue_list.count() == 1, "completed item must leave the queue"
        assert str(f1) in tab.extraction_metadata
        assert str(f1) in tab.master_image_paths

        tab._on_queue_item_completed(
            0, {"status": "success", "output_path": str(f2)}, item2
        )

        assert tab.queue_list.count() == 0
        assert str(f2) in tab.extraction_metadata

    def test_queue_item_error_result_not_recorded(self, q_app, tmp_path):
        tab, video_path = self._make_tab(tmp_path)
        tab.extraction_queue.append(
            {"type": "gif", "video_path": str(video_path), "start_ms": 0,
             "end_ms": 1000, "output_dir": str(tab.extraction_dir)}
        )
        tab._update_queue_ui()
        tab._on_queue_item_completed(0, {"status": "error", "message": "boom"}, {})

        assert tab.queue_list.count() == 1, "failed items must stay for review"
        assert tab.extraction_metadata == {}

    def test_open_ended_gif_end_ms_neg1_succeeds(self, q_app, tmp_path):
        """end_ms=-1 (open-ended, rendered as 'End' in the queue list) must
        produce a gif instead of failing with a negative -t duration."""
        import subprocess

        from gui.src.helpers.core.queue_execution_worker import (
            run_extraction_in_process,
        )

        video_path = tmp_path / "realsource.mp4"
        r = subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "testsrc=duration=3:size=320x240:rate=24",
                "-pix_fmt", "yuv420p", str(video_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if r.returncode != 0:
            pytest.skip("ffmpeg unavailable in test env")

        outdir = tmp_path / "out"
        outdir.mkdir(exist_ok=True)
        cfg = {"type": "gif", "video_path": str(video_path), "start_ms": 0,
               "end_ms": -1, "output_dir": str(outdir),
               "target_resolution": (320, 240), "cuts_ms": [], "frame_interval": 1,
               "smart_extract": False, "smart_method": "", "fps": 24,
               "mute_audio": False, "use_ffmpeg": True, "speed": 1.0}

        res = run_extraction_in_process(cfg)

        assert res.get("status") == "success", res
        assert os.path.exists(res.get("output_path", ""))

    def test_parallel_worker_emits_item_with_original_config(self, q_app, tmp_path):
        """The worker's item_completed must carry the original queue config so
        the tab can remove entries by identity (parallel completes out of
        order; index alignment is not reliable)."""
        import subprocess

        from gui.src.helpers.core.queue_execution_worker import (
            QueueExecutionWorker,
        )

        video_path = tmp_path / "realsource.mp4"
        r = subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "testsrc=duration=3:size=320x240:rate=24",
                "-pix_fmt", "yuv420p", str(video_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if r.returncode != 0:
            pytest.skip("ffmpeg unavailable in test env")

        outdir = tmp_path / "out"
        outdir.mkdir(exist_ok=True)
        cfg1 = {"type": "gif", "video_path": str(video_path), "start_ms": 0,
                "end_ms": 1000, "output_dir": str(outdir),
                "target_resolution": (320, 240), "cuts_ms": [], "frame_interval": 1,
                "smart_extract": False, "smart_method": "", "fps": 24,
                "mute_audio": False, "use_ffmpeg": True, "speed": 1.0}
        cfg2 = {"type": "gif", "video_path": str(video_path), "start_ms": 1000,
                "end_ms": 2000, "output_dir": str(outdir),
                "target_resolution": (320, 240), "cuts_ms": [], "frame_interval": 1,
                "smart_extract": False, "smart_method": "", "fps": 24,
                "mute_audio": False, "use_ffmpeg": True, "speed": 1.0}

        emitted = []
        worker = QueueExecutionWorker([cfg1, cfg2], parallel=True)
        worker.signals.item_completed.connect(
            lambda i, res, item: emitted.append((i, item))
        )
        worker.run()

        assert len(emitted) == 2
        # Parallel pickles the config through multiprocessing, so identity is
        # lost; the emitted items must still equal the original configs by
        # value so the tab can match-and-remove them.
        emitted_vals = [it for _, it in emitted]
        assert cfg1 in emitted_vals
        assert cfg2 in emitted_vals

    def test_finished_after_item_completed_no_duplicate_gallery(self, q_app, tmp_path):
        """When item_completed already handled a result, the finished handler
        must not add the same path to the gallery a second time."""
        tab, video_path = self._make_tab(tmp_path)
        f1 = tab.extraction_dir / "a.gif"
        f1.write_text("gif")
        item = {"type": "gif", "video_path": str(video_path), "start_ms": 0,
                "end_ms": 1000, "output_dir": str(tab.extraction_dir),
                "use_ffmpeg": True, "fps": 24}
        tab.extraction_queue.append(item)
        tab._update_queue_ui()

        tab._on_queue_item_completed(
            0, {"status": "success", "output_path": str(f1)}, item
        )
        tab._on_queue_processing_finished(
            [{"status": "success", "output_path": str(f1)}]
        )

        assert tab.master_image_paths.count(str(f1)) == 1
        assert tab.extraction_metadata.get(str(f1)) is not None

    def test_queue_finished_records_each_successful_result(self, q_app, tmp_path):
        """Multiple successful queue results must all be recorded, and the
        gallery must receive every path (saved_files or output_path)."""
        tab, video_path = self._make_tab(tmp_path)
        f1 = tab.extraction_dir / "a.gif"
        f2 = tab.extraction_dir / "b.gif"
        f3 = tab.extraction_dir / "c.gif"
        for f in (f1, f2, f3):
            f.write_text("gif")

        tab._on_queue_processing_finished(
            [
                {"status": "success", "output_path": str(f1)},
                {"status": "success", "saved_files": [str(f2), str(f3)]},
            ]
        )

        for f in (f1, f2, f3):
            assert str(f) in tab.extraction_metadata
            assert str(f) in tab.master_image_paths
