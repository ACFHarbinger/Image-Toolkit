"""Library listings and search projection over the unified store (L-02 / #896).

This module does not open ``library.db``: the sealed store reader arrives
with the daemon lease (Gate B). The sidecar injects a store exposing the
``UnifiedImageDatabase`` query surface — ``search_files``,
``get_all_tags``, ``get_all_groups``, ``get_all_subgroups_detailed``.
With no store attached, every result carries ``available: False`` and the
views show their unavailable state instead of inventing rows.

The record shape mirrors the Rust ``db.rs`` ``ImageRecord`` / pgvector
surface this capability replaces for the Library rows (L-07 / #901 retires
that duplicate once the pages route through HostClient).
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, Sequence

_MAX_LIMIT = 10_000
_DEFAULT_LIMIT = 500


class LibraryStore(Protocol):
    """The query surface the attached store reader provides."""

    def search_files(self, **query_params: Any) -> list[dict[str, Any]]: ...

    def get_all_tags(self, limit: int = _MAX_LIMIT) -> list[str]: ...

    def get_all_groups(self, limit: int = _MAX_LIMIT) -> list[str]: ...

    def get_all_subgroups_detailed(self, limit: int = _MAX_LIMIT) -> list[tuple[str, str]]: ...


def list_images_result(store: Optional[LibraryStore], params: Mapping[str, Any]) -> dict[str, Any]:
    """Bridge payload for ``library.list_images``: filtered image rows."""
    if store is None:
        return {"available": False, "images": []}
    rows = store.search_files(
        group_name=params.get("group_name") or None,
        subgroup_name=params.get("subgroup_name") or None,
        tags=_clean_tags(params.get("tags")),
        filename_pattern=params.get("filename_pattern") or None,
        input_formats=params.get("input_formats") or None,
        limit=_limit(params.get("limit")),
        group_names=params.get("group_names") or None,
        subgroup_names=params.get("subgroup_names") or None,
    )
    return {"available": True, "images": [_image_record(row) for row in rows]}


def list_tags_result(store: Optional[LibraryStore]) -> dict[str, Any]:
    """Bridge payload for ``library.list_tags``."""
    if store is None:
        return {"available": False, "tags": []}
    return {"available": True, "tags": list(store.get_all_tags())}


def list_groups_result(store: Optional[LibraryStore]) -> dict[str, Any]:
    """Bridge payload for ``library.list_groups``: one row per group with
    its subgroups (``get_all_subgroups_detailed`` returns
    ``(subgroup, parent_group)`` pairs)."""
    if store is None:
        return {"available": False, "groups": []}
    subgroups: dict[str, list[str]] = {group: [] for group in store.get_all_groups()}
    for subgroup, parent in store.get_all_subgroups_detailed():
        subgroups.setdefault(parent, []).append(subgroup)
    groups = [
        {"name": name, "subgroups": sorted(subgroups.get(name, []))}
        for name in sorted(subgroups)
    ]
    return {"available": True, "groups": groups}


def _image_record(row: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a store row to the contract record (dates as ISO strings)."""
    record: dict[str, Any] = {}
    for key in (
        "id",
        "file_path",
        "filename",
        "file_size",
        "width",
        "height",
        "phash",
        "group_name",
        "subgroup_name",
        "tags",
        "distance",
    ):
        if key in row:
            record[key] = row[key]
    for key in ("date_added", "date_modified"):
        value = row.get(key)
        record[key] = value.isoformat() if hasattr(value, "isoformat") else value
    return record


def _clean_tags(tags: Optional[Sequence[str]]) -> Optional[list[str]]:
    if not tags:
        return None
    return [str(tag) for tag in tags if str(tag).strip()]


def _limit(value: Any) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_LIMIT
    if limit < 1:
        return _DEFAULT_LIMIT
    return min(limit, _MAX_LIMIT)


__all__ = [
    "LibraryStore",
    "list_groups_result",
    "list_images_result",
    "list_tags_result",
]
