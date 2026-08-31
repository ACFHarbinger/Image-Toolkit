import contextlib
import os
import subprocess
import tempfile
import time
from typing import Optional, Tuple, Union

from moviepy.editor import VideoFileClip
from PySide6.QtCore import QObject, QRunnable, Signal

from gui.src.helpers.gc_safe import gc_disabled_run


class _Cancelled(Exception):
    """Raised inside the worker when the user cancels mid-ffmpeg."""


class _GifWorkerSignals(QObject):
    progress = Signal(int, int)  # (percent, 100) — §5.9 Option C; no natural item count
    finished = Signal(str)
    error = Signal(str)


class GifCreationWorker(QRunnable):
    def __init__(
        self,
        video_path: str,
        start_ms: int,
        end_ms: int,
        output_path: str,
        target_size: Optional[Union[Tuple[int | str, int | str], str]] = None,
        fps: int = 15,
        use_ffmpeg: bool = False,
        speed: float = 1.0,
        cuts_ms: Optional[list] = None,
        encoder_threads: int = 0,
        max_colors: int = 256,
        fps_clamp: int = 0,
    ):
        super().__init__()
        self.video_path = video_path
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.output_path = output_path
        self.target_size = target_size
        self.fps = min(fps, fps_clamp) if fps_clamp > 0 else fps
        self.use_ffmpeg = use_ffmpeg
        self.speed = speed
        self.cuts_ms = cuts_ms or []
        self.encoder_threads = max(0, int(encoder_threads))
        self.max_colors = max(16, min(256, int(max_colors)))
        self.fps_clamp = max(0, int(fps_clamp))
        self.signals = _GifWorkerSignals()
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

    def _run_ffmpeg(self, cmd: list, phase: str) -> None:
        """Run one ffmpeg pass without the stderr-PIPE deadlock.

        The old code kept ``stderr=PIPE`` and never drained it until the
        process exited, so a long encode that filled the ~64 KB pipe buffer
        hung forever. stderr goes to a temp file instead (already quietened
        to ``-loglevel error``); it is read back only on failure.
        """
        from gui.src.helpers.video.video_thumbnailer import media_backend_spawn_guard

        with tempfile.TemporaryFile(mode="w+") as errf:
            with media_backend_spawn_guard():
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=errf,
                    stdin=subprocess.DEVNULL,
                )
            while proc.poll() is None:
                if self._is_cancelled:
                    proc.terminate()
                    with contextlib.suppress(subprocess.TimeoutExpired):
                        proc.wait(timeout=3)
                    if proc.poll() is None:
                        proc.kill()
                    raise _Cancelled()
                time.sleep(0.3)
            if proc.returncode != 0:
                errf.seek(0)
                tail = errf.read()[-2000:]
                raise RuntimeError(
                    f"ffmpeg {phase} pass failed (code {proc.returncode})\n{tail}"
                )

    @gc_disabled_run
    def run(self):  # noqa: C901
        if self._is_cancelled:
            return

        # Convert ms to seconds
        t_start = self.start_ms / 1000.0
        t_end = self.end_ms / 1000.0

        if self.use_ffmpeg:
            palette_path = None
            try:
                duration = t_end - t_start

                # Shared select/fps/scale/speed chain (everything except the
                # palette step). Built once, reused by both passes.
                chain = []
                keep_regions = self._get_keep_regions(t_start, t_end)
                if self.cuts_ms and keep_regions:
                    select_expr = "+".join(
                        [f"between(t,{r[0]},{r[1]})" for r in keep_regions]
                    )
                    chain.append(f"select='{select_expr}'")
                    chain.append("setpts=N/FRAME_RATE/TB")
                chain.append(f"fps={self.fps}")
                if self.target_size:
                    w, h = self.target_size
                    chain.append(f"scale={w}:{h}:flags=lanczos")
                if self.speed != 1.0:
                    chain.append(f"setpts={1.0 / self.speed}*PTS")
                base_filters = ",".join(chain)

                fd, palette_path = tempfile.mkstemp(prefix="itk_gifpalette_", suffix=".png")
                os.close(fd)

                seek = ["-ss", str(t_start), "-t", str(duration)]
                common = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-nostats"]
                if self.encoder_threads > 0:
                    common.extend(["-threads", str(self.encoder_threads)])

                # Two-pass palette: pass 1 streams the frames through
                # `palettegen` writing only a max_colors PNG; pass 2 streams
                # them again applying it. The old single-pass
                # `split[s0][s1];…palettegen…paletteuse` forced ffmpeg to
                # buffer the *entire* scaled stream in RAM between the two
                # branches — O(frames) memory for a long/high-res range.
                pass1 = [
                    *common, *seek, "-i", self.video_path,
                    "-vf", f"{base_filters},palettegen=max_colors={self.max_colors}:stats_mode=diff",
                    palette_path,
                ]
                pass2 = [
                    *common, *seek, "-i", self.video_path, "-i", palette_path,
                    "-lavfi", f"{base_filters}[x];[x][1:v]paletteuse=dither=bayer",
                    self.output_path,
                ]

                self.signals.progress.emit(0, 100)
                self._run_ffmpeg(pass1, "palette")
                self.signals.progress.emit(50, 100)
                self._run_ffmpeg(pass2, "encode")
                self.signals.progress.emit(100, 100)
                self.signals.finished.emit(self.output_path)

            except _Cancelled:
                self.signals.error.emit("Extraction cancelled by user.")
            except Exception as e:
                self.signals.error.emit(f"FFmpeg Error: {str(e)}")
            finally:
                if palette_path and os.path.exists(palette_path):
                    with contextlib.suppress(OSError):
                        os.remove(palette_path)
            return

        base_clip = None
        clip = None
        try:
            from moviepy.editor import concatenate_videoclips
            self.signals.progress.emit(10, 100)

            base_clip = VideoFileClip(self.video_path).subclip(t_start, t_end)
            keep_regions = self._get_keep_regions(t_start, t_end)

            if self.cuts_ms and keep_regions:
                clips = []
                for start_sec, end_sec in keep_regions:
                    if end_sec > start_sec:
                        clips.append(base_clip.subclip(start_sec, end_sec))
                clip = concatenate_videoclips(clips) if clips else base_clip
            else:
                clip = base_clip

            # Resize if target_size is provided (width, height)
            if self.target_size:
                clip = clip.resize(newsize=self.target_size) # pyrefly: ignore [missing-attribute]

            if self.speed != 1.0:
                clip = clip.speedx(self.speed) # pyrefly: ignore [missing-attribute]

            self.signals.progress.emit(30, 100)
            write_kwargs = {"fps": self.fps, "logger": None}
            if self.encoder_threads > 0:
                write_kwargs["threads"] = self.encoder_threads
            clip.write_gif(
                self.output_path, **write_kwargs
            )  # logger=None to avoid stdout clutter

            self.signals.progress.emit(100, 100)
            self.signals.finished.emit(self.output_path)

        except ImportError:
            self.signals.error.emit(
                "The 'moviepy' library is required to create GIFs.\nPlease install it via: pip install moviepy"
            )
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            # MoviePy leaves an ffmpeg reader subprocess + file handle open per
            # clip until .close(); the old code never closed either.
            for _c in (clip, base_clip):
                if _c is not None:
                    with contextlib.suppress(Exception):
                        _c.close()
