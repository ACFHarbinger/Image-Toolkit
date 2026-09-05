"""Guard the #511 database-family widget-decoupling boundary."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from gui.src.modules.events import EventHub, FilterByTagIntent, ImportPathsIntent
from gui.src.modules.library_service import coerce_library_database_service
from PySide6.QtWidgets import QLabel

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_legacy_non_widget_value_is_snapshotted_as_a_service():
    database = object()
    service = coerce_library_database_service(SimpleNamespace(db=database, vault_manager="vault"))

    assert service.db is database
    assert service.vault_manager == "vault"


def test_database_service_rejects_widget_coupling(q_app):
    with pytest.raises(TypeError, match="not QWidget"):
        coerce_library_database_service(QLabel())


def test_database_intents_keep_filter_and_paths_immutable(q_app):
    hub = EventHub(q_app)
    received = []
    hub.subscribe(FilterByTagIntent, received.append)
    hub.subscribe(ImportPathsIntent, received.append)

    hub.publish(FilterByTagIntent(origin="library.management", module_id="library.search", tag_name="sky"))
    hub.publish(ImportPathsIntent(origin="library.search", module_id="library.scan", paths=("a.png",)))

    assert [(event.module_id, event.correlation_id != "") for event in received] == [
        ("library.search", True),
        ("library.scan", True),
    ]


def test_database_family_has_no_cross_widget_reference_fields():
    sources = [
        PROJECT_ROOT / "gui/src/tabs/database/database_tab",
        PROJECT_ROOT / "gui/src/tabs/database/search_tab",
        PROJECT_ROOT / "gui/src/tabs/database/scan_metadata_tab",
        PROJECT_ROOT / "gui/src/tabs/core/wallpaper_tab",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for root in sources for path in root.rglob("*.py"))

    for reference in (".scan_tab_ref", ".search_tab_ref", ".wallpaper_tab_ref", ".listings_tab_ref"):
        assert reference not in text
