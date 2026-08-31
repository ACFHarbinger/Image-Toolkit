import contextlib
import os
import select
import subprocess
import tempfile
from typing import Optional, Tuple, Union

from moviepy.editor import VideoFileClip
from PySide6.QtCore import QObject, QRunnable, Signal

# Ensure this import matches your MoviePy version
try:
    from moviepy.audio.io.AudioFileClip import AudioFileClip
except ImportError:
    from moviepy.editor import AudioFileClip


class _Cancelled(Exception):
    """Raised inside the worker when the user cancels mid-ffmpeg."""


class _VideoWorkerSignals(QObject):
    progress = Signal(int, int)  # (percent, 100) — §5.9 Option C; no natural item count
    finished = Signal(str)
    error = Signal(str)


def _ffmpeg_thread_count(requested: int) -> int:
    """Cap libx264 thread fan-out. 0 (Auto) → min(4, CPUs); never above CPU count."""
    cpus = os.cpu_count() or 2
    if requested <= 0:
        return max(1, min(4, cpus))
    return max(1, min(int(requested), cpus))


def parse_ffmpeg_progress_line(line: str, duration_s: float) -> Optional[int]:
    """Map an ffmpeg ``-progress`` ``out_time_us=`` line to 0–99 percent."""
    if duration_s <= 0:
        return None
    text = line.strip()
    if not text.startswith("out_time_us="):
        return None
    raw = text.split("=", 1)[1]
    if raw in ("N/A", ""):
        return None
    try:
        us = int(raw)
    except ValueError:
        return None
    if us < 0:
        return None
    return int(min(99, max(0, (us / 1_000_000.0) / duration_s * 100)))


