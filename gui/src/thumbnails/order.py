"""gui/src/thumbnails/order.py
============================
Visible-first path ordering shared by every gallery fill path (§1.2, #526).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Optional


def order_visible_first(
    paths: Sequence[str],
    visible: Optional[Iterable[str]] = None,
) -> list[str]:
    """Return *paths* with viewport-visible entries first, original order kept.

    Non-visible paths follow in their original order. Missing / empty
    *visible* is a no-op. Used by the default scheduler and by the QLabel
    galleries' ``_sort_paths_by_visibility`` helper so all four impls share
    one ordering rule without sharing a queue implementation.
    """
    if not paths:
        return []
    if not visible:
        return list(paths)
    visible_set = visible if isinstance(visible, (set, frozenset)) else set(visible)
    first = [path for path in paths if path in visible_set]
    rest = [path for path in paths if path not in visible_set]
    return first + rest
