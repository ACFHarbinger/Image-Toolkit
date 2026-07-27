import json
from unittest.mock import MagicMock

import pytest
from gui.src.tabs.core.elements.entity_listings_subtab import EntityListingsSubTab

pytestmark = pytest.mark.gui


def _entity_row(entity: dict) -> tuple:
    return (
        entity["id"],
        "Entity",
        entity.get("name", ""),
        json.dumps(entity),
        entity.get("date_added", "2026-01-01"),
    )


@pytest.fixture
def entity_tab(q_app):
    tab = EntityListingsSubTab()
    vault = MagicMock()
    vault.raw_password = "secret"
    vault.account_name = "test_user"
    tab.vault_manager = vault
    return tab


def test_sync_entities_for_entity_adds_reverse_link(entity_tab, monkeypatch):
    entity_a = {
        "id": "e1",
        "name": "Alice",
        "associated_entities": ["e2"],
        "associated_content": [],
        "date_added": "2026-01-01",
    }
    entity_b = {
        "id": "e2",
        "name": "Bob",
        "associated_entities": [],
        "associated_content": [],
        "date_added": "2026-01-01",
    }
    entity_tab._entities = [entity_a.copy(), entity_b.copy()]

    upserts = []

    def fake_fetch(db_path, password, salt):
        return [_entity_row(entity_a), _entity_row(entity_b)]

    def fake_insert(db_path, password, salt, row_id, category, title, metadata, date_added, embedding):
        upserts.append(json.loads(metadata))

    monkeypatch.setattr(
        "gui.src.tabs.core.elements.entity_listings_subtab.base.fetch_all_listings_secure",
        fake_fetch,
    )
    monkeypatch.setattr(
        "gui.src.tabs.core.elements.entity_listings_subtab.base.insert_listing_secure",
        fake_insert,
    )

    changed = entity_tab._sync_entities_for_entity(entity_a)

    assert changed is True
    assert len(upserts) == 1
    assert upserts[0]["id"] == "e2"
    assert upserts[0]["associated_entities"] == ["e1"]
    assert entity_tab._entities[1]["associated_entities"] == ["e1"]


def test_sync_entities_for_entity_removes_stale_reverse_link(entity_tab, monkeypatch):
    entity_a = {
        "id": "e1",
        "name": "Alice",
        "associated_entities": [],
        "associated_content": [],
        "date_added": "2026-01-01",
    }
    entity_b = {
        "id": "e2",
        "name": "Bob",
        "associated_entities": ["e1"],
        "associated_content": [],
        "date_added": "2026-01-01",
    }
    entity_tab._entities = [entity_a.copy(), entity_b.copy()]

    upserts = []

    monkeypatch.setattr(
        "gui.src.tabs.core.elements.entity_listings_subtab.base.fetch_all_listings_secure",
        lambda *args, **kwargs: [_entity_row(entity_a), _entity_row(entity_b)],
    )
    monkeypatch.setattr(
        "gui.src.tabs.core.elements.entity_listings_subtab.base.insert_listing_secure",
        lambda *args: upserts.append(json.loads(args[6])),
    )

    changed = entity_tab._sync_entities_for_entity(entity_a)

    assert changed is True
    assert upserts[0]["associated_entities"] == []
    assert entity_tab._entities[1]["associated_entities"] == []


def test_remove_entity_from_entities_clears_deleted_id(entity_tab, monkeypatch):
    entity_a = {
        "id": "e1",
        "name": "Alice",
        "associated_entities": ["e2"],
        "associated_content": [],
        "date_added": "2026-01-01",
    }
    entity_b = {
        "id": "e2",
        "name": "Bob",
        "associated_entities": ["e1"],
        "associated_content": [],
        "date_added": "2026-01-01",
    }
    entity_tab._entities = [entity_a.copy(), entity_b.copy()]

    upserts = []

    monkeypatch.setattr(
        "gui.src.tabs.core.elements.entity_listings_subtab.base.fetch_all_listings_secure",
        lambda *args, **kwargs: [_entity_row(entity_b)],
    )
    monkeypatch.setattr(
        "gui.src.tabs.core.elements.entity_listings_subtab.base.insert_listing_secure",
        lambda *args: upserts.append(json.loads(args[6])),
    )

    changed = entity_tab._remove_entity_from_entities("e1")

    assert changed is True
    assert upserts[0]["associated_entities"] == []
    assert entity_tab._entities[1]["associated_entities"] == []