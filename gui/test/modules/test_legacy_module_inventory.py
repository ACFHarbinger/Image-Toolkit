"""Keep the #509 migration inventory aligned with the live legacy registry."""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = PROJECT_ROOT / "gui/src/windows/main/_tab_registry.py"
INVENTORY_PATH = PROJECT_ROOT / "docs/moon/roadmaps/gui_refactoring.md"


def _registry_routes() -> list[tuple[str, str, str]]:
    tree = ast.parse(REGISTRY_PATH.read_text(encoding="utf-8"))
    assignment = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "CLASSIC_TAB_ROUTES" for target in node.targets)
    )
    assert isinstance(assignment.value, ast.Tuple)

    routes = []
    for element in assignment.value.elts:
        assert isinstance(element, ast.Tuple) and len(element.elts) == 5
        _module_id, category, title, expression, _factory_id = element.elts
        assert isinstance(category, ast.Constant) and isinstance(category.value, str)
        assert isinstance(title, ast.Constant) and isinstance(title.value, str)
        assert isinstance(expression, ast.Constant) and isinstance(expression.value, str)
        routes.append((category.value, title.value, expression.value))
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


def test_inventory_records_lazy_construction_and_database_intent_migration():
    source = REGISTRY_PATH.read_text(encoding="utf-8")
    inventory = INVENTORY_PATH.read_text(encoding="utf-8")

    assert "Classic startup builds ≤ 1 category" in inventory
    assert "_ensure_category()" in inventory
    assert "LibraryDatabaseService(vault_manager)" in source
    assert "self.module_event_hub = EventHub(self)" in source
    assert "_ensure_category" in source
    assert "build_tab" in source
    for reference in (
        "self.database_tab.scan_tab_ref",
        "self.database_tab.search_tab_ref",
        "self.database_tab.wallpaper_tab_ref",
        "self.database_tab.main_window_ref",
        "self.listings_tab.main_window_ref",
    ):
        assert reference not in source
