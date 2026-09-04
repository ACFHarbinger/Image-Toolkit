"""Keep the #509 migration inventory aligned with the live legacy registry."""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = PROJECT_ROOT / "gui/src/windows/main/_tab_registry.py"
INVENTORY_PATH = PROJECT_ROOT / "docs/moon/roadmaps/ui_module_inventory_2026q3.md"


def _registry_routes() -> list[tuple[str, str, str]]:
    tree = ast.parse(REGISTRY_PATH.read_text(encoding="utf-8"))
    assignment = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Attribute) and target.attr == "all_tabs"
            for target in node.targets
        )
    )
    assert isinstance(assignment.value, ast.Dict)

    routes = []
    for category, tabs in zip(assignment.value.keys, assignment.value.values, strict=True):
        assert isinstance(category, ast.Constant) and isinstance(category.value, str)
        assert isinstance(tabs, ast.Dict)
        for title, expression in zip(tabs.keys, tabs.values, strict=True):
            assert isinstance(title, ast.Constant) and isinstance(title.value, str)
            routes.append((category.value, title.value, ast.unparse(expression)))
    return routes


def _inventory_routes() -> list[tuple[str, str, str]]:
    rows = []
    for line in INVENTORY_PATH.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("| Module ID") or line.startswith("|---"):
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) == 5:
            _module_id, category, title, expression, _kind = parts
            rows.append((category, title, expression))
    return rows


def test_inventory_matches_every_live_all_tabs_route():
    assert _inventory_routes() == _registry_routes()
    assert len(_inventory_routes()) == 33


def test_inventory_records_the_current_eager_and_direct_reference_constraints():
    source = REGISTRY_PATH.read_text(encoding="utf-8")
    inventory = INVENTORY_PATH.read_text(encoding="utf-8")

    assert "imports 25 names" in inventory
    assert "constructs 26 top-level tab" in inventory
    for reference in (
        "self.database_tab.scan_tab_ref = self.scan_metadata_tab",
        "self.database_tab.search_tab_ref = self.search_tab",
        "self.database_tab.wallpaper_tab_ref = self.wallpaper_tab",
        "self.database_tab.main_window_ref = self",
        "self.listings_tab.main_window_ref = self",
    ):
        assert reference in source
