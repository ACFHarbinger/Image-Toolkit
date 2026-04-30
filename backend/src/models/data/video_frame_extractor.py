"""
backend/src/models/data/video_frame_extractor.py
================================================
Scene-aware 4K anime frame extractor.

Uses FFmpeg for decoding and PySceneDetect (AdaptiveDetector) for cut
detection — the two-pass approach recommended in the research reports.
Integrates with PgvectorImageDatabase and the Rust `base` extension for
content-addressed deduplication (blake3) and perceptual hashing (phash64).

Usage
-----
    extractor = VideoFrameExtractor(db=db)
    for rec in extractor.extract(Path("show.mkv"), Path("frames/")):
        print(rec.phash, rec.pts_seconds)
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Try to import optional dependencies gracefully
# ---------------------------------------------------------------------------
try:
    from scenedetect import open_video, SceneManager
    from scenedetect.detectors import AdaptiveDetector, ContentDetector
    _SCENEDETECT_OK = True
except ImportError:
    _SCENEDETECT_OK = False
    log.warning("scenedetect not installed — scene detection disabled; using I-frame sampling")

try:
    import base as rust_base  # Rust PyO3 extension
    _RUST_OK = True
except ImportError:
    _RUST_OK = False
    log.warning("Rust base extension unavailable — falling back to Python hashing")


# ---------------------------------------------------------------------------
# Pure-Python fallback hashers (used when Rust extension is absent)
# ---------------------------------------------------------------------------
def _py_phash64(path: str) -> str:
    """64-bit pHash via PIL (fallback when Rust unavailable)."""
    with Image.open(path) as im:
        gray = im.convert("L").resize((8, 8), Image.LANCZOS)
    arr = np.array(gray, dtype=np.float32)
    mean = arr.mean()
    bits = (arr > mean).flatten().astype(np.uint8)
    val = int(np.packbits(bits).view(np.uint64)[0])
    return hex(val)


def _py_blake3(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _blake3_file(path: str) -> str:
    return rust_base.blake3_file(path) if _RUST_OK else _py_blake3(path)


def _phash64(path: str) -> str:
    return rust_base.phash64(path) if _RUST_OK else _py_phash64(path)


# ---------------------------------------------------------------------------
# Data record
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FrameRecord:
    video_path: Path
    scene_idx: int
    pts_seconds: float
    frame_idx: int
    width: int
    height: int
    phash: str
    blake3: str


# ---------------------------------------------------------------------------
# Main extractor
# ---------------------------------------------------------------------------
class VideoFrameExtractor:
    """
    Parameters
    ----------
    ffmpeg_bin / ffprobe_bin : path to executables (default: system PATH)
    db                       : optional PgvectorImageDatabase for persistence
    sample_per_scene         : frames to extract per scene (1 = thirds sampling)
    adaptive_threshold       : PySceneDetect AdaptiveDetector threshold (3.0 works
                               well for cel-shaded anime)
    min_content_val          : minimum content change to register a scene cut
    min_scene_len            : minimum frames per scene (@24fps: 12 ≈ 0.5 s)
    use_cuda_hwaccel         : use -hwaccel cuda in FFmpeg (requires NVDEC)
    """

    def __init__(
        self,
        ffmpeg_bin: str = "ffmpeg",
        ffprobe_bin: str = "ffprobe",
        db=None,
        sample_per_scene: int = 1,
        adaptive_threshold: float = 3.0,
        min_content_val: float = 15.0,
        min_scene_len: int = 12,
        use_cuda_hwaccel: bool = True,
    ):
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin
        self.db = db
        self.sample_per_scene = sample_per_scene
        self.adaptive_threshold = adaptive_threshold
        self.min_content_val = min_content_val
        self.min_scene_len = min_scene_len
        self.use_cuda = use_cuda_hwaccel

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def probe(self, video_path: Path) -> dict:
        """Return stream metadata via ffprobe (fps, duration, codec, w×h)."""
        cmd = [
            self.ffprobe_bin, "-v", "error", "-count_frames",
            "-select_streams", "v:0",
            "-show_entries",
            "stream=nb_read_frames,r_frame_rate,avg_frame_rate,width,height,codec_name",
            "-show_entries", "format=duration",
            "-of", "json", str(video_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def detect_scenes(self, video_path: Path) -> list[tuple[float, float]]:
        """Return list of (start_sec, end_sec) scene boundaries."""
        if not _SCENEDETECT_OK:
            return self._fallback_scenes(video_path)

        video = open_video(str(video_path))
        sm = SceneManager()
        sm.add_detector(AdaptiveDetector(
            adaptive_threshold=self.adaptive_threshold,
            min_scene_len=self.min_scene_len,
            window_width=2,
            min_content_val=self.min_content_val,
            weights=ContentDetector.Components(
                delta_hue=1.0,
                delta_sat=0.5,      # cel fills jitter saturation; reduce weight
                delta_lum=1.0,
                delta_edges=0.2,    # anime has crisp lineart — keep edges
            ),
            kernel_size=5,
        ))
        sm.detect_scenes(video, show_progress=False)
        scenes = sm.get_scene_list()
        return [(s.get_seconds(), e.get_seconds()) for s, e in scenes]

    def extract(self, video_path: Path, out_dir: Path) -> Iterator[FrameRecord]:
        """
        Main entry point.  Yields FrameRecord for each extracted frame.
        Also inserts into `self.db` if one was provided.
        """
        out_dir.mkdir(parents=True, exist_ok=True)
        scenes = self.detect_scenes(video_path)
        log.info("Detected %d scenes in %s", len(scenes), video_path)

        for scene_idx, (start, end) in enumerate(scenes):
            sample_pts = self._sample_pts(start, end)
            for sub_idx, ts in enumerate(sample_pts):
                stem = f"{video_path.stem}_s{scene_idx:05d}_{sub_idx:02d}"
                out = out_dir / f"{stem}.png"
                self._ffmpeg_extract(video_path, ts, out)

                blake3 = _blake3_file(str(out))
                phash = _phash64(str(out))
                with Image.open(out) as im:
                    w, h = im.size

                rec = FrameRecord(
                    video_path=video_path,
                    scene_idx=scene_idx,
                    pts_seconds=ts,
                    frame_idx=int(ts * 24.0),
                    width=w,
                    height=h,
                    phash=phash,
                    blake3=blake3,
                )
                if self.db is not None:
                    try:
                        self.db.insert_video_frame(rec)
                    except Exception as exc:
                        log.warning("DB insert failed for %s: %s", out, exc)
                yield rec

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _sample_pts(self, start: float, end: float) -> list[float]:
        """
        Return timestamps to sample within [start, end].
        sample_per_scene=1 → single sample at 1/3 from start (avoids
        motion-blur at cut boundaries while sampling early action).
        sample_per_scene=3 → start/mid/end (for large datasets).
        """
        dur = max(end - start, 0.04)
        if self.sample_per_scene == 1:
            return [start + dur / 3.0]
        pts = []
        for i in range(self.sample_per_scene):
            t = start + dur * (i + 0.5) / self.sample_per_scene
            pts.append(t)
        return pts

    def _ffmpeg_extract(self, video_path: Path, ts: float, out: Path) -> None:
        cmd = [self.ffmpeg_bin, "-y", "-loglevel", "error"]
        if self.use_cuda:
            cmd += ["-hwaccel", "cuda"]
        cmd += [
            "-ss", f"{ts:.3f}",
            "-i", str(video_path),
            "-frames:v", "1",
            "-pix_fmt", "rgb24",
            "-compression_level", "9",
            str(out),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            # Retry without hwaccel on failure (handles non-NVDEC sources)
            if self.use_cuda:
                cmd_cpu = [c for c in cmd if c != "cuda" and c != "-hwaccel"]
                subprocess.run(cmd_cpu, check=True, capture_output=True)
            else:
                raise exc

    def _fallback_scenes(self, video_path: Path) -> list[tuple[float, float]]:
        """Fallback: probe duration and create 2-second pseudo-scenes."""
        try:
            meta = self.probe(video_path)
            dur = float(meta.get("format", {}).get("duration", 60.0))
        except Exception:
            dur = 60.0
        step = 2.0
        return [(i * step, min((i + 1) * step, dur)) for i in range(int(dur / step))]
