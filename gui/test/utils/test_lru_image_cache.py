from PySide6.QtGui import QImage

from gui.src.utils.cache.lru_image_cache import (
    DEFAULT_PIXMAP_BUDGET,
    LRU_CACHE_CEILING,
    LRUImageCache,
    PixmapBudget,
)


def _img() -> QImage:
    return QImage(1, 1, QImage.Format.Format_RGB32)


def test_resize_shrink_evicts_lru_entries(q_app):
    cache = LRUImageCache(maxsize=5, budget=None)
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
    cache = LRUImageCache(maxsize=2, budget=None)
    cache["a"] = _img()
    cache["b"] = _img()

    cache.resize(10)

    assert cache.maxsize == 10
    assert len(cache) == 2
    cache["c"] = _img()
    assert len(cache) == 3


def test_setitem_still_evicts_after_resize(q_app):
    cache = LRUImageCache(maxsize=5, budget=None)
    for i in range(5):
        cache[f"k{i}"] = _img()

    cache.resize(2)
    cache["new"] = _img()

    assert len(cache) == 2
    assert "new" in cache
    assert "k4" in cache
    assert "k3" not in cache


def test_pixmap_budget_defaults_match_current_sizes():
    budget = DEFAULT_PIXMAP_BUDGET
    assert budget.card_thumb == 250
    assert budget.single_gallery == 300
    assert budget.two_galleries_selected == 200
    assert budget.two_galleries_found == 300
    assert budget.virtual_dual_shared == 500
    assert budget.virtual_model == 300
    assert budget.ceiling == LRU_CACHE_CEILING == 800
    assert budget.total_entries == LRU_CACHE_CEILING


def test_pixmap_budget_clamp_respects_total():
    budget = PixmapBudget()
    assert budget.clamp(100) == 100
    assert budget.clamp(budget.total_entries) == budget.total_entries
    assert budget.clamp(budget.total_entries + 1) == budget.total_entries
    assert budget.clamp(999999) == budget.total_entries
    tight = PixmapBudget(total_entries=10)
    assert tight.clamp(50) == 10


def test_caches_constructed_from_budget_roles():
    budget = PixmapBudget()
    assert budget.make_cache("card_thumb").maxsize == 250
    assert budget.make_cache("single_gallery").maxsize == 300
    assert budget.make_cache("two_galleries_selected").maxsize == 200
    assert budget.make_cache("two_galleries_found").maxsize == 300
    assert budget.make_cache("virtual_dual_shared").maxsize == 500
    assert budget.make_cache("virtual_model").maxsize == 300


def test_global_budget_evicts_across_independent_caches(q_app):
    budget = PixmapBudget(total_entries=5)
    a = LRUImageCache(maxsize=10, budget=budget)
    b = LRUImageCache(maxsize=10, budget=budget)
    for i in range(4):
        a[f"a{i}"] = _img()
    assert budget.resident_entries() == 4
    b["b0"] = _img()
    assert budget.resident_entries() == 5
    b["b1"] = _img()
    # Six inserts into a 5-entry process budget: globally oldest (a0) goes.
    assert budget.resident_entries() == 5
    assert "a0" not in a
    assert "a1" in a
    assert "b0" in b
    assert "b1" in b


def test_global_budget_get_protects_from_eviction(q_app):
    budget = PixmapBudget(total_entries=3)
    a = LRUImageCache(maxsize=10, budget=budget)
    b = LRUImageCache(maxsize=10, budget=budget)
    a["old"] = _img()
    a["mid"] = _img()
    a.get("old")
    b["new"] = _img()
    b["newer"] = _img()
    # old was touched, so mid is the globally oldest and is evicted.
    assert "old" in a
    assert "mid" not in a
    assert "new" in b
    assert "newer" in b
    assert budget.resident_entries() == 3


def test_isolated_cache_does_not_share_budget(q_app):
    budget = PixmapBudget(total_entries=1)
    isolated = LRUImageCache(maxsize=3, budget=None)
    tracked = LRUImageCache(maxsize=3, budget=budget)
    isolated["i0"] = _img()
    isolated["i1"] = _img()
    isolated["i2"] = _img()
    tracked["t0"] = _img()
    tracked["t1"] = _img()
    assert len(isolated) == 3
    assert len(tracked) == 1
    assert "t0" not in tracked
    assert budget.resident_entries() == 1


def test_clear_releases_budget_slots(q_app):
    budget = PixmapBudget(total_entries=2)
    cache = LRUImageCache(maxsize=10, budget=budget)
    cache["a"] = _img()
    cache["b"] = _img()
    cache.clear()
    assert budget.resident_entries() == 0
    cache["c"] = _img()
    cache["d"] = _img()
    assert budget.resident_entries() == 2
    assert "c" in cache
    assert "d" in cache
