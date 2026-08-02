"""Unified categorized-tag vocabulary (DB.3 / DB.8c — Danbooru-style overhaul).

One `tags` table serves all three domains (images, media_items/listings,
entities); `tag_categories` carries the color and `applies_to` scope. Method
names mirror PgvectorImageDatabase where practical.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ._util import transaction


class TagRepo:
    def __init__(self, db):
        self._db = db

    # ---- categories -------------------------------------------------------

    def list_categories(self, applies_to: Optional[str] = None) -> List[Dict[str, Any]]:
        """All categories, or those usable by *applies_to* ('listing'/'entity'
        plus every 'universal' category)."""
        if applies_to:
            rows = self._db.query(
                "SELECT id, name, color, sort_order, applies_to FROM tag_categories "
                "WHERE applies_to = ? OR applies_to = 'universal' ORDER BY sort_order",
                (applies_to,),
            )
        else:
            rows = self._db.query(
                "SELECT id, name, color, sort_order, applies_to FROM tag_categories "
                "ORDER BY sort_order",
                (),
            )
        return [
            {"id": r[0], "name": r[1], "color": r[2], "sort_order": r[3], "applies_to": r[4]}
            for r in rows
        ]

    def get_category_id(self, name: str) -> Optional[int]:
        rows = self._db.query("SELECT id FROM tag_categories WHERE name = ?", (name,))
        return rows[0][0] if rows else None

    # ---- CRUD (PgvectorImageDatabase parity) --------------------------

    def add_tag(self, name: str, category: Optional[str] = None) -> int:
        """Create a tag or update its category; returns the tag id."""
        if not name or not name.strip():
            raise ValueError("Tag name cannot be empty")
        category_id = self.get_category_id(category) if category else None
        self._db.execute(
            "INSERT INTO tags (name, category_id) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET "
            "category_id = COALESCE(excluded.category_id, tags.category_id)",
            (name.strip(), category_id),
        )
        return self.get_tag_id(name.strip())

    def get_or_create(self, name: str, category: Optional[str] = None) -> int:
        """Like add_tag but never downgrades/overwrites an existing category."""
        existing = self._db.query(
            "SELECT id FROM tags WHERE name = ?", (name.strip(),)
        )
        if existing:
            return existing[0][0]
        return self.add_tag(name, category)

    def get_tag_id(self, name: str) -> int:
        rows = self._db.query("SELECT id FROM tags WHERE name = ?", (name,))
        if not rows:
            raise KeyError(f"tag not found: {name}")
        return rows[0][0]

    def delete_tag(self, name: str) -> None:
        self._db.execute("DELETE FROM tags WHERE name = ?", (name,))

    def rename_tag(self, old_name: str, new_name: str) -> None:
        if not new_name or not new_name.strip():
            raise ValueError("Tag name cannot be empty")
        changed = self._db.execute(
            "UPDATE tags SET name = ? WHERE name = ?",
            (new_name.strip(), old_name),
        )
        if changed == 0:
            raise KeyError(f"tag not found: {old_name}")

    def update_tag_category(self, name: str, new_category: Optional[str]) -> None:
        category_id = self.get_category_id(new_category) if new_category else None
        self._db.execute(
            "UPDATE tags SET category_id = ? WHERE name = ?", (category_id, name),
        )

    # ---- queries -------------------------------------------------------

    def get_all_tags(self, categories: Optional[List[str]] = None) -> List[str]:
        if categories:
            marks = ",".join("?" * len(categories))
            rows = self._db.query(
                "SELECT t.name FROM tags t JOIN tag_categories c ON c.id = t.category_id "
                f"WHERE c.name IN ({marks}) ORDER BY t.name",
                tuple(categories),
            )
        else:
            rows = self._db.query("SELECT name FROM tags ORDER BY name", ())
        return [r[0] for r in rows]

    def get_all_tags_with_categories(self) -> List[Dict[str, str]]:
        rows = self._db.query(
            "SELECT t.name, COALESCE(c.name, ''), COALESCE(c.color, '#95a5a6') "
            "FROM tags t LEFT JOIN tag_categories c ON c.id = t.category_id "
            "ORDER BY t.name",
            (),
        )
        return [{"name": name, "category": category, "color": color} for name, category, color in rows]

    # ---- entity tag links (DB.9 — entities are now taggable) -------------

    def add_entity_tag(self, entity_id: str, tag_name: str, category: Optional[str] = None) -> None:
        tag_id = self.get_or_create(tag_name, category)
        self._db.execute(
            "INSERT OR IGNORE INTO entity_tags (entity_id, tag_id) VALUES (?, ?)",
            (entity_id, tag_id),
        )

    def remove_entity_tag(self, entity_id: str, tag_name: str) -> None:
        self._db.execute(
            "DELETE FROM entity_tags WHERE entity_id = ? AND tag_id = "
            "(SELECT id FROM tags WHERE name = ?)",
            (entity_id, tag_name),
        )

    def get_entity_tags(self, entity_id: str) -> List[Dict[str, str]]:
        rows = self._db.query(
            "SELECT t.name, COALESCE(c.name, ''), COALESCE(c.color, '#95a5a6') "
            "FROM entity_tags et JOIN tags t ON t.id = et.tag_id "
            "LEFT JOIN tag_categories c ON c.id = t.category_id "
            "WHERE et.entity_id = ? ORDER BY c.sort_order, t.name",
            (entity_id,),
        )
        return [{"name": name, "category": category, "color": color} for name, category, color in rows]

    # ---- DB.8c: vocabulary hygiene --------------------------------------

    def merge_tags(self, source_name: str, dest_name: str) -> None:
        """Repoint every reference from *source* to *dest*, then drop source."""
        src = self.get_tag_id(source_name)
        dst = self.get_tag_id(dest_name)
        if src == dst:
            return
        with transaction(self._db):
            for table, col in (
                ("image_tags", "image_id"),
                ("media_tags", "media_item_id"),
                ("entity_tags", "entity_id"),
            ):
                self._db.execute(
                    f"INSERT OR IGNORE INTO {table} ({col}, tag_id) "
                    f"SELECT {col}, ? FROM {table} WHERE tag_id = ?",
                    (dst, src),
                )
                self._db.execute(
                    f"DELETE FROM {table} WHERE tag_id = ?", (src,)
                )
            self._db.execute("DELETE FROM tags WHERE id = ?", (src,))
