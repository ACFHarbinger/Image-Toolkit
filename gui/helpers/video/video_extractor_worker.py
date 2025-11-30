import os

from typing import Optional, Tuple
from moviepy.editor import VideoFileClip
from PySide6.QtCore import QObject, Signal, QRunnable
from moviepy.audio.io.AudioFileClip import AudioFileClip


class VideoWorkerSignals(QObject):
    finished = Signal(str)
    error = Signal(str)


class VideoExtractionWorker(QRunnable):
    def __init__(self, video_path: str, start_ms: int, end_ms: int, output_path: str, target_size: Optional[Tuple[int, int]] = None, mute_audio: bool = False):
        super().__init__()
        self.video_path = video_path
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.output_path = output_path
        self.target_size = target_size
        self.mute_audio = mute_audio 
        self.signals = VideoWorkerSignals()

    def run(self):
        temp_audio_path = 'temp-audio.m4a'
        clip = None
        # Ensure AudioFileClip is accessible if needed
        AudioFileClip_is_available = 'AudioFileClip' in globals() or 'AudioFileClip' in locals()
        
        try:
            t_start = self.start_ms / 1000.0
            t_end = self.end_ms / 1000.0
            
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
                # --- CRITICAL FIX: Use the imported AudioFileClip for pre-decoding ---
                if AudioFileClip_is_available:
                    original_audio_clip = AudioFileClip(self.video_path)
                    clip.audio = original_audio_clip.subclip(t_start, t_end)
                    original_audio_clip.close()
                else:
                    # Fallback if the import failed (unlikely if the user corrects it)
                    print("Warning: AudioFileClip not found for pre-decoding. Reverting to direct write.")
                # ----------------------------------------------------------------------
            
            ffmpeg_params = ['-movflags', 'faststart'] 
            if audio_codec is not None:
                ffmpeg_params.extend(['-b:a', '128k']) 

            clip.write_videofile(
                self.output_path, 
                codec="libx264", 
                audio_codec=audio_codec, 
                temp_audiofile=temp_audio_path,
                remove_temp=True,
                ffmpeg_params=ffmpeg_params,
                verbose=False
            )

            self.signals.finished.emit(self.output_path)
            
        except ImportError:
            self.signals.error.emit("The 'moviepy' library is required to extract video clips.\nPlease install it via: pip install moviepy")
        except Exception as e:
            if os.path.exists(temp_audio_path):
                try: os.remove(temp_audio_path)
                except OSError: pass
            
            error_message = f"Failed to create video (Broken Pipe/Audio Error). Try checking the 'Mute Audio' box.\nDetails: {e}"
            self.signals.error.emit(error_message)
        finally:
             if clip:
                clip.close()
             if os.path.exists(temp_audio_path):
                try: os.remove(temp_audio_path)
                except OSError: pass