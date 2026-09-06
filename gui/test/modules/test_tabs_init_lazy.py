"""ui-arch-27/#549: ``gui.src.tabs`` must not import the submodule GUIs eagerly."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

TABS_INIT = Path(__file__).resolve().parents[3] / "gui/src/tabs/__init__.py"
SUBMODULE_ROOTS = {"asp_gui", "csg_gui", "hie_tab", "asp_backend", "csg_backend"}


def test_no_module_level_submodule_import():
    tree = ast.parse(TABS_INIT.read_text(encoding="utf-8"))
    eager = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            if node.module.split(".")[0] in SUBMODULE_ROOTS:
                eager.append(node.lineno)
        elif isinstance(node, ast.Import):
            eager.extend(n.lineno for a in node.names for n in [node] if a.name.split(".")[0] in SUBMODULE_ROOTS)
    assert eager == []


def test_lazy_names_resolve_to_the_submodule_classes():
    tabs = importlib.import_module("gui.src.tabs")
    assert set(tabs._LAZY_SUBMODULE_EXPORTS) == {
        "StitchTab", "StitchTabBackend", "MangaAnimationTab",
        "MangaColorizationTab", "MangaPuppeteeringTab", "HieEditorTab",
    }
    pytest.importorskip("asp_gui")
    assert tabs.StitchTab is importlib.import_module("asp_gui.tabs").StitchTab
    with pytest.raises(AttributeError):
        tabs.NotATab  # noqa: B018
