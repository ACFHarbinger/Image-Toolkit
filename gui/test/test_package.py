"""Standalone GUI package boundary tests."""

from __future__ import annotations

import sys

import cel_shaded_generator_gui
from cel_shaded_generator_gui.platform import IMAGE_FILE_DIALOG_FILTER


def test_gui_uses_stable_namespace() -> None:
    assert cel_shaded_generator_gui.__name__ == "cel_shaded_generator_gui"
    assert "manga_gui" not in sys.modules


def test_gui_owns_its_image_dialog_configuration() -> None:
    assert IMAGE_FILE_DIALOG_FILTER.startswith("Images (")
    assert "gui.src.constants" not in sys.modules
