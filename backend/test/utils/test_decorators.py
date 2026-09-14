"""Tests for reusable backend decorators."""

from __future__ import annotations

from pathlib import Path

import pytest
from backend.src.utils.decorators import require_path


def test_require_path_passes_existing_positional_and_keyword_paths(tmp_path: Path) -> None:
    path = tmp_path / "input.png"
    path.touch()

    @require_path("input_path")
    def read(input_path: str, *, marker: str = "ok") -> tuple[str, str]:
        return input_path, marker

    assert read(str(path)) == (str(path), "ok")
    assert read(input_path=str(path), marker="validated") == (str(path), "validated")


def test_require_path_names_the_missing_parameter(tmp_path: Path) -> None:
    missing = tmp_path / "missing.png"

    @require_path("source_path")
    def read(source_path: str) -> None:
        return None

    with pytest.raises(FileNotFoundError, match="source_path=.*missing\\.png.*does not exist"):
        read(str(missing))


@pytest.mark.parametrize("optional_path", [None, ""])
def test_require_path_skips_empty_optional_parameters(optional_path: str | None) -> None:
    @require_path("optional_path")
    def operation(optional_path: str | None = None) -> str | None:
        return optional_path

    assert operation() is None
    assert operation(optional_path) == optional_path
