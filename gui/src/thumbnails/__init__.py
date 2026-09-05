"""gui/src/thumbnails/__init__.py
==============================
ThumbnailScheduler contract package (§1.2, #526).

Shared scheduling / cancellation / generation-tracking interface for the
four gallery implementations. Queue state is encapsulated (no broadcast).
Unification onto one implementation is Phase 2 (#531), not this package.
"""

from __future__ import annotations

from .order import order_visible_first
from .protocol import ThumbnailScheduler
from .scheduler import DefaultThumbnailScheduler

__all__ = [
    "DefaultThumbnailScheduler",
    "ThumbnailScheduler",
    "order_visible_first",
]
