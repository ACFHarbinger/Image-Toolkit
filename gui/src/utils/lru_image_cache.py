from collections import OrderedDict
from PySide6.QtGui import QImage


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

    def clear(self):
        self._cache.clear()
