"""Pre-generated storyboard (sprite sheet) scrub preview, YouTube-style.

Every attempt to make the Extractor tab's playhead-drag preview fast by
decoding a real video frame on demand -- a per-frame ffmpeg subprocess, a
background dense-keyframe proxy, a persistent in-process decoder -- kept
hitting either latency or QMediaPlayer/QVideoSink surface-swap bugs (see
moon/roadmaps/new_features.md §4.14 for the retrospective). None of that is
actually how large-scale video platforms solve this: YouTube's scrub
preview isn't a live decode at all. It's a sprite sheet -- a grid of small
thumbnails sampled at a fixed interval across the whole video, built once
when the video is processed. Dragging the scrubber is then just cropping an
already-loaded image, with zero per-tick decode cost, so update speed stops
being bounded by codec, GOP structure, resolution, or seek latency at all.

Sampled at a dense, near-frame-accurate interval (100ms) so a preview tile
never goes visibly stale relative to the real frame at that timestamp --
anime in particular cuts between shots/angles fast enough that anything
coarser (an earlier version of this sampled every ~5s) regularly showed a
tile from a completely different shot than what the timeline position was
actually on. At that density a single sprite sheet for a full episode
would decode to several hundred MB of raw pixels, comfortably over Qt's
QImageIOHandler ~256MB safety allocation limit (confirmed empirically:
QPixmap silently returns a null/failed pixmap past that, no exception) --
so tiles are split across multiple smaller sprite sheet "pages", each kept
well under that ceiling, all loaded into memory for the currently active
video (never more than one video's worth at a time; switching videos drops
the old pixmaps).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from backend.src.constants import IMAGE_TOOLKIT_DIR
from PIL import Image
from PySide6.QtCore import QThread, Signal

_OUT_TIME_RE = re.compile(r"out_time_ms=(\d+)")


def probe_duration_ms(video_path: str) -> int:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(float(result.stdout.strip()) * 1000)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
    return 0

_STORYBOARD_CACHE_VERSION = "v2"
_STORYBOARD_DIR = IMAGE_TOOLKIT_DIR / "storyboard-cache"

# Tile width in pixels (height follows the source's own aspect ratio). Kept
# modest since this is a drag-preview thumbnail, not an extraction target,
# and smaller tiles also directly shrink each page's raw decoded size.
TILE_WIDTH = 128
# Sample (at least) this densely -- see module docstring for why. Only
# widened beyond this for pathologically long sources, bounded by
# MAX_TOTAL_TILES below, rather than left unbounded.
MIN_INTERVAL_MS = 100
MAX_TOTAL_TILES = 50_000
MIN_TILES = 4
# Each page is kept to roughly this many raw decoded megabytes (tile_width *
# tile_height * 3 bytes/px * tiles_per_page), comfortably under Qt's ~256MB
# QImageIOHandler allocation limit -- deliberately well under it, both for
# safety margin and so several pages can be held in memory at once without
# real pressure.
_MAX_PAGE_RAW_MB = 96


def _cache_key(video_path: str) -> str:
    resolved = os.path.abspath(video_path)
    stat = os.stat(resolved)
    payload = f"{resolved}|{stat.st_mtime_ns}|{stat.st_size}|{_STORYBOARD_CACHE_VERSION}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _cache_dir_for(video_path: str) -> Path:
    d = _STORYBOARD_DIR / _cache_key(video_path)
    return d


def storyboard_meta_path_for(video_path: str) -> Path:
    return _cache_dir_for(video_path) / "meta.json"


def storyboard_is_complete(video_path: str) -> bool:
    meta_path = storyboard_meta_path_for(video_path)
    if not meta_path.exists():
        return False
    try:
        data = json.loads(meta_path.read_text())
        if data.get("count", 0) <= 0:
            return False
        page_dir = meta_path.parent
        return all((page_dir / page_name).exists() for page_name in data.get("pages", []))
    except (OSError, json.JSONDecodeError):
        return False


@dataclass
class StoryboardMeta:
    interval_ms: int
    tile_width: int
    tile_height: int
    cols: int  # tiles per row, within a page
    tiles_per_page: int
    count: int  # total tiles across all pages
    duration_ms: int
    pages: List[str]  # page image filenames, in order, relative to meta.json's directory

    def tile_location_for(self, position_ms: int) -> Tuple[int, int, int, int, int]:
        """Returns (page_index, x, y, w, h): which page contains the tile
        for position_ms, and its pixel rect within that page."""
        idx = (position_ms // self.interval_ms) if self.interval_ms > 0 else 0
        idx = max(0, min(self.count - 1, idx))
        page_index = idx // self.tiles_per_page
        idx_in_page = idx % self.tiles_per_page
        col = idx_in_page % self.cols
        row = idx_in_page // self.cols
        return (page_index, col * self.tile_width, row * self.tile_height, self.tile_width, self.tile_height)

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def load(cls, meta_path: Path) -> "StoryboardMeta":
        return cls(**json.loads(meta_path.read_text()))


class StoryboardBuilder(QThread):
    """Builds a (possibly multi-page) storyboard sprite sheet for a single
    video in the background."""

    finished_ok = Signal(str)  # meta_path
    failed = Signal(str)
    progress_changed = Signal(int)  # percent, 0-100

    def __init__(self, video_path: str, duration_ms: int, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.duration_ms = max(0, duration_ms)
        self.cache_dir = _cache_dir_for(video_path)
        self.meta_path = self.cache_dir / "meta.json"
        self._cancelled = False
        self._process: Optional[subprocess.Popen] = None

    def cancel(self):
        self._cancelled = True
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()

    def run(self):  # noqa: C901
        if self._cancelled:
            return
        if self.duration_ms <= 0:
            self.failed.emit("Unknown video duration.")
            return

        interval_ms = max(MIN_INTERVAL_MS, self.duration_ms // MAX_TOTAL_TILES)
        est_tiles = max(1, self.duration_ms // interval_ms)
        if est_tiles < MIN_TILES:
            interval_ms = max(1, self.duration_ms // MIN_TILES)

        with tempfile.TemporaryDirectory(prefix="storyboard_") as tmpdir:
            if self._cancelled:
                return
            tile_pattern = os.path.join(tmpdir, "tile_%06d.jpg")
            cmd = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-progress",
                "pipe:1",
                "-i",
                self.video_path,
                "-vf",
                f"fps=1000/{interval_ms},scale={TILE_WIDTH}:-2",
                "-q:v",
                "4",
                tile_pattern,
            ]
            try:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                self.progress_changed.emit(0)
                assert self._process.stdout is not None
                for line in self._process.stdout:
                    if self._cancelled:
                        break
                    match = _OUT_TIME_RE.search(line)
                    if match and self.duration_ms > 0:
                        out_time_ms = int(match.group(1)) // 1000
                        percent = max(0, min(100, int(out_time_ms * 100 / self.duration_ms)))
                        self.progress_changed.emit(percent)
                self._process.wait()
            except OSError as exc:
                self.failed.emit(str(exc))
                return
            finally:
                self._process = None

            if self._cancelled:
                return

            tile_paths = sorted(Path(tmpdir).glob("tile_*.jpg"))
            if not tile_paths:
                self.failed.emit("No thumbnails extracted.")
                return

            try:
                self._composite(tile_paths, interval_ms)
            except Exception as exc:
                self.failed.emit(str(exc))
                return

        if not self._cancelled:
            self.finished_ok.emit(str(self.meta_path))

    def _composite(self, tile_paths: List[Path], interval_ms: int) -> None:
        count = len(tile_paths)
        with Image.open(tile_paths[0]) as first:
            tw, th = first.size

        raw_bytes_per_tile = tw * th * 3
        tiles_per_page = max(1, ((_MAX_PAGE_RAW_MB * 1_000_000) // raw_bytes_per_tile))
        # Square-ish grid per page for a compact, roughly-square sprite
        # sheet image rather than one extremely wide/tall strip.
        cols = max(1, math.ceil(math.sqrt(tiles_per_page)))

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        page_names: List[str] = []

        for page_start in range(0, count, tiles_per_page):
            if self._cancelled:
                return
            page_tiles = tile_paths[page_start : page_start + tiles_per_page]
            page_rows = math.ceil(len(page_tiles) / cols)
            sheet = Image.new("RGB", (tw * cols, th * page_rows), (0, 0, 0))
            for i, path in enumerate(page_tiles):
                with Image.open(path) as tile:
                    x = (i % cols) * tw
                    y = (i // cols) * th
                    sheet.paste(tile, (x, y))

            page_name = f"page_{page_start // tiles_per_page:04d}.jpg"
            sheet.save(self.cache_dir / page_name, format="JPEG", quality=85)
            page_names.append(page_name)

        meta = StoryboardMeta(
            interval_ms=interval_ms,
            tile_width=tw,
            tile_height=th,
            cols=cols,
            tiles_per_page=tiles_per_page,
            count=count,
            duration_ms=self.duration_ms,
            pages=page_names,
        )
        self.meta_path.write_text(meta.to_json())
