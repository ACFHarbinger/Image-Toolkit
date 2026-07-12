"""Media items (content listings) repository — DB.3.

Speaks the *legacy entry-dict* dialect the Listings subtabs already use
(`title`, `type`, `status`, CSV `genres`/`tags`, `associated_entities`,
`episode_list`, …) so the DB.5 tab port and migration 002 are drop-in:
``save_media(legacy_dict)`` explodes it into the normalized tables inside
one transaction; ``get_media``/``list_media`` reassemble it.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Dict, List, Optional

from ._util import (
    dumps_extra,
    join_csv,
    loads_extra,
    split_csv,
    transaction,
)
from .tag_repo import TagRepo

# Legacy entry key -> media_items column (identical names omitted).
_COLUMN_KEYS = {
    "id": "id",
    "title": "title",
    "type": "type",
    "status": "status",
    "personal_rating": "personal_rating",
    "community_rating": "community_rating",
    "year": "year",
    "episodes": "episodes_total",
    "current_episode": "current_episode",
    "creator": "creator",
    "review": "review",
    "web_link": "web_link",
    "local_file": "local_file",
    "image_path": "image_path",
    "date_added": "date_added",
    "date_watched": "date_watched",
}
# Keys consumed by relations, not columns.
_RELATION_KEYS = {"genres", "tags", "associated_entities", "episode_list"}

_EPISODE_FIELDS = (
    "number", "title", "date_watched", "rating", "review",
    "image_path", "local_file", "web_link",
)

_SELECT_COLUMNS = (
    "id", "title", "type", "status", "personal_rating", "community_rating",
    "year", "episodes_total", "current_episode", "creator", "review",
    "web_link", "local_file", "image_path", "date_added", "date_watched",
    "extra",
)


class MediaRepo:
    def __init__(self, db):
        self._db = db
        self._tags = TagRepo(db)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def save_media(self, entry: Dict[str, Any]) -> str:
        """Upsert a legacy-shaped content entry in one transaction."""
        entry = dict(entry)
        media_id = entry.get("id") or str(uuid.uuid4())
        entry["id"] = media_id
        entry.setdefault("date_added", str(date.today()))

        cols: Dict[str, Any] = {}
        extra: Dict[str, Any] = {}
        for key, value in entry.items():
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
                f"INSERT INTO media_items ({', '.join(column_names)}) "
                f"VALUES ({placeholders}) "
                f"ON CONFLICT(id) DO UPDATE SET {updates}",
                tuple(cols.values()) + (dumps_extra(extra),),
            )

            if "episode_list" in entry:
                self._replace_episodes(media_id, entry.get("episode_list") or [])
            if "genres" in entry:
                self._replace_typed_tags(media_id, "Genre", split_csv(entry.get("genres")))
            if "tags" in entry:
                self._replace_typed_tags(media_id, "Tag", split_csv(entry.get("tags")))
            if "associated_entities" in entry:
                self._replace_entity_links(
                    media_id, list(entry.get("associated_entities") or [])
                )
        return media_id

    def delete_media(self, media_id: str) -> bool:
        """Delete an entry; episodes/associations/tag links cascade."""
        return self._db.execute(
            "DELETE FROM media_items WHERE id = ?", (media_id,)
        ) > 0

    def set_entity_links(self, media_id: str, entity_ids: List[str]) -> None:
        with transaction(self._db):
            self._replace_entity_links(media_id, entity_ids)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_media(self, media_id: str) -> Optional[Dict[str, Any]]:
        rows = self._db.query(
            f"SELECT {', '.join(_SELECT_COLUMNS)} FROM media_items WHERE id = ?",
            (media_id,),
        )
        if not rows:
            return None
        return self._assemble(rows[0])

    def list_media(self) -> List[Dict[str, Any]]:
        rows = self._db.query(
            f"SELECT {', '.join(_SELECT_COLUMNS)} FROM media_items "
            "ORDER BY date_added DESC, title",
            (),
        )
        return [self._assemble(row) for row in rows]

    def list_ids_and_titles(self) -> List[tuple]:
        return self._db.query("SELECT id, title FROM media_items ORDER BY title", ())

    def count(self) -> int:
        return self._db.query("SELECT count(*) FROM media_items", ())[0][0]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _assemble(self, row: tuple) -> Dict[str, Any]:
        data = dict(zip(_SELECT_COLUMNS, row))
        media_id = data["id"]

        entry: Dict[str, Any] = loads_extra(data.pop("extra"))
        reverse = {col: key for key, col in _COLUMN_KEYS.items()}
        for col, value in data.items():
            entry[reverse[col]] = value

        entry["genres"] = join_csv(self._typed_tags(media_id, "Genre"))
        entry["tags"] = join_csv(self._typed_tags(media_id, "Tag"))
        entry["associated_entities"] = [
            r[0] for r in self._db.query(
                "SELECT entity_id FROM media_entity WHERE media_item_id = ? "
                "ORDER BY entity_id",
                (media_id,),
            )
        ]
        entry["episode_list"] = [
            dict(zip(("id",) + _EPISODE_FIELDS, ep_row))
            for ep_row in self._db.query(
                f"SELECT id, {', '.join(_EPISODE_FIELDS)} FROM episodes "
                "WHERE media_item_id = ? "
                "ORDER BY number IS NULL, number, id",
                (media_id,),
            )
        ]
        return entry

    # The unified vocabulary has UNIQUE tag names, so a name saved from a
    # listing CSV may already exist with an image-side type (Artist, General,
    # …). 'Genre' links reconstruct the genres CSV; every other link
    # reconstructs the tags CSV — this keeps round-trips stable even when a
    # name's type was claimed by the other domain.
    _TYPE_CLAUSE = {
        "Genre": "t.type = 'Genre'",
        "Tag": "(t.type IS NULL OR t.type != 'Genre')",
    }

    def _typed_tags(self, media_id: str, tag_type: str) -> List[str]:
        return [
            r[0] for r in self._db.query(
                "SELECT t.name FROM media_tags mt JOIN tags t ON t.id = mt.tag_id "
                f"WHERE mt.media_item_id = ? AND {self._TYPE_CLAUSE[tag_type]} "
                "ORDER BY t.name",
                (media_id,),
            )
        ]

    def _replace_episodes(self, media_id: str, episode_list: List[Dict[str, Any]]) -> None:
        self._db.execute("DELETE FROM episodes WHERE media_item_id = ?", (media_id,))
        if not episode_list:
            return
        rows = []
        for ep in episode_list:
            rows.append(
                (
                    ep.get("id") or str(uuid.uuid4()),
                    media_id,
                    ep.get("number"),
                    ep.get("title", "") or "",
                    ep.get("date_watched", "") or "",
                    ep.get("rating", 0) or 0,
                    ep.get("review", "") or "",
                    ep.get("image_path", "") or "",
                    ep.get("local_file", "") or "",
                    ep.get("web_link", "") or "",
                )
            )
        self._db.executemany(
            "INSERT INTO episodes (id, media_item_id, number, title, "
            "date_watched, rating, review, image_path, local_file, web_link) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )

    def _replace_typed_tags(self, media_id: str, tag_type: str, names: List[str]) -> None:
        """Replace this entry's links to tags of *tag_type* (others untouched)."""
        self._db.execute(
            "DELETE FROM media_tags WHERE media_item_id = ? AND tag_id IN "
            f"(SELECT t.id FROM tags t WHERE {self._TYPE_CLAUSE[tag_type]})",
            (media_id,),
        )
        for name in names:
            tag_id = self._tags.get_or_create(name, tag_type)
            self._db.execute(
                "INSERT OR IGNORE INTO media_tags (media_item_id, tag_id) "
                "VALUES (?, ?)",
                (media_id, tag_id),
            )

    def _replace_entity_links(self, media_id: str, entity_ids: List[str]) -> None:
        """Replace media↔entity links; unknown entity ids are skipped
        (legacy data contains dangling references — migration 002 logs them)."""
        self._db.execute(
            "DELETE FROM media_entity WHERE media_item_id = ?", (media_id,)
        )
        for entity_id in entity_ids:
            self._db.execute(
                "INSERT OR IGNORE INTO media_entity (media_item_id, entity_id) "
                "SELECT ?, id FROM entities WHERE id = ?",
                (media_id, entity_id),
            )
