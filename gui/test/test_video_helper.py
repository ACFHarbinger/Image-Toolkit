import pytest
import numpy as np

from unittest.mock import MagicMock, patch
from gui.src.helpers.video.frame_extractor_worker import FrameExtractionWorker
from gui.src.helpers.video.video_scan_worker import VideoScannerWorker

# --- FrameExtractionWorker Tests ---

class TestFrameExtractionWorker:
    def test_run_range(self, q_app):
        # Configure cv2 mock behavior
        mock_cap = MagicMock()
        frame_mock = np.zeros((100, 100, 3), dtype=np.uint8)
        
        # We want it to loop a bit. 
        # The worker loop calls cap.read()
        mock_cap.read.side_effect = [(True, frame_mock), (True, frame_mock), (False, None)]
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 30.0 # FPS
        
        # Patch cv2 in the WORKER module
        with patch("gui.src.helpers.video.frame_extractor_worker.cv2") as mock_cv2:
             mock_cv2.VideoCapture.return_value = mock_cap
             mock_cv2.resize.return_value = frame_mock
             
             worker = FrameExtractionWorker(
                 video_path="/tmp/vid.mp4",
                 output_dir="/tmp/out",
                 start_ms=0,
                 end_ms=1000,
                 is_range=True
             )
             
             finished_signals = []
             worker.signals.finished.connect(lambda f: finished_signals.append(f))
             
             errors = []
             worker.signals.error.connect(lambda e: errors.append(e))
             
             worker.run()
             
             if errors:
                 pytest.fail(f"Worker emitted error: {errors[0]}")
             
             assert len(finished_signals) == 1
             assert mock_cv2.imwrite.call_count == 2
             mock_cap.release.assert_called()

    def test_run_error(self, q_app):
        with patch("gui.src.helpers.video.frame_extractor_worker.cv2") as mock_cv2:
            mock_cap = MagicMock()
            mock_cv2.VideoCapture.return_value = mock_cap
            mock_cap.isOpened.return_value = False
            
            worker = FrameExtractionWorker("/tmp/bad.mp4", "/tmp/out", 0)
            
            errors = []
            worker.signals.error.connect(lambda e: errors.append(e))
            
            worker.run()
            
            assert len(errors) == 1
            assert "Could not open" in errors[0]

# --- VideoScannerWorker Tests ---

class TestVideoScannerWorker:
    def test_run(self, q_app, tmp_path):
        # Create a video file
        d = tmp_path / "videos"
        d.mkdir()
        v_file = d / "test.mp4"
        v_file.touch()
        
        # Configure cv2 mock to return a frame
        frame_mock = np.zeros((10, 10, 3), dtype=np.uint8)
        
        mock_cap = MagicMock()
        mock_cap.read.return_value = (True, frame_mock)
        
        with patch("gui.src.helpers.video.video_scan_worker.cv2") as mock_cv2, \
             patch("gui.src.helpers.video.video_scan_worker.HAS_NATIVE_IMAGING", False):
            
            mock_cv2.VideoCapture.return_value = mock_cap
            mock_cv2.cvtColor.return_value = frame_mock
            
            worker = VideoScannerWorker(str(d))
             
            thumbs = []
            worker.signals.thumbnail_ready.connect(lambda p, px: thumbs.append(p))
             
            finished = []
            worker.signals.finished.connect(lambda: finished.append(True))
             
            worker.run()
             
            assert len(finished) == 1
            assert len(thumbs) == 1
            assert str(v_file) in thumbs[0]
