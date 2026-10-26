"""Shared pytest configuration for the standalone GUI package."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

# Qt tests run headlessly in local and CI environments.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_GUI_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"


def _load_gui_package() -> None:
    """Load the flattened source root under the public ``csg_gui`` name."""
    if "csg_gui" in sys.modules:
        return
    spec = importlib.util.spec_from_file_location(
        "csg_gui",
        _GUI_SOURCE_ROOT / "__init__.py",
        submodule_search_locations=[str(_GUI_SOURCE_ROOT)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load CSG GUI package from {_GUI_SOURCE_ROOT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["csg_gui"] = module
    spec.loader.exec_module(module)


_load_gui_package()


@pytest.fixture(scope="session")
def q_app() -> QApplication:
    """Provide one QApplication for the standalone GUI test session."""
    return QApplication.instance() or QApplication([])
