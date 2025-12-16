import os
import sys
import pytest

from pathlib import Path
from unittest.mock import patch, MagicMock

# Adjust path to find src (if running directly or via different runner)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.core.video_converter import VideoFormatConverter


# Use pytest-style class for easy fixture access
class TestVideoFormatConverter:
    
    @patch("src.core.video_converter.subprocess.run")
    def test_convert_with_ffmpeg_success(self, mock_subprocess, sample_video, output_dir):
        """Test successful conversion using FFmpeg engine."""
        input_path = sample_video
        output_path = os.path.join(output_dir, "output.avi")
        
        # Mock successful subprocess
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        result = VideoFormatConverter.convert_video(
            input_path, output_path, engine="ffmpeg"
        )
        
        assert result is True
        mock_subprocess.assert_called_with(
            ["ffmpeg", "-y", "-i", input_path, output_path],
            stdout=-1, stderr=-1, stdin=-3, text=True
        )

    @patch("src.core.video_converter.subprocess.run")
    def test_convert_with_ffmpeg_failure(self, mock_subprocess, sample_video, output_dir):
        """Test failure in FFmpeg conversion."""
        input_path = sample_video
        output_path = os.path.join(output_dir, "output.avi")
        
        # Mock failed subprocess
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stderr = "Some FFmpeg error"
        mock_subprocess.return_value = mock_process

        result = VideoFormatConverter.convert_video(
            input_path, output_path, engine="ffmpeg"
        )
        
        assert result is False

    @patch("src.core.video_converter.VideoFileClip")
    def test_convert_with_moviepy_success(self, mock_clip_cls, sample_video, output_dir):
        """Test successful conversion using MoviePy engine."""
        input_path = sample_video
        output_path = os.path.join(output_dir, "output.avi")
        
        mock_clip = MagicMock()
        mock_clip_cls.return_value = mock_clip

        result = VideoFormatConverter.convert_video(
            input_path, output_path, engine="moviepy"
        )
        
        assert result is True
        mock_clip.write_videofile.assert_called_once()
        mock_clip.close.assert_called_once()

    @patch("src.core.video_converter.VideoFileClip")
    def test_convert_with_moviepy_failure(self, mock_clip_cls, sample_video, output_dir):
        """Test failure in MoviePy conversion."""
        input_path = sample_video
        output_path = os.path.join(output_dir, "output.avi")
        
        # Mock exception
        mock_clip_cls.side_effect = Exception("MoviePy Error")

        result = VideoFormatConverter.convert_video(
            input_path, output_path, engine="moviepy"
        )
        
        assert result is False

    @patch("src.core.video_converter.subprocess.run")
    def test_auto_engine_ffmpeg_available(self, mock_subprocess, sample_video, output_dir):
        """Test 'auto' engine selects FFmpeg when available."""
        input_path = sample_video
        output_path = os.path.join(output_dir, "output.avi")

        # Mock calls
        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            # Version check or conversion
            return MagicMock(returncode=0)
            
        mock_subprocess.side_effect = subprocess_side_effect

        result = VideoFormatConverter.convert_video(
            input_path, output_path, engine="auto"
        )
        
        assert result is True
        # Check that it tried to run ffmpeg
        args, _ = mock_subprocess.call_args 
        assert "-i" in args[0]

    @patch("src.core.video_converter.subprocess.run")
    @patch("src.core.video_converter.VideoFileClip")
    def test_auto_engine_ffmpeg_missing(self, mock_clip, mock_subprocess, sample_video, output_dir):
        """Test 'auto' engine falls back to MoviePy when FFmpeg is missing."""
        input_path = sample_video
        output_path = os.path.join(output_dir, "output.avi")

        # 1. Version check fails
        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "-version" in cmd:
                raise FileNotFoundError("No ffmpeg")
            return MagicMock(returncode=0)
            
        mock_subprocess.side_effect = subprocess_side_effect
        
        # MoviePy setup
        mock_instance = MagicMock()
        mock_clip.return_value = mock_instance

        result = VideoFormatConverter.convert_video(
            input_path, output_path, engine="auto"
        )
        
        assert result is True
        # Verify moviepy was used
        mock_clip.assert_called()

    def test_input_file_not_found(self, output_dir):
        """Test failure when input file does not exist."""
        # Using a guaranteed non-existent path
        input_path = "/nonexistent/video.mp4"
        output_path = os.path.join(output_dir, "output.avi")
        
        result = VideoFormatConverter.convert_video(
            input_path, output_path, engine="auto"
        )
        
        assert result is False

    @patch("src.core.video_converter.os.remove")
    @patch("src.core.video_converter.subprocess.run")
    def test_delete_original_success_ffmpeg(self, mock_subprocess, mock_remove, sample_video, output_dir):
        """Test original file is deleted after successful FFmpeg conversion."""
        input_path = sample_video
        output_path = os.path.join(output_dir, "output.avi")
        
        mock_subprocess.return_value = MagicMock(returncode=0)

        result = VideoFormatConverter.convert_video(
            input_path, output_path, engine="ffmpeg", delete=True
        )
        
        assert result is True
        mock_remove.assert_called_with(input_path)

if __name__ == "__main__":
    pytest.main([__file__])
