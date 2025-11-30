from typing import Optional, Tuple
from moviepy.editor import VideoFileClip
from PySide6.QtCore import QObject, Signal, QRunnable


class GifWorkerSignals(QObject):
    finished = Signal(str)
    error = Signal(str)


class GifCreationWorker(QRunnable):
    def __init__(self, video_path: str, start_ms: int, end_ms: int, output_path: str, target_size: Optional[Tuple[int, int]] = None, fps: int = 15):
        super().__init__()
        self.video_path = video_path
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.output_path = output_path
        self.target_size = target_size
        self.fps = fps
        self.signals = GifWorkerSignals()

    def run(self):
        try:
            # Convert ms to seconds
            t_start = self.start_ms / 1000.0
            t_end = self.end_ms / 1000.0
            
            clip = VideoFileClip(self.video_path).subclip(t_start, t_end)
            
            # Resize if target_size is provided (width, height)
            if self.target_size:
                # moviepy resize often prefers just width or just height to maintain aspect ratio,
                # or a tuple. If we pass the full tuple from our UI (e.g. 1920, 1080),
                # moviepy attempts to force that size.
                clip = clip.resize(newsize=self.target_size)
            
            clip.write_gif(self.output_path, fps=self.fps)
            
            self.signals.finished.emit(self.output_path)
            
        except ImportError:
            self.signals.error.emit("The 'moviepy' library is required to create GIFs.\nPlease install it via: pip install moviepy")
        except Exception as e:
            self.signals.error.emit(str(e))