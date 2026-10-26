"""The wired CSG delegate calls the solver and writes a real image."""

from __future__ import annotations

from pathlib import Path

from middleware.src.services.csg.commands import (
    ArapDeformCommand,
    ColorizeReferenceCommand,
    ColorizeScribbleCommand,
    TemporalPropagateCommand,
)
from middleware.src.services.csg.delegate import SOLVER_UNAVAILABLE, SubmoduleCsgDelegate
from middleware.src.sidecar.handlers.csg import csg_service
from PIL import Image


def _gray(path: Path, size: int = 32) -> str:
    image = Image.new("L", (size, size), 240)
    for x in range(size):
        image.putpixel((x, size // 2), 0)
    image.save(path)
    return str(path)


def _color_mark(path: Path, size: int = 32) -> str:
    image = Image.new("RGB", (size, size), (255, 255, 255))
    for y in range(8, 16):
        for x in range(8, 16):
            image.putpixel((x, y), (220, 30, 30))
    image.save(path)
    return str(path)


def test_factory_supplies_the_submodule_delegate() -> None:
    service = csg_service()
    assert isinstance(service._delegate, SubmoduleCsgDelegate)


def test_scribble_delegate_writes_a_real_image(tmp_path: Path) -> None:
    line = _gray(tmp_path / "line.png")
    scribble = _color_mark(tmp_path / "scribble.png")
    out = tmp_path / "out.png"

    result = SubmoduleCsgDelegate().colorize_scribble(
        ColorizeScribbleCommand(lineart_path=line, scribble_path=scribble, output_path=str(out))
    )

    assert result.error != SOLVER_UNAVAILABLE
    assert result.success is True
    assert result.width == 32
    assert result.height == 32
    assert out.is_file()
    assert out.stat().st_size > 0
    with Image.open(out) as written:
        assert written.size == (32, 32)
        assert written.convert("RGB").getpixel((12, 12)) != (255, 255, 255)


def test_reference_delegate_writes_a_real_image(tmp_path: Path) -> None:
    line = _gray(tmp_path / "line.png")
    reference = _color_mark(tmp_path / "reference.png")
    out = tmp_path / "out.png"

    result = SubmoduleCsgDelegate().colorize_reference(
        ColorizeReferenceCommand(lineart_path=line, reference_path=reference, output_path=str(out))
    )

    assert result.success is True, result.error
    assert result.width == 32
    assert result.height == 32
    assert out.stat().st_size > 0


def test_arap_delegate_reports_the_solved_mesh(tmp_path: Path) -> None:
    image = _color_mark(tmp_path / "plate.png", size=48)
    out = tmp_path / "posed.png"

    result = SubmoduleCsgDelegate().arap_deform(
        ArapDeformCommand(
            image_path=image,
            control_points=((8.0, 8.0), (40.0, 40.0)),
            target_points=((12.0, 14.0), (36.0, 42.0)),
            output_path=str(out),
            mesh_resolution=12,
        )
    )

    assert result.success is True, result.error
    assert result.num_vertices > 0
    assert result.num_triangles > 0
    assert result.num_vertices != 8
    assert out.stat().st_size > 0


def test_propagate_delegate_requires_a_keyframe_color(tmp_path: Path) -> None:
    frame_a = _gray(tmp_path / "a.png")
    frame_b = _gray(tmp_path / "b.png")
    out_dir = tmp_path / "frames"

    result = SubmoduleCsgDelegate().propagate_sequence(
        TemporalPropagateCommand(frame_paths=(frame_a, frame_b), output_dir=str(out_dir))
    )

    assert result.success is False
    assert "keyframe color" in (result.error or "")
    assert not out_dir.exists()


def test_propagate_delegate_writes_each_frame(tmp_path: Path) -> None:
    frame_a = _gray(tmp_path / "a.png")
    frame_b = _gray(tmp_path / "b.png")
    key = _color_mark(tmp_path / "key.png")
    out_dir = tmp_path / "frames"

    result = SubmoduleCsgDelegate().propagate_sequence(
        TemporalPropagateCommand(
            frame_paths=(frame_a, frame_b),
            keyframe_index=0,
            keyframe_color_path=key,
            output_dir=str(out_dir),
        )
    )

    assert result.success is True, result.error
    assert result.frames_processed == 2
    assert len(result.output_paths) == 2
    for path in result.output_paths:
        assert Path(path).stat().st_size > 0
