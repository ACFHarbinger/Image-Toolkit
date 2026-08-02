"""Entities (people/organizations/characters) repository — DB.3.

Legacy-dict dialect like MediaRepo: ``save_entity`` accepts the entity shape
the Entity Listings subtab produces (`name`, `credit_list`,
`associated_content`, peer `associated_entities`, …). Associations live in
`media_entity` / `entity_entity`, so the four bidirectional-sync loops from
the old subtabs are unnecessary — both sides read the same table.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from ._util import dumps_extra, intify, loads_extra, normalized_pair, transaction
from .tag_repo import TagRepo

_COLUMN_KEYS = {
    "id": "id",
    "name": "name",
    "first_name": "first_name",
    "last_name": "last_name",
    "type": "type",
    "role": "role",
    "rating": "rating",
    "year": "year",
    "notes": "notes",
    "image_path": "image_path",
    "date_added": "date_added",
}
_RELATION_KEYS = {"credit_list", "associated_content", "associated_entities"}

_CREDIT_FIELDS = ("title", "role", "year", "rating", "notes", "image_path", "web_link")

_SELECT_COLUMNS = (
    "id", "name", "first_name", "last_name", "type", "role", "rating",
    "year", "notes", "image_path", "date_added", "extra",
)


class EntityRepo:
    def __init__(self, db):
        self._db = db
        self._tags = TagRepo(db)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def save_entity(self, entity: Dict[str, Any]) -> str:
        """Upsert a legacy-shaped entity in one transaction."""
        entity = dict(entity)
        entity_id = entity.get("id") or ("ent-" + uuid.uuid4().hex[:8])
        entity["id"] = entity_id
        entity.setdefault("date_added", str(date.today()))

        cols: Dict[str, Any] = {}
        extra: Dict[str, Any] = {}
        for key, value in entity.items():
            if key in _COLUMN_KEYS:
                cols[_COLUMN_KEYS[key]] = value
            elif key not in _RELATION_KEYS:
                extra[key] = value

        with transaction(self._db):
            column_names = list(cols) + ["extra"]
            placeholders = ", ".join("?" * len(column_names))
            updates = ", ".join(
                f"{c}=excluded.{c}" for c in column_names if c != "id"
            )
            self._db.execute(
                f"INSERT INTO entities ({', '.join(column_names)}) "
                f"VALUES ({placeholders}) "
                f"ON CONFLICT(id) DO UPDATE SET {updates}",
                tuple(cols.values()) + (dumps_extra(extra),),
            )

            if "credit_list" in entity:
                self._replace_credits(entity_id, entity.get("credit_list") or [])
            if "associated_content" in entity:
                self._replace_media_links(
                    entity_id, list(entity.get("associated_content") or [])
                )
            if "associated_entities" in entity:
                self._replace_peer_links(
                    entity_id, list(entity.get("associated_entities") or [])
                )

            # Every entity listing gets a self tag under Character so it's
            # part of the searchable vocabulary and shows up on linked
            # series' grouped-tags section as an "associated entities" chip.
            name = (entity.get("name") or cols.get("name") or "").strip()
            if name:
                self_tag_id = self._tags.get_or_create(name, "Character")
                self._db.execute(
                    "INSERT OR IGNORE INTO entity_tags (entity_id, tag_id) "
                    "VALUES (?, ?)",
                    (entity_id, self_tag_id),
                )
        return entity_id

    def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity; credits and all association rows cascade."""
        return self._db.execute(
            "DELETE FROM entities WHERE id = ?", (entity_id,)
        ) > 0

    def set_media_links(self, entity_id: str, media_ids: List[str]) -> None:
        with transaction(self._db):
            self._replace_media_links(entity_id, media_ids)

    def set_peer_links(self, entity_id: str, peer_ids: List[str]) -> None:
        with transaction(self._db):
            self._replace_peer_links(entity_id, peer_ids)

    # ---- DB.8b: entity <-> images -----------------------------------------

    def link_image(self, entity_id: str, image_id: int) -> None:
        self._db.execute(
            "INSERT OR IGNORE INTO entity_images (entity_id, image_id) "
            "VALUES (?, ?)",
            (entity_id, image_id),
        )

    def unlink_image(self, entity_id: str, image_id: int) -> None:
        self._db.execute(
            "DELETE FROM entity_images WHERE entity_id = ? AND image_id = ?",
            (entity_id, image_id),
        )

    def get_linked_images(self, entity_id: str) -> List[Dict[str, Any]]:
        """[{"id": image_id, "file_path": ...}, ...] linked to *entity_id*
        -- an entity detail panel's "linked images" gallery strip."""
        rows = self._db.query(
            "SELECT i.id, i.file_path FROM entity_images ei "
            "JOIN images i ON i.id = ei.image_id "
            "WHERE ei.entity_id = ? ORDER BY i.file_path",
            (entity_id,),
        )
        return [{"id": r[0], "file_path": r[1]} for r in rows]

    def get_entities_for_image(self, image_id: int) -> List[Dict[str, Any]]:
        """Entities (id/name) linked to *image_id* -- the reverse of
        get_linked_images(), e.g. an image card's "linked people" tooltip."""
        rows = self._db.query(
            "SELECT e.id, e.name FROM entity_images ei "
            "JOIN entities e ON e.id = ei.entity_id "
            "WHERE ei.image_id = ? ORDER BY e.name",
            (image_id,),
        )
        return [{"id": r[0], "name": r[1]} for r in rows]

    # ---- DB.7: listings semantic search (BGE-M3) ------------------------

    def upsert_embedding(self, entity_id: str, model: str, vector) -> None:
        """Store *vector* for this entity under *model* -- mirrors
        ImageRepo.upsert_embedding (image_repo.py)."""
        import numpy as np

        self._db.upsert_embedding(
            "entity", entity_id, model, np.asarray(vector, dtype=np.float32)
        )

    def count_unembedded(self, model: str) -> int:
        return self._db.query(
            "SELECT COUNT(*) FROM entities e WHERE NOT EXISTS ("
            "SELECT 1 FROM embeddings em WHERE em.owner_type = 'entity' "
            "AND em.owner_id = e.id AND em.model = ?)",
            (model,),
        )[0][0]

    def list_unembedded(self, model: str, limit: int = 500) -> List[Tuple[str, str]]:
        """[(entity_id, name), ...] for entities with no *model* embedding
        yet -- the backfill worker's work queue."""
        return self._db.query(
            "SELECT e.id, e.name FROM entities e WHERE NOT EXISTS ("
            "SELECT 1 FROM embeddings em WHERE em.owner_type = 'entity' "
            "AND em.owner_id = e.id AND em.model = ?) "
            "ORDER BY e.id LIMIT ?",
            (model, limit),
        )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        rows = self._db.query(
            f"SELECT {', '.join(_SELECT_COLUMNS)} FROM entities WHERE id = ?",
            (entity_id,),
        )
        if not rows:
            return None
        return self._assemble(rows[0])

    def list_entities(self) -> List[Dict[str, Any]]:
        rows = self._db.query(
            f"SELECT {', '.join(_SELECT_COLUMNS)} FROM entities "
            "ORDER BY date_added DESC, name",
            (),
        )
        return [self._assemble(row) for row in rows]

    def name_map(self) -> Dict[str, str]:
        """{entity_id: display_name} — replaces fetch_entity_name_map()."""
        return dict(self._db.query("SELECT id, name FROM entities", ()))

    def count(self) -> int:
        return self._db.query("SELECT count(*) FROM entities", ())[0][0]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _assemble(self, row: tuple) -> Dict[str, Any]:
        data = dict(zip(_SELECT_COLUMNS, row))
        entity_id = data["id"]

        entity: Dict[str, Any] = loads_extra(data.pop("extra"))
        reverse = {col: key for key, col in _COLUMN_KEYS.items()}
        for col, value in data.items():
            entity[reverse[col]] = intify(value)

        entity["credit_list"] = [
            dict(zip(("id",) + _CREDIT_FIELDS, map(intify, credit_row)))
            for credit_row in self._db.query(
                f"SELECT id, {', '.join(_CREDIT_FIELDS)} FROM credits "
                "WHERE entity_id = ? ORDER BY year IS NULL, year, title",
                (entity_id,),
            )
        ]
        entity["associated_content"] = [
            r[0] for r in self._db.query(
                "SELECT media_item_id FROM media_entity WHERE entity_id = ? "
                "ORDER BY media_item_id",
                (entity_id,),
            )
        ]
        entity["associated_entities"] = [
            r[0] for r in self._db.query(
                "SELECT CASE WHEN entity_a = ? THEN entity_b ELSE entity_a END "
                "FROM entity_entity WHERE entity_a = ? OR entity_b = ? "
                "ORDER BY 1",
                (entity_id, entity_id, entity_id),
            )
        ]
        return entity

    def get_grouped_tags(self, entity_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """This entity's tags grouped by category name, including tags
        carried transitively through associated media (e.g. a linked
        series' Genre tags become visible on the entity too). Mirrors
        MediaRepo.get_grouped_tags."""
        rows = self._db.query(
            "SELECT t.name, COALESCE(c.name, 'General') AS cat, "
            "COALESCE(c.color, '#95a5a6') AS color, COALESCE(c.sort_order, 999) AS ord "
            "FROM entity_tags et JOIN tags t ON t.id = et.tag_id "
            "LEFT JOIN tag_categories c ON c.id = t.category_id "
            "WHERE et.entity_id = ? "
            "UNION "
            "SELECT t.name, COALESCE(c.name, 'General') AS cat, "
            "COALESCE(c.color, '#95a5a6') AS color, COALESCE(c.sort_order, 999) AS ord "
            "FROM media_entity me JOIN media_tags mt ON mt.media_item_id = me.media_item_id "
            "JOIN tags t ON t.id = mt.tag_id "
            "LEFT JOIN tag_categories c ON c.id = t.category_id "
            "WHERE me.entity_id = ? "
            "ORDER BY ord, t.name",
            (entity_id, entity_id),
        )
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for name, category, color, _order in rows:
            grouped.setdefault(category, []).append({"name": name, "color": color})
        return grouped

    def add_tag(self, entity_id: str, name: str, category: Optional[str] = None) -> None:
        """Attach an arbitrary tag (any category) to this entity -- the
        "+" add-tag action in the grouped-tags UI section."""
        tag_id = self._tags.get_or_create(name, category)
        self._db.execute(
            "INSERT OR IGNORE INTO entity_tags (entity_id, tag_id) VALUES (?, ?)",
            (entity_id, tag_id),
        )

    def _replace_credits(self, entity_id: str, credit_list: List[Dict[str, Any]]) -> None:
        self._db.execute("DELETE FROM credits WHERE entity_id = ?", (entity_id,))
        if not credit_list:
            return
        rows = []
        for credit in credit_list:
            rows.append(
                (
                    credit.get("id") or str(uuid.uuid4()),
                    entity_id,
                    credit.get("title", "") or "",
                    credit.get("role", "") or "",
                    credit.get("year"),
                    credit.get("rating", 0) or 0,
                    credit.get("notes", "") or "",
                    credit.get("image_path", "") or "",
                    credit.get("web_link", "") or "",
                )
            )
        self._db.executemany(
            "INSERT INTO credits (id, entity_id, title, role, year, rating, "
            "notes, image_path, web_link) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )

    def _replace_media_links(self, entity_id: str, media_ids: List[str]) -> None:
        """Replace entity↔media links; unknown media ids are skipped."""
        self._db.execute(
            "DELETE FROM media_entity WHERE entity_id = ?", (entity_id,)
        )
        for media_id in media_ids:
            self._db.execute(
                "INSERT OR IGNORE INTO media_entity (media_item_id, entity_id) "
                "SELECT id, ? FROM media_items WHERE id = ?",
                (entity_id, media_id),
            )

    def _replace_peer_links(self, entity_id: str, peer_ids: List[str]) -> None:
        """Replace undirected peer links; unknown/self peers are skipped."""
        self._db.execute(
            "DELETE FROM entity_entity WHERE entity_a = ? OR entity_b = ?",
            (entity_id, entity_id),
        )
        for peer_id in peer_ids:
            if peer_id == entity_id:
                continue
            a, b = normalized_pair(entity_id, peer_id)
            self._db.execute(
                "INSERT OR IGNORE INTO entity_entity (entity_a, entity_b) "
                "SELECT ?, ? WHERE EXISTS (SELECT 1 FROM entities WHERE id = ?)",
                (a, b, peer_id),
            )
