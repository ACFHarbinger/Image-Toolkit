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
        
        # Result tuple: (path, data, w, h, bpl)
        mock_data = b'\x00' * 300
        mock_result = (str(v_file), mock_data, 10, 10, 30)
        
        with patch("gui.src.helpers.video.video_scan_worker.concurrent.futures.ProcessPoolExecutor") as MockExecutor, \
             patch("gui.src.helpers.video.video_scan_worker.HAS_NATIVE_IMAGING", False):
             
             # Configure the mock executor
             mock_future = MagicMock()
             mock_future.result.return_value = mock_result
             
             mock_executor_instance = MockExecutor.return_value
             mock_executor_instance.__enter__.return_value = mock_executor_instance
             # We need submit to return a mock that acts as a key in the futures dict
             mock_executor_instance.submit.return_value = mock_future
             
             # The code iterates as_completed(futures)
             # Then it does res_type = futures[future]
             # We need to make sure the futures dict is populated correctly in the WORKER not the TEST.
             # The worker populates `futures` by calling executor.submit.
             # So if we mock as_completed to yield the SAME future object that submit returned, it should             
             # The code uses concurrent.futures.wait now
             mock_wait_res = ({mock_future}, set())
             
             with patch("gui.src.helpers.video.video_scan_worker.concurrent.futures.wait", return_value=mock_wait_res):
                 
                 worker = VideoScannerWorker(str(d))
                 
                 thumbs = []
                 worker.signals.thumbnail_ready.connect(lambda p, px: thumbs.append(p))
                 
                 finished = []
                 worker.signals.finished.connect(lambda: finished.append(True))
                 
                 worker.run()
                 
                 assert len(finished) == 1
                 assert len(thumbs) == 1
                 assert str(v_file) in thumbs[0]

    def test_run_rust_multiprocessing(self, q_app, tmp_path):
        # Create dummy videos
        d = tmp_path / "rust_test_videos"
        d.mkdir()
        v1 = d / "v1.mp4"; v1.touch()
        v2 = d / "v2.mp4"; v2.touch()
        
        # Mock result from Rust process: (path, buffer, w, h)
        # buffer for QImage(Format_RGBA8888) -> 4 bytes per pixel
        # 10x10 image = 100 pixels * 4 bytes = 400 bytes
        mock_buf = b'\xFF' * 400 
        mock_batch_result = [
            (str(v1), mock_buf, 10, 10),
            (str(v2), mock_buf, 10, 10)
        ]
        
        # We need to force HAS_NATIVE_IMAGING = True in the worker module
        with patch("gui.src.helpers.video.video_scan_worker.HAS_NATIVE_IMAGING", True), \
             patch("gui.src.helpers.video.video_scan_worker.base") as mock_base, \
             patch("gui.src.helpers.video.video_scan_worker.concurrent.futures.ProcessPoolExecutor") as MockExecutor:
             
             # Mock scan_files to return our files
             mock_base.scan_files.return_value = [str(v1), str(v2)]
             
             # Mock Executor logic
             mock_future = MagicMock()
             mock_future.result.return_value = mock_batch_result
             
             mock_executor_instance = MockExecutor.return_value
             mock_executor_instance.__enter__.return_value = mock_executor_instance
             mock_executor_instance.submit.return_value = mock_future
             
             mock_wait_res = ({mock_future}, set())
             
             with patch("gui.src.helpers.video.video_scan_worker.concurrent.futures.wait", return_value=mock_wait_res):
                 worker = VideoScannerWorker(str(d))
                 
                 thumbs = []
                 worker.signals.thumbnail_ready.connect(lambda p, px: thumbs.append(p))
                 
                 finished = []
                 worker.signals.finished.connect(lambda: finished.append(True))
                 
                 worker.run()
                 
                 assert len(finished) == 1
                 assert len(thumbs) == 2
                 assert str(v1) in thumbs
                 assert str(v2) in thumbs
