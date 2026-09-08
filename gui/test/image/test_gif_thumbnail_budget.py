"""Oversized GIFs must not go through QImageReader (gallery crash)."""

from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtGui import QImage

from gui.src.helpers.image._qimagereader_disk_cache import (
    QIR_GIF_BYTE_BUDGET,
    load_qir_thumbnail,
)

pytestmark = pytest.mark.gui


def _write_gif(path: Path) -> Path:
    Image.new("RGB", (12, 8), color=(255, 0, 0)).save(path, format="GIF")
    return path


def _isolate_cache(monkeypatch, tmp_path: Path) -> Path:
    cache = tmp_path / "qir-cache"
    cache.mkdir()
    monkeypatch.setattr(
        "gui.src.helpers.image._qimagereader_disk_cache.THUMBNAIL_CACHE_DIR",
        cache,
    )
    return cache


def test_small_gif_thumbnails_via_qimage_reader(q_app, tmp_path, monkeypatch):
    _isolate_cache(monkeypatch, tmp_path)
    gif = _write_gif(tmp_path / "small.gif")
    img = load_qir_thumbnail(str(gif), 32)
    assert not img.isNull()
    assert img.width() <= 32
    assert img.height() <= 32


def test_oversized_gif_skips_qimage_reader(q_app, tmp_path, monkeypatch):
    _isolate_cache(monkeypatch, tmp_path)
    gif = _write_gif(tmp_path / "huge.gif")
    poster = QImage(16, 10, QImage.Format.Format_RGB32)
    poster.fill(0)

    def _fail_reader(*_args, **_kwargs):
        raise AssertionError("QImageReader must not open oversized GIFs")

    monkeypatch.setattr(
        "gui.src.helpers.image._qimagereader_disk_cache._file_size",
        lambda _path: QIR_GIF_BYTE_BUDGET + 1,
    )
    monkeypatch.setattr(
        "gui.src.helpers.image._qimagereader_disk_cache.QImageReader",
        _fail_reader,
    )
    monkeypatch.setattr(
        "gui.src.helpers.image._qimagereader_disk_cache._gif_poster_via_ffmpeg",
        lambda _path, _size: poster,
    )

    img = load_qir_thumbnail(str(gif), 32)
    assert not img.isNull()
    assert img.width() == 16


def test_cached_oversized_gif_does_not_redecode(q_app, tmp_path, monkeypatch):
    _isolate_cache(monkeypatch, tmp_path)
    gif = _write_gif(tmp_path / "cached.gif")
    first = load_qir_thumbnail(str(gif), 32)
    assert not first.isNull()

    def _fail_reader(*_args, **_kwargs):
        raise AssertionError("cache hit must not construct QImageReader")

    monkeypatch.setattr(
        "gui.src.helpers.image._qimagereader_disk_cache.QImageReader",
        _fail_reader,
    )
    monkeypatch.setattr(
        "gui.src.helpers.image._qimagereader_disk_cache._gif_poster_via_ffmpeg",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("cache hit")),
    )
    second = load_qir_thumbnail(str(gif), 32)
    assert not second.isNull()


def test_image_loader_worker_uses_shared_thumbnail_path(q_app, tmp_path, monkeypatch):
    from gui.src.helpers.image.image_loader_worker import ImageLoaderWorker

    _isolate_cache(monkeypatch, tmp_path)
    gif = _write_gif(tmp_path / "worker.gif")
    seen = []

    def _fake_load(path, size):
        seen.append((path, size))
        img = QImage(8, 8, QImage.Format.Format_RGB32)
        img.fill(0)
        return img

    monkeypatch.setattr(
        "gui.src.helpers.image.image_loader_worker.load_qir_thumbnail",
        _fake_load,
    )
    out = ImageLoaderWorker._load_via_qimagereader(str(gif), 48)
    assert seen == [(str(gif), 48)]
    assert not out.isNull()


def test_ffmpeg_gif_poster_reads_first_frame(q_app, tmp_path):
    from gui.src.helpers.video.video_thumbnailer import VideoThumbnailer

    thumb = VideoThumbnailer()
    if not thumb.has_ffmpeg:
        pytest.skip("ffmpeg unavailable")
    gif = _write_gif(tmp_path / "poster.gif")
    img = thumb.generate_gif_poster(str(gif), 24)
    assert img is not None
    assert not img.isNull()
    assert img.width() <= 24 or img.height() <= 24
