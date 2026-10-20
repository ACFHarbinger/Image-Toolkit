"""Command handlers for the Convert service (Issue #881, Wave 0e W0-17).

Executes conversion commands independently of UI or transport frameworks.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from middleware.src.services.base import CommandValidationError, Handler
from middleware.src.services.convert.commands import (
    BatchConvertCommand,
    BatchConvertResult,
    ConvertSingleCommand,
    ConvertSingleResult,
)

SUPPORTED_FORMATS = frozenset({"jpg", "jpeg", "png", "webp", "bmp", "tiff", "tif", "ico", "gif"})


class ConvertSingleHandler(Handler[ConvertSingleCommand, ConvertSingleResult]):
    """Handler for single image conversion."""

    def handle(self, command: ConvertSingleCommand) -> ConvertSingleResult:
        t0 = time.monotonic()
        in_p = Path(command.input_path)
        out_p = Path(command.output_path)

        if not in_p.is_file():
            return ConvertSingleResult(
                input_path=command.input_path,
                output_path=command.output_path,
                success=False,
                elapsed_seconds=round(time.monotonic() - t0, 4),
                error=f"Input file does not exist: {command.input_path}",
            )

        if out_p.exists() and not command.overwrite:
            return ConvertSingleResult(
                input_path=command.input_path,
                output_path=command.output_path,
                success=False,
                elapsed_seconds=round(time.monotonic() - t0, 4),
                error=f"Output file already exists and overwrite=False: {command.output_path}",
            )

        fmt_key = command.output_format.lower().lstrip(".")
        if fmt_key not in SUPPORTED_FORMATS:
            raise CommandValidationError("Unsupported output format", field="output_format")
        if command.quality != 95:
            raise CommandValidationError("The canonical converter does not support a quality override", field="quality")
        if in_p.resolve() == out_p.resolve():
            raise CommandValidationError("Input and output must be different files", field="output_path")

        try:
            from middleware.src.core.image.image_converter import ImageFormatConverter

            out_p.parent.mkdir(parents=True, exist_ok=True)
            # Commit only a complete conversion; failure must preserve an existing destination.
            with tempfile.TemporaryDirectory(prefix=".itk-convert-", dir=out_p.parent) as temporary:
                staged = Path(temporary) / f"output.{fmt_key}"
                if not ImageFormatConverter.convert_single_image(str(in_p), str(staged), format=fmt_key):
                    raise OSError("The canonical converter failed to produce an image")
                if command.overwrite:
                    os.replace(staged, out_p)
                else:
                    os.link(staged, out_p)

            size = out_p.stat().st_size if out_p.exists() else 0
            return ConvertSingleResult(
                input_path=command.input_path,
                output_path=str(out_p),
                success=True,
                size_bytes=size,
                elapsed_seconds=round(time.monotonic() - t0, 4),
            )
        except Exception as e:
            return ConvertSingleResult(
                input_path=command.input_path,
                output_path=command.output_path,
                success=False,
                elapsed_seconds=round(time.monotonic() - t0, 4),
                error=str(e),
            )


class BatchConvertHandler(Handler[BatchConvertCommand, BatchConvertResult]):
    """Handler for batch directory image conversion."""

    def __init__(self, single_handler: Handler[ConvertSingleCommand, ConvertSingleResult] | None = None) -> None:
        self._single_handler = single_handler or ConvertSingleHandler()

    def handle(self, command: BatchConvertCommand) -> BatchConvertResult:
        t0 = time.monotonic()
        in_dir = Path(command.input_dir)
        out_dir = Path(command.output_dir)

        if not in_dir.is_dir():
            raise CommandValidationError(f"Input directory does not exist: {command.input_dir}", field="input_dir")

        out_dir.mkdir(parents=True, exist_ok=True)

        target_exts = {fmt.lower().lstrip(".") for fmt in command.input_formats}
        out_ext = command.output_format.lower().lstrip(".")

        # Discover matching files
        candidates: list[Path] = []
        if command.recursive:
            for root, directories, files in os.walk(in_dir):
                directories[:] = [d for d in directories if (Path(root) / d).resolve() != out_dir.resolve()]
                for f in files:
                    ext = Path(f).suffix.lower().lstrip(".")
                    if ext in target_exts:
                        candidates.append(Path(root) / f)
        else:
            for item in in_dir.iterdir():
                if item.is_file():
                    ext = item.suffix.lower().lstrip(".")
                    if ext in target_exts:
                        candidates.append(item)

        candidates.sort()

        destinations = [out_dir / src.relative_to(in_dir).with_suffix("." + out_ext) for src in candidates]
        if len({path.resolve() for path in destinations}) != len(destinations):
            raise CommandValidationError("Multiple inputs map to the same output file", field="output_dir")

        succeeded = 0
        failed = 0
        outputs: list[str] = []
        errors: list[str] = []

        for src in candidates:
            rel_name = src.stem + "." + out_ext
            if command.recursive:
                rel_dir = src.parent.relative_to(in_dir)
                dest = out_dir / rel_dir / rel_name
            else:
                dest = out_dir / rel_name

            sub_cmd = ConvertSingleCommand(
                input_path=str(src),
                output_path=str(dest),
                output_format=command.output_format,
                quality=command.quality,
                overwrite=command.overwrite,
            )
            res = self._single_handler.handle(sub_cmd)
            if res.success:
                succeeded += 1
                outputs.append(res.output_path)
            else:
                failed += 1
                errors.append(f"{src.name}: {res.error}")

        return BatchConvertResult(
            total_discovered=len(candidates),
            succeeded=succeeded,
            failed=failed,
            output_paths=tuple(outputs),
            elapsed_seconds=round(time.monotonic() - t0, 4),
            errors=tuple(errors),
        )
