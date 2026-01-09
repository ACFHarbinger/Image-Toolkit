import os
import subprocess
from typing import Optional, Callable

class VideoFormatConverter:
    """
    Utilities for converting video formats using FFmpeg (via subprocess).
    """

    @classmethod
    def convert_video(
        cls,
        input_path: str,
        output_path: str,
        engine: str = "auto",
        delete: bool = False,
        process_callback: Optional[Callable[[subprocess.Popen], None]] = None
    ) -> bool:
        """
        Converts a video file using FFmpeg via subprocess.
        Allows for safe cancellation via process_callback.
        """
        if not os.path.exists(input_path):
            print(f"Error: Input file '{input_path}' not found.")
            return False

        print(f"Converting '{os.path.basename(input_path)}' to '{os.path.basename(output_path)}' using Native Backend (ffmpeg)...")

        cmd = [
            "ffmpeg",
            "-y",  # Overwrite
            "-i", input_path,
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "medium",
            "-c:a", "aac",
            output_path
        ]

        process = None
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            
            if process_callback:
                process_callback(process)

            process.wait()
            success = (process.returncode == 0)

            if success and delete:
                try:
                    os.remove(input_path)
                except Exception as e:
                    print(f"Failed to delete original file: {e}")

            return success

        except Exception as e:
            print(f"Error converting video: {e}")
            return False
        finally:
            pass # Popen object cleanup is handled by GC or explicit termination externally

