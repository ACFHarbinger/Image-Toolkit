from unittest.mock import MagicMock, patch

import pytest
from gui.src.helpers.video.frame_extractor_worker import FrameExtractionWorker

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

# VideoScannerWorker (directory scan + thumbnail generation) was removed
# entirely 2026-08-01 -- see Addendum 23 in
# .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md.
