"""Seed data for the ``tag_categories`` vocabulary (Danbooru-style overhaul).

``applies_to`` scopes a category to a domain: ``'universal'`` (image/listing/
entity), ``'listing'``, or ``'entity'``. This list is a starting point, not
exhaustive -- more rows can be added later (by any migration, or directly)
without touching any Python that reads ``tag_categories``.

General/Genre colors are deliberately swapped from the pre-overhaul scheme:
General (catch-all) is grey, Genre is the red/magenta General used to be.
"Series" (the old image-tag type) is renamed "Copyright" here to avoid
colliding with this app's unrelated "Series Listings" naming.
"""

from __future__ import annotations

# (name, color, sort_order, applies_to)
DEFAULT_TAG_CATEGORIES = [
    ("General", "#95a5a6", 0, "universal"),
    ("Artist", "#5865f2", 1, "universal"),
    ("Copyright", "#f1c40f", 2, "universal"),
    ("Character", "#2ecc71", 3, "universal"),
    ("Meta", "#9b59b6", 4, "universal"),
    ("Genre", "#e91e63", 5, "listing"),
    ("Medium", "#3498db", 6, "listing"),
    ("Studio", "#8e44ad", 7, "listing"),
    ("Setting", "#16a085", 8, "listing"),
    ("Content Warning", "#c0392b", 9, "listing"),
    ("Release Status", "#7f8c8d", 10, "listing"),
    ("Appearance", "#1abc9c", 11, "entity"),
    ("Occupation", "#e67e22", 12, "entity"),
    ("Biographical", "#d35400", 13, "entity"),
    ("Organization", "#2980b9", 14, "entity"),
]

# Pre-overhaul image-tag "type" strings that map onto a renamed category.
LEGACY_CATEGORY_ALIASES = {"Series": "Copyright"}


def seed(db) -> None:
    """Insert the default categories; no-op for names that already exist."""
    for name, color, sort_order, applies_to in DEFAULT_TAG_CATEGORIES:
        db.execute(
            "INSERT INTO tag_categories (name, color, sort_order, applies_to) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(name) DO NOTHING",
            (name, color, sort_order, applies_to),
        )
