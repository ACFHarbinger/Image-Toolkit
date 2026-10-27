"""Group, tag, and table-browser operations over an injected store.

This module does not open ``library.db``. The sidecar attaches a store
when the daemon lease arrives. With no store, every result stays
``available: False``.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, Sequence

_NAME_LIMIT = 200
_CREATE_ACTIONS = frozenset({"create_group", "create_subgroup", "create_tag"})


class AdminStore(Protocol):
    """Write and browse surface supplied with the daemon lease."""

    def get_all_groups(self) -> list[str]: ...

    def get_all_subgroups_detailed(self) -> list[tuple[str, str]]: ...

    def get_all_tags_with_categories(self) -> list[dict[str, str]]: ...

    def add_group(self, name: str) -> None: ...

    def add_subgroup(self, name: str, group_name: str) -> None: ...

    def add_tag(self, name: str, category: str | None = None) -> None: ...

    def delete_group(self, name: str) -> None: ...

    def delete_subgroup(self, name: str, group_name: str) -> None: ...

    def delete_tag(self, name: str) -> None: ...

    def merge_tags(self, source_name: str, dest_name: str) -> None: ...

    def list_tables(self) -> list[str]: ...

    def browse_page(
        self,
        table: str,
        column: str | None,
        equals: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[str], list[Sequence[Any]], int]: ...


def catalog_result(store: Optional[AdminStore]) -> dict[str, Any]:
    """Groups, their subgroups, and tags. Empty when no store is attached."""
    if store is None:
        return {"available": False, "groups": [], "tags": [], "tables": []}
    subgroups: dict[str, list[str]] = {group: [] for group in store.get_all_groups()}
    for subgroup, parent in store.get_all_subgroups_detailed():
        subgroups.setdefault(str(parent), []).append(str(subgroup))
    groups = [{"name": name, "subgroups": sorted(members)} for name, members in sorted(subgroups.items())]
    tags = []
    for row in store.get_all_tags_with_categories():
        tags.append({"name": str(row.get("name", "")), "category": str(row.get("category") or "")})
    tags.sort(key=lambda item: item["name"])
    tables = sorted(str(name) for name in store.list_tables()) if hasattr(store, "list_tables") else []
    return {"available": True, "groups": groups, "tags": tags, "tables": tables}


def mutate_result(store: Optional[AdminStore], params: Mapping[str, Any]) -> dict[str, Any]:
    """Apply one management action. ``applied`` counts names that were written."""
    if store is None:
        return {"available": False, "applied": 0, "error": ""}
    action = str(params["action"])
    try:
        applied = _apply(store, action, params)
    except ValueError as exc:
        return {"available": True, "applied": 0, "error": str(exc)}
    return {"available": True, "applied": applied, "error": ""}


def browse_result(store: Optional[AdminStore], params: Mapping[str, Any]) -> dict[str, Any]:
    """One page of one table. A filter is column equality, never a WHERE string."""
    if store is None:
        return {"available": False, "columns": [], "rows": [], "row_count": 0, "error": ""}
    table = str(params["table"])
    column = _optional(params.get("column"))
    equals = params.get("equals")
    equals_text = None if equals is None else str(equals)
    if column and equals_text is None:
        return _browse_error("equals is required when column is set")
    if table not in store.list_tables():
        return _browse_error(f"Unknown table: {table}")
    try:
        columns, raw_rows, row_count = store.browse_page(
            table,
            column,
            equals_text if column else None,
            int(params["limit"]),
            int(params["offset"]),
        )
    except ValueError as exc:
        return _browse_error(str(exc))
    rows = [{"cells": [_cell(value) for value in row]} for row in raw_rows]
    return {
        "available": True,
        "columns": [str(name) for name in columns],
        "rows": rows,
        "row_count": int(row_count),
        "error": "",
    }


def _apply(store: AdminStore, action: str, params: Mapping[str, Any]) -> int:
    names = _names(str(params["name"]), split=action in _CREATE_ACTIONS)
    parent = _optional(params.get("parent"))
    category = _required_category(params) if action == "update_tag" else _optional(params.get("category"))
    destination = _optional(params.get("destination"))
    if action in {"create_subgroup", "remove_subgroup", "rename_subgroup"} and not parent:
        raise ValueError("parent group is required")
    if action == "merge_tags" and not destination:
        raise ValueError("destination tag is required")
    if action in {"rename_group", "rename_subgroup", "rename_tag"} and not destination:
        raise ValueError("destination name is required")
    for name in names:
        _one(store, action, name, parent, category, destination)
    return len(names)


def _one(
    store: AdminStore,
    action: str,
    name: str,
    parent: str | None,
    category: str | None,
    destination: str | None,
) -> None:
    if action == "create_group":
        store.add_group(name)
    elif action == "create_subgroup":
        store.add_subgroup(name, parent or "")
    elif action == "create_tag":
        store.add_tag(name, category)
    elif action == "remove_group":
        store.delete_group(name)
    elif action == "remove_subgroup":
        store.delete_subgroup(name, parent or "")
    elif action == "remove_tag":
        store.delete_tag(name)
    elif action == "merge_tags":
        store.merge_tags(name, destination or "")
    elif action == "rename_group":
        _call(store, "rename_group", name, destination or "")
    elif action == "rename_subgroup":
        _call(store, "rename_subgroup", name, destination or "", parent or "")
    elif action == "rename_tag":
        _call(store, "rename_tag", name, destination or "")
    elif action == "update_tag":
        _call(store, "update_tag_category", name, category)
    elif action == "delete_image":
        if not _call(store, "delete_image_by_path", name):
            raise ValueError("image not found")
    else:
        raise ValueError(f"unknown action: {action}")


def _call(store: AdminStore, method: str, *args: Any) -> Any:
    """Optional store methods. A missing method is an error, not a silent write."""
    fn = getattr(store, method, None)
    if not callable(fn):
        raise ValueError(f"store does not support {method}")
    try:
        return fn(*args)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc


def _names(raw: str, *, split: bool) -> list[str]:
    pieces = raw.split(",") if split else [raw]
    names = []
    for piece in pieces:
        name = piece.strip()
        if not name:
            continue
        if len(name) > _NAME_LIMIT:
            raise ValueError("name is too long")
        names.append(name)
    if not names:
        raise ValueError("name is required")
    return names


def _optional(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _required_category(params: Mapping[str, Any]) -> str | None:
    """Omitted or null is an error. Present empty or whitespace clears the category."""
    if "category" not in params or params.get("category") is None:
        raise ValueError("category is required")
    text = str(params.get("category")).strip()
    return text or None


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _browse_error(message: str) -> dict[str, Any]:
    return {"available": True, "columns": [], "rows": [], "row_count": 0, "error": message}


__all__ = [
    "AdminStore",
    "browse_result",
    "catalog_result",
    "mutate_result",
]
