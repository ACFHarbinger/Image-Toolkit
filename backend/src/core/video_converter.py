import os
import base
from typing import Optional, List, Callable
from ..utils.definitions import SUPPORTED_VIDEO_FORMATS

class VideoFormatConverter:
    """
    A wrapper around the Rust 'base' extension for converting video formats using FFmpeg.
    """

    @classmethod
    def convert_video(
        cls,
        input_path: str,
        output_path: str,
        engine: str = "auto", # Kept for API compatibility, but ignored (always ffmpeg)
        delete: bool = False,
    ) -> bool:
        """
        Converts a video file using the Rust backend (FFmpeg).
        """
        if not os.path.exists(input_path):
            print(f"Error: Input file '{input_path}' not found.")
            return False

        print(f"Converting '{os.path.basename(input_path)}' to '{os.path.basename(output_path)}' using Native Backend (ffmpeg)...")

        try:
            return base.convert_video(input_path, output_path, delete)
        except Exception as e:
            print(f"Error converting video: {e}")
            return False
