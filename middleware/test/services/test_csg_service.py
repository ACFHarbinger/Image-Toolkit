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


def test_colorize_scribble_without_delegate_is_unavailable(tmp_path: Path) -> None:
    line = _create_sample_file(tmp_path / "line.png")
    scrb = _create_sample_file(tmp_path / "scrb.png")
    out = tmp_path / "colorized.png"

    service = CsgService()
    result = service.colorize_scribble(
        ColorizeScribbleCommand(lineart_path=line, scribble_path=scrb, output_path=str(out))
    )
    assert result.success is False
    assert result.error == "CSG solver is unavailable"
    assert not out.exists()


def test_colorize_reference_validation() -> None:
    service = CsgService()
    with pytest.raises(CommandValidationError):
        service.colorize_reference(
            ColorizeReferenceCommand(lineart_path="/missing_l.png", reference_path="/missing_r.png")
        )


def test_colorize_reference_without_delegate_is_unavailable(tmp_path: Path) -> None:
    line = _create_sample_file(tmp_path / "ref_line.png")
    ref = _create_sample_file(tmp_path / "ref_img.png")
    out = tmp_path / "ref_out.png"

    service = CsgService()
    result = service.colorize_reference(
        ColorizeReferenceCommand(lineart_path=line, reference_path=ref, output_path=str(out))
    )
    assert result.success is False
    assert result.error == "CSG solver is unavailable"
    assert not out.exists()


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
    assert result.success is False
    assert result.error == "CSG solver is unavailable"
    assert not Path(out).exists()


def test_propagate_sequence_validation() -> None:
    service = CsgService()
    with pytest.raises(CommandValidationError):
        service.propagate_sequence(TemporalPropagateCommand(frame_paths=()))


def test_propagate_sequence_execution(tmp_path: Path) -> None:
    f1 = _create_sample_file(tmp_path / "f1.png")
    f2 = _create_sample_file(tmp_path / "f2.png")
    out_dir = tmp_path / "anim_out"

    service = CsgService()
    result = service.propagate_sequence(TemporalPropagateCommand(frame_paths=(f1, f2), output_dir=str(out_dir)))
    assert result.success is False
    assert result.error == "CSG solver is unavailable"
    assert result.frames_processed == 0
    assert not out_dir.exists()
