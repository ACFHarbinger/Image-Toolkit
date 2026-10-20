"""Classic route ids stay the catalog ids. Factories are not a second registry."""

from __future__ import annotations

from gui.src.modules.dl_workspace import DL_CLASSIC_ALIASES, DL_ROUTES
from gui.src.modules.stitch_workspace import STITCH_ROUTES
from gui.src.windows.main._tab_registry import CLASSIC_TAB_ROUTES
from middleware.src.shell.catalog import shell_catalog


def test_classic_routes_match_catalog_titles_and_categories():
    catalog = shell_catalog()
    assert len(CLASSIC_TAB_ROUTES) == 33
    for module_id, category, title, _expression, _factory_id in CLASSIC_TAB_ROUTES:
        entry = catalog.require(module_id)
        assert entry.title == title
        assert entry.category.value == category


def test_stitch_and_dl_routes_use_catalog_ids():
    catalog = shell_catalog()
    for module_id, route_key, title, _panel in STITCH_ROUTES:
        entry = catalog.require(module_id)
        assert entry.route_key == route_key
        assert entry.title == title
        assert entry.workspace_id == "stitch"
    for module_id, route_key, title in DL_ROUTES:
        entry = catalog.require(module_id)
        assert entry.route_key == route_key
        assert entry.title == title
    assert catalog.alias_map("experimental-dl") == DL_CLASSIC_ALIASES
