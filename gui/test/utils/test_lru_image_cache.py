from PySide6.QtGui import QImage

from gui.src.utils.cache.lru_image_cache import LRUImageCache


def _img() -> QImage:
    return QImage(1, 1, QImage.Format.Format_RGB32)


def test_resize_shrink_evicts_lru_entries(q_app):
    cache = LRUImageCache(maxsize=5)
    for i in range(5):
        cache[f"k{i}"] = _img()

    cache.get("k0")  # k0 is now most-recently-used
    cache.resize(2)

    assert cache.maxsize == 2
    assert len(cache) == 2
    assert "k0" in cache
    assert "k4" in cache
    assert "k1" not in cache


def test_resize_grow_keeps_entries(q_app):
    cache = LRUImageCache(maxsize=2)
    cache["a"] = _img()
    cache["b"] = _img()

    cache.resize(10)

    assert cache.maxsize == 10
    assert len(cache) == 2
    cache["c"] = _img()
    assert len(cache) == 3


def test_setitem_still_evicts_after_resize(q_app):
    cache = LRUImageCache(maxsize=5)
    for i in range(5):
        cache[f"k{i}"] = _img()

    cache.resize(2)
    cache["new"] = _img()

    assert len(cache) == 2
    assert "new" in cache
    assert "k4" in cache
    assert "k3" not in cache
