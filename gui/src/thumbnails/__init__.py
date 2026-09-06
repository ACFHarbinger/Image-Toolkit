"""gui/src/thumbnails/__init__.py
==============================
ThumbnailScheduler contract package (§1.2, #526).

Shared scheduling / cancellation / generation-tracking for the four
gallery implementations (#526 interface, #543 unification). Queue state
is encapsulated (no broadcast).
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
