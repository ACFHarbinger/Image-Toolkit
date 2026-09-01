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
        assert mock_run.call_count == 2
        pass1 = mock_run.call_args_list[0][0][0]
        pass2 = mock_run.call_args_list[1][0][0]
        for cmd in (pass1, pass2):
            assert "-threads" in cmd
            assert cmd[cmd.index("-threads") + 1] == "4"
        vf_idx = pass1.index("-vf")
        assert "max_colors=64" in pass1[vf_idx + 1]
        assert "fps=24" in pass1[vf_idx + 1]
        assert "palettegen" in pass1[vf_idx + 1]
        lavfi_idx = pass2.index("-lavfi")
        assert "paletteuse" in pass2[lavfi_idx + 1]
        assert "fps=24" in pass2[lavfi_idx + 1]
