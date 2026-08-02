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


def has_column(db, table: str, column: str) -> bool:
    return any(row[1] == column for row in db.query(f"PRAGMA table_info({table})", ()))


def ensure_category_id_column(db) -> None:
    """Add ``tags.category_id`` (nullable, unpopulated) if a pre-DB.11 ``tags``
    table exists without it. MUST run before ``schema.sql``'s DDL is applied:
    that DDL's ``CREATE INDEX idx_tags_category ON tags(category_id)`` fails
    outright against an existing ``tags`` table that doesn't have the column
    yet (``CREATE TABLE IF NOT EXISTS`` is a no-op there since the table
    already exists) -- this is the "no such column: category_id" error a
    live pre-DB.11 database hits otherwise. Safe/idempotent: only adds a
    column, no data touched.
    """
    if not has_column(db, "tags", "type"):
        return  # fresh install (no tags table yet, or already migrated)
    if not has_column(db, "tags", "category_id"):
        # tag_categories may not exist yet on a pre-DB.11 database -- create
        # it now (matching schema.sql's definition) so the FK reference
        # below has a target; schema.sql's own CREATE TABLE IF NOT EXISTS
        # for it later is then a no-op.
        db.execute(
            "CREATE TABLE IF NOT EXISTS tag_categories ("
            "id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, "
            "color TEXT NOT NULL DEFAULT '#95a5a6', "
            "sort_order INTEGER NOT NULL DEFAULT 0, "
            "applies_to TEXT NOT NULL DEFAULT 'universal')"
        )
        db.execute(
            "ALTER TABLE tags ADD COLUMN category_id INTEGER "
            "REFERENCES tag_categories(id)"
        )


def migrate_legacy_type_column(db) -> None:
    """Backfill ``tags.category_id`` from the legacy ``type`` column and
    drop ``type``. Must run AFTER ``schema.sql`` DDL + ``seed()`` (needs
    ``tag_categories`` populated to resolve names to ids). Runs on every
    ``ensure_schema()`` call -- idempotent and safe without a backup gate:
    only adds/backfills, never deletes rows before the final column drop.
    Existing installs self-heal on next session open instead of requiring a
    manual ``migrations upgrade-tag-categories`` run first (that standalone
    script still exists for an explicit backup-first run, and calls this
    same function).
    """
    if not has_column(db, "tags", "type"):
        return  # fresh install, or already migrated

    rows = db.query(
        "SELECT id, type FROM tags WHERE type IS NOT NULL AND type != '' "
        "AND category_id IS NULL",
        (),
    )
    for tag_id, old_type in rows:
        category_name = LEGACY_CATEGORY_ALIASES.get(old_type, old_type)
        cat_rows = db.query(
            "SELECT id FROM tag_categories WHERE name = ?", (category_name,)
        )
        category_id = cat_rows[0][0] if cat_rows else None
        db.execute(
            "UPDATE tags SET category_id = ? WHERE id = ?", (category_id, tag_id)
        )

    try:
        db.execute("ALTER TABLE tags DROP COLUMN type")
    except Exception:
        # Older SQLite builds (<3.35) lack DROP COLUMN; the leftover unused
        # column is harmless (nothing reads it anymore).
        pass
