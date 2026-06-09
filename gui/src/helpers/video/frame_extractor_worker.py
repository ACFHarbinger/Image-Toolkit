import os
import re
import cv2
import time
import subprocess

from pathlib import Path
from PySide6.QtCore import QRunnable, Signal, QObject
from typing import Optional, Tuple
from ...utils.sort_utils import natural_sort_key


# --- Worker Signals ---
class ExtractorSignals(QObject):
    started = Signal()
    progress = Signal(int)
    finished = Signal(list)  # Returns list of saved paths
    error = Signal(str)


# --- Worker Logic (OpenCV) ---
class FrameExtractionWorker(QRunnable):
    """
    Background worker to extract frames using OpenCV or FFmpeg.
    """

    def _get_keep_regions(self, t_start: float, t_end: float):
        if not self.cuts_ms:
            return [(0.0, t_end - t_start)]

        sorted_cuts = sorted(
            [
                (max(t_start, c[0] / 1000.0), min(t_end, c[1] / 1000.0))
                for c in self.cuts_ms
            ]
        )
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

    def __init__(
        self,
        video_path: str,
        output_dir: str,
        start_ms: int,
        end_ms: int = -1,
        is_range: bool = False,
        target_resolution: Optional[Tuple[int, int]] = None,
        cuts_ms: Optional[list] = None,
        frame_interval: int = 1,
        smart_extract: bool = False,
        smart_method: str = "mpdecimate (De-duplicate)",
    ):
        super().__init__()
        self.video_path = video_path
        self.output_dir = output_dir
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.is_range = is_range
        self.target_resolution = target_resolution
        self.cuts_ms = cuts_ms or []
        self.frame_interval = frame_interval
        self.smart_extract = smart_extract
        self.smart_method = smart_method
        self.signals = ExtractorSignals()
        self._is_cancelled = False
        self.fps = 23.976  # Default/detected FPS

    def _get_fps(self) -> float:
        """Get video FPS to calculate timestamps."""
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            return 23.976
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        try:
            if fps <= 0:
                fps = 23.976  # Fallback
        except (TypeError, Exception):
            fps = 23.976
        return fps

    def run(self):
        self.signals.started.emit()
        saved_files = []

        self.fps = self._get_fps()

        if self.smart_extract:
            self._run_smart_extraction(saved_files, self.fps)
            return

        # --- REGULAR EXTRACTION (Replaces OpenCV with FFmpeg for robustness) ---
        try:
            video_name = Path(self.video_path).stem
            t_start = self.start_ms / 1000.0

            cmd = ["ffmpeg", "-y", "-ss", str(t_start)]
            if self.is_range and self.end_ms != -1:
                duration = (self.end_ms - self.start_ms) / 1000.0
                cmd.extend(["-t", str(duration)])

            cmd.extend(["-i", self.video_path])

            filters = []
            if self.cuts_ms:
                keep_regions = self._get_keep_regions(
                    t_start,
                    (self.end_ms / 1000.0 if self.end_ms != -1 else t_start + 1),
                )
                if keep_regions:
                    select_expr = "+".join(
                        [f"between(t,{r[0]},{r[1]})" for r in keep_regions]
                    )
                    filters.append(f"select='{select_expr}'")

            if self.frame_interval > 1:
                filters.append(f"select='not(mod(n,{self.frame_interval}))'")

            if self.target_resolution:
                w, h = self.target_resolution
                filters.append(f"scale={w}:{h}:flags=lanczos")

            if filters:
                cmd.extend(["-vf", ",".join(filters)])

            # Single frame optimization
            if not self.is_range:
                cmd.extend(["-vframes", "1"])

            cmd.extend(
                [
                    "-sws_flags",
                    "spline+accurate_rnd+full_chroma_int",
                    "-vsync",
                    "vfr",
                    "-q:v",
                    "2",
                ]
            )

            out_pattern = os.path.join(self.output_dir, f"{video_name}_tmp_%05d.png")
            cmd.append(out_pattern)

            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            while process.poll() is None:
                if self._is_cancelled:
                    process.terminate()
                    return
                self.signals.progress.emit(50)
                time.sleep(0.5)

            if process.returncode != 0:
                self.signals.error.emit(f"FFmpeg failed: {process.stderr.read()}")
                return

            # Rename temp files to timestamp-based names
            tmp_files = sorted(
                [
                    f
                    for f in os.listdir(self.output_dir)
                    if f.startswith(f"{video_name}_tmp_") and f.endswith(".png")
                ]
            )
            for i, f in enumerate(tmp_files):
                # Calculate approximate MS
                # Frame N (0-indexed) at start_ms + (N * interval * 1000 / self.fps)
                current_ms = self.start_ms + int(
                    i * self.frame_interval * (1000.0 / self.fps)
                )
                new_name = f"{video_name}_{current_ms}ms.png"

                # Check for duplicates if multiple extractions land on same ms
                final_path = os.path.join(self.output_dir, new_name)
                if os.path.exists(final_path):
                    final_path = os.path.join(
                        self.output_dir, f"{video_name}_{current_ms}ms_{i}.png"
                    )

                os.rename(os.path.join(self.output_dir, f), final_path)
                saved_files.append(final_path)

            self.signals.progress.emit(100)
            self.signals.finished.emit(saved_files)

        except Exception as e:
            self.signals.error.emit(str(e))

    def _run_smart_extraction(self, saved_files, fps):
        try:
            video_name = Path(self.video_path).stem
            t_start = self.start_ms / 1000.0
            t_end = self.end_ms / 1000.0
            duration = t_end - t_start

            cmd = ["ffmpeg", "-y"]
            cmd.extend(["-ss", str(t_start)])
            if self.is_range and self.end_ms != -1:
                cmd.extend(["-t", str(duration)])
            cmd.extend(["-i", self.video_path])

            filters = []
            keep_regions = self._get_keep_regions(t_start, t_end)
            if self.cuts_ms and keep_regions:
                select_expr = "+".join(
                    [f"between(t,{r[0]},{r[1]})" for r in keep_regions]
                )
                filters.append(f"select='{select_expr}'")

            if self.frame_interval > 1:
                filters.append(f"select='not(mod(n,{self.frame_interval}))'")

            if "mpdecimate" in self.smart_method:
                filters.append("mpdecimate")
            elif "scene" in self.smart_method:
                match = re.search(r"\((.*?)\)", self.smart_method)
                val = match.group(1) if match else "0.4"
                filters.append(f"select='gt(scene,{val})'")

            if self.target_resolution:
                w, h = self.target_resolution
                filters.append(f"scale={w}:{h}:flags=lanczos")

            if filters:
                cmd.extend(["-vf", ",".join(filters)])

            # Single-frame snapshot: limit output to one frame
            if not self.is_range:
                cmd.extend(["-vframes", "1"])

            cmd.extend(
                [
                    "-sws_flags",
                    "spline+accurate_rnd+full_chroma_int",
                    "-pix_fmt",
                    "rgb48be",  # 16-bit RGB to prevent 10-bit banding
                    "-vsync",
                    "vfr",
                    "-frame_pts",
                    "1",
                ]
            )
            
            # Use a more unique temp prefix to avoid collisions during extraction
            temp_id = int(time.time() * 1000) % 100000
            out_pattern = os.path.join(self.output_dir, f"{video_name}_smart_tmp_{temp_id}_%08d.png")
            cmd.append(out_pattern)

            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            while process.poll() is None:
                if self._is_cancelled:
                    process.terminate()
                    return
                self.signals.progress.emit(50)
                time.sleep(0.5)

            if process.returncode != 0:
                self.signals.error.emit(f"FFmpeg failed: {process.stderr.read()}")
                return

            prefix = f"{video_name}_smart_tmp_{temp_id}_"
            tmp_files = sorted(
                [
                    f
                    for f in os.listdir(self.output_dir)
                    if f.startswith(prefix) and f.endswith(".png")
                ],
                key=natural_sort_key
            )
            
            for f in tmp_files:
                # Extract PTS from filename
                match = re.search(r"_(\d+)\.png$", f)
                if not match:
                    continue
                
                pts = int(match.group(1))
                # Calculate MS: current_ms = start_ms + (pts * 1000 / fps)
                # Assumes input seeking (-ss before -i) resets timestamps to 0
                current_ms = self.start_ms + int(pts * 1000.0 / fps)
                
                new_name = f"{video_name}_smart_{current_ms}ms.png"
                final_path = os.path.join(self.output_dir, new_name)
                
                # Deduplicate if necessary
                if os.path.exists(final_path):
                    final_path = os.path.join(self.output_dir, f"{video_name}_smart_{current_ms}ms_{temp_id}.png")
                
                os.rename(os.path.join(self.output_dir, f), final_path)
                saved_files.append(final_path)

            self.signals.progress.emit(100)
            self.signals.finished.emit(saved_files)
        except Exception as e:
            self.signals.error.emit(str(e))

    def cancel(self):
        self._is_cancelled = True
