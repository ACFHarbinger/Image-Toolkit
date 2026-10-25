"""Sidecar handlers for library management and the data browser."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from middleware.src.services.library_admin.admin import AdminStore, browse_result, catalog_result, mutate_result


def handle_catalog(store: Optional[AdminStore]) -> dict[str, Any]:
    return catalog_result(store)


def handle_mutate(store: Optional[AdminStore], params: Mapping[str, Any]) -> dict[str, Any]:
    return mutate_result(store, params)


def handle_browse(store: Optional[AdminStore], params: Mapping[str, Any]) -> dict[str, Any]:
    return browse_result(store, params)
