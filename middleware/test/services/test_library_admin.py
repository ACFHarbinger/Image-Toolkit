"""Library management and data browser stay closed until a store is attached."""

from __future__ import annotations

from middleware.src.services.library_admin.admin import browse_result, catalog_result, mutate_result
from middleware.src.sidecar.server import SidecarServer


class _Store:
    def __init__(self) -> None:
        self.groups = ["people"]
        self.subgroups = [("faces", "people")]
        self.tags = [{"name": "smile", "category": "mood"}]
        self.tables = {
            "images": {
                "columns": ["id", "filename"],
                "rows": [["1", "a.png"], ["2", "b.png"]],
            }
        }

    def get_all_groups(self):
        return list(self.groups)

    def get_all_subgroups_detailed(self):
        return list(self.subgroups)

    def get_all_tags_with_categories(self):
        return list(self.tags)

    def add_group(self, name: str) -> None:
        self.groups.append(name)

    def add_subgroup(self, name: str, group_name: str) -> None:
        self.subgroups.append((name, group_name))

    def add_tag(self, name: str, category: str | None = None) -> None:
        self.tags.append({"name": name, "category": category or ""})

    def delete_group(self, name: str) -> None:
        self.groups = [group for group in self.groups if group != name]

    def delete_subgroup(self, name: str, group_name: str) -> None:
        self.subgroups = [pair for pair in self.subgroups if pair != (name, group_name)]

    def delete_tag(self, name: str) -> None:
        self.tags = [tag for tag in self.tags if tag["name"] != name]

    def merge_tags(self, source_name: str, dest_name: str) -> None:
        self.delete_tag(source_name)
        if dest_name not in {tag["name"] for tag in self.tags}:
            self.add_tag(dest_name, None)

    def list_tables(self):
        return list(self.tables)

    def browse_page(self, table, column, equals, limit, offset):
        spec = self.tables[table]
        rows = spec["rows"]
        if column:
            index = spec["columns"].index(column)
            rows = [row for row in rows if row[index] == equals]
        page = rows[offset : offset + limit]
        return spec["columns"], page, len(rows)


def test_catalog_without_a_store_is_unavailable() -> None:
    assert catalog_result(None) == {"available": False, "groups": [], "tags": [], "tables": []}


def test_catalog_lists_groups_and_tags() -> None:
    result = catalog_result(_Store())
    assert result["available"] is True
    assert result["groups"] == [{"name": "people", "subgroups": ["faces"]}]
    assert result["tags"] == [{"name": "smile", "category": "mood"}]
    assert result["tables"] == ["images"]


def test_create_splits_comma_separated_groups() -> None:
    store = _Store()
    result = mutate_result(store, {"action": "create_group", "name": "a, b"})
    assert result == {"available": True, "applied": 2, "error": ""}
    assert store.groups[-2:] == ["a", "b"]


def test_subgroup_and_merge_require_their_fields() -> None:
    store = _Store()
    missing_parent = mutate_result(store, {"action": "create_subgroup", "name": "closeup"})
    assert missing_parent["error"] == "parent group is required"
    missing_dest = mutate_result(store, {"action": "merge_tags", "name": "smile"})
    assert missing_dest["error"] == "destination tag is required"


def test_remove_group() -> None:
    store = _Store()
    result = mutate_result(store, {"action": "remove_group", "name": "people"})
    assert result["applied"] == 1
    assert "people" not in store.groups


def test_browse_filters_by_column_equality() -> None:
    result = browse_result(
        _Store(),
        {"table": "images", "limit": 50, "offset": 0, "column": "filename", "equals": "b.png"},
    )
    assert result["available"] is True
    assert result["row_count"] == 1
    assert result["rows"] == [{"cells": ["2", "b.png"]}]
    assert result["error"] == ""


def test_browse_rejects_an_unknown_table() -> None:
    result = browse_result(_Store(), {"table": "secrets", "limit": 10, "offset": 0})
    assert result["error"] == "Unknown table: secrets"
    assert result["rows"] == []


def test_sidecar_catalog_does_not_require_a_database() -> None:
    server = SidecarServer()
    server.handle_frame(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "system.handshake",
            "params": {
                "protocol": "image-toolkit-bridge",
                "client": {"name": "test", "version": "1.0.0"},
            },
        }
    )
    response = server.handle_frame(
        {"jsonrpc": "2.0", "id": 2, "method": "library_admin.catalog", "params": {}}
    )
    assert response["result"]["available"] is False
