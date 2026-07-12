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
from typing import Any, Dict, List, Optional

from ._util import dumps_extra, loads_extra, normalized_pair, transaction

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
            entity[reverse[col]] = value

        entity["credit_list"] = [
            dict(zip(("id",) + _CREDIT_FIELDS, credit_row))
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
