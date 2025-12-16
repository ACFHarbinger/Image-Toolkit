import os
import subprocess
from typing import Optional, List, Callable
from moviepy.editor import VideoFileClip
from ..utils.definitions import SUPPORTED_VIDEO_FORMATS

class VideoFormatConverter:
    """
    A tool for converting video formats using FFmpeg (via subprocess) or MoviePy.
    """

    @staticmethod
    def _convert_with_ffmpeg(
        input_path: str, output_path: str, delete: bool = False
    ) -> bool:
        """
        Converts video using FFmpeg subprocess.
        """
        try:
            # -y to overwrite output files without asking
            cmd = ["ffmpeg", "-y", "-i", input_path, output_path]
            
            # Use subprocess to run the command
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True
            )

            if process.returncode != 0:
                print(f"FFmpeg Error: {process.stderr}")
                return False

            if delete:
                os.remove(input_path)
            
            return True
        except Exception as e:
            print(f"FFmpeg execution failed: {e}")
            return False

    @staticmethod
    def _convert_with_moviepy(
        input_path: str, output_path: str, delete: bool = False
    ) -> bool:
        """
        Converts video using MoviePy.
        """
        try:
            clip = VideoFileClip(input_path)
            # MoviePy uses the extension of output_path to determine format
            clip.write_videofile(
                output_path, 
                codec="libx264" if output_path.endswith(".mp4") else None, 
                verbose=False, 
                logger=None
            )
            clip.close()

            if delete:
                os.remove(input_path)
            
            return True
        except Exception as e:
            print(f"MoviePy conversion failed: {e}")
            return False

    @classmethod
    def convert_video(
        cls,
        input_path: str,
        output_path: str,
        engine: str = "auto",
        delete: bool = False,
    ) -> bool:
        """
        Converts a video file to the format specified by the output_path extension.
        
        Args:
            input_path: Path to the source video.
            output_path: Destination path (must include extension).
            engine: "auto", "ffmpeg", or "moviepy".
            delete: Whether to delete the original file after success.
        """
        if not os.path.exists(input_path):
            print(f"Error: Input file '{input_path}' not found.")
            return False

        # Validate engine preference
        engine = engine.lower()
        if engine not in ["auto", "ffmpeg", "moviepy"]:
            print(f"Warning: Unknown engine '{engine}'. Defaulting to 'auto'.")
            engine = "auto"

        # Determine strategy
        use_ffmpeg = False
        
        if engine == "ffmpeg":
            use_ffmpeg = True
        elif engine == "moviepy":
            use_ffmpeg = False
        else: # auto
            # Simple check if ffmpeg is available in path
            # (In a real scenario we might cache this check)
            try:
                subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                use_ffmpeg = True
            except FileNotFoundError:
                use_ffmpeg = False

        print(f"Converting '{os.path.basename(input_path)}' to '{os.path.basename(output_path)}' using {'FFmpeg' if use_ffmpeg else 'MoviePy'}...")

        success = False
        if use_ffmpeg:
            success = cls._convert_with_ffmpeg(input_path, output_path, delete)
            # Fallback to MoviePy if FFmpeg fails in auto mode?
            # For now, if user selected auto and ffmpeg exists but fails, 
            # we might want to fail or try moviepy. Let's stick to fail for simplicity unless requested.
        else:
            success = cls._convert_with_moviepy(input_path, output_path, delete)

        if success:
            print(f"Successfully converted.")
        else:
            print(f"Failed to convert video.")

        return success
