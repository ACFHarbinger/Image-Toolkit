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
    import gui.src.tabs.core.extractor_tab._video_session_history as vsh

    monkeypatch.setattr(vsh, "IMAGE_TOOLKIT_DIR", tmp_path)


class TestExtractorTabQueue:
    def _make_tab(self, tmp_path):
        from gui.src.tabs.core.extractor_tab import ExtractorTab

        video_path = tmp_path / "episode.mp4"
        video_path.write_text("dummy")
        with (
            patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
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

    def test_queue_section_height_matches_settings_section(self, q_app, tmp_path):
        """The Extraction Queue section must render at the same height as the
        Extraction Settings section: the queue list is capped so the whole
        queue group's sizeHint equals the settings group's sizeHint (the
        settings group is the source of truth). Larger queues scroll inside
        the list instead of stretching the section taller."""
        tab, video_path = self._make_tab(tmp_path)
        tab.show()
        q_app.processEvents()

        assert tab.queue_group.sizeHint().height() == tab.extract_group.sizeHint().height(), (
            "queue group must match the Extraction Settings section height"
        )
        # The queue list is what's tuned (the cap lands on the list, not the
        # group), so it must actually honor the cap once rendered.
        assert tab.queue_list.height() >= tab.queue_list.minimumHeight() - 1, (
            "rendered list height must honor the cap"
        )

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

    def test_empty_item_falls_back_to_live_state(self, q_app, tmp_path):
        """An empty/corrupt queue item must never be recorded as "Unknown
        Video": _queue_result_metadata falls back to the live UI state."""
        tab, video_path = self._make_tab(tmp_path)
        out_file = tab.extraction_dir / "a.gif"
        out_file.write_text("gif")
        tab.video_path = str(video_path)
        tab.start_time_ms = 123
        tab.end_time_ms = 456
        tab.cuts_ms = []
        tab.tags_ms = []

        tab._on_queue_item_completed(
            0, {"status": "success", "output_path": str(out_file)}, {}
        )

        entry = tab.recent_runs[-1]
        assert entry["video_path"] == str(video_path), (
            "empty item must fall back to the live video_path, not 'Unknown Video'"
        )

    def test_queue_item_completed_records_real_metadata(self, q_app, tmp_path):
        """Per-item completion records extraction history with the REAL queue
        item (video_path/start/end). Regression for the "Unknown Video
        (00:00:000 - 00:00:000)" bug: _on_queue_processing_finished used to
        re-record with _queue_result_metadata({}) -- an empty dict -- which
        wrote empty entries for every queued item after restart."""
        tab, video_path = self._make_tab(tmp_path)
        out_file = tab.extraction_dir / "test_0ms_3000ms.gif"
        out_file.write_text("gif")

        item = {
            "type": "gif",
            "video_path": str(video_path),
            "start_ms": 0,
            "end_ms": 3000,
            "output_dir": str(tab.extraction_dir),
            "use_ffmpeg": True,
            "fps": 24,
        }

        tab._on_queue_item_completed(
            0, {"status": "success", "output_path": str(out_file)}, item
        )

        assert str(out_file) in tab.extraction_metadata
        entry = tab.recent_runs[-1]
        assert entry["video_path"] == str(video_path)
        assert entry["start_ms"] == 0
        assert entry["end_ms"] == 3000

    def test_queue_finished_does_not_record_empty_metadata(self, q_app, tmp_path):
        """The finished handler must not write empty 'Unknown Video' entries:
        recording is per-item (_on_queue_item_completed); the finished handler
        only builds the gallery and cleans up."""
        tab, video_path = self._make_tab(tmp_path)
        out_file = tab.extraction_dir / "test_0ms_3000ms.gif"
        out_file.write_text("gif")

        with patch("gui.src.tabs.core.extractor_tab._queue_management.QMessageBox"):
            tab._on_queue_processing_finished(
                [{"status": "success", "output_path": str(out_file)}]
            )

        assert all(
            run.get("video_path") for run in tab.recent_runs
        ), "finished handler must not record empty 'Unknown Video' entries"

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
        worker.signals.item_completed.connect(tab._on_queue_item_completed)
        worker.signals.finished.connect(tab._on_queue_processing_finished)
        with patch("gui.src.tabs.core.extractor_tab._queue_management.QMessageBox"):
            worker.run()

        out_gif = tab.extraction_dir / "realsource_0ms_3000ms.gif"
        assert out_gif.exists(), "gif file must be produced from queued item"
        assert tab.extraction_queue == []
        assert str(out_gif) in tab.master_image_paths
        assert str(out_gif) in tab.extraction_metadata
        # The recorded recent-extraction entry must keep the REAL source
        # video_path/start/end (regression for the "Unknown Video" bug).
        entry = tab.recent_runs[-1]
        assert entry["video_path"] == str(video_path), (
            "recorded entry must keep the source video_path"
        )
        assert entry["start_ms"] == 0
        assert entry["end_ms"] == 3000

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
        # Gallery update is deferred per item (freeze fix): the path lands in
        # the pending list immediately and only enters master_image_paths when
        # the whole run flushes.
        assert str(f1) in tab._queue_pending_gallery_paths
        assert str(f1) not in tab.master_image_paths

        tab._on_queue_item_completed(
            0, {"status": "success", "output_path": str(f2)}, item2
        )

        assert tab.queue_list.count() == 0
        assert str(f2) in tab.extraction_metadata
        assert str(f2) in tab._queue_pending_gallery_paths

        # The finished handler flushes the deferred paths with ONE gallery
        # rebuild.
        tab._on_queue_processing_finished([])
        assert str(f1) in tab.master_image_paths
        assert str(f2) in tab.master_image_paths
        assert tab._queue_pending_gallery_paths == []

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

    def test_item_completed_does_not_rebuild_gallery_per_item(self, q_app, tmp_path):
        """Regression: the per-item gallery rebuild freezes the UI. Each
        item_completed must only buffer paths; a single gallery rebuild
        happens when the run finishes (or errors)."""
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
        item1 = tab.extraction_queue[0]
        item2 = tab.extraction_queue[1]

        with patch.object(
            tab.video_subtab, "start_loading_gallery", return_value=None
        ) as mock_load:
            tab._on_queue_item_completed(
                0, {"status": "success", "output_path": str(f1)}, item1
            )
            tab._on_queue_item_completed(
                0, {"status": "success", "output_path": str(f2)}, item2
            )
            assert mock_load.call_count == 0, (
                "per-item completion must not rebuild the gallery (UI freeze)"
            )

            tab._on_queue_processing_finished([])
            assert mock_load.call_count == 1, (
                "exactly one gallery rebuild at queue end"
            )
            forwarded = mock_load.call_args[0][0]
            assert str(f1) in forwarded
            assert str(f2) in forwarded

    def test_queue_error_flushes_deferred_gallery_paths(self, q_app, tmp_path):
        """Results that completed before a queue error must still appear in
        the gallery when the error handler flushes them."""
        tab, video_path = self._make_tab(tmp_path)
        f1 = tab.extraction_dir / "a.gif"
        f1.write_text("gif")
        item = {"type": "gif", "video_path": str(video_path), "start_ms": 0,
                "end_ms": 1000, "output_dir": str(tab.extraction_dir),
                "use_ffmpeg": True, "fps": 24}
        tab.extraction_queue.append(item)
        tab._update_queue_ui()

        with patch.object(
            tab.video_subtab, "start_loading_gallery", return_value=None
        ) as mock_load:
            tab._on_queue_item_completed(
                0, {"status": "success", "output_path": str(f1)}, item
            )
            assert mock_load.call_count == 0

            with patch(
                "gui.src.tabs.core.extractor_tab._queue_management.QMessageBox"
            ):
                tab._on_queue_processing_error("engine failure")

            assert mock_load.call_count == 1
            assert str(f1) in mock_load.call_args[0][0]
            assert tab._queue_pending_gallery_paths == []

    def test_queue_finished_builds_gallery_for_each_result(self, q_app, tmp_path):
        """The finished handler sends every successful result path
        (saved_files or output_path) to the gallery."""
        tab, video_path = self._make_tab(tmp_path)
        f1 = tab.extraction_dir / "a.gif"
        f2 = tab.extraction_dir / "b.gif"
        f3 = tab.extraction_dir / "c.gif"
        for f in (f1, f2, f3):
            f.write_text("gif")

        with patch("gui.src.tabs.core.extractor_tab._queue_management.QMessageBox"):
            tab._on_queue_processing_finished(
                [
                    {"status": "success", "output_path": str(f1)},
                    {"status": "success", "saved_files": [str(f2), str(f3)]},
                ]
            )

        for f in (f1, f2, f3):
            assert str(f) in tab.master_image_paths

    def test_gallery_never_shows_nonexistent_worker_path(self, q_app, tmp_path):
        """A worker-reported output path that does not exist on disk must not
        appear as a phantom gallery card (the gallery itself never checks
        existence)."""
        tab, video_path = self._make_tab(tmp_path)
        phantom = str(tab.extraction_dir / "does_not_exist.gif")

        tab._on_queue_item_completed(
            0,
            {"status": "success", "output_path": phantom},
            {"type": "gif", "video_path": str(video_path)},
        )

        assert phantom not in tab.master_image_paths

    def test_queue_finished_skips_nonexistent_paths(self, q_app, tmp_path):
        """The finished handler must not pass nonexistent paths into the
        gallery (which would render a phantom card)."""
        tab, video_path = self._make_tab(tmp_path)
        real = tab.extraction_dir / "real.gif"
        real.write_text("gif")
        phantom = str(tab.extraction_dir / "phantom.gif")

        # Avoid real thumbnail decode of the dummy gif in this sandbox; we
        # only assert which paths are forwarded to the gallery.
        with patch.object(
            tab.video_subtab, "start_loading_gallery", return_value=None
        ) as mock_load:
            tab._on_queue_processing_finished(
                [
                    {"status": "success", "output_path": str(real)},
                    {"status": "success", "output_path": phantom},
                ]
            )

        assert mock_load.call_count == 1
        forwarded = mock_load.call_args[0][0]
        assert str(real) in forwarded
        assert phantom not in forwarded
        # The phantom must never reach the gallery's master path list either.
        assert phantom not in tab.master_image_paths

    def test_full_queue_flow_range_single_gif_records_real_metadata(self, q_app, tmp_path):
        """Genuine end-to-end (the exact path Claude asked to pin): build each
        queue config via the REAL _run_extraction/_run_gif_extraction methods,
        run the REAL sequential QueueExecutionWorker with only
        run_extraction_in_process mocked, and diff what reaches
        _record_extraction. No empty "Unknown Video" entry may be recorded --
        every recorded entry must carry the real video_path/start/end.

        This is the Unknown-Video regression test that the hand-built-dict
        tests cannot provide: it exercises add-to-queue -> worker -> per-item
        completion -> _record_extraction for every queue type in one flow.
        """
        from gui.src.helpers.core.queue_execution_worker import (
            QueueExecutionWorker,
        )

        tab, video_path = self._make_tab(tmp_path)
        tab.extraction_queue_enabled = True
        tab.video_path = str(video_path)
        tab.start_time_ms = 1000
        tab.end_time_ms = 3000
        tab.spin_gif_fps.setValue(24)
        tab.combo_engine.setCurrentText("FFmpeg")
        tab.cuts_ms = []
        tab.tags_ms = []
        tab.spin_interval.setValue(1)

        # Queue three different item types through the real UI entry points.
        tab._run_extraction(1000, 3000, is_range=True)   # range -> type "range"
        tab._run_gif_extraction(1000, 3000)              # gif
        tab._run_extraction(1500, 1500, is_range=False)  # single

        assert len(tab.extraction_queue) == 3
        for cfg in tab.extraction_queue:
            assert cfg["video_path"] == str(video_path), (
                f"queue config lost video_path at add time: {cfg!r}"
            )

        # Snapshot the queue before the worker consumes its own copy.
        queued = list(tab.extraction_queue)

        # Mock ONLY the extraction engine: the queue plumbing, per-item
        # completion signal, and _record_extraction are all real.
        def fake_run(cfg):
            t = cfg.get("type")
            if t == "gif":
                out = tab.extraction_dir / f"fake_{cfg['start_ms']}_{cfg['end_ms']}.gif"
            else:
                out = tab.extraction_dir / f"fake_{cfg['start_ms']}_{cfg['end_ms']}.png"
            out.write_text("fake")
            return {"status": "success", "output_path": str(out)}

        with (
            patch("gui.src.tabs.core.extractor_tab._queue_management.QMessageBox"),
            patch(
                "gui.src.helpers.core.queue_execution_worker.run_extraction_in_process",
                side_effect=fake_run,
            ) as mock_engine,
            patch(
                "gui.src.tabs.core.extractor_tab._video_session_history.traceback"
            ) as mock_tb,
            patch.object(tab.video_subtab, "start_loading_gallery", return_value=None),
        ):
            worker = QueueExecutionWorker(queued, parallel=False)
            worker.signals.item_completed.connect(tab._on_queue_item_completed)
            worker.signals.finished.connect(tab._on_queue_processing_finished)
            worker.run()

        assert mock_engine.call_count == 3
        assert tab.extraction_queue == []

        # Every recorded recent run must carry the REAL source video_path.
        assert tab.recent_runs, "queue flow must record extractions"
        for entry in tab.recent_runs:
            assert entry.get("video_path") == str(video_path), (
                f"recorded entry lost video_path: {entry!r}"
            )
            assert entry.get("start_ms") == 1000
        # The defensive empty-item fallback (which prints a stack) must NOT
        # have fired: no empty item ever reached _record_extraction.
        mock_tb.print_stack.assert_not_called()

        # The recorded metadata keys for each file must exist in file_map.
        for f in tab.extraction_dir.glob("fake_*"):
            assert str(f) in tab.extraction_metadata

    def test_full_queue_flow_parallel_records_real_metadata(self, q_app, tmp_path):
        """Parallel mode: configs pickle through multiprocessing, so the item
        arriving at _on_queue_item_completed is a COPY -- it must still carry
        video_path (regression: parallel-mode items previously risked being
        recorded empty). run_extraction_in_process is mocked; the real worker
        + tab handlers run."""
        from gui.src.helpers.core.queue_execution_worker import (
            QueueExecutionWorker,
        )

        tab, video_path = self._make_tab(tmp_path)
        tab.extraction_queue_enabled = True
        tab.video_path = str(video_path)
        tab.start_time_ms = 1000
        tab.end_time_ms = 3000
        tab.spin_gif_fps.setValue(24)
        tab.combo_engine.setCurrentText("FFmpeg")
        tab.cuts_ms = []

        tab._run_gif_extraction(1000, 2000)
        tab._run_gif_extraction(2000, 3000)
        queued = list(tab.extraction_queue)

        def fake_run(cfg):
            out = tab.extraction_dir / f"par_{cfg['start_ms']}.gif"
            out.write_text("fake")
            return {"status": "success", "output_path": str(out)}

        with (
            patch("gui.src.tabs.core.extractor_tab._queue_management.QMessageBox"),
            patch(
                "gui.src.helpers.core.queue_execution_worker.run_extraction_in_process",
                side_effect=fake_run,
            ),
            patch.object(tab.video_subtab, "start_loading_gallery", return_value=None),
        ):
            worker = QueueExecutionWorker(queued, parallel=True)
            worker.signals.item_completed.connect(tab._on_queue_item_completed)
            worker.signals.finished.connect(tab._on_queue_processing_finished)
            worker.run()

        assert tab.recent_runs, "parallel queue flow must record extractions"
        for entry in tab.recent_runs:
            assert entry.get("video_path") == str(video_path), (
                f"parallel-mode entry lost video_path: {entry!r}"
            )

class TestHeadlessKeepAlive:
    """Bug 1: MainWindow defers close while extractions run. The tab reports
    active extractions and fires the deferred-close callback once none remain,
    and the worker keeps itself alive for the whole run()."""

    def _make_tab(self, tmp_path):
        from gui.src.tabs.core.extractor_tab import ExtractorTab

        with (
            patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
        ):
            tab = ExtractorTab()
        tab._media_player = MagicMock()
        return tab

    def test_has_active_extractions_detects_workers(self, q_app, tmp_path):
        tab = self._make_tab(tmp_path)
        tab.active_queue_worker = None
        tab.active_extraction_worker = None
        assert tab.has_active_extractions() is False
        tab.active_queue_worker = object()
        assert tab.has_active_extractions() is True
        tab.active_queue_worker = None
        tab.active_extraction_worker = object()
        assert tab.has_active_extractions() is True

    def test_deferred_close_callback_fires_when_idle(self, q_app, tmp_path):
        tab = self._make_tab(tmp_path)
        tab.active_queue_worker = None
        tab.active_extraction_worker = None
        fired = []
        tab.set_close_when_finished(lambda: fired.append(True))
        tab._maybe_finish_close()
        assert fired == [True]

    def test_deferred_close_callback_defers_while_worker_active(self, q_app, tmp_path):
        tab = self._make_tab(tmp_path)
        tab.active_queue_worker = object()
        tab.active_extraction_worker = None
        fired = []
        tab.set_close_when_finished(lambda: fired.append(True))
        tab._maybe_finish_close()
        assert fired == []
        tab.active_queue_worker = None
        tab._maybe_finish_close()
        assert fired == [True]

    def test_worker_safety_net_keeps_self_alive_through_run(self):
        from gui.src.helpers.core.queue_execution_worker import (
            QueueExecutionWorker,
            _RUNNING_WORKERS,
        )

        worker = QueueExecutionWorker([], parallel=False)
        assert worker not in _RUNNING_WORKERS
        worker.run()  # empty queue: emits started/finished, no extraction
        assert worker not in _RUNNING_WORKERS, (
            "the worker must drop its safety-net reference once run() returns"
        )
