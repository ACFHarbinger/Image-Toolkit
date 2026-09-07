"""Tests for PreviewContext value object and PreviewService (ui-arch-40 / #562)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from gui.src.services.preview_service import (
    PreviewContext,
    PreviewService,
    get_preview_service,
    launch_external_player,
    open_preview,
)
from PySide6.QtGui import QColor, QImage

pytestmark = pytest.mark.gui


@pytest.fixture
def sample_image(tmp_path):
    path = str(tmp_path / "test_preview.png")
    img = QImage(100, 100, QImage.Format.Format_RGB32)
    img.fill(QColor(100, 150, 200))
    img.save(path)
    return path


@pytest.fixture
def sample_video(tmp_path):
    path = str(tmp_path / "test_video.mp4")
    with open(path, "wb") as f:
        f.write(b"fake video content")
    return path


def test_preview_context_initialization():
    ctx = PreviewContext(path="/fake/image.png")
    assert ctx.items == ["/fake/image.png"]
    assert ctx.start_index == 0
    assert not ctx.is_video

    ctx2 = PreviewContext(
        path="/fake/b.png",
        items=["/fake/a.png", "/fake/b.png", "/fake/c.png"],
    )
    assert ctx2.start_index == 1
    assert not ctx2.is_video

    ctx3 = PreviewContext(
        path="/fake/d.png",
        items=["/fake/a.png", "/fake/b.png"],
    )
    assert "/fake/d.png" in ctx3.items
    assert ctx3.start_index == 2

    ctx_video = PreviewContext(path="/fake/movie.mkv")
    assert ctx_video.is_video


def test_launch_external_player_nonexistent():
    assert not launch_external_player("/nonexistent/video.mp4")


def test_launch_external_player_success(sample_video):
    with patch("subprocess.Popen") as mock_popen, patch("platform.system", return_value="Linux"):
        assert launch_external_player(sample_video)
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args == ["xdg-open", sample_video]


def test_preview_service_nonexistent_file():
    service = PreviewService()
    ctx = PreviewContext(path="/nonexistent/file.png")
    result = service.open_preview(ctx)
    assert result is None


def test_preview_service_video_delegation(sample_video):
    service = PreviewService()
    ctx = PreviewContext(path=sample_video)
    with patch("gui.src.services.preview_service.launch_external_player", return_value=True) as mock_launch:
        result = service.open_preview(ctx)
        assert result is None
        mock_launch.assert_called_once_with(sample_video, parent=None)


def test_preview_service_image_preview(sample_image, q_app):
    service = PreviewService()
    mock_db = MagicMock()
    path_changed_calls = []

    def on_changed(old, new):
        path_changed_calls.append((old, new))

    ctx = PreviewContext(
        path=sample_image,
        database_service=mock_db,
        on_path_changed=on_changed,
    )
    win = service.open_preview(ctx)
    assert win is not None
    assert win.database_service is mock_db
    assert win.image_path == sample_image
    assert len(service.open_windows) == 1
    assert service.open_windows[0] is win

    # Opening the same image again returns the same window
    win2 = service.open_preview(ctx)
    assert win2 is win
    assert len(service.open_windows) == 1

    # Closing preview
    service.close_preview(sample_image)
    assert len(service.open_windows) == 0


def test_preview_service_close_all(sample_image, tmp_path, q_app):
    img2_path = str(tmp_path / "img2.png")
    img = QImage(50, 50, QImage.Format.Format_RGB32)
    img.save(img2_path)

    service = PreviewService()
    w1 = service.open_preview(PreviewContext(path=sample_image))
    w2 = service.open_preview(PreviewContext(path=img2_path))
    assert w1 is not None and w2 is not None

    assert len(service.open_windows) == 2
    service.close_all()
    assert len(service.open_windows) == 0


def test_open_preview_convenience_helper(sample_image, q_app):
    win = open_preview(path=sample_image)
    assert win is not None
    global_svc = get_preview_service()
    assert win in global_svc.open_windows
    global_svc.close_all()
