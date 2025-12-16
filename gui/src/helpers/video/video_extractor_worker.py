import os
import subprocess

from typing import Optional, Tuple
from moviepy.editor import VideoFileClip
from PySide6.QtCore import QObject, Signal, QRunnable

# Ensure this import matches your MoviePy version
try:
    from moviepy.audio.io.AudioFileClip import AudioFileClip
except ImportError:
    from moviepy.editor import AudioFileClip


class VideoWorkerSignals(QObject):
    finished = Signal(str)
    error = Signal(str)


class VideoExtractionWorker(QRunnable):
    def __init__(
        self,
        video_path: str,
        start_ms: int,
        end_ms: int,
        output_path: str,
        target_size: Optional[Tuple[int, int]] = None,
        mute_audio: bool = False,
        use_ffmpeg: bool = False,
    ):
        super().__init__()
        self.video_path = video_path
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.output_path = output_path
        self.target_size = target_size
        self.mute_audio = mute_audio
        self.use_ffmpeg = use_ffmpeg
        self.signals = VideoWorkerSignals()

    def run(self):
        t_start = self.start_ms / 1000.0
        t_end = self.end_ms / 1000.0

        if self.use_ffmpeg:
            try:
                # Build FFmpeg command
                # Use fast seeking (input option) for performance.
                # Since we are re-encoding (libx264), this is still frame-accurate.
                
                duration = t_end - t_start
                cmd = ["ffmpeg", "-y"]
                
                # Input with fast seek
                cmd.extend(["-ss", str(t_start)])
                cmd.extend(["-t", str(duration)])
                cmd.extend(["-i", self.video_path])
                
                # Filters (Scaling)
                filters = []
                if self.target_size:
                    w, h = self.target_size
                    filters.append(f"scale={w}:{h}")
                
                if filters:
                    cmd.extend(["-vf", ",".join(filters)])
                
                # Codecs & Audio
                cmd.extend(["-c:v", "libx264", "-movflags", "+faststart"])
                
                if self.mute_audio:
                    cmd.append("-an")
                else:
                    cmd.extend(["-c:a", "aac", "-b:a", "128k"])
                
                cmd.append(self.output_path)
                
                print(f"FFmpeg Video CMD: {cmd}")
                
                # Run command
                # capture_output to hide console window on some OS, but also check errors
                process = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    text=True
                )
                
                if process.returncode != 0:
                    raise RuntimeError(f"FFmpeg failed with return code {process.returncode}\n{process.stderr}")
                    
                self.signals.finished.emit(self.output_path)

            except Exception as e:
                self.signals.error.emit(f"FFmpeg Error: {str(e)}")
            return

        # --- MoviePy Implementation ---
        temp_audio_path = "temp-audio.m4a"
        clip = None
        original_audio_clip = None  # Track the audio resource separately

        try:
            # 1. Load the main clip
            clip = VideoFileClip(self.video_path).subclip(t_start, t_end)

            if self.target_size:
                clip = clip.resize(newsize=self.target_size)

            audio_codec = "aac"

            if self.mute_audio or clip.audio is None:
                clip.audio = None
                audio_codec = None
                if os.path.exists(temp_audio_path):
                    os.remove(temp_audio_path)
            else:
                # --- FIX: Open AudioFileClip but DO NOT close it immediately ---
                # We keep original_audio_clip alive so write_videofile can read from it.
                try:
                    original_audio_clip = AudioFileClip(self.video_path)
                    clip.audio = original_audio_clip.subclip(t_start, t_end)
                except Exception as audio_e:
                    print(f"Warning: Failed to separate audio stream: {audio_e}")
                    # Fallback: use default clip audio (might fail with Broken Pipe on some systems)
                    pass
                # -------------------------------------------------------------

            ffmpeg_params = ["-movflags", "faststart"]
            if audio_codec is not None:
                ffmpeg_params.extend(["-b:a", "128k"])

            clip.write_videofile(
                self.output_path,
                codec="libx264",
                audio_codec=audio_codec,
                temp_audiofile=temp_audio_path,
                remove_temp=True,
                ffmpeg_params=ffmpeg_params,
                verbose=False,
            )

            self.signals.finished.emit(self.output_path)

        except ImportError:
            self.signals.error.emit(
                "The 'moviepy' library is required to extract video clips.\nPlease install it via: pip install moviepy"
            )
        except Exception as e:
            if os.path.exists(temp_audio_path):
                try:
                    os.remove(temp_audio_path)
                except OSError:
                    pass

            error_message = f"Failed to create video. Try checking the 'Mute Audio' box if this persists.\nDetails: {e}"
            self.signals.error.emit(error_message)
        finally:
            # Clean up resources in the correct order
            if original_audio_clip:
                original_audio_clip.close()
            if clip:
                clip.close()
            if os.path.exists(temp_audio_path):
                try:
                    os.remove(temp_audio_path)
                except OSError:
                    pass
