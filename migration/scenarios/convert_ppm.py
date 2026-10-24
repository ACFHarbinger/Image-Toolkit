"""Convert differential: the service and the canonical converter (#883).

Both sides encode one generated PPM. The projection is success, the PNG
signature, and the byte size. Elapsed time is not part of the comparison.
"""

from __future__ import annotations

from pathlib import Path


def pair(tmp: Path) -> tuple[dict[str, object], dict[str, object]]:
    """Return ``(legacy, service)`` projections for one 2×2 PPM."""
    source = tmp / "in.ppm"
    source.write_bytes(b"P6\n2 2\n255\n" + (b"\xff\x00\x00" * 4))
    legacy_out = tmp / "legacy.png"
    service_out = tmp / "service.png"
    return _legacy(source, legacy_out), _service(source, service_out)


def _legacy(source: Path, dest: Path) -> dict[str, object]:
    from middleware.src.core.image.image_converter import ImageFormatConverter

    ok = bool(ImageFormatConverter.convert_single_image(str(source), str(dest), format="png"))
    return _view(dest, ok)


def _service(source: Path, dest: Path) -> dict[str, object]:
    from middleware.src.services.convert.commands import ConvertSingleCommand
    from middleware.src.services.convert.service import ConvertService

    result = ConvertService().convert_single(
        ConvertSingleCommand(
            input_path=str(source),
            output_path=str(dest),
            output_format="png",
            overwrite=True,
        )
    )
    return _view(dest, bool(result.success))


def _view(path: Path, ok: bool) -> dict[str, object]:
    data = path.read_bytes() if path.is_file() else b""
    return {"ok": ok, "png": data.startswith(b"\x89PNG\r\n\x1a\n"), "size": len(data)}
