from __future__ import annotations

import weakref
from collections import OrderedDict
from typing import Optional

from PySide6.QtGui import QImage

# Hard upper bound for one cache's resize() (#444 follow-up) AND the
# process-wide resident-entry cap (R3.1 / #568). Page size can be
# 500/1000/"All" (999999, gallery_base.py); #444's
# `resize(max(current_maxsize, min(page_size, len(paths))))` callers let
# maxsize grow unboundedly and never shrink back. At the largest
# thumbnail_size (512px, ~1MB/QImage) this ceiling bounds *all* registered
# caches together to ~800MB instead of N independent 800-entry heaps.
LRU_CACHE_CEILING = 800


class PixmapBudget:
    """Process-wide thumbnail RAM budget (R3.1 / #568).

    Per-role integers are the *local* maxsize each construction site
    derives. Every ``LRUImageCache`` created with this budget (the default)
    also registers here: inserts that would push the sum of resident
    entries past ``total_entries`` evict the globally oldest entry, from
    whichever cache holds it.
    """

    __slots__ = (
        "total_entries",
        "card_thumb",
        "single_gallery",
        "two_galleries_selected",
        "two_galleries_found",
        "virtual_dual_shared",
        "virtual_model",
        "_order",
        "_caches",
    )

    def __init__(
        self,
        *,
        total_entries: int = LRU_CACHE_CEILING,
        card_thumb: int = 250,
        single_gallery: int = 300,
        two_galleries_selected: int = 200,
        two_galleries_found: int = 300,
        virtual_dual_shared: int = 500,
        virtual_model: int = 300,
    ) -> None:
        self.total_entries = total_entries
        self.card_thumb = card_thumb
        self.single_gallery = single_gallery
        self.two_galleries_selected = two_galleries_selected
        self.two_galleries_found = two_galleries_found
        self.virtual_dual_shared = virtual_dual_shared
        self.virtual_model = virtual_model
        # (cache_id, key) in LRU order (oldest first).
        self._order: OrderedDict[tuple[int, str], None] = OrderedDict()
        self._caches: dict[int, weakref.ref[LRUImageCache]] = {}

    @property
    def ceiling(self) -> int:
        """COMPAT name for the process-wide resident cap."""
        return self.total_entries

    def clamp(self, size: int) -> int:
        return min(size, self.total_entries)

    def role_size(self, role: str) -> int:
        return getattr(self, role)

    def make_cache(self, role: str) -> LRUImageCache:
        return LRUImageCache(maxsize=self.role_size(role), budget=self)

    def resident_entries(self) -> int:
        self._drop_dead()
        return len(self._order)

    def register(self, cache: LRUImageCache) -> None:
        cid = id(cache)
        self._caches[cid] = weakref.ref(cache, lambda _r, cid=cid: self._forget_cache(cid))

    def record_access(self, cache: LRUImageCache, key: str) -> None:
        token = (id(cache), key)
        if token in self._order:
            self._order.move_to_end(token)
        else:
            self._order[token] = None
        self.trim()

    def forget_key(self, cache: LRUImageCache, key: str) -> None:
        self._order.pop((id(cache), key), None)

    def forget_cache(self, cache: LRUImageCache) -> None:
        self._forget_cache(id(cache))

    def trim(self) -> None:
        """Evict globally oldest entries until resident count <= total."""
        self._drop_dead()
        while len(self._order) > self.total_entries:
            cache_id, key = next(iter(self._order))
            self._order.pop((cache_id, key), None)
            ref = self._caches.get(cache_id)
            cache = ref() if ref is not None else None
            if cache is None:
                self._caches.pop(cache_id, None)
                continue
            cache._evict_key(key)

    def _forget_cache(self, cache_id: int) -> None:
        self._caches.pop(cache_id, None)
        stale = [token for token in self._order if token[0] == cache_id]
        for token in stale:
            self._order.pop(token, None)

    def _drop_dead(self) -> None:
        dead = [cid for cid, ref in self._caches.items() if ref() is None]
        for cid in dead:
            self._forget_cache(cid)


DEFAULT_PIXMAP_BUDGET = PixmapBudget()


class LRUImageCache:
    """Bounded LRU cache for QImage thumbnails.

    Stores QImage objects (not QPixmap) to avoid the X11 server-side backing
    copy that QPixmap carries, roughly halving per-entry RAM on Linux.

    Local ``maxsize`` still evicts inside this cache. When constructed with
    a ``PixmapBudget`` (the default), inserts also compete in the process-wide
    resident cap: overflowing that cap evicts the globally oldest entry.
    Pass ``budget=None`` for an isolated cache (unit tests, benches).
    """

    def __init__(
        self,
        maxsize: int = 300,
        *,
        budget: Optional[PixmapBudget] = DEFAULT_PIXMAP_BUDGET,
    ):
        self._cache: OrderedDict[str, QImage] = OrderedDict()
        self.maxsize = maxsize
        self._budget = budget
        if budget is not None:
            budget.register(self)

    def get(self, key: str, default=None):
        if key not in self._cache:
            return default
        self._cache.move_to_end(key)
        if self._budget is not None:
            self._budget.record_access(self, key)
        return self._cache[key]

    def __setitem__(self, key: str, value):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self.maxsize:
            evicted_key, _ = self._cache.popitem(last=False)
            if self._budget is not None:
                self._budget.forget_key(self, evicted_key)
        if self._budget is not None:
            self._budget.record_access(self, key)

    def _evict_key(self, key: str) -> None:
        """Drop one key because the process-wide budget trimmed it."""
        self._cache.pop(key, None)

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def __len__(self) -> int:
        return len(self._cache)

    def items(self):
        """Return a snapshot of (key, value) pairs so callers can safely iterate
        while the cache is modified (e.g. when copying into a new cache)."""
        return list(self._cache.items())

    def pop(self, key: str, default=None):
        if self._budget is not None:
            self._budget.forget_key(self, key)
        return self._cache.pop(key, default)

    def clear(self):
        if self._budget is not None:
            for key in list(self._cache):
                self._budget.forget_key(self, key)
        self._cache.clear()

    def resize(self, maxsize: int) -> None:
        """Re-bound the cache (#444). Evicts LRU entries immediately when
        shrinking below the current entry count, so callers can size the
        cache to the active page size without losing entries mid-populate."""
        self.maxsize = maxsize
        while len(self._cache) > self.maxsize:
            evicted_key, _ = self._cache.popitem(last=False)
            if self._budget is not None:
                self._budget.forget_key(self, evicted_key)
        if self._budget is not None:
            self._budget.trim()
