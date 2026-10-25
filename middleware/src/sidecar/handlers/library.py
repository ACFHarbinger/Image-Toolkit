"""Sidecar handlers for the library capability (L-02 / #896, L-03 / #897).

The store reader arrives with the daemon lease; until it does, the injected
store is ``None`` and every handler answers with its unavailable result.
"""

from __future__ import annotations

from typing import Any, Optional

from middleware.src.services.library import (
    LibraryStore,
    list_groups_result,
    list_images_result,
    list_tags_result,
)


def handle_list_images(store: Optional[LibraryStore], params: dict[str, Any]) -> dict[str, Any]:
    return list_images_result(store, params)


def handle_list_tags(store: Optional[LibraryStore]) -> dict[str, Any]:
    return list_tags_result(store)


def handle_list_groups(store: Optional[LibraryStore]) -> dict[str, Any]:
    return list_groups_result(store)


__all__ = [
    "handle_list_groups",
    "handle_list_images",
    "handle_list_tags",
]
