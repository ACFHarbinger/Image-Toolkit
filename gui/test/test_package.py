"""Standalone GUI package boundary tests."""

from __future__ import annotations

import sys

import csg_gui
from csg_gui.platform import IMAGE_FILE_DIALOG_FILTER


def test_gui_uses_stable_namespace() -> None:
    assert csg_gui.__name__ == "csg_gui"
    assert "manga_gui" not in sys.modules


def test_gui_owns_its_image_dialog_configuration() -> None:
    assert IMAGE_FILE_DIALOG_FILTER.startswith("Images (")
    assert "gui.src.constants" not in sys.modules
