"""H.264 proxy playback for codecs Qt cannot decode (AV1/VP9 on Linux)."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QRunnable, QThread, QThreadPool, QTimer, Signal, Slot
from PySide6.QtGui import QImage

from backend.src.constants import IMAGE_TOOLKIT_DIR

QT_UNSUPPORTED_CODECS = frozenset({"av1", "vp9"})
_PROXY_CACHE_VERSION = "v1"
_PROXY_DIR = IMAGE_TOOLKIT_DIR / "av1-playback-cache"
_PARTIAL_MIN_BYTES = 200_000
_PARTIAL_MIN_MS = 500
_OUT_TIME_RE = re.compile(r"out_time_ms=(\d+)")


def needs_transcoded_playback(video_path: str) -> bool:
    codec = _probe_codec(video_path)
    return bool(codec and codec in QT_UNSUPPORTED_CODECS)


def _probe_codec(video_path: str) -> Optional[str]:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode == 0:
            codec = result.stdout.strip().lower()
            if codec:
                return codec
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


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


def _cache_key(video_path: str) -> str:
    resolved = os.path.abspath(video_path)
    stat = os.stat(resolved)
    payload = (
        f"{resolved}|{stat.st_mtime_ns}|{stat.st_size}|{_PROXY_CACHE_VERSION}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def proxy_path_for(video_path: str) -> Path:
    _PROXY_DIR.mkdir(parents=True, exist_ok=True)
    return _PROXY_DIR / f"{_cache_key(video_path)}.mp4"


def proxy_is_complete(video_path: str) -> bool:
    proxy = proxy_path_for(video_path)
    if not proxy.exists() or proxy.stat().st_size < 4096:
        return False
    proxy_ms = probe_duration_ms(str(proxy))
    if proxy_ms <= 0:
        return False
    source_ms = probe_duration_ms(video_path)
    if source_ms > 0 and proxy_ms < int(source_ms * 0.9):
        return False
    return True


def _extract_frame_jpeg(media_path: str, position_ms: int, *, max_height: int) -> Optional[bytes]:
    if position_ms < 0:
        position_ms = 0
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-an",
        "-sn",
        "-dn",
        "-ss",
        f"{position_ms / 1000.0:.3f}",
        "-i",
        media_path,
        "-frames:v",
        "1",
        "-vf",
        f"scale=-2:{max_height}",
        "-f",
        "image2",
        "-c:v",
        "mjpeg",
        "-q:v",
        "5",
        "pipe:1",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=20, check=False)
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


class _FrameSignals(QObject):
    ready = Signal(int, int, object)
    failed = Signal(int, int)


class _FrameWorker(QRunnable):
    def __init__(self, media_path: str, position_ms: int, request_id: int, max_height: int):
        super().__init__()
        self.media_path = media_path
        self.position_ms = position_ms
        self.request_id = request_id
        self.max_height = max_height
        self.signals = _FrameSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        data = _extract_frame_jpeg(
            self.media_path, self.position_ms, max_height=self.max_height
        )
        if data:
            image = QImage()
            if image.loadFromData(data):
                self.signals.ready.emit(self.request_id, self.position_ms, image)
                return
        self.signals.failed.emit(self.request_id, self.position_ms)


class _ProxyBuilder(QThread):
    progress_changed = Signal(int)
    partial_duration_ms = Signal(int)
    partial_ready = Signal(str)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, video_path: str, duration_ms: int):
        super().__init__()
        self.video_path = video_path
        self.duration_ms = max(0, duration_ms)
        self.proxy_path = proxy_path_for(video_path)
        self._cancelled = False
        self._partial_emitted = False
        self._process: subprocess.Popen[str] | None = None

    def cancel(self):
        self._cancelled = True
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()

    def run(self):
        if self._cancelled:
            return

        self.proxy_path.parent.mkdir(parents=True, exist_ok=True)
        partial = self.proxy_path.with_suffix(".part.mp4")
        partial.unlink(missing_ok=True)

        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-nostats",
            "-progress",
            "pipe:2",
            "-i",
            self.video_path,
            "-vf",
            "scale=-2:720",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-g",
            "48",
            "-keyint_min",
            "48",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+frag_keyframe+empty_moov+default_base_moof",
            str(partial),
        ]

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            self.failed.emit(str(exc))
            return

        assert self._process.stderr is not None
        for line in self._process.stderr:
            if self._cancelled:
                break
            match = _OUT_TIME_RE.search(line)
            if not match:
                continue
            out_ms = int(match.group(1)) // 1000
            self.partial_duration_ms.emit(out_ms)
            if self.duration_ms > 0:
                self.progress_changed.emit(min(99, int(out_ms * 100 / self.duration_ms)))
            if (
                not self._partial_emitted
                and partial.exists()
                and partial.stat().st_size >= _PARTIAL_MIN_BYTES
                and out_ms >= _PARTIAL_MIN_MS
            ):
                self._partial_emitted = True
                self.partial_ready.emit(str(partial))

        if self._cancelled:
            partial.unlink(missing_ok=True)
            return

        code = self._process.wait()
        self._process = None
        if code != 0 or not partial.exists():
            partial.unlink(missing_ok=True)
            self.failed.emit("Proxy transcode failed.")
            return

        partial.replace(self.proxy_path)
        self.progress_changed.emit(100)
        self.finished_ok.emit(str(self.proxy_path))


class TranscodedPlayback(QObject):
    """Manages proxy transcode and FFmpeg scrub previews for AV1/VP9 sources."""

    player_source_changed = Signal(str)
    preview_image = Signal(object)
    build_progress = Signal(int)
    build_failed = Signal(str)

    def __init__(self, source_path: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.source_path = source_path
        self.duration_ms = probe_duration_ms(source_path)
        self._player_path: Optional[str] = None
        self._partial_path: Optional[str] = None
        self._partial_duration_ms = 0
        self._builder: Optional[_ProxyBuilder] = None
        self._pending_ms = 0
        self._request_id = 0
        self._in_flight = False
        self._scrubbing = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._start_frame_request)

    def start(self):
        proxy = proxy_path_for(self.source_path)
        if proxy.exists() and not proxy_is_complete(self.source_path):
            proxy.unlink(missing_ok=True)

        if proxy_is_complete(self.source_path):
            self._set_player_source(str(proxy))
            return

        self._builder = _ProxyBuilder(self.source_path, self.duration_ms)
        self._builder.progress_changed.connect(self.build_progress)
        self._builder.partial_duration_ms.connect(self._on_partial_duration)
        self._builder.partial_ready.connect(self._on_partial_ready)
        self._builder.finished_ok.connect(self._on_build_finished)
        self._builder.failed.connect(self.build_failed)
        self._builder.finished.connect(self._builder.deleteLater)
        self._builder.start()

    def stop(self):
        self._timer.stop()
        self._request_id += 1
        self._in_flight = False
        if self._builder is not None:
            self._builder.cancel()
            self._builder.wait(1000)
            self._builder = None

    @property
    def player_media_path(self) -> Optional[str]:
        return self._player_path

    @property
    def use_preview_scrub(self) -> bool:
        return self._player_path is None

    def set_scrubbing(self, active: bool):
        self._scrubbing = active

    def scrub_limit_ms(self) -> int:
        if self.duration_ms <= 0:
            return 0
        if self._partial_duration_ms > 0 and self._player_path is None:
            return min(self.duration_ms, self._partial_duration_ms)
        return self.duration_ms

    def request_preview(self, position_ms: int, *, force: bool = False):
        if self._player_path is not None:
            return
        self._pending_ms = max(0, position_ms)
        if self._scrubbing:
            if self._in_flight:
                self._request_id += 1
                self._in_flight = False
            self._start_frame_request()
            return
        if force:
            self._request_id += 1
            self._in_flight = False
            self._start_frame_request()
            return
        if self._in_flight:
            return
        self._timer.start()

    def _preview_media_path(self) -> str:
        if self._partial_path and self._partial_duration_ms >= _PARTIAL_MIN_MS:
            partial = Path(self._partial_path)
            if partial.exists() and partial.stat().st_size >= _PARTIAL_MIN_BYTES:
                return str(partial)
        return self.source_path

    def _preview_height(self, media_path: str) -> int:
        if os.path.abspath(media_path) == os.path.abspath(self.source_path):
            return 240
        return 480

    def _start_frame_request(self):
        if self._player_path is not None or self._in_flight:
            return
        media_path = self._preview_media_path()
        self._in_flight = True
        self._request_id += 1
        request_id = self._request_id
        position_ms = min(self._pending_ms, self.scrub_limit_ms() or self._pending_ms)

        worker = _FrameWorker(
            media_path, position_ms, request_id, self._preview_height(media_path)
        )
        worker.signals.ready.connect(self._on_frame_ready)
        worker.signals.failed.connect(self._on_frame_failed)
        QThreadPool.globalInstance().start(worker)

    @Slot(int, int, object)
    def _on_frame_ready(self, request_id: int, position_ms: int, image: QImage):
        if request_id != self._request_id or self._player_path is not None:
            return
        self._in_flight = False
        self.preview_image.emit(image)
        if abs(position_ms - self._pending_ms) >= 50 and self._scrubbing:
            self.request_preview(self._pending_ms)

    @Slot(int, int)
    def _on_frame_failed(self, request_id: int, position_ms: int):
        if request_id != self._request_id:
            return
        self._in_flight = False

    @Slot(int)
    def _on_partial_duration(self, duration_ms: int):
        if duration_ms > self._partial_duration_ms:
            self._partial_duration_ms = duration_ms

    @Slot(str)
    def _on_partial_ready(self, partial_path: str):
        if self._player_path:
            return
        self._partial_path = partial_path
        self._set_player_source(partial_path)

    @Slot(str)
    def _on_build_finished(self, proxy_path: str):
        self._builder = None
        self._partial_path = None
        self._partial_duration_ms = 0
        self._set_player_source(proxy_path)

    def _set_player_source(self, path: str):
        self._player_path = path
        self._timer.stop()
        self._request_id += 1
        self._in_flight = False
        self.player_source_changed.emit(path)