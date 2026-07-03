import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Adjust path to find src (if running directly or via different runner)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend.src.core.video_converter import VideoFormatConverter  # noqa: E402


class TestVideoFormatConverter:
    @patch("backend.src.core.video_converter.subprocess.Popen")
    def test_convert_with_ffmpeg_success(
        self, mock_popen, sample_video, output_dir
    ):
        """Test successful conversion using FFmpeg via Popen."""
        input_path = sample_video
        output_path = os.path.join(output_dir, "output.avi")

        # Mock successful Popen process
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process

        result = VideoFormatConverter.convert_video(
            input_path, output_path
        )

        assert result is True
        mock_popen.assert_called_once()
        # Verify the command called contains basic ffmpeg conversion flags
        cmd_args = mock_popen.call_args[0][0]
        assert cmd_args[0] == "ffmpeg"
        assert "-i" in cmd_args
        assert output_path in cmd_args

    @patch("backend.src.core.video_converter.subprocess.Popen")
    def test_convert_with_ffmpeg_failure(
        self, mock_popen, sample_video, output_dir
    ):
        """Test failure in FFmpeg conversion."""
        input_path = sample_video
        output_path = os.path.join(output_dir, "output.avi")

        # Mock failed Popen process
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process

        result = VideoFormatConverter.convert_video(
            input_path, output_path
        )

        assert result is False

    def test_input_file_not_found(self, output_dir):
        """Test failure when input file does not exist."""
        input_path = "/nonexistent/video.mp4"
        output_path = os.path.join(output_dir, "output.avi")

        result = VideoFormatConverter.convert_video(
            input_path, output_path
        )

        assert result is False

    @patch("backend.src.core.video_converter.os.remove")
    @patch("backend.src.core.video_converter.subprocess.Popen")
    def test_delete_original_success_ffmpeg(
        self, mock_popen, mock_remove, sample_video, output_dir
    ):
        """Test original file is deleted after successful FFmpeg conversion."""
        input_path = sample_video
        output_path = os.path.join(output_dir, "output.avi")

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process

        result = VideoFormatConverter.convert_video(
            input_path, output_path, delete=True
        )

        assert result is True
        mock_remove.assert_called_with(input_path)

    @patch("backend.src.core.video_converter.subprocess.Popen")
    def test_convert_video_with_aspect_ratio(
        self, mock_popen, sample_video, output_dir
    ):
        """Test conversion with target aspect ratio and modes."""
        input_path = sample_video
        output_path = os.path.join(output_dir, "output.avi")

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process

        # Test crop mode
        result = VideoFormatConverter.convert_video(
            input_path, output_path, aspect_ratio=1.77, ar_mode="crop"
        )
        assert result is True
        cmd_args = mock_popen.call_args[0][0]
        assert "-vf" in cmd_args
        # Look for crop filter
        vf_idx = cmd_args.index("-vf")
        assert "crop" in cmd_args[vf_idx + 1]

        # Test pad mode
        result = VideoFormatConverter.convert_video(
            input_path, output_path, aspect_ratio=1.77, ar_mode="pad"
        )
        assert result is True
        cmd_args = mock_popen.call_args[0][0]
        vf_idx = cmd_args.index("-vf")
        assert "pad" in cmd_args[vf_idx + 1]

        # Test stretch mode
        result = VideoFormatConverter.convert_video(
            input_path, output_path, aspect_ratio=1.77, ar_mode="stretch"
        )
        assert result is True
        cmd_args = mock_popen.call_args[0][0]
        vf_idx = cmd_args.index("-vf")
        assert "scale" in cmd_args[vf_idx + 1]

    @patch("backend.src.core.video_converter.subprocess.Popen")
    def test_convert_to_gif_success(
        self, mock_popen, sample_video, output_dir
    ):
        """Test successful conversion to GIF."""
        input_path = sample_video
        output_path = os.path.join(output_dir, "output.gif")

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process

        result = VideoFormatConverter.convert_to_gif(
            input_path, output_path
        )

        assert result is True
        mock_popen.assert_called_once()
        cmd_args = mock_popen.call_args[0][0]
        assert "ffmpeg" in cmd_args
        assert "-filter_complex" in cmd_args

    @patch("backend.src.core.video_converter.subprocess.Popen")
    def test_convert_to_gif_failure(
        self, mock_popen, sample_video, output_dir
    ):
        """Test failure in GIF conversion."""
        input_path = sample_video
        output_path = os.path.join(output_dir, "output.gif")

        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process

        result = VideoFormatConverter.convert_to_gif(
            input_path, output_path
        )

        assert result is False

    @patch("backend.src.core.video_converter.os.remove")
    @patch("backend.src.core.video_converter.subprocess.Popen")
    def test_convert_to_gif_delete(
        self, mock_popen, mock_remove, sample_video, output_dir
    ):
        """Test input file is deleted after successful GIF conversion."""
        input_path = sample_video
        output_path = os.path.join(output_dir, "output.gif")

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process

        result = VideoFormatConverter.convert_to_gif(
            input_path, output_path, delete=True
        )

        assert result is True
        mock_remove.assert_called_once_with(input_path)


if __name__ == "__main__":
    pytest.main([__file__])
