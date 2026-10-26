"""Unit tests for the Anime Stitch Pipeline (ASP) service (W0-03 Phase C, #867)."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from middleware.src.services.asp import (
    MatchFramesCommand,
    RenderCanvasCommand,
    StitchCommand,
    StitchResult,
    StitchService,
    StitchServiceProtocol,
)
from middleware.src.services.base import CommandValidationError
from PIL import Image


def _create_sample_frame(path: Path, color: tuple[int, int, int] = (100, 150, 200)) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (64, 64), color)
    img.save(path)
    return str(path)


def test_asp_protocol_conformance() -> None:
    service = StitchService()
    assert isinstance(service, StitchServiceProtocol)


def test_asp_command_immutability() -> None:
    cmd = StitchCommand(image_paths=("/a.png", "/b.png"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        cmd.image_paths = ("/c.png",)  # type: ignore[misc]

    res = StitchResult(success=True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        res.success = False  # type: ignore[misc]


def test_stitch_validation_minimum_frames() -> None:
    service = StitchService()
    with pytest.raises(CommandValidationError) as exc_info:
        service.stitch(StitchCommand(image_paths=("/a.png",)))
    assert "at least two image paths" in str(exc_info.value)


def test_stitch_missing_files(tmp_path: Path) -> None:
    service = StitchService()
    p1 = str(tmp_path / "missing1.png")
    p2 = str(tmp_path / "missing2.png")
    result = service.stitch(StitchCommand(image_paths=(p1, p2)))
    assert result.success is False
    assert "does not exist" in (result.error or "")


def test_stitch_mock_pipeline_execution(tmp_path: Path) -> None:
    f1 = _create_sample_frame(tmp_path / "frame1.png")
    f2 = _create_sample_frame(tmp_path / "frame2.png")
    out = str(tmp_path / "stitched.png")

    mock_run_result = MagicMock(width=1920, height=2000, metrics={"alignment_score": 0.98})
    mock_pipeline = MagicMock()
    mock_pipeline.run.return_value = mock_run_result

    service = StitchService(pipeline_factory=lambda **kwargs: mock_pipeline)
    result = service.stitch(StitchCommand(image_paths=(f1, f2), output_path=out))

    assert result.success is True
    assert result.canvas_width == 1920
    assert result.canvas_height == 2000
    assert result.num_frames == 2
    assert result.metrics.get("alignment_score") == 0.98
    assert result.elapsed_seconds >= 0.0


def test_match_frames_validation(tmp_path: Path) -> None:
    service = StitchService()
    with pytest.raises(CommandValidationError):
        service.match_frames(MatchFramesCommand(image_path_1="/nonexistent1.png", image_path_2="/nonexistent2.png"))


def test_match_frames_execution(tmp_path: Path) -> None:
    f1 = _create_sample_frame(tmp_path / "f1.png")
    f2 = _create_sample_frame(tmp_path / "f2.png")
    service = StitchService()
    result = service.match_frames(MatchFramesCommand(image_path_1=f1, image_path_2=f2))
    assert result.success is True
    assert result.inlier_count > 0
    assert result.transform_matrix is not None


def test_render_canvas_validation() -> None:
    service = StitchService()
    with pytest.raises(CommandValidationError):
        service.render_canvas(RenderCanvasCommand(image_paths=()))


def test_render_canvas_execution(tmp_path: Path) -> None:
    f1 = _create_sample_frame(tmp_path / "rf1.png")
    f2 = _create_sample_frame(tmp_path / "rf2.png")
    out = str(tmp_path / "canvas.png")
    service = StitchService()
    result = service.render_canvas(RenderCanvasCommand(image_paths=(f1, f2), output_path=out))
    assert result.success is True
    assert result.output_path == out
    assert result.canvas_width > 0


def test_stitch_requires_a_runnable_pipeline(tmp_path: Path) -> None:
    first = _create_sample_frame(tmp_path / "first.png")
    second = _create_sample_frame(tmp_path / "second.png")
    service = StitchService(pipeline_factory=lambda **kwargs: object())
    result = service.stitch(StitchCommand(image_paths=(first, second)))
    assert result.success is False
    assert result.error is not None
    assert "run operation is unavailable" in result.error
