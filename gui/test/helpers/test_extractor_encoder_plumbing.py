from unittest.mock import patch

from gui.src.helpers.core.queue_execution_worker import run_extraction_in_process
from gui.src.helpers.video.frame_extractor_worker import FrameExtractionWorker
from gui.src.helpers.video.gif_extractor_worker import GifCreationWorker
from gui.src.helpers.video.video_extractor_worker import VideoExtractionWorker


def test_frame_extractor_worker_encoder_params():
    worker = FrameExtractionWorker(
        video_path="dummy.mp4",
        output_dir="/tmp",
        start_ms=0,
        end_ms=1000,
        fps=60.0,
        encoder_threads=4,
        fps_clamp=30,
    )
    assert worker.encoder_threads == 4
    assert worker.fps_clamp == 30
    assert worker.fps == 30.0


def test_video_extractor_worker_encoder_params():
    worker = VideoExtractionWorker(
        video_path="dummy.mp4",
        start_ms=0,
        end_ms=1000,
        output_path="/tmp/out.mp4",
        encoder_threads=6,
        fps_clamp=24,
    )
    assert worker.encoder_threads == 6
    assert worker.fps_clamp == 24


def test_gif_creation_worker_encoder_params():
    worker = GifCreationWorker(
        video_path="dummy.mp4",
        start_ms=0,
        end_ms=1000,
        output_path="/tmp/out.gif",
        fps=60,
        encoder_threads=2,
        max_colors=128,
        fps_clamp=20,
    )
    assert worker.encoder_threads == 2
    assert worker.max_colors == 128
    assert worker.fps_clamp == 20
    assert worker.fps == 20


def test_queue_execution_worker_encoder_params_parsing():
    config = {
        "type": "gif",
        "video_path": "nonexistent_video.mp4",
        "start_ms": 0,
        "end_ms": 1000,
        "output_dir": "/tmp",
        "fps": 60,
        "encoder_threads": 4,
        "max_colors": 64,
        "fps_clamp": 24,
        "use_ffmpeg": True,
    }

    with patch("subprocess.run") as mock_run:
        res = run_extraction_in_process(config)
        assert res.get("status") == "success"
        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        # Check threads argument
        assert "-threads" in cmd
        idx = cmd.index("-threads")
        assert cmd[idx + 1] == "4"
        # Check max_colors in palettegen filter
        vf_idx = cmd.index("-vf")
        assert "max_colors=64" in cmd[vf_idx + 1]
        # Check clamped fps filter
        assert "fps=24" in cmd[vf_idx + 1]
