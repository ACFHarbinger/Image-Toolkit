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
        cuts_ms: Optional[list] = None,
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
        self.cuts_ms = cuts_ms or []
        self.signals = GifWorkerSignals()
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def _get_keep_regions(self, t_start: float, t_end: float):
        if not self.cuts_ms:
            return [(0.0, t_end - t_start)]
        
        sorted_cuts = sorted([(max(t_start, c[0]/1000.0), min(t_end, c[1]/1000.0)) for c in self.cuts_ms])
        merged_cuts = []
        for c in sorted_cuts:
            if c[0] >= c[1]:
                continue
            if not merged_cuts:
                merged_cuts.append(c)
            else:
                last = merged_cuts[-1]
                if c[0] <= last[1]:
                    merged_cuts[-1] = (last[0], max(last[1], c[1]))
                else:
                    merged_cuts.append(c)
                    
        keep = []
        current = t_start
        for c_start, c_end in merged_cuts:
            if c_start > current:
                keep.append((current - t_start, c_start - t_start))
            current = max(current, c_end)
        
        if current < t_end:
            keep.append((current - t_start, t_end - t_start))
            
        return keep

    def run(self):
        if self._is_cancelled:
            return

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
                # filters: select -> fps -> scale -> split -> [palettegen/paletteuse]

                filter_chain = []
                
                keep_regions = self._get_keep_regions(t_start, t_end)
                if self.cuts_ms and keep_regions:
                    select_expr = "+".join([f"between(t,{r[0]},{r[1]})" for r in keep_regions])
                    filter_chain.append(f"select='{select_expr}'")
                    filter_chain.append("setpts=N/FRAME_RATE/TB")
                
                filter_chain.append(f"fps={self.fps}")
                
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
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    text=True,
                )

                while process.poll() is None:
                    if self._is_cancelled:
                        process.terminate()
                        self.signals.error.emit("Extraction cancelled by user.")
                        return
                    import time
                    time.sleep(0.5)

                if process.returncode != 0:
                    raise RuntimeError(
                        f"FFmpeg failed with return code {process.returncode}\n{process.stderr.read()}"
                    )

                self.signals.progress.emit(100)
                self.signals.finished.emit(self.output_path)

            except Exception as e:
                self.signals.error.emit(f"FFmpeg Error: {str(e)}")
            return

        try:
            from moviepy.editor import concatenate_videoclips
            self.signals.progress.emit(10)
            
            base_clip = VideoFileClip(self.video_path).subclip(t_start, t_end)
            keep_regions = self._get_keep_regions(t_start, t_end)
            
            if self.cuts_ms and keep_regions:
                clips = []
                for start_sec, end_sec in keep_regions:
                    if end_sec > start_sec:
                        clips.append(base_clip.subclip(start_sec, end_sec))
                if clips:
                    clip = concatenate_videoclips(clips)
                else:
                    clip = base_clip
            else:
                clip = base_clip

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
