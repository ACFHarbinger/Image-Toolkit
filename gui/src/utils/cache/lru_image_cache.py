from collections import OrderedDict

from PySide6.QtGui import QImage

# Hard upper bound for resize() (#444 follow-up). Page size can be 500/1000/
# "All" (999999, gallery_base.py), and #444's `resize(max(current_maxsize,
# min(page_size, len(paths))))` callers let maxsize grow unboundedly and
# never shrink back -- one large directory permanently inflates the cache
# for the rest of the process's life. At the largest thumbnail_size
# (512px, ~1MB/QImage) this ceiling bounds one cache to ~800MB instead of
# unbounded/swap-thrashing on multi-thousand-image directories.
LRU_CACHE_CEILING = 800


class LRUImageCache:
    """Bounded LRU cache for QImage thumbnails.

    Stores QImage objects (not QPixmap) to avoid the X11 server-side backing
    copy that QPixmap carries, roughly halving per-entry RAM on Linux.

    Evicts the least-recently-used entry when maxsize is exceeded so total
    memory stays bounded regardless of directory size.
    """

    def __init__(self, maxsize: int = 300):
        self._cache: OrderedDict[str, QImage] = OrderedDict()
        self.maxsize = maxsize

    def get(self, key: str, default=None):
        if key not in self._cache:
            return default
        self._cache.move_to_end(key)
        return self._cache[key]

    def __setitem__(self, key: str, value):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self.maxsize:
            self._cache.popitem(last=False)  # evict LRU entry

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def __len__(self) -> int:
        return len(self._cache)

    def items(self):
        """Return a snapshot of (key, value) pairs so callers can safely iterate
        while the cache is modified (e.g. when copying into a new cache)."""
        return list(self._cache.items())

    def pop(self, key: str, default=None):
        return self._cache.pop(key, default)

    def clear(self):
        self._cache.clear()

    def resize(self, maxsize: int) -> None:
        """Re-bound the cache (#444). Evicts LRU entries immediately when
        shrinking below the current entry count, so callers can size the
        cache to the active page size without losing entries mid-populate."""
        self.maxsize = maxsize
        while len(self._cache) > self.maxsize:
            self._cache.popitem(last=False)
