"""Sidecar handlers for the reverse_search capability (B-05 / #910).

``reverse_search.search`` runs the live engine at the user's request; the
default manager is built lazily so importing the sidecar stays light. Tests
inject a fake manager — no live HTTP, no Selenium, no provider ops.
"""

from __future__ import annotations

from typing import Any

from middleware.src.services.web.reverse_search import engines_result, search_result


def reverse_search_manager() -> Any:
    """The default live manager (ReverseImageSearchManager)."""
    from middleware.src.web.crawlers.reverse_image_search_crawler import (
        ReverseImageSearchManager,
    )

    return ReverseImageSearchManager()


def handle_reverse_search_engines() -> dict[str, Any]:
    return engines_result()


def handle_reverse_search(params: dict[str, Any]) -> dict[str, Any]:
    manager = reverse_search_manager()
    return search_result(manager, params)


__all__ = [
    "handle_reverse_search",
    "handle_reverse_search_engines",
    "reverse_search_manager",
]
