"""Unit tests for the Cel-Shaded Generator (CSG) service (W0-03 Phase C, #867)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from middleware.src.services.base import CommandValidationError
from middleware.src.services.csg import (
    ArapDeformCommand,
    ColorizeReferenceCommand,
    ColorizeScribbleCommand,
    ColorizeScribbleResult,
    CsgService,
    CsgServiceProtocol,
    TemporalPropagateCommand,
)
from PIL import Image


def _create_sample_file(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (64, 64), (200, 200, 200))
    img.save(path)
    return str(path)


def _lineart(path: Path, size: tuple[int, int] = (64, 64)) -> str:
    image = Image.new("RGB", size, (230, 230, 230))
    draw = image.load()
    width, height = size
    assert draw is not None
    for x in range(width):
        draw[x, height // 2] = (20, 20, 20)
        draw[x, min(height - 1, height // 2 + 1)] = (20, 20, 20)
    for y in range(height):
        draw[width // 3, y] = (20, 20, 20)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return str(path)


def _scribble(path: Path, size: tuple[int, int] = (64, 64), *, colored: bool = True) -> str:
    image = Image.new("RGB", size, (230, 230, 230))
    if colored:
        draw = image.load()
        assert draw is not None
        for y in range(16, 26):
            for x in range(10, 36):
                draw[x, y] = (220, 24, 24)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return str(path)


def _reference(path: Path, size: tuple[int, int] = (64, 64)) -> str:
    image = Image.new("RGB", size, (230, 200, 160))
    draw = image.load()
    width, height = size
    assert draw is not None
    for y in range(height // 2):
        for x in range(width):
            draw[x, y] = (36, 96, 210)
    for y in range(height // 2, height):
        for x in range(width // 2):
            draw[x, y] = (210, 40, 56)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return str(path)


def _assert_real_png(path: str, width: int, height: int) -> None:
    file_path = Path(path)
    assert file_path.is_file()
    assert file_path.stat().st_size > 0
    with Image.open(file_path) as image:
        image.load()
        assert image.size == (width, height)


def test_csg_protocol_conformance() -> None:
    service = CsgService()
    assert isinstance(service, CsgServiceProtocol)


def test_csg_command_immutability() -> None:
    cmd = ColorizeScribbleCommand(lineart_path="/l.png", scribble_path="/s.png")
    with pytest.raises(dataclasses.FrozenInstanceError):
        cmd.intensity = 0.5  # type: ignore[misc]

    res = ColorizeScribbleResult(success=True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        res.success = False  # type: ignore[misc]


def test_colorize_scribble_validation() -> None:
    service = CsgService()
    with pytest.raises(CommandValidationError):
        service.colorize_scribble(
            ColorizeScribbleCommand(lineart_path="/missing_l.png", scribble_path="/missing_s.png")
        )


def test_colorize_scribble_execution(tmp_path: Path) -> None:
    line = _lineart(tmp_path / "line.png")
    scrb = _scribble(tmp_path / "scrb.png")
    out = str(tmp_path / "colorized.png")

    service = CsgService()
    result = service.colorize_scribble(
        ColorizeScribbleCommand(lineart_path=line, scribble_path=scrb, output_path=out)
    )
    assert result.success is True, result.error
    assert result.output_path == out
    assert result.width == 64
    assert result.height == 64
    _assert_real_png(out, result.width, result.height)


def test_colorize_scribble_empty_mask_writes_nothing(tmp_path: Path) -> None:
    line = _lineart(tmp_path / "line.png")
    scrb = _scribble(tmp_path / "flat.png", colored=False)
    out = tmp_path / "colorized.png"

    service = CsgService()
    result = service.colorize_scribble(
        ColorizeScribbleCommand(lineart_path=line, scribble_path=scrb, output_path=str(out))
    )
    assert result.success is False
    assert result.error is not None
    assert "empty" in result.error.lower()
    assert not out.exists()


def test_colorize_reference_validation() -> None:
    service = CsgService()
    with pytest.raises(CommandValidationError):
        service.colorize_reference(
            ColorizeReferenceCommand(lineart_path="/missing_l.png", reference_path="/missing_r.png")
        )


def test_colorize_reference_execution(tmp_path: Path) -> None:
    line = _lineart(tmp_path / "ref_line.png")
    ref = _reference(tmp_path / "ref_img.png")
    out = str(tmp_path / "ref_out.png")

    service = CsgService()
    result = service.colorize_reference(
        ColorizeReferenceCommand(lineart_path=line, reference_path=ref, output_path=out)
    )
    assert result.success is True, result.error
    assert result.output_path == out
    assert result.width == 64
    assert result.height == 64
    _assert_real_png(out, result.width, result.height)


def test_arap_deform_validation(tmp_path: Path) -> None:
    img = _create_sample_file(tmp_path / "char.png")
    service = CsgService()
    # Missing image
    with pytest.raises(CommandValidationError):
        service.arap_deform(
            ArapDeformCommand(
                image_path="/missing_char.png",
                control_points=((10.0, 10.0),),
                target_points=((15.0, 15.0),),
            )
        )
    # Mismatched points count
    with pytest.raises(CommandValidationError):
        service.arap_deform(
            ArapDeformCommand(
                image_path=img,
                control_points=((10.0, 10.0), (20.0, 20.0)),
                target_points=((15.0, 15.0),),
            )
        )


def test_arap_deform_execution(tmp_path: Path) -> None:
    img = _create_sample_file(tmp_path / "character.png")
    out = str(tmp_path / "deformed.png")

    service = CsgService()
    result = service.arap_deform(
        ArapDeformCommand(
            image_path=img,
            control_points=((10.0, 10.0), (50.0, 50.0)),
            target_points=((15.0, 12.0), (48.0, 55.0)),
            output_path=out,
        )
    )
    assert result.success is True, result.error
    assert result.output_path == out
    assert result.num_vertices > 0
    assert result.num_triangles > 0
    _assert_real_png(out, 64, 64)


def test_propagate_sequence_validation() -> None:
    service = CsgService()
    with pytest.raises(CommandValidationError):
        service.propagate_sequence(TemporalPropagateCommand(frame_paths=()))


def test_propagate_sequence_execution(tmp_path: Path) -> None:
    f1 = _scribble(tmp_path / "f1.png")
    f2 = _lineart(tmp_path / "f2.png")
    out_dir = tmp_path / "anim_out"

    service = CsgService()
    result = service.propagate_sequence(
        TemporalPropagateCommand(frame_paths=(f1, f2), output_dir=str(out_dir))
    )
    assert result.success is True, result.error
    assert result.frames_processed == 2
    assert len(result.output_paths) == 2
    for path in result.output_paths:
        _assert_real_png(path, 64, 64)
