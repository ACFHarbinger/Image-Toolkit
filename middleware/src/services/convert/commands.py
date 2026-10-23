"""Commands and results for the Convert service (Issue #881, Wave 0e W0-17).

Immutable frozen dataclasses representing input parameters and results
for single and batch image conversion operations.
"""

from __future__ import annotations

from dataclasses import dataclass

from middleware.src.services.base import Command, Result


@dataclass(frozen=True)
class ConvertSingleCommand(Command):
    """Command to convert a single image file to a desired format."""

    input_path: str
    output_path: str
    output_format: str = "png"
    quality: int = 95
    overwrite: bool = True


@dataclass(frozen=True)
class BatchConvertCommand(Command):
    """Command to convert a directory of images matching input formats."""

    input_dir: str
    output_dir: str
    output_format: str = "png"
    input_formats: tuple[str, ...] = ("webp", "png", "jpg", "jpeg")
    quality: int = 95
    recursive: bool = False
    overwrite: bool = True


@dataclass(frozen=True)
class ConvertSingleResult(Result):
    """Result of converting a single image file."""

    input_path: str
    output_path: str
    success: bool
    size_bytes: int = 0
    elapsed_seconds: float = 0.0
    error: str | None = None


@dataclass(frozen=True)
class BatchConvertResult(Result):
    """Aggregated result of a batch conversion operation."""

    total_discovered: int
    succeeded: int
    failed: int
    output_paths: tuple[str, ...] = ()
    elapsed_seconds: float = 0.0
    errors: tuple[str, ...] = ()
