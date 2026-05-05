import os
import cv2
import time

from pathlib import Path
from PySide6.QtCore import QRunnable, Signal, QObject
from typing import Optional, Tuple


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

        sorted_cuts = sorted([(max(t_start, c[0]/1000.0), min(t_end, c[1]/1000.0)) for c in self.cuts_ms])
        merged_cuts = []
        for c in sorted_cuts:
            if c[0] >= c[1]: continue
            if not merged_cuts: merged_cuts.append(c)
            else:
                last = merged_cuts[-1]
                if c[0] <= last[1]: merged_cuts[-1] = (last[0], max(last[1], c[1]))
                else: merged_cuts.append(c)

        keep = []
        current = t_start
        for c_start, c_end in merged_cuts:
            if c_start > current: keep.append((current - t_start, c_start - t_start))
            current = max(current, c_end)

        if current < t_end: keep.append((current - t_start, t_end - t_start))
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
        smart_method: str = "mpdecimate (De-duplicate)"
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

    def run(self):
        self.signals.started.emit()
        saved_files = []

        if self.smart_extract:
            self._run_smart_extraction(saved_files)
            return

        try:
            import cv2
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                self.signals.error.emit("Could not open video file.")
                return

            cap.set(cv2.CAP_PROP_POS_MSEC, self.start_ms)
            video_name = Path(self.video_path).stem

            total_duration_ms = self.end_ms - self.start_ms if (self.is_range and self.end_ms != -1) else -1
            frame_count = 0

            while not self._is_cancelled:
                ret, frame = cap.read()
                if not ret: break

                current_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
                frame_count += 1

                if self.frame_interval > 1 and (frame_count - 1) % self.frame_interval != 0:
                    continue

                if total_duration_ms > 0:
                    progress = int(((current_ms - self.start_ms) / total_duration_ms) * 100)
                    self.signals.progress.emit(min(100, max(0, progress)))

                in_cut = False
                for c_start, c_end in self.cuts_ms:
                    if c_start <= current_ms <= c_end:
                        in_cut = True; break
                if in_cut: continue

                if self.target_resolution:
                    frame = cv2.resize(frame, self.target_resolution, interpolation=cv2.INTER_AREA)

                filename = f"{video_name}_{int(current_ms)}ms.png"
                save_path = os.path.join(self.output_dir, filename)
                cv2.imwrite(save_path, frame)
                saved_files.append(save_path)

                if not self.is_range: break
                if self.end_ms != -1 and current_ms >= self.end_ms: break

            cap.release()
            self.signals.progress.emit(100)
            self.signals.finished.emit(saved_files)

        except Exception as e:
            self.signals.error.emit(str(e))

    def _run_smart_extraction(self, saved_files):
        try:
            import subprocess
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
                select_expr = "+".join([f"between(t,{r[0]},{r[1]})" for r in keep_regions])
                filters.append(f"select='{select_expr}'")

            if self.frame_interval > 1:
                filters.append(f"select='not(mod(n,{self.frame_interval}))'")

            if "mpdecimate" in self.smart_method:
                filters.append("mpdecimate")
            elif "scene" in self.smart_method:
                import re
                match = re.search(r"\((.*?)\)", self.smart_method)
                val = match.group(1) if match else "0.4"
                filters.append(f"select='gt(scene,{val})'")

            if self.target_resolution:
                w, h = self.target_resolution
                filters.append(f"scale={w}:{h}")

            if filters:
                cmd.extend(["-vf", ",".join(filters)])

            cmd.extend(["-vsync", "vfr", "-frame_pts", "1"])
            out_pattern = os.path.join(self.output_dir, f"{video_name}_smart_%05d.png")
            cmd.append(out_pattern)

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            while process.poll() is None:
                if self._is_cancelled:
                    process.terminate(); return
                self.signals.progress.emit(50)
                import time; time.sleep(0.5)

            if process.returncode != 0:
                self.signals.error.emit(f"FFmpeg failed: {process.stderr.read()}")
                return

            import glob
            extracted = glob.glob(os.path.join(self.output_dir, f"{video_name}_smart_*.png"))
            extracted.sort()
            saved_files.extend(extracted)
            self.signals.progress.emit(100)
            self.signals.finished.emit(saved_files)
        except Exception as e:
            self.signals.error.emit(str(e))

    def cancel(self):
        self._is_cancelled = True
