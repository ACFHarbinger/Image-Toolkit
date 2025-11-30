from typing import Optional, Tuple
from PySide6.QtCore import QObject, Signal, QRunnable


class VideoWorkerSignals(QObject):
    finished = Signal(str)
    error = Signal(str)


class VideoExtractionWorker(QRunnable):
    def __init__(self, video_path: str, start_ms: int, end_ms: int, output_path: str, target_size: Optional[Tuple[int, int]] = None):
        super().__init__()
        self.video_path = video_path
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.output_path = output_path
        self.target_size = target_size
        self.signals = VideoWorkerSignals()

    def run(self):
        try:
            from moviepy.editor import VideoFileClip
            
            t_start = self.start_ms / 1000.0
            t_end = self.end_ms / 1000.0
            
            clip = VideoFileClip(self.video_path).subclip(t_start, t_end)
            
            if self.target_size:
                clip = clip.resize(newsize=self.target_size)
            
            # Write video file using H.264 codec (standard for mp4)
            # audio_codec="aac" ensures audio is included
            clip.write_videofile(self.output_path, codec="libx264", audio_codec="aac", temp_audiofile='temp-audio.m4a', remove_temp=True)
            self.signals.finished.emit(self.output_path)
            
        except ImportError:
            self.signals.error.emit("The 'moviepy' library is required to extract video clips.\nPlease install it via: pip install moviepy")
        except Exception as e:
            self.signals.error.emit(str(e))