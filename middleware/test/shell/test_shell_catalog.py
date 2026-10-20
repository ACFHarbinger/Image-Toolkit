"""The shared catalog is data: unique ids, resolvable aliases, no Qt."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from middleware.src.shell.catalog import CatalogKind, shell_catalog

_ROOT = Path(__file__).resolve().parents[3]
_CATALOG_PATH = _ROOT / "middleware/src/shell/catalog.py"


def test_catalog_module_does_not_import_qt():
    tree = ast.parse(_CATALOG_PATH.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not any(name == "PySide6" or name.startswith("PySide6.") for name in imported)
    assert not any(name == "gui" or name.startswith("gui.") for name in imported)


def test_ids_are_unique_and_routes_name_their_workspace():
    catalog = shell_catalog()
    document = catalog.to_document()
    assert document["version"] == 1
    ids = [entry.id for entry in catalog.entries]
    assert len(ids) == len(set(ids))
    for entry in catalog.entries:
        if entry.kind is CatalogKind.ROUTE:
            assert entry.workspace_id is not None
            assert catalog.require(entry.workspace_id).kind is CatalogKind.WORKSPACE
            assert entry.route_key
    for alias in catalog.aliases:
        catalog.require(alias.target_id)
    roles = {window.role.value for window in catalog.windows}
    assert roles == {"main", "tray", "slideshow", "popout"}
    assert catalog.require("system.wallpaper").companion_window_id == "slideshow"
    assert "qt" not in catalog.require("developer.benchmarks").surfaces


def test_committed_frontend_json_matches_the_document():
    disk = json.loads((_ROOT / "frontend/src/shell/catalog.json").read_text(encoding="utf-8"))
    assert disk == shell_catalog().to_document()


def test_experimental_dl_aliases_cover_the_classic_five():
    aliases = shell_catalog().alias_map("experimental-dl")
    assert aliases == {
        "ml.training": "dl.train",
        "ml.generation": "dl.generate",
        "ml.evaluation": "dl.review",
        "ml.inference": "dl.review",
        "ml.comfyui": "dl.generate",
    }
