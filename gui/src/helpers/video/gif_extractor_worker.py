import subprocess

from typing import Optional, Tuple
from moviepy.editor import VideoFileClip
from PySide6.QtCore import QObject, Signal, QRunnable


class GifWorkerSignals(QObject):
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)


class GifCreationWorker(QRunnable):
    def __init__(
        self,
        video_path: str,
        start_ms: int,
        end_ms: int,
        output_path: str,
        target_size: Optional[Tuple[int, int]] = None,
        fps: int = 15,
        use_ffmpeg: bool = False,
        speed: float = 1.0,
    ):
        super().__init__()
        self.video_path = video_path
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.output_path = output_path
        self.target_size = target_size
        self.fps = fps
        self.use_ffmpeg = use_ffmpeg
        self.speed = speed
        self.signals = GifWorkerSignals()

    def run(self):
        # Convert ms to seconds
        t_start = self.start_ms / 1000.0
        t_end = self.end_ms / 1000.0

        if self.use_ffmpeg:
            try:
                duration = t_end - t_start
                cmd = ["ffmpeg", "-y"]

                # Fast seek (input option)
                cmd.extend(["-ss", str(t_start)])
                cmd.extend(["-t", str(duration)])
                cmd.extend(["-i", self.video_path])

                # Construct complex filter for high quality GIF (palettegen + paletteuse)
                # filters: fps -> scale -> split -> [palettegen/paletteuse]

                filter_chain = [f"fps={self.fps}"]
                if self.target_size:
                    w, h = self.target_size
                    filter_chain.append(f"scale={w}:{h}:flags=lanczos")

                # Speed
                if self.speed != 1.0:
                    pts_mult = 1.0 / self.speed
                    filter_chain.append(f"setpts={pts_mult}*PTS")

                # Join base filters
                base_filters = ",".join(filter_chain)

                # Add palette generation and usage
                complex_filter = (
                    f"{base_filters},split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
                )

                cmd.extend(["-vf", complex_filter])
                cmd.append(self.output_path)

                print(f"FFmpeg CMD: {cmd}")

                self.signals.progress.emit(0)
                process = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    text=True,
                )

                if process.returncode != 0:
                    raise RuntimeError(
                        f"FFmpeg failed with return code {process.returncode}\n{process.stderr}"
                    )

                self.signals.progress.emit(100)
                self.signals.finished.emit(self.output_path)

            except Exception as e:
                self.signals.error.emit(f"FFmpeg Error: {str(e)}")
            return

        # --- MoviePy Implementation ---
        try:
            self.signals.progress.emit(10)
            clip = VideoFileClip(self.video_path).subclip(t_start, t_end)

            # Resize if target_size is provided (width, height)
            if self.target_size:
                clip = clip.resize(newsize=self.target_size)

            if self.speed != 1.0:
                clip = clip.speedx(self.speed)

            self.signals.progress.emit(30)
            clip.write_gif(
                self.output_path, fps=self.fps, logger=None
            )  # logger=None to avoid stdout clutter

            self.signals.progress.emit(100)
            self.signals.finished.emit(self.output_path)

        except ImportError:
            self.signals.error.emit(
                "The 'moviepy' library is required to create GIFs.\nPlease install it via: pip install moviepy"
            )
        except Exception as e:
            self.signals.error.emit(str(e))