class VideoExtractionWorker(QRunnable):
    def __init__(
        self,
        video_path: str,
        start_ms: int,
        end_ms: int,
        output_path: str,
        target_size: Optional[Union[Tuple[int | str, int | str], str]] = None,
        mute_audio: bool = False,
        use_ffmpeg: bool = False,
        speed: float = 1.0,
        cuts_ms: Optional[list] = None,
        encoder_threads: int = 0,
        fps_clamp: int = 0,
    ):
        super().__init__()
        self.video_path = video_path
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.output_path = output_path
        self.target_size = target_size
        self.mute_audio = mute_audio
        self.use_ffmpeg = use_ffmpeg
        self.speed = speed
        self.cuts_ms = cuts_ms or []
        self.encoder_threads = max(0, int(encoder_threads))
        self.fps_clamp = max(0, int(fps_clamp))
        self.signals = _VideoWorkerSignals()
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def _run_ffmpeg(self, cmd: list, duration_s: float = 0.0) -> None:
        """Run ffmpeg without the stderr-PIPE deadlock; parse ``-progress``.

        stderr used to go to ``PIPE`` and was only read after exit, so a
        long encode that filled the ~64 KB pipe buffer hung forever (#484).
        stderr now goes to a temp file (``-loglevel error``); stdout is
        drained for ``out_time_us`` progress lines.
        """
        from gui.src.helpers.video.video_thumbnailer import media_backend_spawn_guard

        last_pct = -1
        with tempfile.TemporaryFile(mode="w+") as errf:
            with media_backend_spawn_guard():
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=errf,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                )
            stdout = proc.stdout
            while True:
                if self._is_cancelled:
                    proc.terminate()
                    with contextlib.suppress(subprocess.TimeoutExpired):
                        proc.wait(timeout=3)
                    if proc.poll() is None:
                        proc.kill()
                    raise _Cancelled()
                if proc.poll() is not None:
                    if stdout is not None:
                        for line in stdout.read().splitlines():
                            pct = parse_ffmpeg_progress_line(line, duration_s)
                            if pct is not None and pct != last_pct:
                                last_pct = pct
                                self.signals.progress.emit(pct, 100)
                    break
                ready, _, _ = select.select([stdout], [], [], 0.2)
                if not ready or stdout is None:
                    continue
                line = stdout.readline()
                if not line:
                    continue
                pct = parse_ffmpeg_progress_line(line, duration_s)
                if pct is not None and pct != last_pct:
                    last_pct = pct
                    self.signals.progress.emit(pct, 100)
            if proc.returncode != 0:
                errf.seek(0)
                tail = errf.read()[-2000:]
                raise RuntimeError(
                    f"FFmpeg failed with return code {proc.returncode}\n{tail}"
                )

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

    def run(self):  # noqa: C901
        if self._is_cancelled:
            return

        t_start = self.start_ms / 1000.0
        t_end = self.end_ms / 1000.0

        if self.use_ffmpeg:
            try:
                # Build FFmpeg command
                # Use fast seeking (input option) for performance.
                # Since we are re-encoding (libx264), this is still frame-accurate.

                keep_regions = self._get_keep_regions(t_start, t_end)
                if self.cuts_ms and keep_regions:
                    kept_duration = sum(r[1] - r[0] for r in keep_regions)
                    if kept_duration <= 0:
                        kept_duration = t_end - t_start
                else:
                    kept_duration = t_end - t_start
                duration = kept_duration / self.speed

                cmd = ["ffmpeg", "-y"]

                # Input with fast seek and duration cap
                cmd.extend(["-ss", str(t_start)])
                cmd.extend(["-t", str(t_end - t_start)])
                cmd.extend(["-i", self.video_path])

                # Filters (Scaling + Speed + Cuts)
                filters = []

                keep_regions = self._get_keep_regions(t_start, t_end)

                # Apply select filter for cuts
                if self.cuts_ms and keep_regions:
                    select_expr = "+".join([f"between(t,{r[0]},{r[1]})" for r in keep_regions])
                    filters.append(f"select='{select_expr}'")
                    filters.append("setpts=N/FRAME_RATE/TB")

                # 1. Scale
                if self.target_size:
                    w, h = self.target_size
                    filters.append(f"scale={w}:{h}")

                # 2. Video Speed: setpts = (1/speed) * PTS
                # e.g., speed=0.5 (slow mo) -> setpts=2.0*PTS
                if self.speed != 1.0:
                    pts_mult = 1.0 / self.speed
                    filters.append(f"setpts={pts_mult}*PTS")

                if self.fps_clamp > 0:
                    filters.append(f"fps=min(fps\\,{self.fps_clamp})")

                if filters:
                    cmd.extend(["-vf", ",".join(filters)])

                # Codecs and Audio
                cmd.extend(["-c:v", "libx264", "-movflags", "+faststart"])
                cmd.extend(["-threads", str(_ffmpeg_thread_count(self.encoder_threads))])

                if self.mute_audio:
                    cmd.append("-an")
                else:
                    # Audio Speed: atempo
                    audio_filters = []

                    if self.cuts_ms and keep_regions:
                        aselect_expr = "+".join([f"between(t,{r[0]},{r[1]})" for r in keep_regions])
                        audio_filters.append(f"aselect='{aselect_expr}'")
                        audio_filters.append("asetpts=N/SR/TB")

                    if self.speed != 1.0:
                        s = self.speed
                        # Handle speeds > 2.0
                        while s > 2.0:
                            audio_filters.append("atempo=2.0")
                            s /= 2.0
                        # Handle speeds < 0.5
                        while s < 0.5:
                            audio_filters.append("atempo=0.5")
                            s /= 0.5
                        # Remainder
                        audio_filters.append(f"atempo={s}")

                    if audio_filters:
                        cmd.extend(["-af", ",".join(audio_filters)])

                    cmd.extend(["-c:a", "aac", "-b:a", "128k"])

                cmd.extend(["-t", str(duration)])
                cmd.append("-shortest")
                cmd.extend(["-progress", "pipe:1", "-nostats", "-loglevel", "error"])
                cmd.append(self.output_path)

                print(f"FFmpeg Video CMD: {cmd}")

                self.signals.progress.emit(0, 100)
                self._run_ffmpeg(cmd, duration)
                self.signals.progress.emit(100, 100)
                self.signals.finished.emit(self.output_path)

            except _Cancelled:
                self.signals.error.emit("Extraction cancelled by user.")
            except Exception as e:
                self.signals.error.emit(f"FFmpeg Error: {str(e)}")
            return

        # --- MoviePy Implementation ---
        temp_audio_path = "temp-audio.m4a"
        clip = None
        base_clip = None
        original_audio_clip = None  # Track the audio resource separately

        try:
            from moviepy.editor import concatenate_videoclips
            self.signals.progress.emit(10, 100)

            base_clip = VideoFileClip(self.video_path)

            if self.mute_audio or base_clip.audio is None:
                base_clip.audio = None
                audio_codec = None
                if os.path.exists(temp_audio_path):
                    os.remove(temp_audio_path)
            else:
                try:
                    original_audio_clip = AudioFileClip(self.video_path)
                    base_clip.audio = original_audio_clip
                except Exception as audio_e:
                    print(f"Warning: Failed to separate audio stream: {audio_e}")
                    pass
                audio_codec = "aac"

            # Apply subclip to start/end range
            subclipped_base = base_clip.subclip(t_start, t_end)
            keep_regions = self._get_keep_regions(t_start, t_end)

            if self.cuts_ms and keep_regions:
                clips = []
                for start_sec, end_sec in keep_regions:
                    if end_sec > start_sec:
                        clips.append(subclipped_base.subclip(start_sec, end_sec))
                clip = concatenate_videoclips(clips) if clips else subclipped_base
            else:
                clip = subclipped_base

            if self.target_size:
                clip = clip.resize(newsize=self.target_size) # pyrefly: ignore [missing-attribute]

            if self.speed != 1.0:
                clip = clip.speedx(self.speed) # pyrefly: ignore [missing-attribute]

            if clip.duration is not None and clip.audio is not None:
                clip.audio = clip.audio.set_duration(clip.duration)

            ffmpeg_params = ["-movflags", "faststart"]
            if audio_codec is not None:
                ffmpeg_params.extend(["-b:a", "128k"])

            self.signals.progress.emit(30, 100)
            write_kwargs = {
                "codec": "libx264",
                "audio_codec": audio_codec,
                "temp_audiofile": temp_audio_path,
                "remove_temp": True,
                "ffmpeg_params": ffmpeg_params,
                "verbose": False,
                "logger": None,
            }
            write_kwargs["threads"] = _ffmpeg_thread_count(self.encoder_threads)
            if self.fps_clamp > 0 and getattr(clip, "fps", None) and clip.fps > self.fps_clamp:
                write_kwargs["fps"] = self.fps_clamp
            clip.write_videofile(
                self.output_path,
                **write_kwargs,
            )

            self.signals.progress.emit(100, 100)
            self.signals.finished.emit(self.output_path)

        except ImportError:
            self.signals.error.emit(
                "The 'moviepy' library is required to extract video clips.\nPlease install it via: pip install moviepy"
            )
        except Exception as e:
            if os.path.exists(temp_audio_path):
                with contextlib.suppress(OSError):
                    os.remove(temp_audio_path)

            error_message = f"Failed to create video. Try checking the 'Mute Audio' box if this persists.\nDetails: {e}"
            self.signals.error.emit(error_message)
        finally:
            # Clean up resources in the correct order
            if original_audio_clip:
                original_audio_clip.close()
            if clip:
                clip.close()
            if base_clip:
                base_clip.close()
            if os.path.exists(temp_audio_path):
                with contextlib.suppress(OSError):
                    os.remove(temp_audio_path)
