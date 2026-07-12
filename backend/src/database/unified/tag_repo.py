"""Unified typed-tag vocabulary (DB.3 / DB.8c).

One `tags` table serves both domains: image-side types
(Artist/Series/Character/General/Meta) and listing-side types (Genre/Tag).
Method names mirror PgvectorImageDatabase where practical.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ._util import transaction


class TagRepo:
    def __init__(self, db):
        self._db = db

    # ---- CRUD (PgvectorImageDatabase parity) --------------------------

    def add_tag(self, name: str, type: Optional[str] = None) -> int:  # noqa: A002
        """Create a tag or update its type; returns the tag id."""
        if not name or not name.strip():
            raise ValueError("Tag name cannot be empty")
        type_value = type.strip() if type and type.strip() else None
        self._db.execute(
            "INSERT INTO tags (name, type) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET "
            "type = COALESCE(excluded.type, tags.type)",
            (name.strip(), type_value),
        )
        return self.get_tag_id(name.strip())

    def get_or_create(self, name: str, type: Optional[str] = None) -> int:  # noqa: A002
        """Like add_tag but never downgrades/overwrites an existing type."""
        existing = self._db.query(
            "SELECT id FROM tags WHERE name = ?", (name.strip(),)
        )
        if existing:
            return existing[0][0]
        return self.add_tag(name, type)

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

    def update_tag_type(self, name: str, new_type: Optional[str]) -> None:
        self._db.execute(
            "UPDATE tags SET type = ? WHERE name = ?",
            (new_type.strip() if new_type and new_type.strip() else None, name),
        )

    # ---- queries -------------------------------------------------------

    def get_all_tags(self, types: Optional[List[str]] = None) -> List[str]:
        if types:
            marks = ",".join("?" * len(types))
            rows = self._db.query(
                f"SELECT name FROM tags WHERE type IN ({marks}) ORDER BY name",
                tuple(types),
            )
        else:
            rows = self._db.query("SELECT name FROM tags ORDER BY name", ())
        return [r[0] for r in rows]

    def get_all_tags_with_types(self) -> List[Dict[str, Optional[str]]]:
        rows = self._db.query("SELECT name, type FROM tags ORDER BY name", ())
        return [{"name": name, "type": type_ or ""} for name, type_ in rows]

    # ---- DB.8c: vocabulary hygiene --------------------------------------

    def merge_tags(self, source_name: str, dest_name: str) -> None:
        """Repoint every reference from *source* to *dest*, then drop source."""
        src = self.get_tag_id(source_name)
        dst = self.get_tag_id(dest_name)
        if src == dst:
            return
        with transaction(self._db):
            for table, col in (("image_tags", "image_id"), ("media_tags", "media_item_id")):
                self._db.execute(
                    f"INSERT OR IGNORE INTO {table} ({col}, tag_id) "
                    f"SELECT {col}, ? FROM {table} WHERE tag_id = ?",
                    (dst, src),
                )
                self._db.execute(
                    f"DELETE FROM {table} WHERE tag_id = ?", (src,)
                )
            self._db.execute("DELETE FROM tags WHERE id = ?", (src,))
