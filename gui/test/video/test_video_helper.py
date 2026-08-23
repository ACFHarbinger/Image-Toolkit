from unittest.mock import MagicMock, patch

import pytest

from gui.src.helpers.video.batch_video_loader_worker import BatchVideoLoaderWorker
from gui.src.helpers.video.frame_extractor_worker import FrameExtractionWorker
from gui.src.helpers.video.video_loader_worker import VideoLoaderWorker
from gui.src.helpers.video.video_scan_worker import VideoScannerWorker

# --- FrameExtractionWorker Tests ---


class TestFrameExtractionWorker:
    def test_run_range(self, q_app, tmp_path):
        # Configure cv2 mock behavior for _get_fps
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 30.0  # FPS

        # Create dummy temp files in tmp_path
        tmp_dir = str(tmp_path)
        t1 = tmp_path / "vid_tmp_00001.png"
        t1.touch()
        t2 = tmp_path / "vid_tmp_00002.png"
        t2.touch()

        mock_process = MagicMock()
        mock_process.poll.side_effect = [None, 0]
        mock_process.returncode = 0

        # Patch cv2 and subprocess.Popen in the WORKER module
        with (
            patch("gui.src.helpers.video.frame_extractor_worker.cv2") as mock_cv2,
            patch("gui.src.helpers.video.frame_extractor_worker.subprocess.Popen", return_value=mock_process) as _mock_popen,
        ):
            mock_cv2.VideoCapture.return_value = mock_cap

            worker = FrameExtractionWorker(
                video_path="/tmp/vid.mp4",
                output_dir=tmp_dir,
                start_ms=0,
                end_ms=1000,
                is_range=True,
            )

            finished_signals = []
            worker.signals.finished.connect(lambda f: finished_signals.append(f))

            errors = []
            worker.signals.error.connect(lambda e: errors.append(e))

            worker.run()

            if errors:
                pytest.fail(f"Worker emitted error: {errors[0]}")

            assert len(finished_signals) == 1
            assert len(finished_signals[0]) == 2
            assert (tmp_path / "vid_0ms.png").exists()
            assert (tmp_path / "vid_33ms.png").exists()
            mock_cap.release.assert_called_once()

    def test_run_error(self, q_app):
        # Mock cv2 to make _get_fps return 23.976 without error
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False

        mock_process = MagicMock()
        mock_process.poll.return_value = 0
        mock_process.returncode = 1
        mock_process.stderr.read.return_value = "Could not open video file /tmp/bad.mp4"

        with (
            patch("gui.src.helpers.video.frame_extractor_worker.cv2") as mock_cv2,
            patch("gui.src.helpers.video.frame_extractor_worker.subprocess.Popen", return_value=mock_process) as _mock_popen,
        ):
            mock_cv2.VideoCapture.return_value = mock_cap

            worker = FrameExtractionWorker("/tmp/bad.mp4", "/tmp/out", 0)

            errors = []
            worker.signals.error.connect(lambda e: errors.append(e))

            worker.run()

            assert len(errors) == 1
            assert "Could not open" in errors[0]

# --- VideoScannerWorker Tests ---
# Reintroduced 2026-08-01 as a scan-only QThread (no thumbnail generation,
# no internal ThreadPoolExecutor) -- see Addendum 24 in
# .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md. Mirrors
# TestImageScannerWorker in gui/test/image/test_image_helper.py.


class TestVideoScannerWorker:
    def test_run_scan(self, q_app, tmp_path):
        d = tmp_path / "videos"
        d.mkdir()
        (d / "clip1.mp4").touch()
        (d / "clip2.mkv").touch()
        (d / "ignore.txt").touch()

        with patch("gui.src.helpers.video.video_scan_worker.HAS_NATIVE_IMAGING", False):
            worker = VideoScannerWorker([str(d)])

            finished_signals = []
            worker.scan_finished.connect(lambda r: finished_signals.append(r))

            worker.run_scan()

            assert len(finished_signals) == 1
            found = finished_signals[0]
            assert len(found) == 2
            assert any("clip1.mp4" in f for f in found)

    def test_error(self, q_app):
        worker = VideoScannerWorker([])

        error_signals = []
        worker.scan_error.connect(lambda e: error_signals.append(e))

        worker.run_scan()

        assert len(error_signals) == 1
        assert "No valid directories" in error_signals[0]


# --- VideoLoaderWorker / BatchVideoLoaderWorker Tests ---
# QRunnable/QThreadPool architecture -- same as ImageLoaderWorker, never
# implicated in the deleteOrphaned crash class.


class TestVideoLoaderWorker:
    def test_run_uses_disk_cache(self, q_app, tmp_path):
        cache_file = tmp_path / "cached.jpg"
        cache_file.write_bytes(b"fake")

        with (
            patch(
                "gui.src.helpers.video.video_loader_worker.get_video_thumbnail_cache_path",
                return_value=str(cache_file),
            ),
            patch("gui.src.helpers.video.video_loader_worker.QImage") as MockQImage,
        ):
            mock_inst = MagicMock()
            MockQImage.return_value = mock_inst
            mock_inst.isNull.return_value = False

            worker = VideoLoaderWorker("/tmp/fake.mp4", 100)
            results = []
            worker.signals.result.connect(lambda p, img: results.append((p, img)))

            worker.run()

            assert len(results) == 1
            assert results[0][0] == "/tmp/fake.mp4"

    def test_run_generates_when_no_cache(self, q_app, tmp_path):
        cache_file = tmp_path / "missing.jpg"

        mock_image = MagicMock()
        mock_image.isNull.return_value = False

        with patch(
            "gui.src.helpers.video.video_loader_worker.get_video_thumbnail_cache_path",
            return_value=str(cache_file),
        ):
            worker = VideoLoaderWorker("/tmp/fake.mp4", 100)
            worker.thumbnailer = MagicMock()
            worker.thumbnailer.generate.return_value = mock_image

            results = []
            worker.signals.result.connect(lambda p, img: results.append((p, img)))

            worker.run()

            worker.thumbnailer.generate.assert_called_once_with(
                "/tmp/fake.mp4", 100, crop_square=False
            )
            mock_image.save.assert_called_once()
            assert len(results) == 1


class TestBatchVideoLoaderWorker:
    def test_run_batch(self, q_app, tmp_path):
        cache_file = tmp_path / "missing.jpg"
        mock_image = MagicMock()
        mock_image.isNull.return_value = False

        with patch(
            "gui.src.helpers.video.batch_video_loader_worker.get_video_thumbnail_cache_path",
            return_value=str(cache_file),
        ):
            worker = BatchVideoLoaderWorker(["/tmp/a.mp4", "/tmp/b.mp4"], 100)
            worker.thumbnailer = MagicMock()
            worker.thumbnailer.generate.return_value = mock_image

            batch_results = []
            worker.signals.batch_result.connect(
                lambda results, paths: batch_results.append((results, paths))
            )

            worker.run()

            assert len(batch_results) == 1
            results, paths = batch_results[0]
            assert paths == ["/tmp/a.mp4", "/tmp/b.mp4"]
            assert len(results) == 2
