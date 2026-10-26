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


def test_match_frames_unreadable_file(tmp_path: Path) -> None:
    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    other = _create_sample_frame(tmp_path / "other.png")
    service = StitchService()
    result = service.match_frames(
        MatchFramesCommand(image_path_1=str(empty), image_path_2=other)
    )
    assert result.success is False
    assert result.error
    assert result.inlier_count != 100
    assert result.confidence != 0.95
    assert result.transform_matrix is None


def _overlap_count(path_1: str, path_2: str, transform: tuple[tuple[float, ...], ...]) -> int:
    import cv2
    import numpy as np

    img1 = cv2.imread(path_1)
    img2 = cv2.imread(path_2)
    assert img1 is not None and img2 is not None
    matrix = np.asarray(transform, dtype=np.float64)
    height, width = img2.shape[:2]
    warped = cv2.warpAffine(img1, matrix, (width, height))
    return int(np.count_nonzero(np.any(warped != 0, axis=-1)))


def test_match_frames_execution(tmp_path: Path) -> None:
    f1 = _create_sample_frame(tmp_path / "f1.png", color=(100, 150, 200))
    f2 = _create_sample_frame(tmp_path / "f2.png", color=(20, 80, 140))
    service = StitchService()
    result = service.match_frames(MatchFramesCommand(image_path_1=f1, image_path_2=f2))
    identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    stub = (
        result.inlier_count == 100
        and result.confidence == 0.95
        and result.transform_matrix == identity
    )
    if stub:
        import cv2
        from asp_backend.alignment.matching._matcher_plugins import TemplateMatcher

        img1 = cv2.imread(f1)
        img2 = cv2.imread(f2)
        matrix, confidence = TemplateMatcher().match(img1, img2)
        assert matrix is not None
        assert float(confidence) == 0.95
        assert _overlap_count(f1, f2, identity) == 100
    if result.success:
        assert result.transform_matrix is not None
        assert len(result.transform_matrix) == 2
        assert all(len(row) == 3 for row in result.transform_matrix)
        assert isinstance(result.confidence, float)
        assert 0.0 <= result.confidence <= 1.0
        assert result.inlier_count == _overlap_count(f1, f2, result.transform_matrix)
        assert not stub
    else:
        assert result.error
        assert result.transform_matrix is None
        assert "no transform" in result.error.lower() or "unavailable" in result.error.lower()


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
    assert result.success is True, result.error
    assert result.output_path == out
    assert Path(out).stat().st_size > 0
    with Image.open(out) as image:
        assert image.size != (1920, 1080)
        assert result.canvas_width == image.size[0]
        assert result.canvas_height == image.size[1]


def test_stitch_requires_a_runnable_pipeline(tmp_path):
    first = _create_sample_frame(tmp_path / "first.png")
    second = _create_sample_frame(tmp_path / "second.png")
    service = StitchService(pipeline_factory=lambda **kwargs: object())
    result = service.stitch(StitchCommand(image_paths=(first, second)))
    assert result.success is False
    assert "run operation is unavailable" in result.error
