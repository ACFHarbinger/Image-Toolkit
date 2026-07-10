"""Unit tests for listing association backfill logic."""

from backend.migrations.sync_listing_associations import (
    AssociationFixPlan,
    compute_association_fixes,
    normalize_id_list,
)


def test_normalize_id_list_handles_list_and_scalar():
    assert normalize_id_list(["a", "b"]) == ["a", "b"]
    assert normalize_id_list("uuid-1") == ["uuid-1"]
    assert normalize_id_list("") == []
    assert normalize_id_list(None) == []


def test_compute_association_fixes_entity_side_missing_link():
    contents = {
        "c1": {
            "id": "c1",
            "title": "Anime A",
            "associated_entities": ["e1"],
        }
    }
    entities = {
        "e1": {
            "id": "e1",
            "name": "Actor A",
            "associated_content": [],
        }
    }

    plan = compute_association_fixes(contents, entities)

    assert plan.total_fixes == 1
    assert plan.entity_to_content_fixes == [("e1", "c1")]
    assert plan.content_to_entity_fixes == []
    assert entities["e1"]["associated_content"] == ["c1"]
    assert contents["c1"]["associated_entities"] == ["e1"]


def test_compute_association_fixes_content_side_missing_link():
    contents = {
        "c1": {
            "id": "c1",
            "title": "Anime A",
            "associated_entities": [],
        }
    }
    entities = {
        "e1": {
            "id": "e1",
            "name": "Actor A",
            "associated_content": ["c1"],
        }
    }

    plan = compute_association_fixes(contents, entities)

    assert plan.total_fixes == 1
    assert plan.content_to_entity_fixes == [("c1", "e1")]
    assert plan.entity_to_content_fixes == []
    assert contents["c1"]["associated_entities"] == ["e1"]
    assert entities["e1"]["associated_content"] == ["c1"]


def test_compute_association_fixes_both_directions_at_once():
    contents = {
        "c1": {"id": "c1", "title": "Show A", "associated_entities": ["e1"]},
        "c2": {"id": "c2", "title": "Show B", "associated_entities": []},
    }
    entities = {
        "e1": {"id": "e1", "name": "Person A", "associated_content": []},
        "e2": {"id": "e2", "name": "Person B", "associated_content": ["c2"]},
    }

    plan = compute_association_fixes(contents, entities)

    assert plan.total_fixes == 2
    assert set(plan.entity_to_content_fixes) == {("e1", "c1")}
    assert set(plan.content_to_entity_fixes) == {("c2", "e2")}
    assert contents["c1"]["associated_entities"] == ["e1"]
    assert contents["c2"]["associated_entities"] == ["e2"]
    assert entities["e1"]["associated_content"] == ["c1"]
    assert entities["e2"]["associated_content"] == ["c2"]


def test_compute_association_fixes_warns_on_missing_targets():
    contents = {"c1": {"id": "c1", "title": "Show A", "associated_entities": ["missing"]}}
    entities = {"e1": {"id": "e1", "name": "Person A", "associated_content": ["missing"]}}

    plan = compute_association_fixes(contents, entities)

    assert plan.total_fixes == 0
    assert len(plan.warnings) == 2


def test_compute_association_fixes_entity_peer_missing_reverse_link():
    entities = {
        "e1": {
            "id": "e1",
            "name": "Alice",
            "associated_content": [],
            "associated_entities": ["e2"],
        },
        "e2": {
            "id": "e2",
            "name": "Bob",
            "associated_content": [],
            "associated_entities": [],
        },
    }

    plan = compute_association_fixes({}, entities)

    assert plan.total_fixes == 1
    assert plan.entity_to_entity_fixes == [("e2", "e1")]
    assert entities["e2"]["associated_entities"] == ["e1"]
    assert entities["e1"]["associated_entities"] == ["e2"]


def test_compute_association_fixes_entity_peer_both_directions_at_once():
    entities = {
        "e1": {
            "id": "e1",
            "name": "Alice",
            "associated_content": [],
            "associated_entities": ["e2"],
        },
        "e2": {
            "id": "e2",
            "name": "Bob",
            "associated_content": [],
            "associated_entities": ["e3"],
        },
        "e3": {
            "id": "e3",
            "name": "Carol",
            "associated_content": [],
            "associated_entities": [],
        },
    }

    plan = compute_association_fixes({}, entities)

    assert plan.total_fixes == 2
    assert set(plan.entity_to_entity_fixes) == {("e2", "e1"), ("e3", "e2")}
    assert entities["e2"]["associated_entities"] == ["e1", "e3"]
    assert entities["e3"]["associated_entities"] == ["e2"]


def test_compute_association_fixes_warns_on_missing_entity_peer():
    entities = {
        "e1": {
            "id": "e1",
            "name": "Alice",
            "associated_content": [],
            "associated_entities": ["missing"],
        }
    }

    plan = compute_association_fixes({}, entities)

    assert plan.total_fixes == 0
    assert len(plan.warnings) == 1


def test_compute_association_fixes_noop_when_already_synced():
    contents = {"c1": {"id": "c1", "title": "Show A", "associated_entities": ["e1"]}}
    entities = {"e1": {"id": "e1", "name": "Person A", "associated_content": ["c1"]}}

    plan = compute_association_fixes(contents, entities)

    assert isinstance(plan, AssociationFixPlan)
    assert plan.total_fixes == 0
    assert plan.changed_content_ids == set()
    assert plan.changed_entity_ids == set()