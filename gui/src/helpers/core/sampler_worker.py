import contextlib
import logging
import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Union

from middleware.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import Signal

from gui.src.helpers.base import BaseQThreadWorker
from gui.src.helpers.core.config_types import SamplerConfig

logger = logging.getLogger(__name__)

class SamplerWorker(BaseQThreadWorker):
    """Resample images, GIFs, and videos to new dimensions or a scale factor."""

    finished = Signal(object)  # (done:int, message:str), None on failure/cancel
    progress_update = Signal(int, int)  # (ticks, file_count * 100)
    stage_update = Signal(str)

    def __init__(self, config: Union[SamplerConfig, Dict[str, Any]]):
        super().__init__()
        self.config = config
        self._is_cancelled = False
        self._executor: Optional[ThreadPoolExecutor] = None
        self._process_lock = threading.Lock()
        self._progress_lock = threading.Lock()
        self._file_ticks: Dict[int, int] = {}
        self._active_procs: set = set()

    def cancel(self):
        self._is_cancelled = True
        self.requestInterruption()
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
        with self._process_lock:
            for p in list(self._active_procs):
                with contextlib.suppress(Exception):
                    p.terminate()
            self._active_procs.clear()

    def stop(self):
        self.cancel()

    def _execute(self) -> object:  # noqa: C901
        try:
            files: List[str] = self.config.get("files_to_process", [])
            if not files:
                self.error.emit("No files to resample.")
                return

            total = len(files)
            done = 0
            failures: List[str] = []
            use_multicore = self.config.get("use_multicore", True)

            with self._progress_lock:
                self._file_ticks.clear()
            self.progress_update.emit(0, total * 100)

            if use_multicore and total > 1:
                max_w = min(os.cpu_count() or 1, 8)
                self._executor = ThreadPoolExecutor(max_workers=max_w)
                futures = {
                    self._executor.submit(self._resample_one, f, i, total): i
                    for i, f in enumerate(files)
                    if not self._is_cancelled
                }
                for future in as_completed(futures):
                    file_index = futures[future]
                    if self._is_cancelled:
                        break
                    try:
                        if future.result():
                            done += 1
                    except Exception as exc:
                        failures.append(str(exc))
                    self._publish_ticks(file_index, total, 100, None)
                self._executor.shutdown(wait=True)
                self._executor = None
            else:
                for i, f in enumerate(files):
                    if self._is_cancelled:
                        break
                    try:
                        if self._resample_one(f, i, total):
                            done += 1
                    except Exception as exc:
                        failures.append(str(exc))
                    self._publish_ticks(i, total, 100, None)

            if self._is_cancelled:
                return (done, "**Resampling Cancelled**")
            elif failures:
                msg = f"Processed {done}/{total} files. {len(failures)} error(s)."
                if failures:
                    msg += "\n\nFirst error: " + failures[0]
                return (done, msg)
            else:
                return (done, f"Resampled {done} file(s) successfully!")

        except Exception as exc:
            self.progress_update.emit(0, 0)
            self.error.emit(str(exc))
        finally:
            if self._executor:
                self._executor.shutdown(wait=False)

    # ------------------------------------------------------------------
    # Per-file dispatch
    # ------------------------------------------------------------------

    def _resample_one(self, input_path: str, idx: int, total: int) -> bool:
        if self._is_cancelled or not os.path.exists(input_path):
            return False

        ext = os.path.splitext(input_path)[1].lstrip(".").lower()
        vid_exts = {f.lstrip(".").lower() for f in SUPPORTED_VIDEO_FORMATS}

        out_path = self._build_output_path(input_path, idx, total, ext)
        if out_path is None:
            return False

        algorithm = str(self.config.get("algorithm") or "lanczos").lower()
        progress = self._make_progress(idx, total)
        if ext in vid_exts:
            if algorithm not in {"lanczos", "bicubic", "bilinear", "nearest"}:
                raise RuntimeError(f"{algorithm} does not resample video.")
            return self._resample_video(input_path, out_path)
        elif ext == "gif":
            return self._resample_gif(input_path, out_path, progress)
        else:
            return self._resample_image(input_path, out_path, ext, progress)

    def _make_progress(self, file_index: int, file_count: int):
        def progress(stage: str, done: int, total: int) -> None:
            if self._is_cancelled:
                return
            ticks = _stage_ticks(stage, done, total)
            self._publish_ticks(file_index, file_count, ticks, _stage_text(stage, done, total))

        return progress

    def _publish_ticks(self, file_index: int, file_count: int, ticks: int, text: Optional[str]) -> None:
        """Sum per-file ticks so overlapping multicore jobs cannot rewind the bar."""
        ticks = max(0, min(100, int(ticks)))
        with self._progress_lock:
            self._file_ticks[file_index] = ticks
            done_ticks = sum(self._file_ticks.values())
            self.progress_update.emit(done_ticks, file_count * 100)
            if text:
                self.stage_update.emit(text)

    def _build_output_path(
        self, input_path: str, idx: int, total: int, src_ext: str
    ) -> Optional[str]:
        fmt_override = self.config.get("output_format")
        out_ext = fmt_override if fmt_override else src_ext

        out_dir_cfg = self.config.get("output_path") or ""
        out_dir = out_dir_cfg if out_dir_cfg and os.path.isdir(out_dir_cfg) else os.path.dirname(input_path)

        prefix = self.config.get("output_filename_prefix") or ""
        base = os.path.splitext(os.path.basename(input_path))[0]
        name = (f"{prefix}{idx + 1}" if total > 1 else prefix) if prefix else f"{base}_resampled"

        return os.path.join(out_dir, f"{name}.{out_ext}")

    # ------------------------------------------------------------------
    # Compute target dimensions
    # ------------------------------------------------------------------

    def _compute_dims(self, orig_w: int, orig_h: int) -> tuple[int, int]:
        scale_mode = self.config.get("scale_mode", "factor")
        if scale_mode == "factor":
            factor = float(self.config.get("scale_factor", 2.0))
            new_w = max(1, round(orig_w * factor))
            new_h = max(1, round(orig_h * factor))
        else:
            tw: Optional[int] = self.config.get("target_width")
            th: Optional[int] = self.config.get("target_height")
            preserve = self.config.get("preserve_aspect_ratio", True)
            if tw and th:
                if preserve:
                    ratio = min(tw / orig_w, th / orig_h)
                    new_w = max(1, round(orig_w * ratio))
                    new_h = max(1, round(orig_h * ratio))
                else:
                    new_w, new_h = tw, th
            elif tw:
                new_w = tw
                new_h = max(1, round(orig_h * (tw / orig_w)))
            elif th:
                new_h = th
                new_w = max(1, round(orig_w * (th / orig_h)))
            else:
                new_w, new_h = orig_w, orig_h
        return new_w, new_h

    # ------------------------------------------------------------------
    # Image resampling (Pillow)
    # ------------------------------------------------------------------

    def _registry_params(self, orig_w: int, orig_h: int) -> dict:
        new_w, new_h = self._compute_dims(orig_w, orig_h)
        return {
            "mode": "dimensions",
            "width": new_w,
            "height": new_h,
            "algorithm": str(self.config.get("algorithm") or "lanczos").lower(),
        }

    def _resample_image(self, in_path: str, out_path: str, src_ext: str, progress) -> bool:
        from middleware.src.services.media.gif_upscale.pipeline import resample_still
        from PIL import Image

        del src_ext
        with Image.open(in_path) as img:
            params = self._registry_params(*img.size)
        params["progress"] = progress
        result = resample_still(in_path, out_path, params)
        if not result.get("success"):
            raise RuntimeError(str(result.get("message") or "Resample failed."))

        if self.config.get("delete_original") and os.path.exists(out_path) and os.path.abspath(in_path) != os.path.abspath(out_path):
            os.remove(in_path)
        return True

    # ------------------------------------------------------------------
    # GIF resampling (Pillow, frame-by-frame)
    # ------------------------------------------------------------------

    def _resample_gif(self, in_path: str, out_path: str, progress) -> bool:
        from middleware.src.services.media.gif_upscale.pipeline import resample_gif
        from PIL import Image

        with Image.open(in_path) as gif:
            params = self._registry_params(*gif.size)
        params["progress"] = progress
        result = resample_gif(in_path, out_path, params)
        if not result.get("success"):
            raise RuntimeError(str(result.get("message") or "GIF resample failed."))

        if self.config.get("delete_original") and os.path.exists(out_path) and os.path.abspath(in_path) != os.path.abspath(out_path):
            os.remove(in_path)
        return True

    # ------------------------------------------------------------------
    # Video resampling (FFmpeg)
    # ------------------------------------------------------------------

    def _resample_video(self, in_path: str, out_path: str) -> bool:
        orig_w, orig_h = self._probe_video_dims(in_path)
        new_w, new_h = self._compute_dims(orig_w, orig_h)
        # FFmpeg requires even dimensions for most codecs
        new_w += new_w % 2
        new_h += new_h % 2

        algo = self.config.get("algorithm", "lanczos")
        # Map to FFmpeg scale flags
        sws_flags = {
            "lanczos": "lanczos",
            "bicubic": "bicubic",
            "bilinear": "bilinear",
            "nearest": "neighbor",
        }.get(algo, "lanczos")

        vf = f"scale={new_w}:{new_h}:flags={sws_flags}"
        cmd = ["ffmpeg", "-y", "-i", in_path, "-vf", vf, "-c:a", "copy", out_path]
        proc = None
        try:
            # Issue #81 crash family: serialize the ffmpeg fork against the
            # first QMediaPlayer construction (QThread worker).
            from gui.src.helpers.video.video_thumbnailer import media_backend_spawn_guard

            with media_backend_spawn_guard():
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            with self._process_lock:
                self._active_procs.add(proc)
            proc.wait(timeout=600)
            with self._process_lock:
                self._active_procs.discard(proc)
        except subprocess.TimeoutExpired:
            if proc is not None:
                proc.terminate()
            return False
        except FileNotFoundError:
            self.error.emit("FFmpeg not found. Install FFmpeg to resample videos.")
            return False

        success = proc.returncode == 0 and os.path.exists(out_path)
        if success and self.config.get("delete_original") and os.path.abspath(in_path) != os.path.abspath(out_path):
            os.remove(in_path)
        return success

    @staticmethod
    def _probe_video_dims(path: str) -> tuple[int, int]:
        try:
            # Issue #81 crash family: ffprobe fork on a worker thread must
            # not race the first QMediaPlayer construction.
            from gui.src.helpers.video.video_thumbnailer import media_backend_spawn_guard

            with media_backend_spawn_guard():
                result = subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-select_streams",
                        "v:0",
                        "-show_entries",
                        "stream=width,height",
                        "-of",
                        "csv=p=0:s=x",
                        path,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
            if result.returncode == 0 and "x" in result.stdout:
                w_str, h_str = result.stdout.strip().split("x", 1)
                return int(w_str), int(h_str)
        except Exception:
            logger.debug("Suppressed Exception in SamplerWorker._probe_video_dims", exc_info=True)
        return 1920, 1080


# Decode and encode bookend the bar. Scaling is the long stretch of one GIF.
_STAGE_TICKS = {
    "decode": (0, 8),
    "scale": (8, 90),
    "encode": (90, 100),
}


def _stage_ticks(stage: str, done: int, total: int) -> int:
    start, end = _STAGE_TICKS.get(stage, (0, 100))
    if total <= 0 or done <= 0:
        return start
    if done >= total:
        return end
    return start + (end - start) * done // total


def _stage_text(stage: str, done: int, total: int) -> str:
    if stage == "scale" and total > 0:
        frame_no = total if done >= total else done + 1
        return f"Scaling frame {frame_no}/{total}"
    if stage == "encode":
        return "Encoding"
    if stage == "decode":
        return "Decoding"
    return stage or "Resampling"
