import contextlib
import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import QThread, Signal

_PILLOW_FILTERS = {
    "lanczos": None,  # resolved at runtime via Image.LANCZOS
    "bicubic": None,
    "bilinear": None,
    "nearest": None,
}


def _get_pil_filter(name: str):
    from PIL import Image

    return {
        "lanczos": Image.Resampling.LANCZOS,
        "bicubic": Image.Resampling.BICUBIC,
        "bilinear": Image.Resampling.BILINEAR,
        "nearest": Image.Resampling.NEAREST,
    }.get(name, Image.Resampling.LANCZOS)


class SamplerWorker(QThread):
    """Resample images, GIFs, and videos to new dimensions or a scale factor."""

    finished = Signal(int, str)
    error = Signal(str)
    progress_update = Signal(int)

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self._is_cancelled = False
        self._executor: Optional[ThreadPoolExecutor] = None
        self._process_lock = threading.Lock()
        self._active_procs: set = set()

    def cancel(self):
        self._is_cancelled = True
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
        with self._process_lock:
            for p in list(self._active_procs):
                with contextlib.suppress(Exception):
                    p.terminate()
            self._active_procs.clear()

    def stop(self):
        self.cancel()

    def run(self):
        try:
            files: List[str] = self.config.get("files_to_process", [])
            if not files:
                self.error.emit("No files to resample.")
                return

            total = len(files)
            done = 0
            failures: List[str] = []
            use_multicore = self.config.get("use_multicore", True)

            self.progress_update.emit(0)

            if use_multicore and total > 1:
                max_w = min(os.cpu_count() or 1, 8)
                self._executor = ThreadPoolExecutor(max_workers=max_w)
                futures = {
                    self._executor.submit(self._resample_one, f, i, total): i
                    for i, f in enumerate(files)
                    if not self._is_cancelled
                }
                for completed_idx, future in enumerate(as_completed(futures)):
                    if self._is_cancelled:
                        break
                    try:
                        if future.result():
                            done += 1
                    except Exception as exc:
                        failures.append(str(exc))
                    self.progress_update.emit(int((completed_idx + 1) / total * 100))
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
                    self.progress_update.emit(int((i + 1) / total * 100))

            if self._is_cancelled:
                self.finished.emit(done, "**Resampling Cancelled**")
            elif failures:
                msg = f"Processed {done}/{total} files. {len(failures)} error(s)."
                if failures:
                    msg += "\n\nFirst error: " + failures[0]
                self.finished.emit(done, msg)
            else:
                self.finished.emit(done, f"Resampled {done} file(s) successfully!")

        except Exception as exc:
            self.progress_update.emit(0)
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

        if ext in vid_exts:
            return self._resample_video(input_path, out_path)
        elif ext == "gif":
            return self._resample_gif(input_path, out_path)
        else:
            return self._resample_image(input_path, out_path, ext)

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

    def _resample_image(self, in_path: str, out_path: str, src_ext: str) -> bool:
        from PIL import Image

        filt = _get_pil_filter(self.config.get("algorithm", "lanczos"))

        with Image.open(in_path) as img:
            orig_w, orig_h = img.size
            new_w, new_h = self._compute_dims(orig_w, orig_h)

            # Preserve mode where possible; RGBA → RGB for JPEG
            out_ext = os.path.splitext(out_path)[1].lstrip(".").lower()
            if out_ext in ("jpg", "jpeg") and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            resampled = img.resize((new_w, new_h), filt)
            save_fmt = out_ext.upper()
            if save_fmt in ("JPG",):
                save_fmt = "JPEG"
            resampled.save(out_path, format=save_fmt)

        if self.config.get("delete_original") and os.path.exists(out_path) and os.path.abspath(in_path) != os.path.abspath(out_path):
            os.remove(in_path)
        return True

    # ------------------------------------------------------------------
    # GIF resampling (Pillow, frame-by-frame)
    # ------------------------------------------------------------------

    def _resample_gif(self, in_path: str, out_path: str) -> bool:
        from PIL import Image

        filt = _get_pil_filter(self.config.get("algorithm", "lanczos"))

        with Image.open(in_path) as gif:
            orig_w, orig_h = gif.size
            new_w, new_h = self._compute_dims(orig_w, orig_h)
            loop = gif.info.get("loop", 0)

            frames: List[Image.Image] = []
            durations: List[int] = []
            try:
                while True:
                    if self._is_cancelled:
                        return False
                    frame = gif.copy().convert("RGBA")
                    frames.append(frame.resize((new_w, new_h), filt))
                    durations.append(gif.info.get("duration", 100))
                    gif.seek(gif.tell() + 1)
            except EOFError:
                pass

            if not frames:
                return False

            frames[0].save(
                out_path,
                format="GIF",
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=loop,
                optimize=False,
            )

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
            pass
        return 1920, 1080
